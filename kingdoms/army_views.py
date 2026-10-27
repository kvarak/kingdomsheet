"""Army roster pages. Editing an army or its units needs that army's own lock. Adding and deleting
armies happens in kingdom edit mode, in views.py.

Armies only record units for battles played by hand on Roll20; nothing about combat is calculated.
"""

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import services
from .access import get_remembered_kingdom_or_404
from .editing import (
    army_edit_url,
    army_url,
    holds_lock,
    lock_context,
    release_lock,
    take_lock,
)
from .forms import ArmyForm, NewUnitForm, UnitForm
from .models import Army, Unit
from .names import current_writer
from .roster import unit_summary
from .sheet import error_messages


def _get_army(request, pk, apk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    return get_object_or_404(
        Army.objects.select_related("kingdom", "garrison", "commander"), pk=apk, kingdom=kingdom
    )


def _get_unit(army, upk):
    return get_object_or_404(Unit, pk=upk, army=army)


def _unit_edit_url(unit):
    army = unit.army
    return reverse("kingdoms:unit_edit", args=[army.kingdom_id, army.pk, unit.pk])


def _context(request, army):
    writer = current_writer(request)
    return {
        "army": army,
        "kingdom": army.kingdom,
        "writer": writer,
        "units": [(unit, unit_summary(unit)) for unit in army.units.all()],
        **lock_context(army, writer),
    }


def _render_edit(request, army, *, form=None, unit_form=None, status=200):
    context = _context(request, army)
    form = form or ArmyForm(instance=army, kingdom=army.kingdom)
    context.update(
        {
            "form": form,
            "form_errors": error_messages(form) if form.is_bound else [],
            "unit_form": unit_form or NewUnitForm(),
        }
    )
    return render(request, "kingdoms/army_edit.html", context, status=status)


@require_GET
def army(request, pk, apk):
    army = _get_army(request, pk, apk)
    return render(request, "kingdoms/army.html", _context(request, army))


@require_POST
def army_edit_start(request, pk, apk):
    army = _get_army(request, pk, apk)
    _, refused = take_lock(request, army, army_url(army))
    return refused or redirect(army_edit_url(army))


@require_POST
def army_edit_stop(request, pk, apk):
    army = _get_army(request, pk, apk)
    release_lock(request, army)
    return redirect(army_url(army))


@require_http_methods(["GET", "POST"])
def army_edit(request, pk, apk):
    army = _get_army(request, pk, apk)
    if request.method == "GET":
        if not holds_lock(request, army):
            return redirect(army_url(army))
        return _render_edit(request, army)

    writer, refused = take_lock(request, army, army_url(army))
    if refused:
        return refused
    form = ArmyForm(request.POST, kingdom=army.kingdom)
    if not form.is_valid():
        return _render_edit(request, army, form=form, status=400)
    services.update_army(army, writer, form.cleaned_data)
    return redirect(army_edit_url(army))


@require_POST
def unit_add(request, pk, apk):
    army = _get_army(request, pk, apk)
    writer, refused = take_lock(request, army, army_url(army))
    if refused:
        return refused
    form = NewUnitForm(request.POST)
    if not form.is_valid():
        return _render_edit(request, army, unit_form=form, status=400)
    unit = services.add_unit(army, writer, form.cleaned_data["name"])
    return redirect(_unit_edit_url(unit))


@require_http_methods(["GET", "POST"])
def unit_edit(request, pk, apk, upk):
    army = _get_army(request, pk, apk)
    unit = _get_unit(army, upk)
    if request.method == "GET":
        if not holds_lock(request, army):
            return redirect(army_url(army))
        form = UnitForm(instance=unit)
        status = 200
    else:
        writer, refused = take_lock(request, army, army_url(army))
        if refused:
            return refused
        form = UnitForm(request.POST)
        if form.is_valid():
            services.update_unit(unit, writer, form.cleaned_data)
            return redirect(army_edit_url(army))
        status = 400
    context = _context(request, army)
    context.update(
        {
            "unit": unit,
            "form": form,
            "form_errors": error_messages(form) if form.is_bound else [],
        }
    )
    return render(request, "kingdoms/unit_edit.html", context, status=status)


@require_POST
def unit_delete(request, pk, apk, upk):
    army = _get_army(request, pk, apk)
    unit = _get_unit(army, upk)
    writer, refused = take_lock(request, army, army_url(army))
    if refused:
        return refused
    services.delete_unit(unit, writer)
    return redirect(army_edit_url(army))
