import re
import secrets

from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Kingdom

REMEMBERED_KEY = "kingdom_ids"
ACCESS_CODE_BYTES = 32
ACCESS_CODE_LENGTH = ACCESS_CODE_BYTES * 2
ACCESS_CODE_RE = re.compile(rf"[0-9a-f]{{{ACCESS_CODE_LENGTH}}}")


def normalize_access_code(raw):
    return raw.strip().lower()


def is_valid_access_code(code):
    return ACCESS_CODE_RE.fullmatch(code) is not None


def new_access_code():
    return secrets.token_hex(ACCESS_CODE_BYTES)


def find_kingdom_by_code(raw):
    code = normalize_access_code(raw)
    if not is_valid_access_code(code):
        return None
    return Kingdom.objects.filter(access_code=code).first()


def remember_kingdom(request, kingdom):
    remembered = request.session.get(REMEMBERED_KEY, [])
    if kingdom.pk not in remembered:
        request.session[REMEMBERED_KEY] = [*remembered, kingdom.pk]


def remembered_kingdoms(request):
    return Kingdom.objects.filter(pk__in=request.session.get(REMEMBERED_KEY, []))


def get_remembered_kingdom_or_404(request, pk):
    """Return the kingdom only if this session has access. Other requests get a 404."""
    if pk not in request.session.get(REMEMBERED_KEY, []):
        raise Http404("No such kingdom.")
    return get_object_or_404(Kingdom, pk=pk)
