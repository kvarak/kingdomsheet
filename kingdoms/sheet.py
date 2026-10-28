"""How the PF2e kingdom sheet maps onto models, form fields and template rows."""

from dataclasses import dataclass

from . import rules
from .models import KingdomAbility, KingdomCommodity, KingdomLeader, KingdomSkill

# Single-value fields on Kingdom that the sheet edits.
KINGDOM_FIELDS = (
    "name",
    "charter",
    "heartland",
    "government",
    "capital",
    "size",
    "resource_points",
    "xp",
    "level",
    "renown",
    "fame",
    "fame_max",
    "resource_dice",
    "bonus_dice",
    "unrest",
    "unrest_penalty",
    "consumption",
    "farmlands",
    "lumber_camps",
    "mines",
    "quarries",
    "trade_agreements",
    "event_check_dc",
    "feats",
    "kingdom_abilities",
    "relations",
    "ongoing_events",
    "description",
    "notes",
)


@dataclass(frozen=True)
class RowGroup:
    """A fixed set of rows per kingdom, such as one row per skill."""

    model: type
    key_field: str
    keys: tuple
    fields: tuple

    def field_name(self, key, field):
        return f"{key}_{field}"

    def rows(self, kingdom):
        rows = self.model.objects.filter(kingdom=kingdom)
        if "character" in self.fields:
            rows = rows.select_related("character")
        return {getattr(row, self.key_field): row for row in rows}


ABILITY_ROWS = RowGroup(
    KingdomAbility,
    "ability",
    tuple(key for key, _ in rules.ABILITIES),
    ("score", "ruin", "ruin_penalty", "ruin_threshold"),
)
SKILL_ROWS = RowGroup(
    KingdomSkill,
    "skill",
    tuple(key for key, _, _ in rules.SKILLS),
    ("rank", "bonus"),
)
LEADER_ROWS = RowGroup(
    KingdomLeader,
    "role",
    tuple(key for key, _, _ in rules.LEADERSHIP_ROLES),
    ("character", "invested"),
)
COMMODITY_ROWS = RowGroup(
    KingdomCommodity,
    "commodity",
    tuple(key for key, _ in rules.COMMODITIES),
    ("stored", "capacity"),
)
ROW_GROUPS = (ABILITY_ROWS, SKILL_ROWS, LEADER_ROWS, COMMODITY_ROWS)


def field_values(instance, fields):
    return {field: getattr(instance, field) for field in fields}


def create_rows(kingdom):
    """Create any missing sheet rows for the kingdom, with default values."""
    for group in ROW_GROUPS:
        group.model.objects.bulk_create(
            [group.model(kingdom=kingdom, **{group.key_field: key}) for key in group.keys],
            ignore_conflicts=True,
        )


def sheet_values(kingdom):
    """Return the saved sheet as a flat dict keyed by form field name."""
    values = field_values(kingdom, KINGDOM_FIELDS)
    for group in ROW_GROUPS:
        for key, row in group.rows(kingdom).items():
            for field in group.fields:
                values[group.field_name(key, field)] = getattr(row, field)
    return values


