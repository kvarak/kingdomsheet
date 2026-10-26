from django.test import TestCase
from django.urls import reverse

from ..models import HistoryEntry, PlayerName
from .helpers import PASSWORD, PLAYER_NAME


class NameSelectionTests(TestCase):
    def post_name(self, client, name, password="", action=None):
        data = {"display_name": name, "password": password, "next": reverse("kingdoms:home")}
        if action:
            data["action"] = action
        return client.post(reverse("kingdoms:names"), data)

    def test_open_name_is_unverified(self):
        client = self.client_class()
        self.post_name(client, PLAYER_NAME)
        response = client.post(
            reverse("kingdoms:create"), {"name": "Open", "description": "", "notes": ""}
        )
        self.assertEqual(response.status_code, 302)
        kingdom_id = client.session["kingdom_ids"][0]
        entry = HistoryEntry.objects.get(kingdom_id=kingdom_id)
        self.assertEqual(entry.display_name, PLAYER_NAME)
        self.assertFalse(entry.name_verified)

    def test_protected_name_requires_correct_password(self):
        owner = self.client_class()
        self.post_name(owner, PLAYER_NAME, PASSWORD)
        self.assertTrue(PlayerName.objects.get(display_name=PLAYER_NAME).is_protected)

        impostor = self.client_class()
        response = self.post_name(impostor, PLAYER_NAME, "wrongpassword")
        self.assertContains(response, "That name is protected", status_code=400)
        self.assertNotIn("player_name_id", impostor.session)

        self.post_name(impostor, PLAYER_NAME, PASSWORD)
        self.assertEqual(impostor.session["player_name_id"], owner.session["player_name_id"])

    def test_name_match_ignores_case_and_extra_spaces(self):
        first = self.client_class()
        self.post_name(first, "Alice   Smith", PASSWORD)
        second = self.client_class()
        response = self.post_name(second, "  alice smith  ", "")
        self.assertContains(response, "That name is protected", status_code=400)
        self.assertEqual(PlayerName.objects.count(), 1)

    def test_password_on_open_name_is_rejected(self):
        self.post_name(self.client, PLAYER_NAME)
        other = self.client_class()
        response = self.post_name(other, PLAYER_NAME, PASSWORD)
        self.assertContains(response, "This name is not protected", status_code=400)

    def test_protecting_open_name_makes_it_verified(self):
        client = self.client_class()
        self.post_name(client, PLAYER_NAME)
        response = client.post(
            reverse("kingdoms:names"),
            {
                "action": "protect",
                "password": PASSWORD,
                "display_name": PLAYER_NAME,
                "next": reverse("kingdoms:home"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlayerName.objects.get(display_name=PLAYER_NAME).is_protected)

    def test_writer_is_cleared_when_another_session_protects_name(self):
        writer = self.client_class()
        self.post_name(writer, PLAYER_NAME)
        writer.post(reverse("kingdoms:create"), {"name": "Before", "description": "", "notes": ""})

        protector = self.client_class()
        self.post_name(protector, PLAYER_NAME)
        protector.post(
            reverse("kingdoms:names"),
            {"action": "protect", "password": PASSWORD, "display_name": PLAYER_NAME},
        )

        response = writer.post(
            reverse("kingdoms:create"), {"name": "After", "description": "", "notes": ""}
        )
        self.assertRedirects(
            response,
            f"{reverse('kingdoms:names')}?next=%2F",
            fetch_redirect_response=False,
        )
        self.assertFalse(writer.session.get("player_name_id"))

    def test_repeated_wrong_passwords_are_throttled(self):
        owner = self.client_class()
        self.post_name(owner, PLAYER_NAME, PASSWORD)
        attacker = self.client_class()
        statuses = [
            self.post_name(attacker, PLAYER_NAME, "wrongpassword").status_code for _ in range(10)
        ]
        self.assertEqual(statuses[-1], 429)
