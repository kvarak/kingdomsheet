"""Edit lock: one protected name edits a kingdom at a time, released after 15 idle minutes."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Kingdom

IDLE_TIMEOUT = timedelta(minutes=15)


def active_editor(kingdom, now=None):
    """Return the PlayerName holding a live lock, or None if the kingdom is free."""
    now = now or timezone.now()
    if kingdom.editor_id and kingdom.editor_expires_at and kingdom.editor_expires_at > now:
        return kingdom.editor
    return None


def seconds_left(kingdom, now=None):
    now = now or timezone.now()
    if active_editor(kingdom, now) is None:
        return 0
    return int((kingdom.editor_expires_at - now).total_seconds())


def holds_lock(kingdom, player_id):
    editor = active_editor(kingdom)
    return editor is not None and editor.pk == player_id


def acquire(kingdom, player_id):
    """Take or renew the lock for this name. Returns False if someone else holds it.

    An expired lock counts as free, so an editor whose timer ran out can still save as long as
    nobody else has started editing.
    """
    with transaction.atomic():
        locked = Kingdom.objects.select_for_update().get(pk=kingdom.pk)
        editor = active_editor(locked)
        if editor is not None and editor.pk != player_id:
            return False
        locked.editor_id = player_id
        locked.editor_expires_at = timezone.now() + IDLE_TIMEOUT
        locked.save(update_fields=["editor", "editor_expires_at"])
    kingdom.editor_id = locked.editor_id
    kingdom.editor_expires_at = locked.editor_expires_at
    return True


def release(kingdom, player_id):
    Kingdom.objects.filter(pk=kingdom.pk, editor_id=player_id).update(
        editor=None, editor_expires_at=None
    )
