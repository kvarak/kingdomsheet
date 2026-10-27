import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0017_army_kingdom"),
    ]

    operations = [
        migrations.AlterField(
            model_name="army",
            name="kingdom",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="armies",
                to="kingdoms.kingdom",
            ),
        ),
        migrations.RenameField(model_name="army", old_name="settlement", new_name="garrison"),
        migrations.AlterField(
            model_name="army",
            name="garrison",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="garrisoned_armies",
                to="kingdoms.settlement",
            ),
        ),
    ]
