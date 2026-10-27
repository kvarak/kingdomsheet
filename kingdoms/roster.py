"""Plain-text unit summaries for pasting into Roll20 chat. Only the recorded values, no rules."""

from .models import Unit


def unit_summary(unit):
    """A readable plain-text block with the unit's recorded values."""
    kind = ", ".join(
        value for value in (unit.ancestry, unit.experience, unit.equipment, unit.unit_type) if value
    )
    lines = [f"{unit.name} ({unit.army.name})"]
    if kind:
        lines.append(kind)
    lines.append(
        ", ".join(f"{field.capitalize()} {getattr(unit, field)}" for field in Unit.STATISTICS)
    )
    strength = f"Strength {unit.current_strength}/{unit.max_strength}"
    if unit.size:
        strength += f", size {unit.size}"
    lines.append(strength)
    for label, value in (("Status", unit.status), ("Traits", unit.traits), ("Notes", unit.notes)):
        if value.strip():
            lines.append(f"{label}: {' '.join(value.split())}")
    return "\n".join(lines)
