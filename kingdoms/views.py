from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from . import services
from .access import (
    find_kingdom_by_code,
    get_remembered_kingdom_or_404,
    remember_kingdom,
    remembered_kingdoms,
)
from .forms import JoinForm, KingdomForm, ProtectForm, SelectNameForm, StatisticForm
from .models import Statistic
from .names import (
    NameSelectionError,
    current_editor,
    current_writer,
    forget_name,
    normalize_name,
    protect_current_name,
    select_name,
)
from .services import DETAIL_FIELDS, STATISTIC_FIELDS, field_values


def _sheet_url(pk):
    return reverse("kingdoms:sheet", args=[pk])


def _names_redirect(next_url):
    return redirect(f"{reverse('kingdoms:names')}?{urlencode({'next': next_url})}")


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return reverse("kingdoms:home")


def _render_home(request, create_form, join_form, status=200):
    context = {
        "kingdoms": remembered_kingdoms(request),
        "writer": current_writer(request),
        "create_form": create_form,
        "join_form": join_form,
    }
    return render(request, "kingdoms/home.html", context, status=status)


def _render_sheet(
    request, kingdom, *, details_form=None, stat_form=None, row_forms=None, status=200
):
    """Render the sheet. `row_forms` maps statistic IDs to bound forms that failed validation."""
    row_forms = row_forms or {}
    rows = [
        (
            statistic,
            row_forms.get(statistic.pk)
            or StatisticForm(initial=field_values(statistic, STATISTIC_FIELDS)),
        )
        for statistic in kingdom.statistics.all()
    ]
    context = {
        "kingdom": kingdom,
        "share_url": request.build_absolute_uri(
            reverse("kingdoms:join_link", args=[kingdom.access_code])
        ),
        "writer": current_writer(request),
        "details_form": details_form or KingdomForm(initial=field_values(kingdom, DETAIL_FIELDS)),
        "stat_form": stat_form or StatisticForm(initial={"value": 0, "display_order": 0}),
        "rows": rows,
    }
    return render(request, "kingdoms/sheet.html", context, status=status)


def home(request):
    return _render_home(request, KingdomForm(), JoinForm())


@require_POST
def create_kingdom(request):
    writer = current_editor(request)
    if writer is None:
        return _names_redirect(reverse("kingdoms:home"))
    form = KingdomForm(request.POST)
    if not form.is_valid():
        return _render_home(request, create_form=form, join_form=JoinForm(), status=400)
    kingdom = services.create_kingdom(writer, **form.cleaned_data)
    remember_kingdom(request, kingdom)
    return redirect(_sheet_url(kingdom.pk))


@require_http_methods(["GET", "POST"])
def join(request):
    form = JoinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        kingdom = find_kingdom_by_code(form.cleaned_data["code"])
        if kingdom is not None:
            remember_kingdom(request, kingdom)
            return redirect(_sheet_url(kingdom.pk))
        form.add_error("code", "No kingdom has that sharing ID. Check it and try again.")
    status = 400 if form.errors else 200
    return render(request, "kingdoms/join.html", {"form": form}, status=status)


@require_http_methods(["GET", "POST"])
def join_by_link(request, code):
    kingdom = find_kingdom_by_code(code)
    if kingdom is None:
        return render(request, "kingdoms/join_missing.html", status=404)
    if request.method == "POST":
        remember_kingdom(request, kingdom)
        return redirect(_sheet_url(kingdom.pk))
    return render(request, "kingdoms/join_confirm.html", {"kingdom": kingdom})


@require_http_methods(["GET", "POST"])
def sheet(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    if request.method == "GET":
        return _render_sheet(request, kingdom)

    writer = current_editor(request)
    if writer is None:
        return _names_redirect(_sheet_url(pk))
    form = KingdomForm(request.POST)
    if not form.is_valid():
        return _render_sheet(request, kingdom, details_form=form, status=400)
    services.update_kingdom(kingdom, writer, form.cleaned_data)
    return redirect(_sheet_url(pk))


@require_POST
def statistic_add(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return _names_redirect(_sheet_url(pk))
    form = StatisticForm(request.POST)
    if not form.is_valid():
        return _render_sheet(request, kingdom, stat_form=form, status=400)
    services.add_statistic(kingdom, writer, form.cleaned_data)
    return redirect(_sheet_url(pk))


@require_POST
def statistic_edit(request, pk, stat_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return _names_redirect(_sheet_url(pk))
    statistic = get_object_or_404(Statistic, pk=stat_pk, kingdom=kingdom)
    form = StatisticForm(request.POST)
    if not form.is_valid():
        return _render_sheet(request, kingdom, row_forms={statistic.pk: form}, status=400)
    services.update_statistic(kingdom, writer, statistic, form.cleaned_data)
    return redirect(_sheet_url(pk))


@require_POST
def statistic_delete(request, pk, stat_pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    writer = current_editor(request)
    if writer is None:
        return _names_redirect(_sheet_url(pk))
    statistic = get_object_or_404(Statistic, pk=stat_pk, kingdom=kingdom)
    services.delete_statistic(kingdom, writer, statistic)
    return redirect(_sheet_url(pk))


@require_GET
def history(request, pk):
    kingdom = get_remembered_kingdom_or_404(request, pk)
    context = {"kingdom": kingdom, "entries": kingdom.history.all()}
    return render(request, "kingdoms/history.html", context)


def _name_ratelimit_key(group, request):
    return normalize_name(request.POST.get("display_name", ""))


def _submit_name_form(form, action):
    """Run `action` with the form's cleaned data. Returns True on success.

    Validation and name errors are attached to the form so the page can show them.
    """
    if not form.is_valid():
        return False
    try:
        action(form.cleaned_data)
    except NameSelectionError as error:
        form.add_error(None, str(error))
        return False
    return True


def _render_names(request, select_form, protect_form, next_url, status=200, rate_limited=False):
    context = {
        "writer": current_writer(request),
        "select_form": select_form,
        "protect_form": protect_form,
        "next_url": next_url,
        "rate_limited": rate_limited,
    }
    return render(request, "kingdoms/names.html", context, status=status)


@ratelimit(group="names", key=_name_ratelimit_key, rate="5/10m", method="POST", block=False)
@require_http_methods(["GET", "POST"])
def names(request):
    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    select_form = SelectNameForm()
    protect_form = ProtectForm()
    if request.method == "GET":
        return _render_names(request, select_form, protect_form, next_url)
    if getattr(request, "limited", False):
        return _render_names(
            request, select_form, protect_form, next_url, status=429, rate_limited=True
        )

    if request.POST.get("action") == "protect":
        protect_form = ProtectForm(request.POST)
        succeeded = _submit_name_form(
            protect_form, lambda data: protect_current_name(request, data["password"])
        )
    else:
        select_form = SelectNameForm(request.POST)
        succeeded = _submit_name_form(
            select_form, lambda data: select_name(request, data["display_name"], data["password"])
        )
    if succeeded:
        return redirect(next_url)
    return _render_names(request, select_form, protect_form, next_url, status=400)


@require_POST
def forget_selected_name(request):
    forget_name(request)
    return redirect(reverse("kingdoms:names"))
