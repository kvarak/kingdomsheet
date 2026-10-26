from django.db import migrations

# A frozen copy of growth.type_from_layout, so this migration keeps working if the rules change.


def _adjacent(a, b):
    row_a, col_a = divmod(a, 3)
    row_b, col_b = divmod(b, 3)
    return abs(row_a - row_b) + abs(col_a - col_b) == 1


def _contiguous(blocks):
    blocks = set(blocks)
    reached, frontier = set(), [next(iter(blocks))]
    while frontier:
        block = frontier.pop()
        if block not in reached:
            reached.add(block)
            frontier.extend(b for b in blocks if _adjacent(block, b) and b not in reached)
    return reached == blocks


def _type_from_layout(blocks):
    if len(blocks) <= 1:
        return "village"
    if len(blocks) <= 4 and _contiguous(blocks):
        return "town"
    return "city"


def retype(apps, schema_editor):
    Settlement = apps.get_model("kingdoms", "Settlement")
    for settlement in Settlement.objects.exclude(settlement_type="metropolis"):
        blocks = set(settlement.placements.values_list("block", flat=True))
        new_type = _type_from_layout(blocks)
        if new_type != settlement.settlement_type:
            settlement.settlement_type = new_type
            settlement.save(update_fields=["settlement_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("kingdoms", "0008_tidy_settlement_borders"),
    ]

    operations = [
        migrations.RunPython(retype, migrations.RunPython.noop),
    ]
