import django.db.models.deletion
from django.db import migrations, models


def set_army_kingdoms(apps, schema_editor):
    """Every army belongs to the kingdom of the settlement it was garrisoned in."""
    Army = apps.get_model("kingdoms", "Army")
    for army in Army.objects.select_related("settlement"):
        army.kingdom_id = army.settlement.kingdom_id
        army.save(update_fields=["kingdom"])


# 0018 makes the kingdom required and turns the settlement into an optional garrison. It is a
# separate migration because PostgreSQL refuses to alter a table in the same transaction that just
# updated its rows.


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0016_army_rosters"),
    ]

    operations = [
        migrations.AddField(
            model_name="army",
            name="kingdom",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="armies",
                to="kingdoms.kingdom",
            ),
        ),
        migrations.RunPython(set_army_kingdoms, migrations.RunPython.noop),
    ]
