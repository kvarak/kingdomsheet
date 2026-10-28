from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Kingdom
from .names import current_writer, is_admin_writer


@require_GET
def kingdom_list(request):
    if not is_admin_writer(current_writer(request)):
        raise Http404("No such page.")
    kingdoms = Kingdom.objects.order_by("name", "pk")
    return render(request, "kingdoms/admin_kingdoms.html", {"kingdoms": kingdoms})
