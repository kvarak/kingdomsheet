from django.db import models
from django.db.models import Q

from . import rules


class EditLock(models.Model):
    """Fields for the one-editor-at-a-time lock. See kingdoms.locks."""

    editor = models.ForeignKey(
        "PlayerName", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    editor_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class Kingdom(EditLock):
    class Renown(models.TextChoices):
        FAME = "fame", "Fame"
        INFAMY = "infamy", "Infamy"

    access_code = models.CharField(max_length=64, unique=True, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # PF2e kingdom sheet. Grouped as on the printed sheet.
    charter = models.CharField(max_length=120, blank=True)
    heartland = models.CharField(max_length=120, blank=True)
    government = models.CharField(max_length=120, blank=True)
    capital = models.CharField(max_length=120, blank=True)
    level = models.IntegerField(default=1)
    size = models.IntegerField(default=1)
    resource_points = models.IntegerField(default=0)
    xp = models.IntegerField(default=0)
    renown = models.CharField(max_length=10, choices=Renown.choices, default=Renown.FAME)
    fame = models.IntegerField(default=0)
    fame_max = models.IntegerField(default=3)
    resource_dice = models.CharField(max_length=20, blank=True)
    bonus_dice = models.IntegerField(default=0)

    unrest = models.IntegerField(default=0)
    unrest_penalty = models.IntegerField(default=0)
    consumption = models.IntegerField(default=0)

    farmlands = models.IntegerField(default=0)
    lumber_camps = models.IntegerField(default=0)
    mines = models.IntegerField(default=0)
    quarries = models.IntegerField(default=0)
    trade_agreements = models.IntegerField(default=0)
    event_check_dc = models.IntegerField(default=0)

    feats = models.TextField(blank=True)
    kingdom_abilities = models.TextField(blank=True)
    relations = models.TextField(blank=True)
    ongoing_events = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(access_code__regex=r"^[0-9a-f]{64}$"),
                name="kingdom_access_code_format",
            ),
        ]

    def __str__(self):
        return self.name


class KingdomAbility(models.Model):
    """One ability score and its ruin. Each kingdom has one row per ability."""

    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="abilities")
    ability = models.CharField(max_length=20, choices=rules.ABILITIES)
    score = models.IntegerField(default=10)
    ruin = models.IntegerField(default=0)
    ruin_penalty = models.IntegerField(default=0)
    ruin_threshold = models.IntegerField(default=10)

    class Meta:
        verbose_name_plural = "kingdom abilities"
        constraints = [
            models.UniqueConstraint(fields=["kingdom", "ability"], name="unique_kingdom_ability"),
        ]

    def __str__(self):
        return self.get_ability_display()


class KingdomSkill(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="skills")
    skill = models.CharField(
        max_length=20, choices=[(key, label) for key, label, _ in rules.SKILLS]
    )
    rank = models.IntegerField(default=0, choices=rules.PROFICIENCY_RANKS)
    # Every other bonus or penalty on the skill (structures, invested leaders, effects).
    bonus = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kingdom", "skill"], name="unique_kingdom_skill"),
        ]

    def __str__(self):
        return self.get_skill_display()


