from django.test import TestCase
from django.urls import reverse

from ..models import Army, Character, HistoryEntry, Kingdom, Settlement
from .helpers import PASSWORD, PLAYER_NAME


def army_post_data(army, **overrides):
    """A full army sheet POST, sending IDs for linked rows and blanks for empty ones."""
    values = {**{field: getattr(army, field) for field in Army.SHEET_FIELDS}, **overrides}
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
        settlement_args = [self.kingdom.pk, self.settlement.pk]
        self.settlement_start = reverse("kingdoms:settlement_edit_start", args=settlement_args)
        self.settlement_stop = reverse("kingdoms:settlement_edit_stop", args=settlement_args)
        self.client.post(self.settlement_start)
        self.client.post(
            reverse("kingdoms:army_add", args=settlement_args), {"name": "Tatzlford Militia"}
        )
        self.army = Army.objects.get(name="Tatzlford Militia")
        args = [*settlement_args, self.army.pk]
        self.view_url = reverse("kingdoms:army", args=args)
        self.edit_url = reverse("kingdoms:army_edit", args=args)
        self.start_url = reverse("kingdoms:army_edit_start", args=args)
        self.delete_url = reverse("kingdoms:army_delete", args=args)

        self.bob = self.client_class()
        self.bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.bob.post(
            reverse("kingdoms:names"), {"display_name": "Bob", "password": PASSWORD, "next": "/"}
        )

    def test_adding_an_army_needs_the_settlement_lock(self):
        response = self.bob.post(
            reverse("kingdoms:army_add", args=[self.kingdom.pk, self.settlement.pk]),
            {"name": "Bob's Band"},
        )
        self.assertContains(self.bob.get(response.url), f"{PLAYER_NAME} is editing Tatzlford")
        self.assertFalse(Army.objects.filter(name="Bob's Band").exists())
        self.assertTrue(self.kingdom.history.filter(action=HistoryEntry.Action.ARMY_ADDED).exists())

    def test_settlement_page_lists_its_armies(self):
        response = self.client.get(
            reverse("kingdoms:settlement", args=[self.kingdom.pk, self.settlement.pk])
        )
        self.assertContains(response, self.view_url)
        self.assertContains(response, "Tatzlford Militia")

    def test_kingdom_page_lists_armies_with_levels(self):
        Army.objects.filter(pk=self.army.pk).update(level=4)
        for name in ("kingdoms:sheet", "kingdoms:edit"):
            response = self.client.get(reverse(name, args=[self.kingdom.pk]))
            self.assertContains(response, self.view_url)
            self.assertContains(response, 'Tatzlford Militia</a> <span class="hint">level 4</span>')

    def test_army_page_is_read_only_until_editing(self):
        response = self.client.get(self.view_url)
        self.assertContains(response, 'aria-label="Edit army"')
        self.assertNotContains(response, 'name="armor_bonus"')
        self.assertRedirects(self.client.get(self.edit_url), self.view_url)

    def test_army_lock_is_separate_from_the_settlement_lock(self):
        # Alice holds the settlement lock, yet Bob may edit the army.
        self.assertRedirects(self.bob.post(self.start_url), self.edit_url)
        response = self.client.post(self.start_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford Militia")

    def test_saving_the_army_sheet(self):
        self.client.post(self.start_url)
        response = self.client.post(
            self.edit_url,
            army_post_data(
                self.army,
                level=3,
                armor_bonus=2,
                hp=4,
                current_hp=3,
                tactics="Defensive Tactics\nLive off the Land",
                healing_potions=2,
            ),
        )
        self.assertRedirects(response, self.edit_url)
        self.army.refresh_from_db()
        self.assertEqual((self.army.level, self.army.armor_bonus, self.army.current_hp), (3, 2, 3))
        page = self.client.get(self.view_url)
        self.assertContains(page, "<li>Live off the Land</li>", html=True)
        entry = self.kingdom.history.get(action=HistoryEntry.Action.ARMY_EDITED)
        self.assertEqual(entry.subject_label, "Tatzlford Militia")
        self.assertEqual(entry.changes["armor bonus"], {"old": 0, "new": 2})
        # AC = 11 + proficiency (+2 at level 3) + armor bonus 2.
        self.assertContains(page, '<strong class="calc">15</strong>')

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

    def test_save_button_sits_in_the_toolbar(self):
        self.client.post(self.start_url)
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'form="army-form">Save army</button>', count=1)
        self.assertContains(response, '<form id="army-form"')

    def test_healing_potions_are_capped(self):
        self.client.post(self.start_url)
        response = self.client.post(self.edit_url, army_post_data(self.army, healing_potions=4))
        self.assertContains(response, "Healing potions:", status_code=400)
        self.army.refresh_from_db()
        self.assertEqual(self.army.healing_potions, 0)

    def test_editing_without_the_lock_changes_nothing(self):
        self.client.post(self.start_url)
        self.bob.post(self.edit_url, army_post_data(self.army, armor_bonus=9))
        self.army.refresh_from_db()
        self.assertEqual(self.army.armor_bonus, 0)

    def test_army_being_edited_by_someone_else_cannot_be_deleted(self):
        self.bob.post(self.start_url)
        response = self.client.post(self.delete_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford Militia")
        self.assertTrue(Army.objects.filter(pk=self.army.pk).exists())

        self.bob.post(
            reverse(
                "kingdoms:army_edit_stop",
                args=[self.kingdom.pk, self.settlement.pk, self.army.pk],
            )
        )
        self.client.post(self.delete_url)
        self.assertFalse(Army.objects.filter(pk=self.army.pk).exists())

    def test_settlement_with_army_in_use_cannot_be_deleted(self):
        self.bob.post(self.start_url)
        self.client.post(self.settlement_stop)
        delete_url = reverse(
            "kingdoms:settlement_delete", args=[self.kingdom.pk, self.settlement.pk]
        )
        response = self.client.post(delete_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford Militia")
        self.assertTrue(Settlement.objects.filter(pk=self.settlement.pk).exists())

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
