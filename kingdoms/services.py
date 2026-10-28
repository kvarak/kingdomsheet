from django.db import IntegrityError, models, transaction
from django.utils import timezone

from . import growth
from .access import new_access_code
from .models import (
    Army,
    Battle,
    Character,
    HistoryEntry,
    Kingdom,
    KingdomLeader,
    Placement,
    Settlement,
    Statistic,
    Unit,
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
    _update(
        settlement,
        settlement.kingdom,
        SETTLEMENT_FIELDS,
        values,
        writer,
        HistoryEntry.Action.SETTLEMENT_EDITED,
    )


def delete_settlement(settlement, writer):
    with transaction.atomic():
        buildings = sorted(building_label(p.building) for p in settlement.placements.all())
        armies = sorted(army.name for army in settlement.garrisoned_armies.all())
        changes = _deleted(
            {
                "type": settlement.get_settlement_type_display(),
                "buildings": buildings,
                "garrisoned armies": armies,
            }
        )
        # Armies outlive their garrison; they are only left without one until it is restored.
        garrisoned = Army.all_objects.filter(garrison=settlement)
        restore = {"armies": list(garrisoned.values_list("pk", flat=True))}
        garrisoned.update(garrison=None)
        _soft_delete(settlement, writer, HistoryEntry.Action.SETTLEMENT_DELETED, changes, restore)


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


def add_army(kingdom, writer, name):
    with transaction.atomic():
        army = Army.objects.create(kingdom=kingdom, name=name)
        changes = _created({"name": name})
        _record_and_touch(kingdom, writer, HistoryEntry.Action.ARMY_ADDED, changes, army)
    return army


def update_army(army, writer, values):
    _update(army, army.kingdom, Army.ROSTER_FIELDS, values, writer, HistoryEntry.Action.ARMY_EDITED)


def delete_army(army, writer):
    with transaction.atomic():
        changes = _deleted({"name": army.name, "units": army.units.count()})
        _soft_delete(army, writer, HistoryEntry.Action.ARMY_DELETED, changes)


def add_unit(army, writer, name):
    with transaction.atomic():
        order = (army.units.aggregate(models.Max("display_order"))["display_order__max"] or 0) + 1
        unit = Unit.objects.create(army=army, name=name, display_order=order)
        changes = _created({"name": name, "army": army.name})
        _record_and_touch(army.kingdom, writer, HistoryEntry.Action.UNIT_ADDED, changes, unit)
    return unit


def update_unit(unit, writer, values):
    _update(unit, unit.army.kingdom, Unit.FIELDS, values, writer, HistoryEntry.Action.UNIT_EDITED)


def delete_unit(unit, writer):
    with transaction.atomic():
        changes = _deleted({"name": unit.name, "army": unit.army.name})
        _soft_delete(unit, writer, HistoryEntry.Action.UNIT_DELETED, changes)


def record_battle(kingdom, writer, values):
    with transaction.atomic():
        battle = Battle.objects.create(kingdom=kingdom, **values)
        changes = _created({field: values[field] for field in ("name", "outcome")})
        _record_and_touch(kingdom, writer, HistoryEntry.Action.BATTLE_RECORDED, changes, battle)
    return battle


def update_battle(battle, writer, values):
    _update(
        battle, battle.kingdom, Battle.FIELDS, values, writer, HistoryEntry.Action.BATTLE_EDITED
    )


def delete_battle(battle, writer):
    with transaction.atomic():
        changes = _deleted({"name": battle.name, "outcome": battle.outcome})
        _record_and_touch(
            battle.kingdom, writer, HistoryEntry.Action.BATTLE_DELETED, changes, battle
        )
        battle.delete()


def add_character(kingdom, writer, name, kind, picture, notes="", reminder=False):
    with transaction.atomic():
        character = Character(kingdom=kingdom, name=name, kind=kind, notes=notes, reminder=reminder)
        if picture:
            character.picture.save(picture.name, picture, save=False)
        character.save()
        changes = _created(
            {"name": name, "kind": character.get_kind_display(), "picture": bool(picture)}
        )
        if notes:
            changes["notes"] = {"old": None, "new": notes}
        if reminder:
            changes["reminder"] = {"old": False, "new": True}
        _record_and_touch(kingdom, writer, HistoryEntry.Action.CHARACTER_ADDED, changes, character)
    return character


def update_character(character, writer, name, kind, picture, notes="", reminder=False):
    """Rename the character, change PC or NPC, replace its picture if `picture` is given, change
    its notes and set whether the notes show as a kingdom reminder."""
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
        if notes != character.notes:
            changes["notes"] = {"old": character.notes or None, "new": notes or None}
            character.notes = notes
        if reminder != character.reminder:
            changes["reminder"] = {"old": character.reminder, "new": reminder}
            character.reminder = reminder
        if changes:
            character.save()
            _record_and_touch(
                character.kingdom, writer, HistoryEntry.Action.CHARACTER_EDITED, changes, character
            )


def delete_character(character, writer):
    with transaction.atomic():
        # Their roles become vacant (and a vacant role cannot be invested). The picture is kept
        # so the character can be restored.
        leaders = KingdomLeader.objects.filter(character=character)
        commands = Army.all_objects.filter(commander=character)
        heroes = Unit.all_objects.filter(hero=character)
        restore = {
            "leaders": [
                [role, invested] for role, invested in leaders.values_list("role", "invested")
            ],
            "armies": list(commands.values_list("pk", flat=True)),
            "units": list(heroes.values_list("pk", flat=True)),
        }
        leaders.update(character=None, invested=False)
        commands.update(commander=None)
        heroes.update(hero=None)
        changes = _deleted({"name": character.name, "kind": character.get_kind_display()})
        _soft_delete(character, writer, HistoryEntry.Action.CHARACTER_DELETED, changes, restore)


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


def _update(instance, kingdom, fields, values, writer, action):
    """Save the changed fields of one row and record them in the kingdom history, if any changed."""
    with transaction.atomic():
        changes = _labelled(_apply_changes(instance, fields, values))
        if changes:
            _record_and_touch(kingdom, writer, action, changes, instance)


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


def _kingdom_of(subject):
    return subject.army.kingdom if isinstance(subject, Unit) else subject.kingdom


def _soft_delete(subject, writer, action, changes, restore=None):
    subject.deleted_at = timezone.now()
    subject.save(update_fields=["deleted_at"])
    restore = {"deleted_at": subject.deleted_at.isoformat(), **(restore or {})}
    _record_and_touch(_kingdom_of(subject), writer, action, changes, subject, restore)


RESTORABLE_MODELS = {
    HistoryEntry.Action.SETTLEMENT_DELETED: Settlement,
    HistoryEntry.Action.ARMY_DELETED: Army,
    HistoryEntry.Action.UNIT_DELETED: Unit,
    HistoryEntry.Action.CHARACTER_DELETED: Character,
}


def restorable_subject(entry):
    """The deleted row a history entry can bring back, or None. Only the latest deletion of a row
    can be undone, and only while the row is still deleted."""
    model = RESTORABLE_MODELS.get(entry.action)
    if model is None or entry.subject_id is None:
        return None
    rows = model.all_objects.filter(pk=entry.subject_id, deleted_at__isnull=False)
    if model is Unit:
        rows = rows.filter(army__kingdom=entry.kingdom)
    else:
        rows = rows.filter(kingdom=entry.kingdom)
    subject = rows.first()
    if subject and subject.deleted_at.isoformat() == entry.restore.get("deleted_at"):
        return subject
    return None


def restore_deleted(entry, writer):
    """Undo a deletion. Links it cleared, such as a garrison or leader role, are only put back
    where nobody has filled them since. Returns the restored row, or None if it cannot be."""
    with transaction.atomic():
        subject = restorable_subject(entry)
        if subject is None:
            return None
        subject.deleted_at = None
        subject.save(update_fields=["deleted_at"])
        changes = {"restored": {"old": None, "new": str(subject)}}
        if isinstance(subject, Settlement):
            changes.update(_relink(Army, entry.restore.get("armies"), "garrison", subject))
        elif isinstance(subject, Character):
            changes.update(_relink_leaders(subject, entry.restore.get("leaders", [])))
            changes.update(_relink(Army, entry.restore.get("armies"), "commander", subject))
            changes.update(_relink(Unit, entry.restore.get("units"), "hero", subject))
        _record_and_touch(
            entry.kingdom, writer, HistoryEntry.RESTORABLE[entry.action], changes, subject
        )
    return subject


def _relink(model, pks, field, subject):
    """Point `field` back at the subject on rows where it is still empty."""
    rows = model.all_objects.filter(pk__in=pks or [], **{f"{field}__isnull": True})
    names = sorted(str(row) for row in rows)
    rows.update(**{field: subject})
    label = {"garrison": "garrisoned armies", "commander": "commands", "hero": "hero of"}[field]
    return {label: {"old": None, "new": names}} if names else {}


def _relink_leaders(character, saved):
    leaders = KingdomLeader.objects.filter(kingdom=character.kingdom)
    roles = []
    for role, was_invested in saved:
        leader = leaders.filter(role=role, character__isnull=True).first()
        if leader is None:
            continue
        leader.character = character
        leader.invested = was_invested
        leader.save(update_fields=["character", "invested"])
        roles.append(str(leader))
    return {"leader roles": {"old": None, "new": roles}} if roles else {}


def _record_and_touch(kingdom, writer, action, changes, subject=None, restore=None):
    _record(kingdom, writer, action, changes, subject, restore)
    # Any change to the sheet, its statistics or settlements moves it up "Your kingdoms".
    kingdom.save(update_fields=["updated_at"])


def _record(kingdom, writer, action, changes, subject=None, restore=None):
    HistoryEntry.objects.create(
        kingdom=kingdom,
        action=action,
        display_name=writer.display_name,
        name_verified=writer.verified,
        subject_id=subject.pk if subject else None,
        subject_label=str(subject) if subject else "",
        changes=changes,
        restore=restore or {},
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
