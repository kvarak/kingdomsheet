from django.db import IntegrityError, transaction

from .access import new_access_code
from .models import HistoryEntry, Kingdom, Statistic
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
        _record_statistic(
            kingdom, writer, HistoryEntry.Action.STATISTIC_ADDED, _created(values), statistic
        )
    return statistic


def update_statistic(kingdom, writer, statistic, values):
    with transaction.atomic():
        changes = _apply_changes(statistic, STATISTIC_FIELDS, values)
        if changes:
            _record_statistic(
                kingdom, writer, HistoryEntry.Action.STATISTIC_EDITED, changes, statistic
            )


def delete_statistic(kingdom, writer, statistic):
    with transaction.atomic():
        changes = _deleted(field_values(statistic, STATISTIC_FIELDS))
        _record_statistic(
            kingdom, writer, HistoryEntry.Action.STATISTIC_DELETED, changes, statistic
        )
        statistic.delete()


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


def _record_statistic(kingdom, writer, action, changes, statistic):
    _record(kingdom, writer, action, changes, statistic)
    # A statistic change is a change to the kingdom sheet, so it moves the kingdom up the list.
    kingdom.save(update_fields=["updated_at"])


def _record(kingdom, writer, action, changes, statistic=None):
    HistoryEntry.objects.create(
        kingdom=kingdom,
        action=action,
        display_name=writer.display_name,
        name_verified=writer.verified,
        statistic_id=statistic.pk if statistic else None,
        statistic_label=statistic.label if statistic else "",
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
