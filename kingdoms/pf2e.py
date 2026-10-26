"""Pathfinder 2e kingdom sheet (Kingmaker), following the official Paizo kingdom sheet.

Only the sums printed on the sheet and the standard modifier and proficiency formulas are
calculated here. All other kingdom rules are tracked by hand.
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

PROFICIENCY_RANKS = [
    (0, "Untrained"),
    (1, "Trained"),
    (2, "Expert"),
    (3, "Master"),
    (4, "Legendary"),
]


def ability_modifier(score):
    return (score - 10) // 2


def proficiency_bonus(rank, level):
    return 0 if rank == 0 else level + 2 * rank


def skill_total(*, ability_score, rank, level, status, circumstance, item, other):
    """Total = ability modifier + proficiency + status + circumstance + item + other."""
    return (
        ability_modifier(ability_score)
        + proficiency_bonus(rank, level)
        + status
        + circumstance
        + item
        + other
    )


def control_dc(base, size):
    return base + size