def build_sheet(kingdom, form):
    """Group bound form fields and calculated values the way the template lays them out."""
    abilities = ABILITY_ROWS.rows(kingdom)
    scores = {key: row.score for key, row in abilities.items()}
    leaders = LEADER_ROWS.rows(kingdom)
    vacant = {role for role, leader in leaders.items() if leader.character_id is None}

    def field(group, key, name):
        return form[group.field_name(key, name)]

    return {
        "abilities": [
            {
                "label": label,
                "score": field(ABILITY_ROWS, key, "score"),
                "modifier": rules.ability_modifier(scores[key]),
            }
            for key, label in rules.ABILITIES
        ],
        "control_dc": rules.control_dc(kingdom.level, kingdom.size, ruler_vacant="ruler" in vacant),
        "control_dc_parts": {
            "base": rules.CONTROL_DC_BASE,
            "proficiency": rules.proficiency_bonus(kingdom.level),
            "size": rules.size_modifier(kingdom.size),
        },
        "kingdom_dc": rules.kingdom_dc(kingdom.level),
        "proficiency": rules.proficiency_bonus(kingdom.level),
        "ruler_vacant": "ruler" in vacant,
        "warnings": _vacancy_reminders(vacant) + _investiture_warnings(form),
        "ruins": [
            {
                "label": label,
                "score": field(ABILITY_ROWS, key, "ruin"),
                "penalty": field(ABILITY_ROWS, key, "ruin_penalty"),
                "threshold": field(ABILITY_ROWS, key, "ruin_threshold"),
            }
            for key, label in rules.RUINS
        ],
        "leaders": [
            {
                "label": label,
                "invested": field(LEADER_ROWS, key, "invested"),
                "character": field(LEADER_ROWS, key, "character"),
                "saved_character": leaders[key].character,
                "key_ability": rules.ABILITY_LABELS[ability],
                "vacancy_penalty": rules.VACANCY_PENALTIES[key],
                "vacant": key in vacant,
            }
            for key, label, ability in rules.LEADERSHIP_ROLES
        ],
        "max_invested": rules.MAX_INVESTED_LEADERS,
        "skills": _skill_rows(kingdom, form, scores, vacant),
        "commodities": [
            {
                "label": label,
                "stored": field(COMMODITY_ROWS, key, "stored"),
                "capacity": field(COMMODITY_ROWS, key, "capacity"),
            }
            for key, label in rules.COMMODITIES
        ],
        "work_sites": [form[key] for key, _ in rules.WORK_SITES],
    }


def _investiture_warnings(form):
    """Going over the usual limit is only a warning, since some characters add extra investiture."""
    invested = [
        rules.ROLE_LABELS[key]
        for key in LEADER_ROWS.keys
        if form[LEADER_ROWS.field_name(key, "character")].value()
        and form[LEADER_ROWS.field_name(key, "invested")].value()
    ]
    if len(invested) <= rules.MAX_INVESTED_LEADERS:
        return []
    return [
        f"{len(invested)} leaders are invested, more than the usual "
        f"{rules.MAX_INVESTED_LEADERS} ({', '.join(invested)})."
    ]


def _vacancy_reminders(vacant):
    """One line per effect, naming every vacant role that causes it, such as
    "General or magister vacant: -4 to Warfare activities"."""
    roles_by_effect = {}
    for role, effect in rules.OTHER_VACANCY_EFFECTS.items():
        if role in vacant:
            roles_by_effect.setdefault(effect, []).append(rules.ROLE_LABELS[role])
    return [
        f"{' or '.join(roles).capitalize()} vacant: {effect}"
        for effect, roles in roles_by_effect.items()
    ]


def _skill_rows(kingdom, form, scores, vacant):
    saved = SKILL_ROWS.rows(kingdom)
    rows = []
    for key, label, ability in rules.SKILLS:
        skill = saved[key]
        vacancy, disadvantage = rules.vacancy_effects(key, ability, vacant)
        rows.append(
            {
                "label": label,
                "ability": rules.ABILITY_LABELS[ability],
                "ability_modifier": rules.ability_modifier(scores[ability]),
                "proficiency": rules.rank_bonus(skill.rank, kingdom.level),
                "rank_label": rules.RANK_LABELS[skill.rank],
                "total": rules.skill_total(
                    ability_score=scores[ability],
                    rank=skill.rank,
                    level=kingdom.level,
                    bonus=skill.bonus,
                    vacancy=vacancy,
                ),
                "roll": rules.roll_mode(rules.has_expertise(skill.rank), disadvantage),
                "vacancy": vacancy,
                "vacancy_disadvantage": disadvantage,
                **{name: form[SKILL_ROWS.field_name(key, name)] for name in SKILL_ROWS.fields},
            }
        )
    return rows


def error_messages(form):
    """Flatten form errors into readable lines, such as "Agriculture bonus: Enter a number"."""
    messages = list(form.non_field_errors())
    for name, errors in form.errors.items():
        if name != "__all__":
            label = name.replace("_", " ").capitalize()
            messages.extend(f"{label}: {error}" for error in errors)
    return messages
