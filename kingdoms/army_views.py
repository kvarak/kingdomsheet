"""Army pages. Editing an army needs that army's own lock. Adding and deleting armies happens in
settlement edit mode, in settlement_views.py."""

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import rules, services
from .access import get_remembered_kingdom_or_404
from .editing import (
    army_edit_url,
    army_url,
    holds_lock,
    lock_context,
    release_lock,
    take_lock,
)
from .forms import ArmyForm
from .models import Army
from .names import current_writer
from .sheet import error_messages


def _get_army(request, pk, spk, apk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    return get_object_or_404(
        Army.objects.select_related("settlement__kingdom", "commander"),
        pk=apk,
        settlement_id=spk,
        settlement__kingdom=kingdom,
    )


def _context(request, army):
    writer = current_writer(request)
    return {
        "army": army,
        "settlement": army.settlement,
        "kingdom": army.settlement.kingdom,
        "writer": writer,
        "numbers": rules.army_numbers(
            level=army.level,
            armor_bonus=army.armor_bonus,
            scouting=army.scouting,
            maneuver=army.maneuver,
            morale=army.morale,
        ),
        **lock_context(army, writer),
    }


@require_GET
def army(request, pk, spk, apk):
    army = _get_army(request, pk, spk, apk)
    return render(request, "kingdoms/army.html", _context(request, army))


@require_POST
def army_edit_start(request, pk, spk, apk):
    army = _get_army(request, pk, spk, apk)
    _, refused = take_lock(request, army, army_url(army))
    return refused or redirect(army_edit_url(army))


@require_POST
def army_edit_stop(request, pk, spk, apk):
    army = _get_army(request, pk, spk, apk)
    release_lock(request, army)
    return redirect(army_url(army))


@require_http_methods(["GET", "POST"])
def army_edit(request, pk, spk, apk):
    army = _get_army(request, pk, spk, apk)
    if request.method == "GET":
        if not holds_lock(request, army):
            return redirect(army_url(army))
        form = ArmyForm(instance=army, kingdom=army.settlement.kingdom)
        status = 200
    else:
        writer, refused = take_lock(request, army, army_url(army))
        if refused:
            return refused
        form = ArmyForm(request.POST, kingdom=army.settlement.kingdom)
        if form.is_valid():
            services.update_army(army, writer, form.cleaned_data)
            return redirect(army_edit_url(army))
        status = 400
    context = _context(request, army)
    context["form"] = form
    context["form_errors"] = error_messages(form) if form.is_bound else []
    return render(request, "kingdoms/army_edit.html", context, status=status)
