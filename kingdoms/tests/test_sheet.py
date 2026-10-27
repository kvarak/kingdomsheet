from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import rules
from ..models import Character, HistoryEntry, Kingdom
from .helpers import PASSWORD, PLAYER_NAME, sheet_post_data


class VarlynArithmeticTests(SimpleTestCase):
    def test_ability_modifier_rounds_down(self):
        self.assertEqual(
            [rules.ability_modifier(score) for score in (8, 9, 10, 11, 12, 18)],
            [-1, -1, 0, 0, 1, 4],
        )

    def test_proficiency_bonus_follows_5e_levels(self):
        levels = (1, 4, 5, 8, 9, 13, 17, 20)
        self.assertEqual(
            [rules.proficiency_bonus(level) for level in levels], [2, 2, 3, 3, 4, 5, 6, 6]
        )

    def test_ranks_use_proficiency_expertise_and_improved_steps(self):
        self.assertEqual([rules.rank_bonus(rank, 5) for rank in range(5)], [0, 3, 3, 4, 5])
        self.assertEqual(
            [rules.has_expertise(rank) for rank in range(5)], [False, False, True, True, True]
        )
        self.assertEqual(rules.RANK_LABELS[2], "Expertise")

    def test_skill_total(self):
        total = rules.skill_total(ability_score=14, rank=3, level=5, bonus=1, vacancy=-1)
        self.assertEqual(total, 2 + 3 + 1 + 1 - 1)

    def test_advantage_and_disadvantage_cancel(self):
        self.assertEqual(rules.roll_mode(True, False), "advantage")
        self.assertEqual(rules.roll_mode(False, True), "disadvantage")
        self.assertEqual(rules.roll_mode(True, True), "")

    def test_control_and_kingdom_dcs(self):
        self.assertEqual(rules.control_dc(1, 1), 14)
        self.assertEqual(rules.control_dc(10, 30), 12 + 4 + 2)
        self.assertEqual(rules.control_dc(20, 150, ruler_vacant=True), 12 + 6 + 4 + 2)
        self.assertEqual(rules.kingdom_dc(5), 15)
        self.assertEqual(rules.kingdom_dc(5, "very hard"), 20)


class VacancyTests(SimpleTestCase):
    def test_vacant_ruler_costs_every_skill_and_stacks(self):
        self.assertEqual(rules.vacancy_effects("arts", "culture", {"ruler"}), (-1, False))
        self.assertEqual(
            rules.vacancy_effects("arts", "culture", {"ruler", "counselor"}), (-2, False)
        )

    def test_ability_vacancies_hit_only_their_ability(self):
        self.assertEqual(rules.vacancy_effects("trade", "economy", {"treasurer"}), (-1, False))
        self.assertEqual(rules.vacancy_effects("arts", "culture", {"treasurer"}), (0, False))

    def test_vacant_general_or_magister_gives_warfare_disadvantage(self):
        # Disadvantage is the worst non-ruler penalty, so the emissary's -1 does not add to it.
        self.assertEqual(
            rules.vacancy_effects("warfare", "loyalty", {"emissary", "general"}), (0, True)
        )
        self.assertEqual(
            rules.vacancy_effects("warfare", "loyalty", {"magister", "ruler"}), (-1, True)
        )
        self.assertEqual(rules.vacancy_effects("intrigue", "loyalty", {"general"}), (0, False))

    def test_warden_has_no_skill_penalty(self):
        self.assertEqual(rules.vacancy_effects("wilderness", "stability", {"warden"}), (0, False))


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
                trade_bonus=1,
                ruler_character=kesten,
                ruler_invested=True,
            ),
        )
        self.assertRedirects(response, self.edit_url)

        page = self.client.get(self.url)
        # Only the ruler is filled, so the vacant treasurer costs Trade (an Economy skill) 1.
        trade = self.skill_row(page, "Trade")
        self.assertEqual(trade["vacancy"], -1)
        self.assertEqual(trade["total"], 2 + 2 + 1 - 1)
        self.assertEqual(trade["roll"], "")
        self.assertEqual(page.context["sheet"]["control_dc"], 12 + 2 + 0)
        self.assertContains(page, "Warden vacant: disadvantage on Region activities")
        self.assertNotContains(page, "Ruler vacant")

        leader = self.kingdom.leaders.get(role="ruler")
        self.assertEqual((leader.character, leader.invested), (kesten, True))

        entry = self.kingdom.history.get(action=HistoryEntry.Action.KINGDOM_EDITED)
        self.assertEqual(entry.changes["Trade rank"], {"old": 0, "new": 1})
        self.assertEqual(entry.changes["Economy score"], {"old": 10, "new": 14})
        self.assertEqual(entry.changes["level"], {"old": 1, "new": 3})

    def test_one_vacant_warfare_role_is_named_alone(self):
        self.kingdom.leaders.filter(role="general").update(
            character=Character.objects.create(kingdom=self.kingdom, name="Jamandi", kind="npc")
        )
        page = self.client.get(self.url)
        self.assertContains(page, "Magister vacant: disadvantage on Warfare activities")
        self.assertNotContains(page, "General and magister")

    def test_unchecking_invested_clears_it(self):
        self.kingdom.leaders.filter(role="ruler").update(invested=True)
        self.client.post(self.edit_url, sheet_post_data(self.kingdom, ruler_invested=False))
        self.assertFalse(self.kingdom.leaders.get(role="ruler").invested)

    def test_invalid_rank_is_rejected(self):
        response = self.client.post(self.edit_url, sheet_post_data(self.kingdom, trade_rank=9))
        self.assertContains(response, "Trade rank:", status_code=400)
        self.assertEqual(self.kingdom.skills.get(skill="trade").rank, 0)

    def test_empty_kingdom_shows_vacancy_penalties(self):
        page = self.client.get(self.url)
        warfare = self.skill_row(page, "Warfare")
        self.assertEqual((warfare["vacancy"], warfare["roll"]), (-1, "disadvantage"))
        self.assertEqual(self.skill_row(page, "Arts")["vacancy"], -2)
        self.assertEqual(page.context["sheet"]["control_dc"], 12 + 2 + 0 + 2)
        self.assertContains(page, "+ 2 vacant ruler")
        self.assertContains(page, "Ruler vacant: gain 1d4 Unrest")
        self.assertContains(
            page, "General or magister vacant: disadvantage on Warfare activities", count=1
        )

    def test_expertise_rolls_with_advantage(self):
        self.kingdom.skills.filter(skill="trade").update(rank=3)
        trade = self.skill_row(self.client.get(self.url), "Trade")
        self.assertEqual(trade["proficiency"], 3)
        self.assertEqual(trade["roll"], "advantage")

    def test_edit_mode_explains_each_role(self):
        page = self.client.get(reverse("kingdoms:edit", args=[self.kingdom.pk]))
        self.assertContains(page, "Key ability: Loyalty. Vacancy penalty: -1 to all checks")
        self.assertContains(
            page, "Key ability: Stability. Vacancy penalty: disadvantage on Region activities"
        )
