"""Characters: the kingdom's PCs and NPCs, with pictures. They fill the leader roles, command armies
and lead units as heroes. The page lists every role each character holds; nothing stops a character
holding several, since different pages can be edited at the same time.

Any protected name in the kingdom can add, change or delete them. Changes are single saves, so
characters do not use an edit lock. Pictures are only served to the kingdom's members.
"""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import pictures, services
from .access import get_remembered_kingdom_or_404
from .editing import names_redirect
from .forms import CharacterForm
from .models import Character
from .names import current_editor, current_writer
from .roles import character_roles


def _characters_url(pk):
    return reverse("kingdoms:characters", args=[pk])


def _render(request, kingdom, *, add_form=None, edit_forms=None, status=200):
    edit_forms = edit_forms or {}
    roles = character_roles(kingdom)
    characters = [
        (
            character,
            roles.get(character.pk, []),
            edit_forms.get(character.pk)
            or CharacterForm(
                initial={"name": character.name, "kind": character.kind},
                prefix=f"character{character.pk}",
            ),
        )
        for character in kingdom.characters.all()
    ]
    context = {
        "kingdom": kingdom,
        "writer": current_writer(request),
        "characters": characters,
        "add_form": add_form or CharacterForm(),
    }
    return render(request, "kingdoms/characters.html", context, status=status)


@require_GET
def characters(request, pk):
    return _render(request, get_remembered_kingdom_or_404(request, pk))


@require_POST
def character_add(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_characters_url(pk))
    form = CharacterForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render(request, kingdom, add_form=form, status=400)
    data = form.cleaned_data
    services.add_character(kingdom, writer, data["name"], data["kind"], data["picture"])
    return redirect(_characters_url(pk))


@require_POST
def character_edit(request, pk, character_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    character = get_object_or_404(Character, pk=character_pk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_characters_url(pk))
    form = CharacterForm(request.POST, request.FILES, prefix=f"character{character.pk}")
    if not form.is_valid():
        return _render(request, kingdom, edit_forms={character.pk: form}, status=400)
    data = form.cleaned_data
    services.update_character(character, writer, data["name"], data["kind"], data["picture"])
    return redirect(_characters_url(pk))


@require_POST
def character_delete(request, pk, character_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    character = get_object_or_404(Character, pk=character_pk, kingdom=kingdom)
    writer = current_editor(request)
    if writer is None:
        return names_redirect(_characters_url(pk))
    services.delete_character(character, writer)
    return redirect(_characters_url(pk))


@require_GET
def character_picture(request, pk, character_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    character = get_object_or_404(Character, pk=character_pk, kingdom=kingdom)
    if not character.picture:
        raise Http404("This character has no picture.")
    try:
        file = character.picture.open("rb")
    except FileNotFoundError as error:
        raise Http404("Picture missing.") from error
    response = FileResponse(file, content_type=pictures.CONTENT_TYPE)
    # Members only, so browsers may cache it but shared caches must not.
    response["Cache-Control"] = "private, max-age=3600"
    return response
