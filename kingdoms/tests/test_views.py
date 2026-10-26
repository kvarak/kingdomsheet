import logging
import re

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import HistoryEntry, Kingdom, Statistic
from ..redaction import RedactAccessCodes
from .helpers import PLAYER_NAME

ZERO_CODE = "0" * 64


class KingdomViewTests(TestCase):
    def select_name(self, name=PLAYER_NAME, password=""):
        return self.client.post(
            reverse("kingdoms:names"),
            {"display_name": name, "password": password, "next": reverse("kingdoms:home")},
        )

    def create_kingdom(self, name="Stolen Lands"):
        self.select_name()
        self.client.post(reverse("kingdoms:create"), {"name": name, "description": "", "notes": ""})
        return Kingdom.objects.get(name=name)

    def test_home_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("kingdoms:home"))
        self.assertEqual(response.status_code, 200)

    def test_writes_require_a_selected_name(self):
        response = self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.assertRedirects(
            response,
            f"{reverse('kingdoms:names')}?next=%2F",
            fetch_redirect_response=False,
        )
        self.assertFalse(Kingdom.objects.exists())

    def test_creating_kingdom_creates_membership(self):
        kingdom = self.create_kingdom()
        self.assertEqual(
            self.client.get(reverse("kingdoms:sheet", args=[kingdom.pk])).status_code, 200
        )
        self.assertTrue(
            HistoryEntry.objects.filter(
                kingdom=kingdom, action=HistoryEntry.Action.KINGDOM_CREATED
            ).exists()
        )

    def test_sheet_shows_full_sharing_link(self):
        kingdom = self.create_kingdom()
        response = self.client.get(reverse("kingdoms:sheet", args=[kingdom.pk]))
        self.assertContains(response, f"http://testserver/join/{kingdom.access_code}/")

    def test_sharing_ids_are_unique_and_formatted(self):
        first = self.create_kingdom("First")
        second = self.create_kingdom("Second")
        pattern = re.compile(r"^[0-9a-f]{64}$")
        self.assertRegex(first.access_code, pattern)
        self.assertRegex(second.access_code, pattern)
        self.assertNotEqual(first.access_code, second.access_code)

    def test_nonmembers_cannot_view_or_modify_kingdom(self):
        kingdom = self.create_kingdom()
        statistic = Statistic.objects.create(
            kingdom=kingdom, label="Gold", value=5, display_order=0
        )
        outsider = self.__class__.client_class()
        outsider.post(reverse("kingdoms:names"), {"display_name": "Mallory"})

        urls_and_methods = [
            ("get", reverse("kingdoms:sheet", args=[kingdom.pk])),
            ("get", reverse("kingdoms:history", args=[kingdom.pk])),
            ("post", reverse("kingdoms:sheet", args=[kingdom.pk])),
            ("post", reverse("kingdoms:statistic_add", args=[kingdom.pk])),
            ("post", reverse("kingdoms:statistic_edit", args=[kingdom.pk, statistic.pk])),
            ("post", reverse("kingdoms:statistic_delete", args=[kingdom.pk, statistic.pk])),
        ]
        data = {
            "name": "Hacked",
            "description": "",
            "notes": "",
            "label": "X",
            "value": 1,
            "display_order": 0,
        }
        for method, url in urls_and_methods:
            response = getattr(outsider, method)(url, data)
            self.assertEqual(response.status_code, 404, url)

        kingdom.refresh_from_db()
        statistic.refresh_from_db()
        self.assertEqual(kingdom.name, "Stolen Lands")
        self.assertEqual(statistic.value, 5)
        self.assertEqual(kingdom.statistics.count(), 1)

    def test_join_link_get_does_not_add_membership(self):
        kingdom = self.create_kingdom()
        outsider = self.__class__.client_class()
        response = outsider.get(reverse("kingdoms:join_link", args=[kingdom.access_code]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            outsider.get(reverse("kingdoms:sheet", args=[kingdom.pk])).status_code, 404
        )

    def test_join_link_post_adds_membership_and_is_idempotent(self):
        kingdom = self.create_kingdom()
        outsider = self.__class__.client_class()
        url = reverse("kingdoms:join_link", args=[kingdom.access_code])
        outsider.post(url)
        outsider.post(url)
        self.assertEqual(
            outsider.get(reverse("kingdoms:sheet", args=[kingdom.pk])).status_code, 200
        )
        self.assertEqual(outsider.session["kingdom_ids"], [kingdom.pk])

    def test_join_form_normalizes_and_joins(self):
        kingdom = self.create_kingdom()
        outsider = self.__class__.client_class()
        response = outsider.post(
            reverse("kingdoms:join"), {"code": f"  {kingdom.access_code.upper()}  "}
        )
        self.assertRedirects(response, reverse("kingdoms:sheet", args=[kingdom.pk]))
        self.assertEqual(outsider.session["kingdom_ids"], [kingdom.pk])

    def test_join_form_reports_malformed_sharing_id(self):
        response = self.client.post(reverse("kingdoms:join"), {"code": "not-a-code"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "64 lowercase hexadecimal characters", status_code=400)

    def test_join_form_reports_unknown_sharing_id(self):
        response = self.client.post(reverse("kingdoms:join"), {"code": ZERO_CODE})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "No kingdom has that sharing ID", status_code=400)

    def test_join_link_with_unknown_code_returns_404_message(self):
        response = self.client.get(reverse("kingdoms:join_link", args=[ZERO_CODE]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "No kingdom found", status_code=404)

    def test_member_can_edit_details_and_history_records_changes(self):
        kingdom = self.create_kingdom()
        response = self.client.post(
            reverse("kingdoms:sheet", args=[kingdom.pk]),
            {"name": "Stolen Lands", "description": "Frontier", "notes": "Wild"},
        )
        self.assertRedirects(response, reverse("kingdoms:sheet", args=[kingdom.pk]))
        kingdom.refresh_from_db()
        self.assertEqual(kingdom.description, "Frontier")
        entry = kingdom.history.get(action=HistoryEntry.Action.KINGDOM_EDITED)
        self.assertEqual(entry.changes["description"], {"old": "", "new": "Frontier"})
        self.assertNotIn("name", entry.changes)

    def test_saving_unchanged_details_writes_no_history(self):
        kingdom = self.create_kingdom()
        before = kingdom.history.count()
        self.client.post(
            reverse("kingdoms:sheet", args=[kingdom.pk]),
            {"name": "Stolen Lands", "description": "", "notes": ""},
        )
        self.assertEqual(kingdom.history.count(), before)

    def test_invalid_details_show_form_errors(self):
        kingdom = self.create_kingdom()
        response = self.client.post(
            reverse("kingdoms:sheet", args=[kingdom.pk]),
            {"name": "", "description": "", "notes": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This field is required", status_code=400)

    def test_statistics_add_edit_delete_with_history(self):
        kingdom = self.create_kingdom()
        self.client.post(
            reverse("kingdoms:statistic_add", args=[kingdom.pk]),
            {"label": "Gold", "value": 10, "display_order": 1},
        )
        statistic = kingdom.statistics.get(label="Gold")
        self.client.post(
            reverse("kingdoms:statistic_edit", args=[kingdom.pk, statistic.pk]),
            {"label": "Gold", "value": 12, "display_order": 1},
        )
        statistic.refresh_from_db()
        self.assertEqual(statistic.value, 12)
        self.client.post(reverse("kingdoms:statistic_delete", args=[kingdom.pk, statistic.pk]))
        self.assertFalse(kingdom.statistics.exists())

        actions = list(kingdom.history.values_list("action", flat=True))
        self.assertIn(HistoryEntry.Action.STATISTIC_ADDED, actions)
        self.assertIn(HistoryEntry.Action.STATISTIC_EDITED, actions)
        self.assertIn(HistoryEntry.Action.STATISTIC_DELETED, actions)

    def test_invalid_statistic_value_shows_error(self):
        kingdom = self.create_kingdom()
        response = self.client.post(
            reverse("kingdoms:statistic_add", args=[kingdom.pk]),
            {"label": "Gold", "value": "lots", "display_order": 0},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Enter a whole number", status_code=400)
        self.assertFalse(kingdom.statistics.exists())

    def test_invalid_edit_of_existing_statistic_shows_error_on_that_row(self):
        kingdom = self.create_kingdom()
        gold = Statistic.objects.create(kingdom=kingdom, label="Gold", value=5, display_order=0)
        Statistic.objects.create(kingdom=kingdom, label="Food", value=3, display_order=1)
        response = self.client.post(
            reverse("kingdoms:statistic_edit", args=[kingdom.pk, gold.pk]),
            {"label": "Gold", "value": "lots", "display_order": 0},
        )
        self.assertContains(response, "Enter a whole number", status_code=400)
        self.assertContains(response, 'value="Food"', status_code=400)
        gold.refresh_from_db()
        self.assertEqual(gold.value, 5)

    def test_unchanged_statistic_writes_no_history(self):
        kingdom = self.create_kingdom()
        gold = Statistic.objects.create(kingdom=kingdom, label="Gold", value=5, display_order=0)
        before = kingdom.history.count()
        self.client.post(
            reverse("kingdoms:statistic_edit", args=[kingdom.pk, gold.pk]),
            {"label": "Gold", "value": 5, "display_order": 0},
        )
        self.assertEqual(kingdom.history.count(), before)

    def test_deleting_statistic_records_old_values(self):
        kingdom = self.create_kingdom()
        gold = Statistic.objects.create(kingdom=kingdom, label="Gold", value=5, display_order=2)
        self.client.post(reverse("kingdoms:statistic_delete", args=[kingdom.pk, gold.pk]))
        entry = kingdom.history.get(action=HistoryEntry.Action.STATISTIC_DELETED)
        self.assertEqual(entry.statistic_label, "Gold")
        self.assertEqual(
            entry.changes,
            {
                "label": {"old": "Gold", "new": None},
                "value": {"old": 5, "new": None},
                "display_order": {"old": 2, "new": None},
            },
        )

    def test_member_without_name_is_sent_to_names_page(self):
        kingdom = self.create_kingdom()
        member = self.client_class()
        member.post(reverse("kingdoms:join_link", args=[kingdom.access_code]))
        sheet_url = reverse("kingdoms:sheet", args=[kingdom.pk])
        response = member.post(sheet_url, {"name": "Renamed", "description": "", "notes": ""})
        self.assertRedirects(
            response,
            f"{reverse('kingdoms:names')}?next={sheet_url.replace('/', '%2F')}",
            fetch_redirect_response=False,
        )
        kingdom.refresh_from_db()
        self.assertEqual(kingdom.name, "Stolen Lands")


class RedactionTests(SimpleTestCase):
    def test_access_codes_are_redacted_from_log_messages(self):
        code = "ab" * 32
        record = logging.LogRecord(
            "gunicorn.access",
            logging.INFO,
            __file__,
            1,
            '"GET /join/%s/ HTTP/1.1" 200',
            (code,),
            None,
        )
        self.assertTrue(RedactAccessCodes().filter(record))
        message = record.getMessage()
        self.assertNotIn(code, message)
        self.assertIn("[redacted]", message)
