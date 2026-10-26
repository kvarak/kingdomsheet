"""Settlement pages. Editing a settlement needs that settlement's own lock, so a kingdom and its
settlements can be edited at the same time by different players. Adding and deleting
settlements happens in kingdom edit mode, in views.py."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import growth, services
from . import settlements as grid
from .access import get_remembered_kingdom_or_404
from .editing import (
    holds_lock,
    lock_context,
    locked_by_other,
    release_lock,
    settlement_edit_url,
    settlement_url,
    take_lock,
)
from .forms import NewArmyForm, PlacementForm, SettlementForm
from .models import Army, Placement, Settlement
from .names import current_writer
from .sheet import error_messages


def _get_settlement(request, pk, spk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    return get_object_or_404(Settlement, pk=spk, kingdom=kingdom)


def _context(request, settlement, *, form=None, selected=None):
    writer = current_writer(request)
    counts = growth.lots_per_block(settlement.placements.all())
    allowed = growth.allowed_blocks(settlement.settlement_type, counts)
    return {
        "kingdom": settlement.kingdom,
        "settlement": settlement,
        "writer": writer,
        "growth": growth.status(
            settlement.settlement_type,
            counts,
            settlement.kingdom.level,
            settlement.overcrowded,
        ),
        "blocks": grid.build_grid(settlement, selected, allowed),
        "border_sides": grid.border_sides(settlement, form),
        "infrastructure": grid.infrastructure_labels(settlement),
        "armies": settlement.armies.all(),
        "block_image": grid.BLOCK_IMAGE,
        **lock_context(settlement, writer),
    }


def _selected_lot(placement_form):
    """The (block, lot) the placement form points at, if it points at one."""
    try:
        return int(placement_form["block"].value()), int(placement_form["lot"].value())
    except (TypeError, ValueError):
        return None


def _render_edit(
    request, settlement, *, form=None, placement_form=None, army_form=None, status=200
):
    form = form or SettlementForm(initial=SettlementForm.initial_for(settlement))
    if placement_form is None:
        initial = {"rotation": 0}
        for name in ("block", "lot"):
            if request.GET.get(name, "").isdigit():
                initial[name] = int(request.GET[name])
        placement_form = PlacementForm(settlement=settlement, initial=initial)
    context = _context(request, settlement, form=form, selected=_selected_lot(placement_form))
    context.update(
        {
            "form": form,
            "form_errors": error_messages(form) if form.is_bound else [],
            "placement_form": placement_form,
            "army_form": army_form or NewArmyForm(),
            "catalog": grid.catalog_by_size(),
        }
    )
    return render(request, "kingdoms/settlement_edit.html", context, status=status)


@require_GET
def settlement(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    return render(request, "kingdoms/settlement.html", _context(request, settlement))


@require_POST
def settlement_edit_start(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    _, refused = take_lock(request, settlement, settlement_url(settlement))
    return refused or redirect(settlement_edit_url(settlement))


@require_POST
def settlement_edit_stop(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    release_lock(request, settlement)
    return redirect(settlement_url(settlement))


@require_http_methods(["GET", "POST"])
def settlement_edit(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    if request.method == "GET":
        if not holds_lock(request, settlement):
            return redirect(settlement_url(settlement))
        return _render_edit(request, settlement)

    writer, refused = take_lock(request, settlement, settlement_url(settlement))
    if refused:
        return refused
    form = SettlementForm(request.POST)
    if not form.is_valid():
        return _render_edit(request, settlement, form=form, status=400)
    services.update_settlement(settlement, writer, form.settlement_values())
    return redirect(settlement_edit_url(settlement))


@require_POST
def building_place(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    writer, refused = take_lock(request, settlement, settlement_url(settlement))
    if refused:
        return refused
    form = PlacementForm(request.POST, settlement=settlement)
    if not form.is_valid():
        return _render_edit(request, settlement, placement_form=form, status=400)
    services.place_building(settlement, writer, form.cleaned_data)
    return redirect(settlement_edit_url(settlement))


@require_POST
def building_remove(request, pk, spk, ppk):
    settlement = _get_settlement(request, pk, spk)
    writer, refused = take_lock(request, settlement, settlement_url(settlement))
    if refused:
        return refused
    placement = get_object_or_404(Placement, pk=ppk, settlement=settlement)
    services.remove_building(settlement, writer, placement)
    return redirect(settlement_edit_url(settlement))


@require_POST
def army_add(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    writer, refused = take_lock(request, settlement, settlement_url(settlement))
    if refused:
        return refused
    form = NewArmyForm(request.POST)
    if not form.is_valid():
        return _render_edit(request, settlement, army_form=form, status=400)
    services.add_army(settlement, writer, form.cleaned_data["name"])
    return redirect(settlement_edit_url(settlement))


@require_POST
def army_delete(request, pk, spk, apk):
    settlement = _get_settlement(request, pk, spk)
    army = get_object_or_404(Army, pk=apk, settlement=settlement)
    writer, refused = take_lock(request, settlement, settlement_url(settlement))
    if refused:
        return refused
    busy = locked_by_other([army], writer)
    if busy:
        messages.error(request, f"{busy[1]} is editing {army}, so it cannot be deleted now.")
    else:
        services.delete_army(army, writer)
    return redirect(settlement_edit_url(settlement))
