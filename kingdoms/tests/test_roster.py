from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.urls import reverse

from ..models import Army, Battle, Character, HistoryEntry, Kingdom, Settlement, Unit
from ..roster import unit_summary
from .helpers import PASSWORD, PLAYER_NAME
from .test_armies import army_post_data


def unit_post_data(unit, **overrides):
    """A full unit form POST built from the unit's saved values, sending IDs for linked rows."""
    values = {**{field: getattr(unit, field) for field in Unit.FIELDS}, **overrides}
    return {
        name: "" if value is None else getattr(value, "pk", value) for name, value in values.items()
    }


class RosterTestCase(TestCase):
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
        self.client.post(
            reverse("kingdoms:army_add", args=[self.kingdom.pk]), {"name": "Tatzlford Militia"}
        )
        self.army = Army.objects.get(name="Tatzlford Militia")
        self.army_args = [self.kingdom.pk, self.army.pk]
        self.army_url = reverse("kingdoms:army", args=self.army_args)
        self.army_edit_url = reverse("kingdoms:army_edit", args=self.army_args)
        self.army_start = reverse("kingdoms:army_edit_start", args=self.army_args)
        self.unit_add_url = reverse("kingdoms:unit_add", args=self.army_args)
        self.battles_url = reverse("kingdoms:battles", args=[self.kingdom.pk])

        self.bob = self.client_class()
        self.bob.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        self.bob.post(
            reverse("kingdoms:names"), {"display_name": "Bob", "password": PASSWORD, "next": "/"}
        )

    def unit_url(self, name, unit):
        return reverse(name, args=[*self.army_args, unit.pk])

    def add_unit(self, client=None, name="Pikes"):
        return (client or self.client).post(self.unit_add_url, {"name": name})


class UnitTests(RosterTestCase):
    def setUp(self):
        super().setUp()
        self.client.post(self.army_start)

    def test_adding_a_unit_opens_its_editor_and_is_recorded(self):
        response = self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        self.assertRedirects(response, self.unit_url("kingdoms:unit_edit", unit))
        entry = self.kingdom.history.get(action=HistoryEntry.Action.UNIT_ADDED)
        self.assertEqual(entry.subject_label, "Pikes")

    def test_editing_a_unit_records_every_value_by_hand(self):
        self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        response = self.client.post(
            self.unit_url("kingdoms:unit_edit", unit),
            unit_post_data(
                unit,
                ancestry="Human",
                quality="veteran",
                unit_type="Infantry",
                attack=2,
                defense=13,
                power=1,
                toughness=11,
                morale=1,
                size="about 50 soldiers",
                current_strength=4,
                max_strength=6,
                status="Shaken",
            ),
        )
        self.assertRedirects(response, self.army_edit_url)
        unit.refresh_from_db()
        self.assertEqual(
            (unit.quality, unit.current_strength, unit.size),
            ("veteran", 4, "about 50 soldiers"),
        )
        entry = self.kingdom.history.get(action=HistoryEntry.Action.UNIT_EDITED)
        self.assertEqual(entry.changes["current strength"], {"old": 0, "new": 4})
        self.assertEqual(entry.changes["defense"], {"old": 0, "new": 13})

    def test_quality_is_one_of_the_four_or_empty(self):
        self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        url = self.unit_url("kingdoms:unit_edit", unit)
        editor = self.client.get(url)
        self.assertContains(editor, '<option value="" selected>-</option>', html=True)
        self.assertContains(editor, '<option value="elite">Elite</option>', html=True)
        response = self.client.post(url, unit_post_data(unit, quality="Regular"))
        self.assertContains(response, "Quality:", status_code=400)
        unit.refresh_from_db()
        self.assertEqual(unit.quality, "")

    def test_strength_must_be_nonnegative_and_not_above_maximum(self):
        self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        url = self.unit_url("kingdoms:unit_edit", unit)
        negative = self.client.post(url, unit_post_data(unit, current_strength=-1, max_strength=6))
        self.assertContains(negative, "Current strength:", status_code=400)
        over = self.client.post(url, unit_post_data(unit, current_strength=7, max_strength=6))
        self.assertContains(over, "cannot be more than maximum", status_code=400)
        unit.refresh_from_db()
        self.assertEqual((unit.current_strength, unit.max_strength), (0, 0))

    def test_units_need_the_army_lock(self):
        self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        self.add_unit(client=self.bob, name="Bob's Archers")
        self.bob.post(self.unit_url("kingdoms:unit_edit", unit), unit_post_data(unit, attack=9))
        self.bob.post(self.unit_url("kingdoms:unit_delete", unit))
        self.assertRedirects(self.bob.get(self.unit_url("kingdoms:unit_edit", unit)), self.army_url)
        unit.refresh_from_db()
        self.assertEqual(unit.attack, 0)
        self.assertEqual(list(Unit.objects.values_list("name", flat=True)), ["Pikes"])

    def test_deleting_a_unit_is_recorded(self):
        self.add_unit()
        unit = Unit.objects.get(name="Pikes")
        self.client.post(self.unit_url("kingdoms:unit_delete", unit))
        self.assertFalse(Unit.objects.exists())
        self.assertTrue(
            self.kingdom.history.filter(action=HistoryEntry.Action.UNIT_DELETED).exists()
        )


