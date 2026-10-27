import django.db.models.deletion
from django.db import migrations, models


def merge_skill_bonuses(apps, schema_editor):
    """The four Pathfinder bonus columns become one Varlyn bonus column."""
    KingdomSkill = apps.get_model("kingdoms", "KingdomSkill")
    for skill in KingdomSkill.objects.all():
        skill.bonus = skill.status + skill.circumstance + skill.item + skill.other
        if skill.bonus:
            skill.save(update_fields=["bonus"])


# Table changes that follow the data change are in 0015, because PostgreSQL refuses to alter a
# table in the same transaction that just updated its rows.


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0013_leader_character_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="kingdomskill",
            name="bonus",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="army",
            name="armor_bonus",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="army",
            name="commander",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="kingdoms.character",
            ),
        ),
        migrations.RunPython(merge_skill_bonuses, migrations.RunPython.noop),
    ]