class Character(models.Model):
    """A player character or NPC with a picture, belonging to one kingdom."""

    class Kind(models.TextChoices):
        PC = "pc", "PC"
        NPC = "npc", "NPC"

    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="characters")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=3, choices=Kind.choices, default=Kind.NPC)
    # Always a downscaled WebP made by kingdoms.pictures, stored under a random name.
    picture = models.FileField(upload_to="characters/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "name", "id"]

    def __str__(self):
        return self.name


class KingdomLeader(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="leaders")
    role = models.CharField(
        max_length=20, choices=[(key, label) for key, label, _ in rules.LEADERSHIP_ROLES]
    )
    character = models.ForeignKey(
        Character, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    invested = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kingdom", "role"], name="unique_kingdom_role"),
        ]

    def __str__(self):
        return self.get_role_display()


class KingdomCommodity(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="commodities")
    commodity = models.CharField(max_length=20, choices=rules.COMMODITIES)
    stored = models.IntegerField(default=0)
    capacity = models.IntegerField(default=4)

    class Meta:
        verbose_name_plural = "kingdom commodities"
        constraints = [
            models.UniqueConstraint(
                fields=["kingdom", "commodity"], name="unique_kingdom_commodity"
            ),
        ]

    def __str__(self):
        return self.get_commodity_display()


class Settlement(EditLock):
    """One settlement and its urban grid, following the PF2e urban grid sheet."""

    class Type(models.TextChoices):
        VILLAGE = "village", "Village"
        TOWN = "town", "Town"
        CITY = "city", "City"
        METROPOLIS = "metropolis", "Metropolis"

    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="settlement_set")
    name = models.CharField(max_length=120)
    settlement_type = models.CharField(
        "type", max_length=20, choices=Type.choices, default=Type.VILLAGE
    )
    # Number of blocks with at least one building, kept up to date by services. See growth.
    level = models.IntegerField(default=0)
    consumption = models.IntegerField(default=0)
    overcrowded = models.BooleanField(default=False)
    max_item_bonus = models.IntegerField(default=0)
    influence = models.IntegerField("influence (hexes)", default=0)
    magical_streetlamps = models.BooleanField(default=False)
    paved_streets = models.BooleanField(default=False)
    sewer_system = models.BooleanField(default=False)
    # Border features per side, for example {"north": ["water", "bridge"]}.
    borders = models.JSONField(default=dict, blank=True)
    ongoing_events = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Army(EditLock):
    """An army roster: a named group of units belonging to a kingdom, optionally garrisoned in one
    of its settlements.

    Armies only record units and their state for battles played by hand on Roll20. Nothing about
    combat is calculated here.
    """

    # Fields edited in the interface.
    ROSTER_FIELDS = ("name", "garrison", "commander", "location", "notes")

    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="armies")
    garrison = models.ForeignKey(
        Settlement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="garrisoned_armies",
    )
    name = models.CharField(max_length=120)
    commander = models.ForeignKey(
        "Character", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    location = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        verbose_name_plural = "armies"

    def __str__(self):
        return self.name


class Unit(models.Model):
    """One unit in an army roster, as in the campaign's Kingmaker Warfare house rules (inspired by
    Strongholds & Followers). Every value is typed in by the players; only `diminished` and
    `battle_morale` are derived.
    """

    # A unit's hero gives it this much Morale while the hero is with it.
    HERO_MORALE = 2

    class Quality(models.TextChoices):
        MILITIA = "militia", "Militia"
        TRAINED = "trained", "Trained"
        VETERAN = "veteran", "Veteran"
        ELITE = "elite", "Elite"

    # Fields edited in the interface, in display order.
    FIELDS = (
        "name",
        "hero",
        "ancestry",
        "quality",
        "equipment",
        "unit_type",
        "attack",
        "defense",
        "power",
        "toughness",
        "morale",
        "size",
        "current_strength",
        "max_strength",
        "status",
        "traits",
        "notes",
        "display_order",
    )
    STATISTICS = ("attack", "defense", "power", "toughness", "morale")

    army = models.ForeignKey(Army, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=120)
    hero = models.ForeignKey(
        "Character", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ancestry = models.CharField(max_length=80, blank=True)
    quality = models.CharField(max_length=10, choices=Quality.choices, blank=True)
    equipment = models.CharField(max_length=80, blank=True)
    unit_type = models.CharField("unit type", max_length=80, blank=True)
    attack = models.IntegerField(default=0)
    defense = models.IntegerField(default=0)
    power = models.IntegerField(default=0)
    toughness = models.IntegerField(default=0)
    morale = models.IntegerField(default=0)
    size = models.CharField(max_length=40, blank=True)
    current_strength = models.PositiveIntegerField(default=0)
    max_strength = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=80, blank=True)
    traits = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name", "id"]

    def __str__(self):
        return self.name

    @property
    def diminished(self):
        """At half its maximum Strength or less (rounding down) but not yet defeated."""
        return 0 < self.current_strength <= self.max_strength // 2

    @property
    def battle_morale(self):
        """Morale including the hero's bonus, as written on the unit card before battle."""
        return self.morale + (self.HERO_MORALE if self.hero_id else 0)


class Battle(models.Model):
    """A battle in the kingdom's battle log. Recording one never changes any unit."""

    class Outcome(models.TextChoices):
        VICTORY = "victory", "Victory"
        DEFEAT = "defeat", "Defeat"
        DRAW = "draw", "Draw"
        WITHDRAWAL = "withdrawal", "Withdrawal"

    FIELDS = ("name", "location", "date", "opponents", "outcome", "notes")

    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="battles")
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    date = models.CharField("in-game date", max_length=80, blank=True)
    opponents = models.TextField(blank=True)
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class Placement(models.Model):
    """A building on the urban grid. `block` is 0-8 left to right, top to bottom.

    `lot` is the building's top-left lot in its block: 0 top left, 1 top right, 2 bottom left,
    3 bottom right. Which lots it covers depends on its size and rotation.
    """

    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE, related_name="placements")
    building = models.CharField(max_length=80)
    block = models.PositiveSmallIntegerField()
    lot = models.PositiveSmallIntegerField()
    rotation = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["block", "lot", "id"]

    def __str__(self):
        return self.building


