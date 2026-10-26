from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import settlements as grid
from ..models import HistoryEntry, Kingdom, Settlement
from .helpers import PASSWORD, PLAYER_NAME


class GridTests(SimpleTestCase):
    def test_catalog_reads_building_images_by_size(self):
        catalog = grid.catalog()
        self.assertEqual(catalog["1/inn"].lots, 1)
        self.assertEqual(catalog["2/keep"].lots, 2)
        self.assertEqual(catalog["4/castle"].lots, 4)
        self.assertEqual(catalog["2/temple"].label, "Temple")
        self.assertNotIn("settlement-base", " ".join(catalog))

    def test_covered_lots(self):
        self.assertEqual(grid.covered_lots(1, 3, 0), {3})
        self.assertEqual(grid.covered_lots(2, 2, 0), {2, 3})
        self.assertIsNone(grid.covered_lots(2, 1, 0))
        self.assertEqual(grid.covered_lots(2, 1, 90), {1, 3})
        self.assertIsNone(grid.covered_lots(2, 2, 270))
        self.assertEqual(grid.covered_lots(4, 0, 180), {0, 1, 2, 3})
        self.assertIsNone(grid.covered_lots(4, 1, 0))


class SettlementTests(TestCase):
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
        self.view_url = reverse("kingdoms:settlement", args=args)
        self.edit_url = reverse("kingdoms:settlement_edit", args=args)
        self.start_url = reverse("kingdoms:settlement_edit_start", args=args)
        self.place_url = reverse("kingdoms:building_place", args=args)

        self.bob = self.client_class()
        self.bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.bob.post(
            reverse("kingdoms:names"), {"display_name": "Bob", "password": PASSWORD, "next": "/"}
        )

    def place(self, client, building, block=0, lot=0, rotation=0):
        return client.post(
            self.place_url,
            {"building": building, "block": block, "lot": lot, "rotation": rotation},
        )

    def test_adding_a_settlement_needs_the_kingdom_lock(self):
        response = self.bob.post(
            reverse("kingdoms:settlement_add", args=[self.kingdom.pk]),
            {"name": "Bobton", "settlement_type": "town"},
        )
        self.assertRedirects(response, reverse("kingdoms:sheet", args=[self.kingdom.pk]))
        self.assertFalse(Settlement.objects.filter(name="Bobton").exists())
        self.assertTrue(
            self.kingdom.history.filter(action=HistoryEntry.Action.SETTLEMENT_ADDED).exists()
        )

    def test_settlement_lock_is_separate_from_the_kingdom_lock(self):
        # Alice still holds the kingdom lock from creating it, yet Bob may edit the settlement.
        self.assertRedirects(self.bob.post(self.start_url), self.edit_url)
        response = self.client.post(self.start_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford")

    def test_settlement_page_is_read_only_until_editing(self):
        response = self.client.get(self.view_url)
        self.assertContains(response, 'aria-label="Edit settlement"')
        self.assertNotContains(response, 'name="building"')
        self.assertRedirects(self.client.get(self.edit_url), self.view_url)

    def test_place_and_remove_buildings(self):
        self.client.post(self.start_url)
        self.assertRedirects(
            self.place(self.client, "2/keep", block=4, lot=1, rotation=90), self.edit_url
        )
        self.assertRedirects(self.place(self.client, "1/inn", block=4, lot=0), self.edit_url)
        placement = self.settlement.placements.get(building="2/keep")
        self.assertEqual((placement.block, placement.lot, placement.rotation), (4, 1, 90))

        page = self.client.get(self.view_url)
        self.assertContains(page, 'alt="Keep"')
        self.assertContains(page, "--rotation: 90deg")

        self.client.post(
            reverse(
                "kingdoms:building_remove",
                args=[self.kingdom.pk, self.settlement.pk, placement.pk],
            )
        )
        self.assertFalse(self.settlement.placements.filter(building="2/keep").exists())
        actions = set(self.kingdom.history.values_list("action", flat=True))
        self.assertTrue(
            {HistoryEntry.Action.BUILDING_PLACED, HistoryEntry.Action.BUILDING_REMOVED} <= actions
        )

    def test_kingdom_page_shows_grid_thumbnail_per_settlement(self):
        self.client.post(self.start_url)
        self.place(self.client, "4/castle", block=4)
        for url in ("kingdoms:sheet", "kingdoms:edit"):
            response = self.client.get(reverse(url, args=[self.kingdom.pk]))
            self.assertContains(response, 'class="blocks grid-thumbnail"', count=1)
            self.assertContains(response, "img/4/castle.png")
            self.assertContains(response, self.view_url)

    def test_overlapping_or_misfit_buildings_are_refused(self):
        self.client.post(self.start_url)
        self.place(self.client, "4/castle", block=2)
        overlap = self.place(self.client, "1/inn", block=2, lot=3)
        self.assertContains(overlap, "would overlap Castle", status_code=400)
        misfit = self.place(self.client, "2/keep", block=0, lot=1, rotation=0)
        self.assertContains(misfit, "must start in a left lot", status_code=400)
        unknown = self.place(self.client, "../../secret", block=0)
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(self.settlement.placements.count(), 1)

    def test_editing_without_the_lock_changes_nothing(self):
        self.client.post(self.start_url)
        self.place(self.bob, "1/inn")
        self.assertFalse(self.settlement.placements.exists())

    def test_saving_settlement_details_and_borders(self):
        self.client.post(self.start_url)
        response = self.client.post(
            self.edit_url,
            {
                "name": "Tatzlford",
                "settlement_type": "town",
                "level": 3,
                "consumption": 2,
                "overcrowded": "on",
                "max_item_bonus": 1,
                "influence": 1,
                "paved_streets": "on",
                "border_north": ["water", "bridge"],
                "border_west": ["wall_stone"],
                "ongoing_events": "",
            },
        )
        self.assertRedirects(response, self.edit_url)
        self.settlement.refresh_from_db()
        self.assertEqual(self.settlement.settlement_type, "town")
        self.assertTrue(self.settlement.overcrowded)
        self.assertEqual(
            self.settlement.borders, {"north": ["water", "bridge"], "west": ["wall_stone"]}
        )
        page = self.client.get(self.view_url)
        self.assertContains(page, "Water, Bridge")
        self.assertContains(page, "Paved streets")

    def test_settlement_being_edited_by_someone_else_cannot_be_deleted(self):
        self.bob.post(self.start_url)
        delete_url = reverse(
            "kingdoms:settlement_delete", args=[self.kingdom.pk, self.settlement.pk]
        )
        response = self.client.post(delete_url, follow=True)
        self.assertContains(response, "Bob is editing Tatzlford")
        self.assertTrue(Settlement.objects.filter(pk=self.settlement.pk).exists())

        self.bob.post(
            reverse("kingdoms:settlement_edit_stop", args=[self.kingdom.pk, self.settlement.pk])
        )
        self.client.post(delete_url)
        self.assertFalse(Settlement.objects.filter(pk=self.settlement.pk).exists())

    def test_nonmembers_cannot_see_or_change_settlements(self):
        outsider = self.client_class()
        outsider.post(
            reverse("kingdoms:names"), {"display_name": "Eve", "password": PASSWORD, "next": "/"}
        )
        for method, url in (
            ("get", self.view_url),
            ("post", self.start_url),
            ("post", self.place_url),
            ("post", reverse("kingdoms:settlement_add", args=[self.kingdom.pk])),
        ):
            self.assertEqual(getattr(outsider, method)(url).status_code, 404, url)
