from dataclasses import dataclass

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from .models import PlayerName

PLAYER_KEY = "player_name_id"
VERIFIED_KEY = "verified_player_name_id"


class NameSelectionError(Exception):
    """A name could not be selected or protected. The message is safe to show the user."""


@dataclass(frozen=True)
class Writer:
    display_name: str
    verified: bool
    player_id: int


def clean_display_name(raw):
    return " ".join(raw.split())


def normalize_name(raw):
    return clean_display_name(raw).casefold()


def select_name(request, raw_name, password):
    display = clean_display_name(raw_name)
    key = normalize_name(display)
    with transaction.atomic():
        player = PlayerName.objects.select_for_update().filter(normalized_name=key).first()
        if player is None:
            player = _create_name(display, key, password)

        if player.is_protected:
            if not password or not check_password(password, player.password_hash):
                raise NameSelectionError("That name is protected. Enter its password.")
            verified = True
        else:
            if password:
                raise NameSelectionError(
                    "This name is not protected. Select it without a password, then protect it."
                )
            verified = False

    _remember(request, player, verified)


def protect_current_name(request, password):
    with transaction.atomic():
        player = (
            PlayerName.objects.select_for_update()
            .filter(pk=request.session.get(PLAYER_KEY))
            .first()
        )
        if player is None:
            raise NameSelectionError("Select a name before protecting it.")
        if player.is_protected:
            raise NameSelectionError("This name is already protected.")
        player.password_hash = make_password(password)
        player.save(update_fields=["password_hash"])

    _remember(request, player, verified=True)


def current_writer(request):
    """Return the selected name as a Writer, or None if no usable name is selected."""
    player = PlayerName.objects.filter(pk=request.session.get(PLAYER_KEY)).first()
    if player is None:
        return None
    if player.is_protected and request.session.get(VERIFIED_KEY) != player.pk:
        forget_name(request)
        return None
    return Writer(
        display_name=player.display_name, verified=player.is_protected, player_id=player.pk
    )


def current_editor(request):
    """Return the selected name only if it is password protected. Only protected names may edit."""
    writer = current_writer(request)
    return writer if writer is not None and writer.verified else None


def forget_name(request):
    request.session.pop(PLAYER_KEY, None)
    request.session.pop(VERIFIED_KEY, None)


def _create_name(display, key, password):
    try:
        with transaction.atomic():
            return PlayerName.objects.create(
                display_name=display,
                normalized_name=key,
                password_hash=make_password(password) if password else "",
            )
    except IntegrityError:
        # Another request created the same name first, so fall back to the existing row.
        return PlayerName.objects.get(normalized_name=key)


def _remember(request, player, verified):
    request.session[PLAYER_KEY] = player.pk
    if verified:
        request.session[VERIFIED_KEY] = player.pk
    else:
        request.session.pop(VERIFIED_KEY, None)
