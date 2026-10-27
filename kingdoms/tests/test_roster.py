from django.test import TestCase
from django.urls import reverse

from ..models import Army, Battle, HistoryEntry, Kingdom, Settlement, Unit
from ..roster import unit_summary
from .helpers import PASSWORD, PLAYER_NAME


def unit_post_data(unit, **overrides):
    """A full unit form POST built from the unit's saved values."""
    return {**{field: getattr(unit, field) for field in Unit.FIELDS}, **overrides}


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
                experience="Something unlisted",
                unit_type="Infantry",
                attack=2,
                defense=13,
                power=1,
                toughness=11,
                morale=1,
                size="1d6",
                current_strength=4,
                max_strength=6,
                status="Shaken",
            ),
        )
        self.assertRedirects(response, self.army_edit_url)
        unit.refresh_from_db()
        self.assertEqual(
            (unit.experience, unit.current_strength, unit.size), ("Something unlisted", 4, "1d6")
        )
        entry = self.kingdom.history.get(action=HistoryEntry.Action.UNIT_EDITED)
        self.assertEqual(entry.changes["current strength"], {"old": 0, "new": 4})
        self.assertEqual(entry.changes["defense"], {"old": 0, "new": 13})

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
            experience="Regular",
            unit_type="Infantry",
            attack=2,
            defense=13,
            power=1,
            toughness=11,
            morale=-1,
            size="1d6",
            current_strength=4,
            max_strength=6,
            traits="Set for charge",
            notes="Raised in\nTatzlford",
        )
        self.assertEqual(
            unit_summary(unit),
            "Pikes (Tatzlford Militia)\n"
            "Human, Regular, Infantry\n"
            "Attack 2, Defense 13, Power 1, Toughness 11, Morale -1\n"
            "Strength 4/6, size 1d6\n"
            "Traits: Set for charge\n"
            "Notes: Raised in Tatzlford",
        )

    def test_army_page_offers_copy_and_read_only_box(self):
        unit = Unit.objects.create(army=self.army, name="Pikes", current_strength=3, max_strength=4)
        page = self.client.get(self.army_url)
        self.assertContains(
            page, f'data-copy-target="summary-{unit.pk}">Copy unit summary</button>'
        )
        self.assertContains(page, f'<textarea id="summary-{unit.pk}" readonly')
        self.assertContains(page, "Strength 3/4")


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
