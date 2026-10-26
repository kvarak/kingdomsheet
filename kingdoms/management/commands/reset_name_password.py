from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from kingdoms.forms import PASSWORD_MIN_LENGTH
from kingdoms.models import PlayerName
from kingdoms.names import normalize_name


class Command(BaseCommand):
    help = "Set a new password for a player name, for players who lost theirs."

    def add_arguments(self, parser):
        parser.add_argument("name", help="The player name, matched like the name page does.")

    def handle(self, *args, name, **options):
        player = PlayerName.objects.filter(normalized_name=normalize_name(name)).first()
        if player is None:
            raise CommandError(f"No player name matches {name!r}.")

        password = getpass(f"New password for {player.display_name}: ")
        if len(password) < PASSWORD_MIN_LENGTH:
            raise CommandError(f"The password must be at least {PASSWORD_MIN_LENGTH} characters.")
        if getpass("Repeat the password: ") != password:
            raise CommandError("The passwords do not match.")

        player.password_hash = make_password(password)
        player.save(update_fields=["password_hash"])
        self.stdout.write(self.style.SUCCESS(f"Password reset for {player.display_name}."))
