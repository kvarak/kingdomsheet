from django.test import TestCase
from django.urls import reverse

from ..models import Army, Character, HistoryEntry, Kingdom, Settlement
from .helpers import PASSWORD, PLAYER_NAME


def army_post_data(army, **overrides):
    """A full army sheet POST, sending IDs for linked rows and blanks for empty ones."""
    values = {**{field: getattr(army, field) for field in Army.ROSTER_FIELDS}, **overrides}
    return {
        name: "" if value is None else getattr(value, "pk", value) for name, value in values.items()
    }


class ArmyTests(TestCase):
    def setUp(self):
        self.client.post(
            reverse("kingdoms:names"),
            {"display_name": PLAYER_NAME, "password": PASSWORD, "next": "/"},
        )
        self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Stolen Lands")
        self.client.post(
            reverse("kingdoms:settlement_add", args=[self.kingdom.pk]),
            {"name": "Tatzlford", "settlement_type": "village"},
        )
        self.settlement = Settlement.objects.get(name="Tatzlford")
        # Creating the kingdom gave Alice its edit lock, which adding armies needs.
        self.client.post(
            reverse("kingdoms:army_add", args=[self.kingdom.pk]), {"name": "Tatzlford Militia"}
        )
        self.army = Army.objects.get(name="Tatzlford Militia")
        args = [self.kingdom.pk, self.army.pk]
        self.view_url = reverse("kingdoms:army", args=args)
        self.edit_url = reverse("kingdoms:army_edit", args=args)
        self.start_url = reverse("kingdoms:army_edit_start", args=args)
        self.delete_url = reverse("kingdoms:army_delete", args=args)

        self.bob = self.client_class()
        self.bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.bob.post(
            reverse("kingdoms:names"), {"display_name": "Bob", "password": PASSWORD, "next": "/"}
        )

    def test_armies_belong_to_the_kingdom_without_a_garrison(self):
        self.assertEqual((self.army.kingdom, self.army.garrison), (self.kingdom, None))

    def test_adding_an_army_needs_the_kingdom_lock(self):
        response = self.bob.post(
            reverse("kingdoms:army_add", args=[self.kingdom.pk]), {"name": "Bob's Band"}
        )
        self.assertContains(self.bob.get(response.url), f"{PLAYER_NAME} is editing Stolen Lands")
        self.assertFalse(Army.objects.filter(name="Bob's Band").exists())
        self.assertTrue(self.kingdom.history.filter(action=HistoryEntry.Action.ARMY_ADDED).exists())

    def test_settlement_page_lists_its_garrisoned_armies(self):
        Army.objects.filter(pk=self.army.pk).update(garrison=self.settlement)
        response = self.client.get(
            reverse("kingdoms:settlement", args=[self.kingdom.pk, self.settlement.pk])
        )
        self.assertContains(response, self.view_url)
        self.assertContains(response, "Tatzlford Militia")

    def test_kingdom_page_has_its_own_armies_box(self):
        self.army.units.create(name="Pikes")
        Army.objects.filter(pk=self.army.pk).update(garrison=self.settlement)
        for name in ("kingdoms:sheet", "kingdoms:edit"):
            page = self.client.get(reverse(name, args=[self.kingdom.pk])).content.decode()
            armies_box = page.split("<legend>Armies</legend>")[1].split("</fieldset>")[0]
            self.assertIn(f'<a href="{self.view_url}">Tatzlford Militia</a>', armies_box)
            self.assertIn("<td>1</td>", armies_box)
            self.assertIn(">Tatzlford</a>", armies_box)
            # The settlement cards no longer list armies.
            settlements_box = page.split("<legend>Settlements</legend>")[1].split("</fieldset>")[0]
            self.assertNotIn("Tatzlford Militia", settlements_box)

    def test_army_page_is_read_only_until_editing(self):
        response = self.client.get(self.view_url)
        self.assertContains(response, 'aria-label="Edit army"')
        self.assertNotContains(response, 'name="location"')
        self.assertRedirects(self.client.get(self.edit_url), self.view_url)

    def test_army_lock_is_separate_from_the_kingdom_lock(self):
        # Alice holds the kingdom lock, yet Bob may edit the army.
        self.assertRedirects(self.bob.post(self.start_url), self.edit_url)
        response = self.client.post(self.start_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford Militia")

    def test_saving_the_roster_details(self):
        self.client.post(self.start_url)
        response = self.client.post(
            self.edit_url,
            army_post_data(
                self.army, garrison=self.settlement, location="Narlmarches", notes="Marching north"
            ),
        )
        self.assertRedirects(response, self.edit_url)
        self.army.refresh_from_db()
        self.assertEqual((self.army.location, self.army.notes), ("Narlmarches", "Marching north"))
        self.assertEqual(self.army.garrison, self.settlement)
        page = self.client.get(self.view_url)
        self.assertContains(page, "Narlmarches")
        entry = self.kingdom.history.get(action=HistoryEntry.Action.ARMY_EDITED)
        self.assertEqual(entry.subject_label, "Tatzlford Militia")
        self.assertEqual(entry.changes["location"], {"old": "", "new": "Narlmarches"})
        self.assertEqual(entry.changes["garrison"], {"old": None, "new": "Tatzlford"})

    def test_commander_is_one_of_the_kingdoms_characters(self):
        self.client.post(self.start_url)
        amiri = Character.objects.create(kingdom=self.kingdom, name="Amiri", kind="pc")
        self.client.post(self.edit_url, army_post_data(self.army, commander=amiri))
        self.army.refresh_from_db()
        self.assertEqual(self.army.commander, amiri)
        self.assertContains(self.client.get(self.view_url), "Amiri")

        other = Kingdom.objects.create(name="Elsewhere", access_code="e" * 64)
        stranger = Character.objects.create(kingdom=other, name="Spy", kind="npc")
        response = self.client.post(self.edit_url, army_post_data(self.army, commander=stranger))
        self.assertContains(response, "Commander:", status_code=400)
        far_town = Settlement.objects.create(kingdom=other, name="Far Town")
        response = self.client.post(self.edit_url, army_post_data(self.army, garrison=far_town))
        self.assertContains(response, "Garrison:", status_code=400)

    def test_save_button_sits_in_the_toolbar(self):
        self.client.post(self.start_url)
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'form="army-form">Save army</button>', count=1)
        self.assertContains(response, '<form id="army-form"')

    def test_editing_without_the_lock_changes_nothing(self):
        self.client.post(self.start_url)
        self.bob.post(self.edit_url, army_post_data(self.army, location="Bob's camp"))
        self.army.refresh_from_db()
        self.assertEqual(self.army.location, "")

    def test_army_being_edited_by_someone_else_cannot_be_deleted(self):
        self.bob.post(self.start_url)
        response = self.client.post(self.delete_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford Militia")
        self.assertTrue(Army.objects.filter(pk=self.army.pk).exists())

        self.bob.post(reverse("kingdoms:army_edit_stop", args=[self.kingdom.pk, self.army.pk]))
        self.client.post(self.delete_url)
        self.assertFalse(Army.objects.filter(pk=self.army.pk).exists())

    def test_deleting_the_garrison_keeps_the_army(self):
        Army.objects.filter(pk=self.army.pk).update(garrison=self.settlement)
        self.army.units.create(name="Pikes")
        self.client.post(
            reverse("kingdoms:settlement_delete", args=[self.kingdom.pk, self.settlement.pk])
        )
        self.assertFalse(Settlement.objects.filter(pk=self.settlement.pk).exists())
        self.army.refresh_from_db()
        self.assertIsNone(self.army.garrison)
        self.assertEqual(self.army.units.count(), 1)
        entry = self.kingdom.history.get(action=HistoryEntry.Action.SETTLEMENT_DELETED)
        self.assertEqual(entry.changes["garrisoned armies"]["old"], ["Tatzlford Militia"])

    def test_nonmembers_cannot_see_or_change_armies(self):
        outsider = self.client_class()
        outsider.post(
            reverse("kingdoms:names"), {"display_name": "Eve", "password": PASSWORD, "next": "/"}
        )
        for method, url in (
            ("get", self.view_url),
            ("post", self.start_url),
            ("post", self.edit_url),
            ("post", self.delete_url),
        ):
            self.assertEqual(getattr(outsider, method)(url).status_code, 404, url)
