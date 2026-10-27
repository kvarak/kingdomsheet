from django.db import migrations, models


def leader_names_to_characters(apps, schema_editor):
    """Free-text leader names become PC characters, so no leader is lost."""
    KingdomLeader = apps.get_model("kingdoms", "KingdomLeader")
    Character = apps.get_model("kingdoms", "Character")
    for leader in KingdomLeader.objects.exclude(character="").filter(npc=None):
        name = leader.character.strip()
        if not name:
            continue
        character = Character.objects.filter(kingdom_id=leader.kingdom_id, name=name).first()
        if character is None:
            character = Character.objects.create(kingdom_id=leader.kingdom_id, name=name, kind="pc")
        leader.npc = character
        leader.save(update_fields=["npc"])


def rename_history_actions(apps, schema_editor):
    HistoryEntry = apps.get_model("kingdoms", "HistoryEntry")
    for old, new in (
        ("npc_added", "character_added"),
        ("npc_edited", "character_edited"),
        ("npc_deleted", "character_deleted"),
    ):
        HistoryEntry.objects.filter(action=old).update(action=new)


# Data changes and table changes live in separate migrations: PostgreSQL refuses to alter a table
# in the same transaction that just updated its rows. 0013 drops the free-text leader name.


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0011_settlement_level_default"),
    ]

    operations = [
        migrations.RenameModel("Npc", "Character"),
        migrations.AddField(
            model_name="character",
            name="kind",
            field=models.CharField(
                choices=[("pc", "PC"), ("npc", "NPC")], default="npc", max_length=3
            ),
        ),
        migrations.RunPython(leader_names_to_characters, migrations.RunPython.noop),
        migrations.RunPython(rename_history_actions, migrations.RunPython.noop),
    ]
