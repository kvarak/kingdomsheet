from django.db import migrations


def tidy_borders(apps, schema_editor):
    """Apply the border rules to existing data: a bridge implies water, and one wall per side."""
    Settlement = apps.get_model("kingdoms", "Settlement")
    for settlement in Settlement.objects.all():
        borders = {}
        for side, features in settlement.borders.items():
            water = "water" in features or "bridge" in features
            bridge = "bridge" in features
            wall = "wall_stone" if "wall_stone" in features else (
                "wall_wood" if "wall_wood" in features else ""
            )
            tidy = [key for key, on in (("water", water), ("bridge", bridge), (wall, bool(wall))) if on]
            if tidy:
                borders[side] = tidy
        if borders != settlement.borders:
            settlement.borders = borders
            settlement.save(update_fields=["borders"])


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0007_npcs"),
    ]

    operations = [
        migrations.RunPython(tidy_borders, migrations.RunPython.noop),
    ]
