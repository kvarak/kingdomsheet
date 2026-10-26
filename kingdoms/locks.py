"""Edit locks: one protected name edits a kingdom or settlement at a time.

A lock is released by the editor or after 15 minutes without a save. Works on any model with
`editor` and `editor_expires_at` fields.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

IDLE_TIMEOUT = timedelta(minutes=15)


def active_editor(instance, now=None):
    """Return the PlayerName holding a live lock, or None if it is free."""
    now = now or timezone.now()
    if instance.editor_id and instance.editor_expires_at and instance.editor_expires_at > now:
        return instance.editor
    return None


def seconds_left(instance, now=None):
    now = now or timezone.now()
    if active_editor(instance, now) is None:
        return 0
    return int((instance.editor_expires_at - now).total_seconds())


def holds_lock(instance, player_id):
    editor = active_editor(instance)
    return editor is not None and editor.pk == player_id


def acquire(instance, player_id):
    """Take or renew the lock for this name. Returns False if someone else holds it.

    An expired lock counts as free, so an editor whose timer ran out can still save as long as
    nobody else has started editing.
    """
    with transaction.atomic():
        locked = type(instance).objects.select_for_update().get(pk=instance.pk)
        editor = active_editor(locked)
        if editor is not None and editor.pk != player_id:
            return False
        locked.editor_id = player_id
        locked.editor_expires_at = timezone.now() + IDLE_TIMEOUT
        locked.save(update_fields=["editor", "editor_expires_at"])
    instance.editor_id = locked.editor_id
    instance.editor_expires_at = locked.editor_expires_at
    return True


def release(instance, player_id):
    type(instance).objects.filter(pk=instance.pk, editor_id=player_id).update(
        editor=None, editor_expires_at=None
    )