class UnitSummaryTests(RosterTestCase):
    def test_summary_lists_the_recorded_values(self):
        unit = Unit.objects.create(
            army=self.army,
            name="Pikes",
            ancestry="Human",
            quality="trained",
            unit_type="Infantry",
            attack=2,
            defense=13,
            power=1,
            toughness=11,
            morale=-1,
            size="about 50 soldiers",
            current_strength=4,
            max_strength=6,
            traits="Set for charge",
            notes="Raised in\nTatzlford",
        )
        self.assertEqual(
            unit_summary(unit),
            "Pikes (Tatzlford Militia)\n"
            "Human, Trained, Infantry\n"
            "Attack 2, Defense 13, Power 1, Toughness 11, Morale -1\n"
            "Strength 4/6, size about 50 soldiers\n"
            "Traits: Set for charge\n"
            "Notes: Raised in Tatzlford",
        )

    def test_diminished_is_half_maximum_or_less_rounding_down_but_not_defeated(self):
        cases = {(6, 4): False, (6, 3): True, (5, 3): False, (5, 2): True, (6, 1): True}
        cases[(6, 0)] = False
        for (maximum, current), expected in cases.items():
            unit = Unit(army=self.army, current_strength=current, max_strength=maximum)
            self.assertIs(unit.diminished, expected, (current, maximum))

    def test_diminished_units_are_marked_in_the_table_and_summary(self):
        Unit.objects.create(army=self.army, name="Pikes", current_strength=3, max_strength=6)
        Unit.objects.create(army=self.army, name="Bows", current_strength=4, max_strength=6)
        page = self.client.get(self.army_url)
        self.assertContains(page, "<strong>diminished</strong>", count=1)
        self.assertContains(page, "Strength 3/6, diminished")
        self.assertNotContains(page, "Strength 4/6, diminished")
        self.assertContains(page, "12_kingmaker_war.html")

    def test_army_page_offers_copy_and_read_only_box(self):
        unit = Unit.objects.create(army=self.army, name="Pikes", current_strength=3, max_strength=4)
        page = self.client.get(self.army_url)
        self.assertContains(
            page, f'data-copy-target="summary-{unit.pk}">Copy unit summary</button>'
        )
        self.assertContains(page, f'<textarea id="summary-{unit.pk}" readonly')
        self.assertContains(page, "Strength 3/4")


