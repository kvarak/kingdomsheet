from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0012_characters"),
    ]

    operations = [
        migrations.RemoveField(model_name="kingdomleader", name="character"),
        migrations.RenameField(model_name="kingdomleader", old_name="npc", new_name="character"),
    ]
