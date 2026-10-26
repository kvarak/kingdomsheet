from django.db import IntegrityError, transaction

from .access import new_access_code
from .models import HistoryEntry, Kingdom, Placement, Settlement, Statistic
from .settlements import catalog
from .sheet import KINGDOM_FIELDS, ROW_GROUPS, create_rows, field_values

STATISTIC_FIELDS = ("label", "value", "display_order")
MAX_CODE_ATTEMPTS = 5


def create_kingdom(writer, name, description, notes):
    values = {"name": name, "description": description, "notes": notes}
    for _ in range(MAX_CODE_ATTEMPTS):
        try:
            with transaction.atomic():
                kingdom = Kingdom.objects.create(access_code=new_access_code(), **values)
                create_rows(kingdom)
                _record(kingdom, writer, HistoryEntry.Action.KINGDOM_CREATED, _created(values))
            return kingdom
        except IntegrityError:
            # Only a sharing ID collision is expected here, so try again with a new code.
            continue
    raise RuntimeError("Could not generate a unique sharing ID.")


def update_sheet(kingdom, writer, values):
    """Save the whole sheet from flat form values and record one history entry for the changes."""
    with transaction.atomic():
        kingdom_values = {field: values[field] for field in KINGDOM_FIELDS}
        changes = _labelled(_apply_changes(kingdom, KINGDOM_FIELDS, kingdom_values))
        for group in ROW_GROUPS:
            for key, row in group.rows(kingdom).items():
                row_values = {field: values[group.field_name(key, field)] for field in group.fields}
                changes.update(_labelled(_apply_changes(row, group.fields, row_values), row))
        if changes:
            kingdom.save(update_fields=["updated_at"])
            _record(kingdom, writer, HistoryEntry.Action.KINGDOM_EDITED, changes)


def add_statistic(kingdom, writer, values):
    with transaction.atomic():
        statistic = Statistic.objects.create(kingdom=kingdom, **values)
        _record_and_touch(
            kingdom, writer, HistoryEntry.Action.STATISTIC_ADDED, _created(values), statistic
        )
    return statistic


def update_statistic(kingdom, writer, statistic, values):
    with transaction.atomic():
        changes = _apply_changes(statistic, STATISTIC_FIELDS, values)
        if changes:
            _record_and_touch(
                kingdom, writer, HistoryEntry.Action.STATISTIC_EDITED, changes, statistic
            )


def delete_statistic(kingdom, writer, statistic):
    with transaction.atomic():
        changes = _deleted(field_values(statistic, STATISTIC_FIELDS))
        _record_and_touch(
            kingdom, writer, HistoryEntry.Action.STATISTIC_DELETED, changes, statistic
        )
        statistic.delete()


SETTLEMENT_FIELDS = (
    "name",
    "settlement_type",
    "level",
    "consumption",
    "overcrowded",
    "max_item_bonus",
    "influence",
    "magical_streetlamps",
    "paved_streets",
    "sewer_system",
    "borders",
    "garrisoned_armies",
    "ongoing_events",
)


def add_settlement(kingdom, writer, values):
    with transaction.atomic():
        settlement = Settlement.objects.create(kingdom=kingdom, **values)
        _record_and_touch(
            kingdom, writer, HistoryEntry.Action.SETTLEMENT_ADDED, _created(values), settlement
        )
    return settlement


def update_settlement(settlement, writer, values):
    with transaction.atomic():
        changes = _labelled(_apply_changes(settlement, SETTLEMENT_FIELDS, values))
        if changes:
            _record_and_touch(
                settlement.kingdom,
                writer,
                HistoryEntry.Action.SETTLEMENT_EDITED,
                changes,
                settlement,
            )


def delete_settlement(settlement, writer):
    with transaction.atomic():
        buildings = sorted(
            catalog()[p.building].label
            for p in settlement.placements.all()
            if p.building in catalog()
        )
        changes = _deleted(
            {"type": settlement.get_settlement_type_display(), "buildings": buildings}
        )
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.SETTLEMENT_DELETED, changes, settlement
        )
        settlement.delete()


def place_building(settlement, writer, values):
    with transaction.atomic():
        placement = Placement.objects.create(settlement=settlement, **values)
        changes = _created({"building": catalog()[placement.building].label, **_where(placement)})
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.BUILDING_PLACED, changes, settlement
        )
    return placement


def remove_building(settlement, writer, placement):
    with transaction.atomic():
        building = catalog().get(placement.building)
        label = building.label if building else placement.building
        changes = _deleted({"building": label, **_where(placement)})
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.BUILDING_REMOVED, changes, settlement
        )
        placement.delete()


def _where(placement):
    lot_names = ("top left", "top right", "bottom left", "bottom right")
    return {"block": placement.block + 1, "lot": lot_names[placement.lot]}


def _apply_changes(instance, fields, values, extra_fields=()):
    """Copy changed values onto the instance and save them. Returns the diff, empty if none."""
    changes = _diff(field_values(instance, fields), values)
    if changes:
        for field in changes:
            setattr(instance, field, values[field])
        instance.save(update_fields=[*changes, *extra_fields])
    return changes


def _labelled(changes, row=None):
    """Use readable history keys, such as "Agriculture rank" or "control dc base"."""
    prefix = f"{row} " if row is not None else ""
    return {f"{prefix}{field.replace('_', ' ')}": diff for field, diff in changes.items()}


def _record_and_touch(kingdom, writer, action, changes, subject):
    _record(kingdom, writer, action, changes, subject)
    # Statistic and settlement changes move the kingdom up the "Your kingdoms" list.
    kingdom.save(update_fields=["updated_at"])


def _record(kingdom, writer, action, changes, subject=None):
    HistoryEntry.objects.create(
        kingdom=kingdom,
        action=action,
        display_name=writer.display_name,
        name_verified=writer.verified,
        subject_id=subject.pk if subject else None,
        subject_label=str(subject) if subject else "",
        changes=changes,
    )


def _diff(old, new):
    return {
        field: {"old": old[field], "new": new[field]} for field in new if old[field] != new[field]
    }


def _created(values):
    return {field: {"old": None, "new": value} for field, value in values.items()}


def _deleted(values):
    return {field: {"old": value, "new": None} for field, value in values.items()}
