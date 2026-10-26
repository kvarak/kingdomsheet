"""Settlement pages. Adding and deleting settlements needs the kingdom's edit lock; editing a
settlement needs that settlement's own lock, so a kingdom and its settlements can be edited at
the same time by different players."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import locks, services
from . import settlements as grid
from .access import get_remembered_kingdom_or_404
from .forms import NewSettlementForm, PlacementForm, SettlementForm
from .models import Placement, Settlement
from .names import current_editor, current_writer
from .sheet import error_messages
from .views import lock_context, render_edit, take_lock


def _settlement_url(settlement):
    return reverse("kingdoms:settlement", args=[settlement.kingdom_id, settlement.pk])


def _settlement_edit_url(settlement):
    return reverse("kingdoms:settlement_edit", args=[settlement.kingdom_id, settlement.pk])


def _get_settlement(request, pk, spk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    return get_object_or_404(Settlement, pk=spk, kingdom=kingdom)


def _context(request, settlement):
    return {
        "kingdom": settlement.kingdom,
        "settlement": settlement,
        "writer": current_writer(request),
        "blocks": grid.build_grid(settlement),
        "borders": grid.border_labels(settlement),
        "block_image": grid.BLOCK_IMAGE,
        "sides": grid.SIDES,
        **lock_context(request, settlement),
    }


def _render_edit(request, settlement, *, form=None, placement_form=None, status=200):
    form = form or SettlementForm(initial=SettlementForm.initial_for(settlement))
    if placement_form is None:
        initial = {"rotation": 0}
        for name in ("block", "lot"):
            if request.GET.get(name, "").isdigit():
                initial[name] = int(request.GET[name])
        placement_form = PlacementForm(settlement=settlement, initial=initial)
    context = _context(request, settlement)
    selected = (placement_form["block"].value(), placement_form["lot"].value())
    for block in context["blocks"]:
        for lot in block["free"]:
            lot["selected"] = (str(block["number"]), str(lot["lot"])) == tuple(map(str, selected))
    context.update(
        {
            "form": form,
            "form_errors": error_messages(form) if form.is_bound else [],
            "border_fields": {side: form[f"border_{side}"] for side, _ in grid.SIDES},
            "placement_form": placement_form,
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
    _, refused = take_lock(request, settlement, _settlement_url(settlement))
    return refused or redirect(_settlement_edit_url(settlement))


@require_POST
def settlement_edit_stop(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    writer = current_writer(request)
    if writer is not None:
        locks.release(settlement, writer.player_id)
    return redirect(_settlement_url(settlement))


@require_http_methods(["GET", "POST"])
def settlement_edit(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    if request.method == "GET":
        writer = current_editor(request)
        if writer is None or not locks.holds_lock(settlement, writer.player_id):
            return redirect(_settlement_url(settlement))
        return _render_edit(request, settlement)

    writer, refused = take_lock(request, settlement, _settlement_url(settlement))
    if refused:
        return refused
    form = SettlementForm(request.POST)
    if not form.is_valid():
        return _render_edit(request, settlement, form=form, status=400)
    services.update_settlement(settlement, writer, form.settlement_values())
    return redirect(_settlement_edit_url(settlement))


@require_POST
def building_place(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    writer, refused = take_lock(request, settlement, _settlement_url(settlement))
    if refused:
        return refused
    form = PlacementForm(request.POST, settlement=settlement)
    if not form.is_valid():
        return _render_edit(request, settlement, placement_form=form, status=400)
    services.place_building(settlement, writer, form.cleaned_data)
    return redirect(_settlement_edit_url(settlement))


@require_POST
def building_remove(request, pk, spk, ppk):
    settlement = _get_settlement(request, pk, spk)
    writer, refused = take_lock(request, settlement, _settlement_url(settlement))
    if refused:
        return refused
    placement = get_object_or_404(Placement, pk=ppk, settlement=settlement)
    services.remove_building(settlement, writer, placement)
    return redirect(_settlement_edit_url(settlement))


@require_POST
def settlement_add(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer, refused = take_lock(request, kingdom, reverse("kingdoms:sheet", args=[pk]))
    if refused:
        return refused
    form = NewSettlementForm(request.POST)
    if not form.is_valid():
        return render_edit(request, kingdom, settlement_form=form, status=400)
    services.add_settlement(kingdom, writer, form.cleaned_data)
    return redirect(reverse("kingdoms:edit", args=[pk]))


@require_POST
def settlement_delete(request, pk, spk):
    settlement = _get_settlement(request, pk, spk)
    kingdom = settlement.kingdom
    writer, refused = take_lock(request, kingdom, reverse("kingdoms:sheet", args=[pk]))
    if refused:
        return refused
    editor = locks.active_editor(settlement)
    if editor is not None and editor.pk != writer.player_id:
        messages.error(request, f"{editor} is editing {settlement}, so it cannot be deleted now.")
    else:
        services.delete_settlement(settlement, writer)
    return redirect(reverse("kingdoms:edit", args=[pk]))
