"""NPCs: named characters with pictures that can fill a kingdom's leader roles.

Any protected name in the kingdom can add, change or delete them. Changes are single saves, so
NPCs do not use an edit lock. Pictures are only served to the kingdom's members.
"""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import pictures, services
from .access import get_remembered_kingdom_or_404
from .editing import names_redirect
from .forms import NpcForm
from .models import Npc
from .names import current_editor, current_writer


def _npcs_url(pk):
    return reverse("kingdoms:npcs", args=[pk])


def _render(request, kingdom, *, add_form=None, edit_forms=None, status=200):
    edit_forms = edit_forms or {}
    npcs = [
        (npc, edit_forms.get(npc.pk) or NpcForm(initial={"name": npc.name}, prefix=f"npc{npc.pk}"))
        for npc in kingdom.npcs.all()
    ]
    context = {
        "kingdom": kingdom,
        "writer": current_writer(request),
        "npcs": npcs,
        "add_form": add_form or NpcForm(),
    }
    return render(request, "kingdoms/npcs.html", context, status=status)


@require_GET
def npcs(request, pk):
    return _render(request, get_remembered_kingdom_or_404(request, pk))


@require_POST
def npc_add(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_npcs_url(pk))
    form = NpcForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render(request, kingdom, add_form=form, status=400)
    services.add_npc(kingdom, writer, form.cleaned_data["name"], form.cleaned_data["picture"])
    return redirect(_npcs_url(pk))


@require_POST
def npc_edit(request, pk, npc_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    npc = get_object_or_404(Npc, pk=npc_pk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_npcs_url(pk))
    form = NpcForm(request.POST, request.FILES, prefix=f"npc{npc.pk}")
    if not form.is_valid():
        return _render(request, kingdom, edit_forms={npc.pk: form}, status=400)
    services.update_npc(npc, writer, form.cleaned_data["name"], form.cleaned_data["picture"])
    return redirect(_npcs_url(pk))


@require_POST
def npc_delete(request, pk, npc_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    npc = get_object_or_404(Npc, pk=npc_pk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_npcs_url(pk))
    services.delete_npc(npc, writer)
    return redirect(_npcs_url(pk))


@require_GET
def npc_picture(request, pk, npc_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    npc = get_object_or_404(Npc, pk=npc_pk, kingdom=kingdom)
    if not npc.picture:
        raise Http404("This NPC has no picture.")
    try:
        file = npc.picture.open("rb")
    except FileNotFoundError as error:
        raise Http404("Picture missing.") from error
    response = FileResponse(file, content_type=pictures.CONTENT_TYPE)
    # Members only, so browsers may cache it but shared caches must not.
    response["Cache-Control"] = "private, max-age=3600"
    return response
