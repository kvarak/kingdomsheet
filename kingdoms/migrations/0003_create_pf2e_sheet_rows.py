from django.db import migrations

# Copied here so this migration keeps working if the sheet structure changes later.
SHEET_ROWS = [
    ("KingdomAbility", "ability", ["culture", "economy", "loyalty", "stability"]),
    (
        "KingdomSkill",
        "skill",
        [
            "agriculture", "arts", "boating", "defense", "engineering", "exploration",
            "folklore", "industry", "intrigue", "magic", "politics", "scholarship",
            "statecraft", "trade", "warfare", "wilderness",
        ],
    ),
    (
        "KingdomLeader",
        "role",
        ["ruler", "counselor", "general", "emissary", "magister", "treasurer", "viceroy", "warden"],
    ),
    ("KingdomCommodity", "commodity", ["food", "lumber", "luxuries", "ore", "stone"]),
]


def create_sheet_rows(apps, schema_editor):
    Kingdom = apps.get_model("kingdoms", "Kingdom")
    for kingdom in Kingdom.objects.all():
        for model_name, key_field, keys in SHEET_ROWS:
            model = apps.get_model("kingdoms", model_name)
            model.objects.bulk_create(
                [model(kingdom=kingdom, **{key_field: key}) for key in keys],
                ignore_conflicts=True,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0002_pf2e_sheet"),
    ]

    operations = [
        migrations.RunPython(create_sheet_rows, migrations.RunPython.noop),
    ]
