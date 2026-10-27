"""Plain-text unit summaries for pasting into Roll20 chat: the recorded values, with Morale
including the hero's bonus and whether the unit is diminished, under the campaign's Kingmaker
Warfare house rules."""

from .models import Unit

WARFARE_RULES_URL = "https://dnd.rigo.nu/CampaignRules/12_kingmaker_war.html"


def unit_summary(unit):
    """A readable plain-text block with the unit's recorded values."""
    kind = ", ".join(
        value
        for value in (unit.ancestry, unit.get_quality_display(), unit.equipment, unit.unit_type)
        if value
    )
    lines = [f"{unit.name} ({unit.army.name})"]
    if kind:
        lines.append(kind)
    statistics = {field: getattr(unit, field) for field in Unit.STATISTICS}
    statistics["morale"] = unit.battle_morale
    lines.append(", ".join(f"{field.capitalize()} {value}" for field, value in statistics.items()))
    if unit.hero:
        lines.append(f"Hero: {unit.hero} (Morale includes +{Unit.HERO_MORALE})")
    strength = f"Strength {unit.current_strength}/{unit.max_strength}"
    if unit.diminished:
        strength += ", diminished"
    if unit.size:
        strength += f", size {unit.size}"
    lines.append(strength)
    for label, value in (("Status", unit.status), ("Traits", unit.traits), ("Notes", unit.notes)):
        if value.strip():
            lines.append(f"{label}: {' '.join(value.split())}")
    return "\n".join(lines)
