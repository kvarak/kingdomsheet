from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Kingdom
from .helpers import PASSWORD, PLAYER_NAME, sheet_post_data


class EditLockTests(TestCase):
    def setUp(self):
        self.client.post(
            reverse("kingdoms:names"),
            {"display_name": PLAYER_NAME, "password": PASSWORD, "next": "/"},
        )
        self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Stolen Lands")
        self.view_url = reverse("kingdoms:sheet", args=[self.kingdom.pk])
        self.edit_url = reverse("kingdoms:edit", args=[self.kingdom.pk])
        self.start_url = reverse("kingdoms:edit_start", args=[self.kingdom.pk])
        self.stop_url = reverse("kingdoms:edit_stop", args=[self.kingdom.pk])

        self.bob = self.client_class()
        self.bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.bob.post(
            reverse("kingdoms:names"), {"display_name": "Bob", "password": PASSWORD, "next": "/"}
        )

    def test_sheet_is_read_only_by_default(self):
        self.client.post(self.stop_url)
        response = self.client.get(self.view_url)
        self.assertNotContains(response, 'name="level"')
        self.assertContains(response, 'aria-label="Edit sheet"')

    def test_creator_starts_in_edit_mode_with_timer(self):
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'name="level"')
        self.assertContains(response, 'id="lock-timer"')

    def test_second_player_is_locked_out_while_someone_edits(self):
        response = self.bob.post(self.start_url, follow=True)
        self.assertRedirects(response, self.view_url)
        self.assertContains(response, f"{PLAYER_NAME} is editing Stolen Lands")
        self.assertRedirects(self.bob.get(self.edit_url), self.view_url)

        self.bob.post(self.edit_url, sheet_post_data(self.kingdom, name="Bobland"))
        self.bob.post(
            reverse("kingdoms:statistic_add", args=[self.kingdom.pk]),
            {"label": "Gold", "value": 1, "display_order": 0},
        )
        self.kingdom.refresh_from_db()
        self.assertEqual(self.kingdom.name, "Stolen Lands")
        self.assertFalse(self.kingdom.statistics.exists())

    def test_done_releases_the_lock(self):
        self.client.post(self.stop_url)
        self.assertRedirects(self.bob.post(self.start_url), self.edit_url)

    def test_idle_lock_expires_after_fifteen_minutes(self):
        Kingdom.objects.filter(pk=self.kingdom.pk).update(
            editor_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertRedirects(self.bob.post(self.start_url), self.edit_url)

    def test_saving_resets_the_idle_timer(self):
        Kingdom.objects.filter(pk=self.kingdom.pk).update(
            editor_expires_at=timezone.now() + timedelta(minutes=1)
        )
        self.client.post(self.edit_url, sheet_post_data(self.kingdom, level=2))
        self.kingdom.refresh_from_db()
        self.assertGreater(self.kingdom.editor_expires_at, timezone.now() + timedelta(minutes=14))

    def test_others_see_who_is_editing(self):
        response = self.bob.get(self.view_url)
        self.assertContains(response, f"{PLAYER_NAME} is editing")
        self.assertContains(response, "disabled")
