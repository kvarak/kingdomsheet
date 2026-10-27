"""Which roles each character holds: leader roles, army commands and unit heroes.

Nothing stops a character holding several, because different pages can be edited at the same time,
so the Characters page lists them and the kingdom sheet warns about overlaps.
"""

from django.urls import reverse

from . import rules
from .models import Army, Character, KingdomLeader, Unit


def character_roles(kingdom):
    """Every role in the kingdom by character id, as (label, url) pairs."""
    roles = {}
    sheet_url = reverse("kingdoms:sheet", args=[kingdom.pk])
    leaders = KingdomLeader.objects.filter(kingdom=kingdom, character__isnull=False)
    order = [key for key, _, _ in rules.LEADERSHIP_ROLES]
    for leader in sorted(leaders, key=lambda leader: order.index(leader.role)):
        roles.setdefault(leader.character_id, []).append((str(leader), sheet_url))
    for army in Army.objects.filter(kingdom=kingdom, commander__isnull=False):
        url = reverse("kingdoms:army", args=[kingdom.pk, army.pk])
        roles.setdefault(army.commander_id, []).append((f"Commander of {army}", url))
    heroes = Unit.objects.filter(
        army__kingdom=kingdom, army__deleted_at__isnull=True, hero__isnull=False
    ).select_related("army")
    for unit in heroes:
        url = reverse("kingdoms:army", args=[kingdom.pk, unit.army_id])
        roles.setdefault(unit.hero_id, []).append((f"Hero of {unit} ({unit.army})", url))
    return roles


def multiple_roles(kingdom):
    """Characters holding more than one role, as (character, [role labels]) pairs."""
    roles = {pk: labels for pk, labels in character_roles(kingdom).items() if len(labels) > 1}
    characters = Character.objects.filter(pk__in=roles)
    return [(character, [label for label, _ in roles[character.pk]]) for character in characters]
