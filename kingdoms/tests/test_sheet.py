from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import pf2e
from ..models import Character, HistoryEntry, Kingdom
from .helpers import PASSWORD, PLAYER_NAME, sheet_post_data


class Pf2eArithmeticTests(SimpleTestCase):
    def test_ability_modifier_rounds_down(self):
        self.assertEqual(
            [pf2e.ability_modifier(score) for score in (8, 9, 10, 11, 12, 18)],
            [-1, -1, 0, 0, 1, 4],
        )

    def test_proficiency_is_zero_untrained_and_level_plus_rank_bonus_otherwise(self):
        self.assertEqual(pf2e.proficiency_bonus(0, 5), 0)
        self.assertEqual(pf2e.proficiency_bonus(1, 5), 7)
        self.assertEqual(pf2e.proficiency_bonus(4, 5), 13)

    def test_skill_total_adds_every_column(self):
        total = pf2e.skill_total(
            ability_score=14, rank=1, level=3, status=-1, circumstance=2, item=1, other=1
        )
        self.assertEqual(total, 2 + 5 - 1 + 2 + 1 + 1)


class KingdomSheetTests(TestCase):
    def setUp(self):
        self.client.post(
            reverse("kingdoms:names"),
            {"display_name": PLAYER_NAME, "password": PASSWORD, "next": "/"},
        )
        self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Stolen Lands")
        self.url = reverse("kingdoms:sheet", args=[self.kingdom.pk])
        self.edit_url = reverse("kingdoms:edit", args=[self.kingdom.pk])

    def skill_row(self, response, label):
        return next(row for row in response.context["sheet"]["skills"] if row["label"] == label)

    def test_new_kingdom_has_every_sheet_row(self):
        self.assertEqual(self.kingdom.abilities.count(), 4)
        self.assertEqual(self.kingdom.skills.count(), 16)
        self.assertEqual(self.kingdom.leaders.count(), 8)
        self.assertEqual(self.kingdom.commodities.count(), 5)

    def test_sheet_shows_every_section(self):
        response = self.client.get(self.url)
        for text in (
            "Ability scores",
            "Ruin",
            "Corruption",
            "Leaders",
            "Viceroy",
            "Skills",
            "Wilderness",
            "Commodities",
            "Work sites",
            "Feats",
            "Ongoing events",
        ):
            self.assertContains(response, text)

    def test_saving_updates_values_totals_and_history(self):
        kesten = Character.objects.create(kingdom=self.kingdom, name="Kesten", kind="pc")
        response = self.client.post(
            self.edit_url,
            sheet_post_data(
                self.kingdom,
                level=3,
                economy_score=14,
                trade_rank=1,
                trade_item=1,
                ruler_character=kesten,
                ruler_invested=True,
                control_dc_base=16,
                control_dc_size=1,
            ),
        )
        self.assertRedirects(response, self.edit_url)

        page = self.client.get(self.url)
        self.assertEqual(self.skill_row(page, "Trade")["total"], 2 + 5 + 1)
        self.assertEqual(page.context["sheet"]["control_dc"], 17)
        leader = self.kingdom.leaders.get(role="ruler")
        self.assertEqual((leader.character, leader.invested), (kesten, True))

        entry = self.kingdom.history.get(action=HistoryEntry.Action.KINGDOM_EDITED)
        self.assertEqual(entry.changes["Trade rank"], {"old": 0, "new": 1})
        self.assertEqual(entry.changes["Economy score"], {"old": 10, "new": 14})
        self.assertEqual(entry.changes["level"], {"old": 1, "new": 3})

    def test_unchecking_invested_clears_it(self):
        self.kingdom.leaders.filter(role="ruler").update(invested=True)
        self.client.post(self.edit_url, sheet_post_data(self.kingdom, ruler_invested=False))
        self.assertFalse(self.kingdom.leaders.get(role="ruler").invested)

    def test_invalid_rank_is_rejected(self):
        response = self.client.post(self.edit_url, sheet_post_data(self.kingdom, trade_rank=9))
        self.assertContains(response, "Trade rank:", status_code=400)
        self.assertEqual(self.kingdom.skills.get(skill="trade").rank, 0)
