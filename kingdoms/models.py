from django.db import models
from django.db.models import Q

from . import pf2e


class Kingdom(models.Model):
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

    control_dc_base = models.IntegerField(default=14)
    control_dc_size = models.IntegerField(default=0)
    unrest = models.IntegerField(default=0)
    unrest_penalty = models.IntegerField(default=0)
    consumption = models.IntegerField(default=0)

    farmlands = models.IntegerField(default=0)
    lumber_camps = models.IntegerField(default=0)
    mines = models.IntegerField(default=0)
    quarries = models.IntegerField(default=0)
    trade_agreements = models.IntegerField(default=0)
    event_check_dc = models.IntegerField(default=0)

    # Edit lock: only one protected name may edit at a time. See kingdoms.locks.
    editor = models.ForeignKey(
        "PlayerName", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    editor_expires_at = models.DateTimeField(null=True, blank=True)

    feats = models.TextField(blank=True)
    kingdom_abilities = models.TextField(blank=True)
    settlements = models.TextField(blank=True)
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
    ability = models.CharField(max_length=20, choices=pf2e.ABILITIES)
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
    skill = models.CharField(max_length=20, choices=[(key, label) for key, label, _ in pf2e.SKILLS])
    rank = models.IntegerField(default=0, choices=pf2e.PROFICIENCY_RANKS)
    status = models.IntegerField(default=0)
    circumstance = models.IntegerField(default=0)
    item = models.IntegerField(default=0)
    other = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kingdom", "skill"], name="unique_kingdom_skill"),
        ]

    def __str__(self):
        return self.get_skill_display()


class KingdomLeader(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="leaders")
    role = models.CharField(
        max_length=20, choices=[(key, label) for key, label, _ in pf2e.LEADERSHIP_ROLES]
    )
    character = models.CharField(max_length=80, blank=True)
    invested = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kingdom", "role"], name="unique_kingdom_role"),
        ]

    def __str__(self):
        return self.get_role_display()


class KingdomCommodity(models.Model):
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE, related_name="commodities")
    commodity = models.CharField(max_length=20, choices=pf2e.COMMODITIES)
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

    kingdom = models.ForeignKey(Kingdom, on_delete=models.PROTECT, related_name="history")
    action = models.CharField(max_length=32, choices=Action.choices)
    display_name = models.CharField(max_length=40)
    name_verified = models.BooleanField()
    statistic_id = models.PositiveBigIntegerField(null=True, blank=True)
    statistic_label = models.CharField(max_length=80, blank=True)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "history entries"

    def __str__(self):
        return f"{self.get_action_display()} by {self.display_name}"
