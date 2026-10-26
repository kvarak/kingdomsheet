from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import growth
from ..models import HistoryEntry, Kingdom, Settlement
from .helpers import PASSWORD, PLAYER_NAME


class GrowthRuleTests(SimpleTestCase):
    def test_adjacency_is_by_side_not_corner(self):
        self.assertTrue(growth.adjacent(4, 1))
        self.assertTrue(growth.adjacent(4, 5))
        self.assertFalse(growth.adjacent(4, 0))
        self.assertFalse(growth.adjacent(2, 3))

    def test_type_from_layout(self):
        self.assertEqual(growth.type_from_layout({}), "village")
        self.assertEqual(growth.type_from_layout({4: 3}), "village")
        # An L shape and an S shape are both valid towns.
        self.assertEqual(growth.type_from_layout({0: 4, 3: 1, 6: 1, 7: 1}), "town")
        self.assertEqual(growth.type_from_layout({0: 4, 1: 1, 4: 1, 5: 1}), "town")
        self.assertEqual(growth.type_from_layout({0: 4, 2: 1}), "city")
        self.assertEqual(growth.type_from_layout({0: 1, 1: 1, 2: 1, 3: 1, 4: 1}), "city")

    def test_village_builds_in_one_block_until_full(self):
        growth.check_placement("village", {}, 8)
        growth.check_placement("village", {4: 3}, 4)
        with self.assertRaisesMessage(growth.PlacementNotAllowed, "one block only (block 5)"):
            growth.check_placement("village", {4: 3}, 5)

    def test_full_village_grows_into_an_adjacent_block(self):
        growth.check_placement("village", {4: 4}, 5)
        with self.assertRaisesMessage(growth.PlacementNotAllowed, "next to block 5"):
            growth.check_placement("village", {4: 4}, 0)
        self.assertEqual(growth.type_after_placement("village", {4: 4}, {4: 4, 5: 1}), "town")

    def test_town_grows_by_adjacent_blocks_up_to_four(self):
        town = {4: 4, 5: 1}
        growth.check_placement("town", town, 1)
        with self.assertRaisesMessage(growth.PlacementNotAllowed, "not next to any"):
            growth.check_placement("town", town, 0)
        four = {4: 4, 5: 1, 1: 1, 7: 1}
        with self.assertRaisesMessage(growth.PlacementNotAllowed, "at most 4 blocks"):
            growth.check_placement("town", four, 3)

    def test_town_with_two_lots_per_block_becomes_city_on_next_building(self):
        ready = {4: 4, 5: 2, 1: 2, 7: 2}
        growth.check_placement("town", ready, 0)
        self.assertEqual(growth.type_after_placement("town", ready, {**ready, 0: 1}), "city")
        self.assertEqual(growth.type_after_placement("town", ready, {**ready, 5: 3}), "city")

    def test_level_counts_blocks_with_buildings_up_to_twenty(self):
        self.assertEqual(growth.settlement_level({}), 0)
        self.assertEqual(growth.settlement_level({4: 4, 5: 1, 1: 0}), 2)
        self.assertEqual(growth.settlement_level({b: 1 for b in range(25)}), 20)

    def test_removal_recalculates_but_keeps_metropolis(self):
        self.assertEqual(growth.type_after_removal("city", {4: 4, 5: 1}), "town")
        self.assertEqual(growth.type_after_removal("town", {4: 2}), "village")
        self.assertEqual(growth.type_after_removal("metropolis", {4: 1}), "metropolis")

    def test_status_for_a_town_set_by_hand_without_buildings(self):
        self.assertIn("no buildings yet", growth.status("town", {}, 1, False)[0])

    def test_metropolis_readiness_is_explained(self):
        lines = growth.status("city", {b: 2 for b in range(9)}, 14, False)
        self.assertIn("kingdom level 15+ (now 14)", lines[1])
        self.assertIn(
            "Ready to become a metropolis",
            growth.status("city", {b: 2 for b in range(9)}, 15, False)[1],
        )
        self.assertIn(
            "not overcrowded", growth.status("city", {b: 2 for b in range(9)}, 15, True)[1]
        )


class GrowthViewTests(TestCase):
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
        args = [self.kingdom.pk, self.settlement.pk]
        self.client.post(reverse("kingdoms:settlement_edit_start", args=args))
        self.place_url = reverse("kingdoms:building_place", args=args)
        self.remove_args = args
        self.edit_url = reverse("kingdoms:settlement_edit", args=args)

    def place(self, building, block, lot=0, rotation=0):
        return self.client.post(
            self.place_url,
            {"building": building, "block": block, "lot": lot, "rotation": rotation},
        )

    def test_village_grows_into_town_and_shrinks_back(self):
        self.place("4/castle", 4)
        refused = self.place("1/inn", 0)
        self.assertContains(refused, "next to block 5", status_code=400)

        self.assertRedirects(self.place("1/inn", 5), self.edit_url)
        self.settlement.refresh_from_db()
        self.assertEqual(self.settlement.settlement_type, "town")
        self.assertEqual(self.settlement.level, 2)
        entry = self.kingdom.history.filter(action=HistoryEntry.Action.BUILDING_PLACED).first()
        self.assertEqual(entry.changes["type"], {"old": "village", "new": "town"})
        self.assertEqual(entry.changes["level"], {"old": 1, "new": 2})

        inn = self.settlement.placements.get(building="1/inn")
        self.client.post(reverse("kingdoms:building_remove", args=[*self.remove_args, inn.pk]))
        self.settlement.refresh_from_db()
        self.assertEqual(self.settlement.settlement_type, "village")
        self.assertEqual(self.settlement.level, 1)

    def test_level_cannot_be_set_by_hand(self):
        self.client.post(
            self.edit_url,
            {
                "name": "Tatzlford",
                "settlement_type": "village",
                "level": 9,
                "consumption": 0,
                "max_item_bonus": 0,
                "influence": 0,
                "ongoing_events": "",
            },
        )
        self.settlement.refresh_from_db()
        self.assertEqual(self.settlement.level, 0)
        self.assertNotContains(self.client.get(self.edit_url), 'name="level"')

    def test_edit_page_only_offers_allowed_lots(self):
        self.place("1/inn", 4)
        page = self.client.get(self.edit_url).content.decode()
        self.assertIn('aria-label="Place a building in block 5, lot 2"', page)
        self.assertNotIn('aria-label="Place a building in block 1, lot 1"', page)
        self.assertIn('class="free-lot blocked"', page)
        self.assertIn("Village: build only in block 5", page)
