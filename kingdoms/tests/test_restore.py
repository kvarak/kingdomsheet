from django.test import TestCase
from django.urls import reverse

from ..models import Army, Character, HistoryEntry, Kingdom, Placement, Settlement, Unit
from .helpers import PASSWORD, PLAYER_NAME

Action = HistoryEntry.Action


class RestoreTests(TestCase):
    def setUp(self):
        self.client.post(
            reverse("kingdoms:names"),
            {"display_name": PLAYER_NAME, "password": PASSWORD, "next": "/"},
        )
        self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Stolen Lands")
        self.pk = self.kingdom.pk
        self.history_url = reverse("kingdoms:history", args=[self.pk])
        self.settlement = Settlement.objects.create(kingdom=self.kingdom, name="Tatzlford")
        Placement.objects.create(settlement=self.settlement, building="1/houses", block=0, lot=0)
        self.army = Army.objects.create(
            kingdom=self.kingdom, name="Militia", garrison=self.settlement
        )
        self.unit = Unit.objects.create(army=self.army, name="Pikes", current_strength=4)

    def delete(self, name, *args):
        self.client.post(reverse(f"kingdoms:{name}", args=[self.pk, *args]))
        return self.kingdom.history.latest("id")

    def restore(self, entry, client=None):
        url = reverse("kingdoms:history_restore", args=[self.pk, entry.pk])
        return (client or self.client).post(url)

    def test_settlement_comes_back_with_buildings_and_garrison(self):
        entry = self.delete("settlement_delete", self.settlement.pk)
        self.assertEqual(entry.action, Action.SETTLEMENT_DELETED)
        self.assertFalse(Settlement.objects.exists())
        self.army.refresh_from_db()
        self.assertIsNone(self.army.garrison)
        self.assertContains(self.client.get(self.history_url), ">Restore</button>", count=1)

        self.assertRedirects(self.restore(entry), self.history_url)
        settlement = Settlement.objects.get()
        self.assertEqual(settlement.placements.count(), 1)
        self.army.refresh_from_db()
        self.assertEqual(self.army.garrison, settlement)
        restored = self.kingdom.history.get(action=Action.SETTLEMENT_RESTORED)
        self.assertEqual(restored.changes["garrisoned armies"], {"old": None, "new": ["Militia"]})
        self.assertNotContains(self.client.get(self.history_url), ">Restore</button>")

    def test_a_garrison_filled_since_is_left_alone(self):
        entry = self.delete("settlement_delete", self.settlement.pk)
        elsewhere = Settlement.objects.create(kingdom=self.kingdom, name="Oleg's")
        Army.objects.filter(pk=self.army.pk).update(garrison=elsewhere)
        self.restore(entry)
        self.army.refresh_from_db()
        self.assertEqual(self.army.garrison, elsewhere)

    def test_army_comes_back_with_its_units(self):
        entry = self.delete("army_delete", self.army.pk)
        self.assertNotContains(
            self.client.get(reverse("kingdoms:sheet", args=[self.pk])), "Militia"
        )
        self.restore(entry)
        self.assertEqual(Army.objects.get().units.get(), self.unit)
        sheet = self.client.get(reverse("kingdoms:sheet", args=[self.pk]))
        self.assertEqual(sheet.context["armies"][0].unit_count, 1)

    def test_unit_comes_back(self):
        self.client.post(reverse("kingdoms:army_edit_start", args=[self.pk, self.army.pk]))
        entry = self.delete("unit_delete", self.army.pk, self.unit.pk)
        self.assertFalse(Unit.objects.exists())
        self.restore(entry)
        self.assertEqual(Unit.objects.get().current_strength, 4)

    def test_character_gets_back_only_roles_nobody_has_taken(self):
        kesten = Character.objects.create(kingdom=self.kingdom, name="Kesten", kind="npc")
        amiri = Character.objects.create(kingdom=self.kingdom, name="Amiri", kind="pc")
        leaders = self.kingdom.leaders
        leaders.filter(role="general").update(character=kesten, invested=True)
        leaders.filter(role="warden").update(character=kesten)
        Army.objects.filter(pk=self.army.pk).update(commander=kesten)
        Unit.objects.filter(pk=self.unit.pk).update(hero=kesten)

        entry = self.delete("character_delete", kesten.pk)
        self.assertEqual(leaders.filter(character__isnull=False).count(), 0)
        leaders.filter(role="warden").update(character=amiri)

        self.restore(entry)
        self.assertEqual(Character.objects.count(), 2)
        general = leaders.get(role="general")
        self.assertEqual((general.character, general.invested), (kesten, True))
        self.assertEqual(leaders.get(role="warden").character, amiri)
        self.army.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual((self.army.commander, self.unit.hero), (kesten, kesten))
        restored = self.kingdom.history.get(action=Action.CHARACTER_RESTORED)
        self.assertEqual(restored.changes["leader roles"], {"old": None, "new": ["General"]})

    def test_only_the_latest_deletion_can_be_restored_once(self):
        first = self.delete("army_delete", self.army.pk)
        self.restore(first)
        second = self.delete("army_delete", self.army.pk)
        page = self.client.get(self.history_url)
        self.assertContains(page, ">Restore</button>", count=1)
        self.assertContains(page, f"/history/{second.pk}/restore/")

        response = self.restore(first, client=self.client)
        self.assertFalse(Army.objects.exists())
        self.assertContains(self.client.get(response.url), "can no longer be restored")
        self.restore(second)
        self.restore(second)
        self.assertEqual(self.kingdom.history.filter(action=Action.ARMY_RESTORED).count(), 2)

    def test_restoring_needs_a_protected_name_and_membership(self):
        entry = self.delete("army_delete", self.army.pk)
        stranger = self.client_class()
        self.assertEqual(self.restore(entry, client=stranger).status_code, 404)

        guest = self.client_class()
        guest.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        guest.post(reverse("kingdoms:names"), {"display_name": "Guest", "next": "/"})
        self.assertNotContains(guest.get(self.history_url), ">Restore</button>")
        self.restore(entry, client=guest)
        self.assertFalse(Army.objects.exists())
