from django.db.models import Max, Prefetch
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import HistoryEntry, Kingdom, KingdomMember, PlayerName
from .names import current_writer, is_admin_writer, normalize_name


@require_GET
def kingdom_list(request):
    if not is_admin_writer(current_writer(request)):
        raise Http404("No such page.")
    kingdoms = Kingdom.objects.order_by("name", "pk")
    memberships = KingdomMember.objects.select_related("kingdom").order_by("kingdom__name", "pk")
    players = list(
        PlayerName.objects.order_by("display_name", "pk").prefetch_related(
            Prefetch("kingdom_memberships", queryset=memberships, to_attr="memberships")
        )
    )
    last_edits = _latest_entries_by_name()
    for player in players:
        player.last_edit = last_edits.get(player.normalized_name)
    return render(
        request,
        "kingdoms/admin_kingdoms.html",
        {"kingdoms": kingdoms, "players": players},
    )


def _latest_entries_by_name():
    """Newest history entry for each normalized name. History stores names, not links.
    Newer entries have larger primary keys, so the largest pk per name is the latest."""
    newest_pks = HistoryEntry.objects.values("display_name").annotate(newest=Max("pk"))
    entries = HistoryEntry.objects.select_related("kingdom").in_bulk(
        [row["newest"] for row in newest_pks]
    )
    latest = {}
    for entry in entries.values():
        key = normalize_name(entry.display_name)
        if key not in latest or entry.pk > latest[key].pk:
            latest[key] = entry
    return latest
