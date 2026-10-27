"""Kingdom rules: the Pathfinder 2e Kingmaker kingdom subsystem adapted to Varlyn 5e.

The structure (abilities, ruin, 16 kingdom skills, leadership roles) follows the official
Kingmaker kingdom sheet. The numbers use the Varlyn 5e scale: a proficiency bonus by level,
Expertise as advantage and Improved Proficiency as +1 steps (see dnd.rigo.nu). Only the formulas
here are calculated; everything else is typed in by the players.
"""

ABILITIES = [
    ("culture", "Culture"),
    ("economy", "Economy"),
    ("loyalty", "Loyalty"),
    ("stability", "Stability"),
]
ABILITY_LABELS = dict(ABILITIES)

# Ruin tied to each ability, in the order the official sheet prints them.
RUINS = [
    ("culture", "Corruption"),
    ("economy", "Crime"),
    ("stability", "Decay"),
    ("loyalty", "Strife"),
]

# (key, label, ability)
SKILLS = [
    ("agriculture", "Agriculture", "stability"),
    ("arts", "Arts", "culture"),
    ("boating", "Boating", "economy"),
    ("defense", "Defense", "stability"),
    ("engineering", "Engineering", "stability"),
    ("exploration", "Exploration", "economy"),
    ("folklore", "Folklore", "culture"),
    ("industry", "Industry", "economy"),
    ("intrigue", "Intrigue", "loyalty"),
    ("magic", "Magic", "culture"),
    ("politics", "Politics", "loyalty"),
    ("scholarship", "Scholarship", "culture"),
    ("statecraft", "Statecraft", "loyalty"),
    ("trade", "Trade", "economy"),
    ("warfare", "Warfare", "loyalty"),
    ("wilderness", "Wilderness", "stability"),
]

# (key, label, ability)
LEADERSHIP_ROLES = [
    ("ruler", "Ruler", "loyalty"),
    ("counselor", "Counselor", "culture"),
    ("general", "General", "stability"),
    ("emissary", "Emissary", "loyalty"),
    ("magister", "Magister", "culture"),
    ("treasurer", "Treasurer", "economy"),
    ("viceroy", "Viceroy", "economy"),
    ("warden", "Warden", "stability"),
]
ROLE_LABELS = {key: label for key, label, _ in LEADERSHIP_ROLES}

# What each role costs while it is vacant (no character fills it). The -4 penalties of the
# Pathfinder rules are disadvantage in Varlyn.
VACANCY_PENALTIES = {
    "ruler": "-1 to all checks (stacks with any other vacancy penalty); gain 1d4 Unrest at the "
    "start of the Kingdom turn; Control DC increases by 2",
    "counselor": "-1 to all Culture-based checks",
    "general": "disadvantage on Warfare activities",
    "emissary": "-1 to all Loyalty-based checks",
    "magister": "disadvantage on Warfare activities",
    "treasurer": "-1 to all Economy-based checks",
    "viceroy": "-1 to Stability-based checks",
    "warden": "disadvantage on Region activities",
}
# The ruler's -1 stacks with everything. The other vacancy penalties do not stack with each other,
# so a skill takes only the worst one; disadvantage counts as worse than -1.
RULER_VACANCY_PENALTY = -1
RULER_VACANCY_CONTROL_DC = 2
ABILITY_VACANCIES = {
    "counselor": "culture",
    "emissary": "loyalty",
    "treasurer": "economy",
    "viceroy": "stability",
}
ABILITY_VACANCY_PENALTY = -1
WARFARE_VACANCIES = ("general", "magister")
# Vacancy effects the skill table cannot show, listed as reminders under Leaders. Warfare
# activities can use other skills than Warfare, so that penalty is listed here too.
OTHER_VACANCY_EFFECTS = {
    "ruler": "gain 1d4 Unrest at the start of the Kingdom turn",
    "general": "disadvantage on Warfare activities",
    "magister": "disadvantage on Warfare activities",
    "warden": "disadvantage on Region activities",
}

WORK_SITES = [
    ("farmlands", "Farmlands"),
    ("lumber_camps", "Lumber camps"),
    ("mines", "Mines"),
    ("quarries", "Quarries"),
]

COMMODITIES = [
    ("food", "Food"),
    ("lumber", "Lumber"),
    ("luxuries", "Luxuries"),
    ("ore", "Ore"),
    ("stone", "Stone"),
]

# Kingdom skill ranks in Varlyn terms. Expertise gives advantage; each step after it adds +1,
# like Varlyn's Improved Proficiency. Stored as 0-4, matching the Pathfinder ranks they replace.
PROFICIENCY_RANKS = [
    (0, "Untrained"),
    (1, "Proficient"),
    (2, "Expertise"),
    (3, "Expertise +1"),
    (4, "Expertise +2"),
]
RANK_LABELS = dict(PROFICIENCY_RANKS)
EXPERTISE_RANK = 2

CONTROL_DC_BASE = 12
KINGDOM_DC_ADJUSTMENTS = {"hard": 2, "very hard": 5}
# (fewest hexes, size modifier) from the Kingmaker kingdom size table.
SIZE_MODIFIERS = [(100, 4), (50, 3), (25, 2), (10, 1), (1, 0)]


def ability_modifier(score):
    return (score - 10) // 2


def proficiency_bonus(level):
    """The 5e proficiency bonus: +2 at levels 1-4, rising by 1 every 4 levels to +6."""
    return 2 + (max(1, min(level, 20)) - 1) // 4


def rank_bonus(rank, level):
    """What a kingdom skill rank adds to checks, before advantage."""
    if rank == 0:
        return 0
    return proficiency_bonus(level) + max(0, rank - EXPERTISE_RANK)


def has_expertise(rank):
    return rank >= EXPERTISE_RANK


def vacancy_effects(skill, ability, vacant_roles):
    """(penalty, disadvantage) a skill takes from vacant leadership roles."""
    disadvantage = skill == "warfare" and any(role in vacant_roles for role in WARFARE_VACANCIES)
    penalty = 0
    if not disadvantage and any(
        role in vacant_roles and role_ability == ability
        for role, role_ability in ABILITY_VACANCIES.items()
    ):
        penalty = ABILITY_VACANCY_PENALTY
    if "ruler" in vacant_roles:
        penalty += RULER_VACANCY_PENALTY
    return penalty, disadvantage


def roll_mode(advantage, disadvantage):
    """As in 5e, advantage and disadvantage cancel each other out."""
    if advantage and not disadvantage:
        return "advantage"
    if disadvantage and not advantage:
        return "disadvantage"
    return ""


def skill_total(*, ability_score, rank, level, bonus, vacancy=0):
    """Total = ability modifier + rank bonus + bonus + vacancy penalty."""
    return ability_modifier(ability_score) + rank_bonus(rank, level) + bonus + vacancy


def size_modifier(size):
    return next(modifier for fewest, modifier in SIZE_MODIFIERS if size >= fewest)


def kingdom_dc(level, adjustment=None):
    """Kingdom check DC for content of a level: 12 + proficiency, +2 hard, +5 very hard."""
    return CONTROL_DC_BASE + proficiency_bonus(level) + KINGDOM_DC_ADJUSTMENTS.get(adjustment, 0)


def control_dc(level, size, ruler_vacant=False):
    """12 + proficiency bonus + size modifier, +2 while the ruler role is vacant."""
    return (
        kingdom_dc(level) + size_modifier(size) + (RULER_VACANCY_CONTROL_DC if ruler_vacant else 0)
    )
