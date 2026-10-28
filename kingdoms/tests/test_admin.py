from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Kingdom, KingdomMember
from .helpers import PASSWORD, PLAYER_NAME

ADMIN_NAME = "Varlyn Admin"
ADMIN_PASSWORD = "admin-secret-1"
ADMIN_SETTINGS = {"ADMIN_USERNAME": ADMIN_NAME, "ADMIN_PASSWORD": ADMIN_PASSWORD}
ADMIN_LINK = f'href="{reverse("kingdoms:admin_kingdoms")}"'


@override_settings(**ADMIN_SETTINGS)
class AdminTests(TestCase):
    def setUp(self):
        member = self.client_class()
        self.sign_in(member, PLAYER_NAME, PASSWORD)
        member.post(
            reverse("kingdoms:create"), {"name": "Other Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Other Lands")
        member.post(reverse("kingdoms:edit_stop", args=[self.kingdom.pk]))

    def sign_in(self, client, name, password):
        return client.post(
            reverse("kingdoms:names"),
            {"display_name": name, "password": password, "next": reverse("kingdoms:home")},
        )

    def test_admin_link_hidden_from_anonymous_visitors_and_members(self):
        self.assertNotContains(self.client.get(reverse("kingdoms:home")), ADMIN_LINK)
        self.sign_in(self.client, PLAYER_NAME, PASSWORD)
        self.assertNotContains(self.client.get(reverse("kingdoms:home")), ADMIN_LINK)

    def test_admin_page_is_hidden_from_non_admins(self):
        self.assertEqual(self.client.get(reverse("kingdoms:admin_kingdoms")).status_code, 404)
        self.sign_in(self.client, PLAYER_NAME, PASSWORD)
        self.assertEqual(self.client.get(reverse("kingdoms:admin_kingdoms")).status_code, 404)

    def test_admin_signs_in_and_sees_all_kingdoms(self):
        client = self.client_class()
        self.sign_in(client, ADMIN_NAME, ADMIN_PASSWORD)
        self.assertContains(client.get(reverse("kingdoms:home")), ADMIN_LINK)
        response = client.get(reverse("kingdoms:admin_kingdoms"))
        self.assertContains(response, self.kingdom.name)
        self.assertContains(response, reverse("kingdoms:sheet", args=[self.kingdom.pk]))

    def test_admin_can_open_and_edit_a_kingdom_without_membership(self):
        client = self.client_class()
        self.sign_in(client, ADMIN_NAME, ADMIN_PASSWORD)
        url = reverse("kingdoms:sheet", args=[self.kingdom.pk])
        self.assertEqual(client.get(url).status_code, 200)
        client.post(reverse("kingdoms:edit_start", args=[self.kingdom.pk]))
        edit_url = reverse("kingdoms:edit", args=[self.kingdom.pk])
        self.assertEqual(client.get(edit_url).status_code, 200)

    def test_non_admin_still_cannot_open_other_kingdoms(self):
        self.sign_in(self.client, PLAYER_NAME, PASSWORD)
        url = reverse("kingdoms:sheet", args=[self.kingdom.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_admin_page_lists_users_with_their_kingdoms(self):
        client = self.client_class()
        self.sign_in(client, ADMIN_NAME, ADMIN_PASSWORD)
        response = client.get(reverse("kingdoms:admin_kingdoms"))
        self.assertContains(response, "Users and their kingdoms")
        self.assertContains(response, PLAYER_NAME)
        self.assertContains(response, reverse("kingdoms:sheet", args=[self.kingdom.pk]))

    def test_admin_page_shows_last_edit_per_user(self):
        bob = self.client_class()
        self.sign_in(bob, "Bob", PASSWORD)
        bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        client = self.client_class()
        self.sign_in(client, ADMIN_NAME, ADMIN_PASSWORD)
        response = client.get(reverse("kingdoms:admin_kingdoms"))
        self.assertContains(response, "<th>Latest update</th>")
        self.assertContains(response, reverse("kingdoms:history", args=[self.kingdom.pk]))
        self.assertContains(response, "Kingdom created")
        self.assertContains(response, "Never")
        self.assertNotContains(response, "No users yet.")

    def test_joining_by_link_records_membership_once(self):
        bob = self.client_class()
        self.sign_in(bob, "Bob", PASSWORD)
        url = reverse("kingdoms:join_link", args=[self.kingdom.access_code])
        bob.post(url)
        bob.post(url)
        self.assertEqual(
            KingdomMember.objects.filter(kingdom=self.kingdom, player__display_name="Bob").count(),
            1,
        )

    def test_anonymous_join_records_no_new_membership(self):
        before = KingdomMember.objects.filter(kingdom=self.kingdom).count()
        self.client.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.assertEqual(KingdomMember.objects.filter(kingdom=self.kingdom).count(), before)

    def test_admin_name_is_reserved_for_the_admin_password(self):
        response = self.sign_in(self.client, ADMIN_NAME, "wrong-password")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "That name is reserved.", status_code=400)
        self.assertEqual(self.client.get(reverse("kingdoms:admin_kingdoms")).status_code, 404)

    def test_admin_name_cannot_be_claimed_without_a_password(self):
        response = self.sign_in(self.client, ADMIN_NAME, "")
        self.assertContains(response, "That name is reserved.", status_code=400)

    def test_admin_password_change_in_env_updates_the_stored_hash(self):
        self.sign_in(self.client, ADMIN_NAME, ADMIN_PASSWORD)
        with override_settings(ADMIN_PASSWORD="new-admin-secret"):
            client = self.client_class()
            self.sign_in(client, ADMIN_NAME, "new-admin-secret")
            self.assertEqual(client.get(reverse("kingdoms:admin_kingdoms")).status_code, 200)

    @override_settings(ADMIN_USERNAME="", ADMIN_PASSWORD="")
    def test_admin_is_disabled_without_configuration(self):
        response = self.sign_in(self.client, "Anyone", "anything-long")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("kingdoms:admin_kingdoms")).status_code, 404)
