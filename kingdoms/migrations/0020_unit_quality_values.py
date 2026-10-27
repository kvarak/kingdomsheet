"""Turn free-text unit quality into one of the four qualities. Text that is not one of them moves to
the unit's notes so nothing is lost. Kept apart from the schema change in 0021 because PostgreSQL
refuses to alter a table with pending updates in the same transaction."""

from django.db import migrations

QUALITIES = {"militia", "trained", "veteran", "elite"}


def to_choices(apps, schema_editor):
    Unit = apps.get_model("kingdoms", "Unit")
    for unit in Unit.objects.exclude(quality=""):
        value = unit.quality.strip().lower()
        if value not in QUALITIES:
            unit.notes = "\n".join(text for text in (unit.notes, f"Quality: {unit.quality}") if text)
            value = ""
        unit.quality = value
        unit.save(update_fields=["quality", "notes"])


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0019_unit_quality_remove_old_army_fields"),
    ]

    operations = [
        migrations.RunPython(to_choices, migrations.RunPython.noop),
    ]
