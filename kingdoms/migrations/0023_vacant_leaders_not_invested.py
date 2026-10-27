"""A vacant leader role cannot be invested."""

from django.db import migrations


def clear_vacant(apps, schema_editor):
    KingdomLeader = apps.get_model("kingdoms", "KingdomLeader")
    KingdomLeader.objects.filter(character__isnull=True, invested=True).update(invested=False)


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0022_unit_hero"),
    ]

    operations = [
        migrations.RunPython(clear_vacant, migrations.RunPython.noop),
    ]
