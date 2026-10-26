from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core.management import CommandError, call_command
from django.test import TestCase

from ..models import PlayerName

NEW_PASSWORD = "brandnew123"


class ResetNamePasswordTests(TestCase):
    def setUp(self):
        self.player = PlayerName.objects.create(
            display_name="Alice", normalized_name="alice", password_hash="old-hash"
        )

    def reset(self, name, *answers):
        with mock.patch(
            "kingdoms.management.commands.reset_name_password.getpass", side_effect=answers
        ):
            call_command("reset_name_password", name, stdout=mock.MagicMock())

    def test_sets_new_password_matching_name_loosely(self):
        self.reset("  ALICE ", NEW_PASSWORD, NEW_PASSWORD)
        self.player.refresh_from_db()
        self.assertTrue(check_password(NEW_PASSWORD, self.player.password_hash))

    def test_unknown_name_is_an_error(self):
        with self.assertRaisesMessage(CommandError, "No player name matches"):
            self.reset("Bob", NEW_PASSWORD, NEW_PASSWORD)

    def test_short_or_mismatched_password_changes_nothing(self):
        for answers in (("short", "short"), (NEW_PASSWORD, "different123")):
            with self.assertRaises(CommandError):
                self.reset("Alice", *answers)
        self.player.refresh_from_db()
        self.assertEqual(self.player.password_hash, "old-hash")