class HeroTests(RosterTestCase):
    def setUp(self):
        super().setUp()
        self.client.post(self.army_start)
        self.add_unit()
        self.add_unit(name="Bows")
        self.pikes = Unit.objects.get(name="Pikes")
        self.bows = Unit.objects.get(name="Bows")
        self.amiri = Character.objects.create(kingdom=self.kingdom, name="Amiri", kind="pc")
        self.kesten = Character.objects.create(kingdom=self.kingdom, name="Kesten", kind="npc")

    def set_hero(self, unit, hero, **values):
        return self.client.post(
            self.unit_url("kingdoms:unit_edit", unit), unit_post_data(unit, hero=hero, **values)
        )

    def set_commander(self, commander):
        return self.client.post(self.army_edit_url, army_post_data(self.army, commander=commander))

    def test_hero_adds_two_morale_to_the_table_and_summary(self):
        response = self.set_hero(self.pikes, self.amiri, morale=2)
        self.assertRedirects(response, self.army_edit_url)
        self.pikes.refresh_from_db()
        self.assertEqual(
            (self.pikes.hero, self.pikes.morale, self.pikes.battle_morale), (self.amiri, 2, 4)
        )
        page = self.client.get(self.army_url)
        self.assertContains(page, "incl. hero +2")
        self.assertContains(page, "Morale 4\nHero: Amiri (Morale includes +2)")
        entry = self.kingdom.history.get(action=HistoryEntry.Action.UNIT_EDITED)
        self.assertEqual(entry.changes["hero"], {"old": None, "new": "Amiri"})

    def test_a_character_is_the_hero_of_only_one_unit(self):
        self.set_hero(self.pikes, self.amiri)
        response = self.set_hero(self.bows, self.amiri)
        self.assertContains(response, "Amiri is already the hero of Pikes.", status_code=400)
        self.bows.refresh_from_db()
        self.assertIsNone(self.bows.hero)
        self.assertRedirects(self.set_hero(self.pikes, self.amiri, morale=1), self.army_edit_url)

    def test_the_commander_cannot_also_be_a_hero(self):
        self.assertRedirects(self.set_commander(self.kesten), self.army_edit_url)
        self.army.refresh_from_db()
        response = self.set_hero(self.pikes, self.kesten)
        self.assertContains(response, "Kesten commands this army.", status_code=400)

    def test_a_hero_cannot_also_be_the_commander(self):
        self.set_hero(self.pikes, self.amiri)
        response = self.set_commander(self.amiri)
        self.assertContains(response, "Amiri is the hero of Pikes.", status_code=400)
        self.army.refresh_from_db()
        self.assertIsNone(self.army.commander)

    def test_heroes_come_from_this_kingdom(self):
        other = Kingdom.objects.create(name="Pitax", access_code="e" * 64)
        stranger = Character.objects.create(kingdom=other, name="Irovetti", kind="npc")
        response = self.set_hero(self.pikes, stranger)
        self.assertContains(response, "Hero:", status_code=400)
        self.assertNotContains(
            self.client.get(self.unit_url("kingdoms:unit_edit", self.pikes)), "Irovetti"
        )


class QualityMigrationTests(RosterTestCase):
    def test_free_text_quality_becomes_a_choice_or_moves_to_notes(self):
        migration = import_module("kingdoms.migrations.0020_unit_quality_values")
        Unit.objects.bulk_create(
            [
                Unit(army=self.army, name="Pikes", quality=" Veteran "),
                Unit(army=self.army, name="Bows", quality="Regular", notes="Longbows"),
                Unit(army=self.army, name="Levy", quality="Green"),
            ]
        )
        migration.to_choices(apps, None)
        values = {u.name: (u.quality, u.notes) for u in Unit.objects.all()}
        self.assertEqual(
            values,
            {
                "Pikes": ("veteran", ""),
                "Bows": ("", "Longbows\nQuality: Regular"),
                "Levy": ("", "Quality: Green"),
            },
        )


