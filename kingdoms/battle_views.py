"""The kingdom's battle log. Recording a battle never changes any unit: players update unit strength
and status by hand. Any protected name in the kingdom can add, correct or delete entries; they are
single saves, so the log does not use an edit lock."""

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import services
from .access import get_remembered_kingdom_or_404
from .editing import names_redirect
from .forms import BattleForm
from .models import Battle
from .names import current_editor, current_writer


def _battles_url(pk):
    return reverse("kingdoms:battles", args=[pk])


def _render(request, kingdom, *, add_form=None, edit_forms=None, status=200):
    edit_forms = edit_forms or {}
    battles = [
        (
            battle,
            edit_forms.get(battle.pk) or BattleForm(instance=battle, prefix=f"battle{battle.pk}"),
        )
        for battle in kingdom.battles.all()
    ]
    context = {
        "kingdom": kingdom,
        "writer": current_writer(request),
        "battles": battles,
        "add_form": add_form or BattleForm(),
    }
    return render(request, "kingdoms/battles.html", context, status=status)


@require_GET
def battles(request, pk):
    return _render(request, get_remembered_kingdom_or_404(request, pk))


@require_POST
def battle_add(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_battles_url(pk))
    form = BattleForm(request.POST)
    if not form.is_valid():
        return _render(request, kingdom, add_form=form, status=400)
    services.record_battle(kingdom, writer, form.cleaned_data)
    return redirect(_battles_url(pk))


@require_POST
def battle_edit(request, pk, bpk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    battle = get_object_or_404(Battle, pk=bpk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_battles_url(pk))
    form = BattleForm(request.POST, prefix=f"battle{battle.pk}")
    if not form.is_valid():
        return _render(request, kingdom, edit_forms={battle.pk: form}, status=400)
    services.update_battle(battle, writer, form.cleaned_data)
    return redirect(_battles_url(pk))


@require_POST
def battle_delete(request, pk, bpk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    battle = get_object_or_404(Battle, pk=bpk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_battles_url(pk))
    services.delete_battle(battle, writer)
    return redirect(_battles_url(pk))