class Statistic(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="statistics")
    label = models.CharField(max_length=80)
    value = models.IntegerField(default=0)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name_plural = "statistics"

    def __str__(self):
        return self.label


class PlayerName(models.Model):
    """A display name shared across the app. It is protected once it has a password."""

    display_name = models.CharField(max_length=40)
    normalized_name = models.CharField(max_length=120, unique=True)
    password_hash = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name

    @property
    def is_protected(self):
        return bool(self.password_hash)


class HistoryEntry(models.Model):
    """A read-only record of one change. The application never edits or deletes these rows."""

    class Action(models.TextChoices):
        KINGDOM_CREATED = "kingdom_created", "Kingdom created"
        KINGDOM_EDITED = "kingdom_edited", "Kingdom sheet edited"
        STATISTIC_ADDED = "statistic_added", "Statistic added"
        STATISTIC_EDITED = "statistic_edited", "Statistic edited"
        STATISTIC_DELETED = "statistic_deleted", "Statistic deleted"
        SETTLEMENT_ADDED = "settlement_added", "Settlement added"
        SETTLEMENT_EDITED = "settlement_edited", "Settlement edited"
        SETTLEMENT_DELETED = "settlement_deleted", "Settlement deleted"
        BUILDING_PLACED = "building_placed", "Building placed"
        BUILDING_REMOVED = "building_removed", "Building removed"
        ARMY_ADDED = "army_added", "Army added"
        ARMY_EDITED = "army_edited", "Army edited"
        ARMY_DELETED = "army_deleted", "Army deleted"
        UNIT_ADDED = "unit_added", "Unit added"
        UNIT_EDITED = "unit_edited", "Unit edited"
        UNIT_DELETED = "unit_deleted", "Unit deleted"
        BATTLE_RECORDED = "battle_recorded", "Battle recorded"
        BATTLE_EDITED = "battle_edited", "Battle edited"
        BATTLE_DELETED = "battle_deleted", "Battle deleted"
        CHARACTER_ADDED = "character_added", "Character added"
        CHARACTER_EDITED = "character_edited", "Character edited"
        CHARACTER_DELETED = "character_deleted", "Character deleted"

    kingdom = models.ForeignKey(Kingdom, on_delete=models.PROTECT, related_name="history")
    action = models.CharField(max_length=32, choices=Action.choices)
    display_name = models.CharField(max_length=40)
    name_verified = models.BooleanField()
    # What the entry is about besides the kingdom, such as a statistic, settlement or unit.
    subject_id = models.PositiveBigIntegerField(null=True, blank=True)
    subject_label = models.CharField(max_length=120, blank=True)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "history entries"

    def __str__(self):
        return f"{self.get_action_display()} by {self.display_name}"