class BattleTests(RosterTestCase):
    def battle_data(self, **overrides):
        data = {
            "name": "Battle of Tuskwater",
            "location": "Tuskwater",
            "date": "4th of Arodus",
            "opponents": "Tiger Lords",
            "outcome": "victory",
            "notes": "",
        }
        return {**data, **overrides}

    def test_recording_a_battle_leaves_units_alone(self):
        unit = Unit.objects.create(army=self.army, name="Pikes", current_strength=5, max_strength=6)
        response = self.client.post(
            reverse("kingdoms:battle_add", args=[self.kingdom.pk]), self.battle_data()
        )
        self.assertRedirects(response, self.battles_url)
        battle = Battle.objects.get()
        self.assertEqual((battle.outcome, battle.date), ("victory", "4th of Arodus"))
        unit.refresh_from_db()
        self.assertEqual(unit.current_strength, 5)
        entry = self.kingdom.history.get(action=HistoryEntry.Action.BATTLE_RECORDED)
        self.assertEqual(entry.subject_label, "Battle of Tuskwater")
        self.assertContains(self.client.get(self.battles_url), "Battle of Tuskwater")

    def test_outcome_must_be_one_of_the_four(self):
        response = self.client.post(
            reverse("kingdoms:battle_add", args=[self.kingdom.pk]),
            self.battle_data(outcome="rout"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Battle.objects.exists())

    def test_battles_can_be_corrected_and_deleted(self):
        battle = Battle.objects.create(kingdom=self.kingdom, name="Skirmish", outcome="draw")
        self.client.post(
            reverse("kingdoms:battle_edit", args=[self.kingdom.pk, battle.pk]),
            {
                f"battle{battle.pk}-{key}": value
                for key, value in self.battle_data(name="Skirmish", outcome="withdrawal").items()
            },
        )
        battle.refresh_from_db()
        self.assertEqual(battle.outcome, "withdrawal")
        self.client.post(reverse("kingdoms:battle_delete", args=[self.kingdom.pk, battle.pk]))
        self.assertFalse(Battle.objects.exists())
        actions = set(self.kingdom.history.values_list("action", flat=True))
        self.assertTrue(
            {HistoryEntry.Action.BATTLE_EDITED, HistoryEntry.Action.BATTLE_DELETED} <= actions
        )

    def test_unprotected_names_cannot_record_battles(self):
        visitor = self.client_class()
        visitor.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        visitor.post(reverse("kingdoms:names"), {"display_name": "Carl", "next": "/"})
        visitor.post(reverse("kingdoms:battle_add", args=[self.kingdom.pk]), self.battle_data())
        self.assertFalse(Battle.objects.exists())


class RosterAccessTests(RosterTestCase):
    def test_nonmembers_cannot_see_or_change_units_or_battles(self):
        unit = Unit.objects.create(army=self.army, name="Pikes")
        battle = Battle.objects.create(kingdom=self.kingdom, name="Skirmish", outcome="draw")
        outsider = self.client_class()
        outsider.post(
            reverse("kingdoms:names"), {"display_name": "Eve", "password": PASSWORD, "next": "/"}
        )
        for method, url in (
            ("get", self.army_url),
            ("post", self.unit_add_url),
            ("get", self.unit_url("kingdoms:unit_edit", unit)),
            ("post", self.unit_url("kingdoms:unit_edit", unit)),
            ("post", self.unit_url("kingdoms:unit_delete", unit)),
            ("get", self.battles_url),
            ("post", reverse("kingdoms:battle_add", args=[self.kingdom.pk])),
            ("post", reverse("kingdoms:battle_edit", args=[self.kingdom.pk, battle.pk])),
            ("post", reverse("kingdoms:battle_delete", args=[self.kingdom.pk, battle.pk])),
        ):
            self.assertEqual(getattr(outsider, method)(url).status_code, 404, url)

    def test_units_of_another_army_are_not_reachable_through_this_one(self):
        other = Army.objects.create(kingdom=self.kingdom, name="Other")
        stranger = Unit.objects.create(army=other, name="Stranger")
        self.client.post(self.army_start)
        url = reverse("kingdoms:unit_edit", args=[*self.army_args, stranger.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
