"""Armies follow the Kingmaker Warfare house rules: unit experience becomes quality, size is no
longer a casualty die, and the old Kingmaker army sheet fields are removed."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0018_army_garrison"),
    ]

    operations = [
        migrations.RenameField(model_name="unit", old_name="experience", new_name="quality"),
        migrations.AlterField(
            model_name="unit",
            name="size",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.RemoveField(model_name="army", name="level"),
        migrations.RemoveField(model_name="army", name="alignment"),
        migrations.RemoveField(model_name="army", name="army_type"),
        migrations.RemoveField(model_name="army", name="scouting"),
        migrations.RemoveField(model_name="army", name="scouting_dc"),
        migrations.RemoveField(model_name="army", name="recruitment_dc"),
        migrations.RemoveField(model_name="army", name="ac"),
        migrations.RemoveField(model_name="army", name="maneuver"),
        migrations.RemoveField(model_name="army", name="maneuver_dc"),
        migrations.RemoveField(model_name="army", name="morale"),
        migrations.RemoveField(model_name="army", name="morale_dc"),
        migrations.RemoveField(model_name="army", name="armor_bonus"),
        migrations.RemoveField(model_name="army", name="hp"),
        migrations.RemoveField(model_name="army", name="current_hp"),
        migrations.RemoveField(model_name="army", name="rout_threshold"),
        migrations.RemoveField(model_name="army", name="melee"),
        migrations.RemoveField(model_name="army", name="ranged"),
        migrations.RemoveField(model_name="army", name="shots"),
        migrations.RemoveField(model_name="army", name="tactics"),
        migrations.RemoveField(model_name="army", name="tactical_actions"),
        migrations.RemoveField(model_name="army", name="conditions"),
        migrations.RemoveField(model_name="army", name="abilities"),
        migrations.RemoveField(model_name="army", name="armor_gear"),
        migrations.RemoveField(model_name="army", name="melee_gear"),
        migrations.RemoveField(model_name="army", name="ranged_gear"),
        migrations.RemoveField(model_name="army", name="healing_potions"),
    ]
