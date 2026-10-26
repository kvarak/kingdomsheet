"""How the PF2e kingdom sheet maps onto models, form fields and template rows."""

from dataclasses import dataclass

from . import pf2e
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
    "control_dc_base",
    "control_dc_size",
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
        return {
            getattr(row, self.key_field): row for row in self.model.objects.filter(kingdom=kingdom)
        }


ABILITY_ROWS = RowGroup(
    KingdomAbility,
    "ability",
    tuple(key for key, _ in pf2e.ABILITIES),
    ("score", "ruin", "ruin_penalty", "ruin_threshold"),
)
SKILL_ROWS = RowGroup(
    KingdomSkill,
    "skill",
    tuple(key for key, _, _ in pf2e.SKILLS),
    ("rank", "status", "circumstance", "item", "other"),
)
LEADER_ROWS = RowGroup(
    KingdomLeader,
    "role",
    tuple(key for key, _, _ in pf2e.LEADERSHIP_ROLES),
    ("character", "invested"),
)
COMMODITY_ROWS = RowGroup(
    KingdomCommodity,
    "commodity",
    tuple(key for key, _ in pf2e.COMMODITIES),
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

    def field(group, key, name):
        return form[group.field_name(key, name)]

    return {
        "abilities": [
            {
                "label": label,
                "score": field(ABILITY_ROWS, key, "score"),
                "modifier": pf2e.ability_modifier(scores[key]),
            }
            for key, label in pf2e.ABILITIES
        ],
        "control_dc": pf2e.control_dc(kingdom.control_dc_base, kingdom.control_dc_size),
        "ruins": [
            {
                "label": label,
                "score": field(ABILITY_ROWS, key, "ruin"),
                "penalty": field(ABILITY_ROWS, key, "ruin_penalty"),
                "threshold": field(ABILITY_ROWS, key, "ruin_threshold"),
            }
            for key, label in pf2e.RUINS
        ],
        "leaders": [
            {
                "label": label,
                "invested": field(LEADER_ROWS, key, "invested"),
                "character": field(LEADER_ROWS, key, "character"),
            }
            for key, label, _ in pf2e.LEADERSHIP_ROLES
        ],
        "skills": _skill_rows(kingdom, form, scores),
        "commodities": [
            {
                "label": label,
                "stored": field(COMMODITY_ROWS, key, "stored"),
                "capacity": field(COMMODITY_ROWS, key, "capacity"),
            }
            for key, label in pf2e.COMMODITIES
        ],
        "work_sites": [form[key] for key, _ in pf2e.WORK_SITES],
    }


def _skill_rows(kingdom, form, scores):
    saved = SKILL_ROWS.rows(kingdom)
    rows = []
    for key, label, ability in pf2e.SKILLS:
        skill = saved[key]
        rows.append(
            {
                "label": label,
                "ability": pf2e.ABILITY_LABELS[ability],
                "ability_modifier": pf2e.ability_modifier(scores[ability]),
                "proficiency": pf2e.proficiency_bonus(skill.rank, kingdom.level),
                "rank_label": dict(pf2e.PROFICIENCY_RANKS)[skill.rank],
                "total": pf2e.skill_total(
                    ability_score=scores[ability],
                    rank=skill.rank,
                    level=kingdom.level,
                    status=skill.status,
                    circumstance=skill.circumstance,
                    item=skill.item,
                    other=skill.other,
                ),
                **{name: form[SKILL_ROWS.field_name(key, name)] for name in SKILL_ROWS.fields},
            }
        )
    return rows


def error_messages(form):
    """Flatten form errors into readable lines, such as "Agriculture status: Enter a number"."""
    messages = list(form.non_field_errors())
    for name, errors in form.errors.items():
        if name != "__all__":
            label = name.replace("_", " ").capitalize()
            messages.extend(f"{label}: {error}" for error in errors)
    return messages
