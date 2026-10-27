from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0020_unit_quality_values"),
    ]

    operations = [
        migrations.AlterField(
            model_name="unit",
            name="quality",
            field=models.CharField(
                blank=True,
                choices=[
                    ("militia", "Militia"),
                    ("trained", "Trained"),
                    ("veteran", "Veteran"),
                    ("elite", "Elite"),
                ],
                max_length=10,
            ),
        ),
    ]
