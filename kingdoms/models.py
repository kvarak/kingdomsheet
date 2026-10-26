from django.db import models
from django.db.models import Q


class Kingdom(models.Model):
    access_code = models.CharField(max_length=64, unique=True, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        KINGDOM_EDITED = "kingdom_edited", "Kingdom details edited"
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

    @property
    def attribution(self):
        return "password-verified" if self.name_verified else "unverified"
