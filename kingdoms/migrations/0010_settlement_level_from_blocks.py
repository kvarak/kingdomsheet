from django.db import migrations


def set_levels(apps, schema_editor):
    """A settlement's level is the number of blocks with at least one building, at most 20."""
    Settlement = apps.get_model("kingdoms", "Settlement")
    for settlement in Settlement.objects.all():
        level = min(20, settlement.placements.values("block").distinct().count())
        if level != settlement.level:
            settlement.level = level
            settlement.save(update_fields=["level"])


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0009_retype_settlements"),
    ]

    operations = [
        migrations.RunPython(set_levels, migrations.RunPython.noop),
    ]
