from django.db import IntegrityError, models, transaction

from . import growth
from .access import new_access_code
from .models import (
    Army,
    Character,
    HistoryEntry,
    Kingdom,
    Placement,
    Settlement,
    Statistic,
)
from .settlements import DETAIL_FIELDS, LOT_NAMES, building_label
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
            _record_and_touch(kingdom, writer, HistoryEntry.Action.KINGDOM_EDITED, changes)


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


SETTLEMENT_FIELDS = (*DETAIL_FIELDS, "borders")


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
        buildings = sorted(building_label(p.building) for p in settlement.placements.all())
        armies = sorted(army.name for army in settlement.armies.all())
        changes = _deleted(
            {
                "type": settlement.get_settlement_type_display(),
                "buildings": buildings,
                "armies": armies,
            }
        )
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.SETTLEMENT_DELETED, changes, settlement
        )
        settlement.delete()


def place_building(settlement, writer, values):
    with transaction.atomic():
        before = growth.lots_per_block(settlement.placements.all())
        placement = Placement.objects.create(settlement=settlement, **values)
        after = growth.lots_per_block(settlement.placements.all())
        changes = _created({"building": building_label(placement.building), **_where(placement)})
        changes.update(
            _regrow(
                settlement,
                growth.type_after_placement(settlement.settlement_type, before, after),
                after,
            )
        )
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.BUILDING_PLACED, changes, settlement
        )
    return placement


def remove_building(settlement, writer, placement):
    with transaction.atomic():
        changes = _deleted({"building": building_label(placement.building), **_where(placement)})
        placement.delete()
        after = growth.lots_per_block(settlement.placements.all())
        changes.update(
            _regrow(settlement, growth.type_after_removal(settlement.settlement_type, after), after)
        )
        _record_and_touch(
            settlement.kingdom, writer, HistoryEntry.Action.BUILDING_REMOVED, changes, settlement
        )


def add_army(settlement, writer, name):
    with transaction.atomic():
        army = Army.objects.create(settlement=settlement, name=name)
        changes = _created({"name": name, "settlement": settlement.name})
        _record_and_touch(settlement.kingdom, writer, HistoryEntry.Action.ARMY_ADDED, changes, army)
    return army


def update_army(army, writer, values):
    with transaction.atomic():
        changes = _labelled(_apply_changes(army, Army.SHEET_FIELDS, values))
        if changes:
            _record_and_touch(
                army.settlement.kingdom, writer, HistoryEntry.Action.ARMY_EDITED, changes, army
            )


def delete_army(army, writer):
    with transaction.atomic():
        changes = _deleted({"name": army.name, "settlement": army.settlement.name})
        _record_and_touch(
            army.settlement.kingdom, writer, HistoryEntry.Action.ARMY_DELETED, changes, army
        )
        army.delete()


def add_character(kingdom, writer, name, kind, picture):
    with transaction.atomic():
        character = Character(kingdom=kingdom, name=name, kind=kind)
        if picture:
            character.picture.save(picture.name, picture, save=False)
        character.save()
        changes = _created(
            {"name": name, "kind": character.get_kind_display(), "picture": bool(picture)}
        )
        _record_and_touch(kingdom, writer, HistoryEntry.Action.CHARACTER_ADDED, changes, character)
    return character


def update_character(character, writer, name, kind, picture):
    """Rename the character, change PC or NPC and, if `picture` is given, replace its picture."""
    with transaction.atomic():
        changes = {}
        if name != character.name:
            changes["name"] = {"old": character.name, "new": name}
            character.name = name
        if kind != character.kind:
            old_kind = character.get_kind_display()
            character.kind = kind
            changes["kind"] = {"old": old_kind, "new": character.get_kind_display()}
        if picture:
            _delete_file_after_commit(character.picture)
            character.picture.save(picture.name, picture, save=False)
            changes["picture"] = {"old": "previous picture", "new": "new picture"}
        if changes:
            character.save()
            _record_and_touch(
                character.kingdom, writer, HistoryEntry.Action.CHARACTER_EDITED, changes, character
            )


def delete_character(character, writer):
    with transaction.atomic():
        _delete_file_after_commit(character.picture)
        changes = _deleted({"name": character.name, "kind": character.get_kind_display()})
        _record_and_touch(
            character.kingdom, writer, HistoryEntry.Action.CHARACTER_DELETED, changes, character
        )
        character.delete()


def _delete_file_after_commit(field_file):
    if field_file:
        name, storage = field_file.name, field_file.storage
        transaction.on_commit(lambda: storage.delete(name))


def _regrow(settlement, new_type, counts):
    """Save the type and level the buildings now give. Returns the history changes, if any."""
    new = {"settlement_type": new_type, "level": growth.settlement_level(counts)}
    changes = {}
    for field, value in new.items():
        old = getattr(settlement, field)
        if value != old:
            changes["type" if field == "settlement_type" else field] = {"old": old, "new": value}
            setattr(settlement, field, value)
    if changes:
        settlement.save(update_fields=list(new))
    return changes


def _where(placement):
    return {"block": placement.block + 1, "lot": LOT_NAMES[placement.lot].lower()}


def _apply_changes(instance, fields, values):
    """Copy changed values onto the instance and save them. Returns the diff, empty if none."""
    changes = _diff(field_values(instance, fields), values)
    if changes:
        for field in changes:
            setattr(instance, field, values[field])
        instance.save(update_fields=list(changes))
    return changes


def _labelled(changes, row=None):
    """Use readable history keys, such as "Agriculture rank" or "control dc base"."""
    prefix = f"{row} " if row is not None else ""
    return {f"{prefix}{field.replace('_', ' ')}": diff for field, diff in changes.items()}


def _record_and_touch(kingdom, writer, action, changes, subject=None):
    _record(kingdom, writer, action, changes, subject)
    # Any change to the sheet, its statistics or settlements moves it up "Your kingdoms".
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
        field: {"old": _json(old[field]), "new": _json(new[field])}
        for field in new
        if old[field] != new[field]
    }


def _created(values):
    return {field: {"old": None, "new": _json(value)} for field, value in values.items()}


def _deleted(values):
    return {field: {"old": _json(value), "new": None} for field, value in values.items()}


def _json(value):
    """History is stored as JSON, so linked rows such as a character are recorded by name."""
    return str(value) if isinstance(value, models.Model) else value
