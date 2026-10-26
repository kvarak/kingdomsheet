"""Shared view helpers for edit locks and the URLs the edit flows redirect between."""

from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from . import locks
from .names import current_editor, current_writer


def kingdom_url(pk):
    return reverse("kingdoms:sheet", args=[pk])


def kingdom_edit_url(pk):
    return reverse("kingdoms:edit", args=[pk])


def settlement_url(settlement):
    return reverse("kingdoms:settlement", args=[settlement.kingdom_id, settlement.pk])


def settlement_edit_url(settlement):
    return reverse("kingdoms:settlement_edit", args=[settlement.kingdom_id, settlement.pk])


def army_url(army):
    settlement = army.settlement
    return reverse("kingdoms:army", args=[settlement.kingdom_id, settlement.pk, army.pk])


def army_edit_url(army):
    settlement = army.settlement
    return reverse("kingdoms:army_edit", args=[settlement.kingdom_id, settlement.pk, army.pk])


def names_redirect(next_url):
    return redirect(f"{reverse('kingdoms:names')}?{urlencode({'next': next_url})}")


def lock_context(instance, writer):
    """Who holds the edit lock on a kingdom or settlement, for the toolbar templates."""
    editor = locks.active_editor(instance)
    seconds = locks.seconds_left(instance)
    return {
        "editor": editor,
        "editing_is_mine": editor is not None
        and writer is not None
        and writer.player_id == editor.pk,
        "lock_seconds": seconds,
        "lock_minutes": -(-seconds // 60),
    }


def take_lock(request, instance, view_url):
    """Return (writer, None) once this name holds the edit lock, or (None, redirect response)."""
    writer = current_editor(request)
    if writer is None:
        return None, names_redirect(view_url)
    if not locks.acquire(instance, writer.player_id):
        instance.refresh_from_db()
        messages.error(
            request,
            f"{locks.active_editor(instance)} is editing {instance}. Try again when they are done.",
        )
        return None, redirect(view_url)
    return writer, None


def locked_by_other(instances, writer):
    """The first of these objects someone other than `writer` is editing, or None."""
    for instance in instances:
        editor = locks.active_editor(instance)
        if editor is not None and editor.pk != writer.player_id:
            return instance, editor
    return None


def holds_lock(request, instance):
    writer = current_editor(request)
    return writer is not None and locks.holds_lock(instance, writer.player_id)


def release_lock(request, instance):
    writer = current_writer(request)
    if writer is not None:
        locks.release(instance, writer.player_id)
