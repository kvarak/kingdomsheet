import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .. import pictures
from ..models import Army, Character, HistoryEntry, Kingdom, KingdomLeader, Unit
from .helpers import PASSWORD, PLAYER_NAME, sheet_post_data


def image_upload(size=(1600, 1200), image_format="JPEG", name="portrait.jpg"):
    buffer = BytesIO()
    Image.new("RGB", size, "darkgreen").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class PictureTests(SimpleTestCase):
    def test_large_picture_is_shrunk_to_webp(self):
        result = pictures.downscale(image_upload())
        self.assertTrue(result.name.endswith(".webp"))
        with Image.open(result) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.size, (512, 384))

    def test_non_images_are_refused(self):
        upload = SimpleUploadedFile("evil.jpg", b"<script>alert(1)</script>")
        with self.assertRaisesMessage(ValidationError, "not a picture"):
            pictures.downscale(upload)

    def test_unsupported_formats_are_refused(self):
        with self.assertRaisesMessage(ValidationError, "JPEG, PNG, GIF or WebP"):
            pictures.downscale(image_upload(image_format="BMP", name="x.bmp"))

    def test_huge_pictures_are_refused_before_decoding(self):
        buffer = BytesIO()
        Image.new("1", (6400, 6400)).save(buffer, format="PNG")
        upload = SimpleUploadedFile("huge.png", buffer.getvalue())
        with self.assertRaisesMessage(ValidationError, "too large"):
            pictures.downscale(upload)

    def test_oversized_uploads_are_refused(self):
        upload = SimpleUploadedFile("big.jpg", b"x" * (pictures.MAX_UPLOAD_BYTES + 1))
        with self.assertRaisesMessage(ValidationError, "at most"):
            pictures.downscale(upload)


class CharacterTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=self.media)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.client.post(
            reverse("kingdoms:names"),
            {"display_name": PLAYER_NAME, "password": PASSWORD, "next": "/"},
        )
        self.client.post(
            reverse("kingdoms:create"), {"name": "Stolen Lands", "description": "", "notes": ""}
        )
        self.kingdom = Kingdom.objects.get(name="Stolen Lands")
        self.characters_url = reverse("kingdoms:characters", args=[self.kingdom.pk])

    def add_character(self, client=None, name="Kesten Garess", kind="npc", picture=True):
        data = {"name": name, "kind": kind}
        if picture:
            data["picture"] = image_upload()
        return (client or self.client).post(
            reverse("kingdoms:character_add", args=[self.kingdom.pk]), data
        )

    def test_characters_list_every_role_they_hold(self):
        kesten = Character.objects.create(kingdom=self.kingdom, name="Kesten", kind="npc")
        Character.objects.create(kingdom=self.kingdom, name="Amiri", kind="pc")
        KingdomLeader.objects.filter(kingdom=self.kingdom, role__in=["general", "ruler"]).update(
            character=kesten
        )
        army = Army.objects.create(kingdom=self.kingdom, name="Ravagers", commander=kesten)
        Unit.objects.create(army=army, name="Pikes", hero=kesten)
        page = self.client.get(self.characters_url).content.decode()
        army_url = reverse("kingdoms:army", args=[self.kingdom.pk, army.pk])
        roles = [
            '<a href="{}">Ruler</a>'.format(reverse("kingdoms:sheet", args=[self.kingdom.pk])),
            ">General</a>",
            f'<a href="{army_url}">Commander of Ravagers</a>',
            f'<a href="{army_url}">Hero of Pikes (Ravagers)</a>',
        ]
        positions = [page.index(role) for role in roles]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(page.count("No roles"), 1)

    def test_add_character_with_picture_served_to_members_only(self):
        self.assertRedirects(self.add_character(), self.characters_url)
        character = Character.objects.get(name="Kesten Garess")
        self.assertTrue(character.picture.name.endswith(".webp"))

        picture_url = reverse("kingdoms:character_picture", args=[self.kingdom.pk, character.pk])
        response = self.client.get(picture_url)
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(self.client_class().get(picture_url).status_code, 404)

        page = self.client.get(self.characters_url)
        self.assertContains(page, picture_url)
        self.assertTrue(
            self.kingdom.history.filter(action=HistoryEntry.Action.CHARACTER_ADDED).exists()
        )

    def test_kingdom_box_links_to_characters(self):
        for name in ("kingdoms:sheet", "kingdoms:edit"):
            response = self.client.get(reverse(name, args=[self.kingdom.pk]))
            self.assertContains(
                response, f'<a href="{self.characters_url}">Characters</a>', html=True
            )
        history = self.client.get(reverse("kingdoms:history", args=[self.kingdom.pk]))
        self.assertNotContains(history, self.characters_url)

    def test_unprotected_names_cannot_add_characters(self):
        visitor = self.client_class()
        visitor.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        visitor.post(reverse("kingdoms:names"), {"display_name": "Bob", "next": "/"})
        self.add_character(client=visitor)
        self.assertFalse(Character.objects.exists())

    def test_bad_picture_shows_an_error(self):
        response = self.client.post(
            reverse("kingdoms:character_add", args=[self.kingdom.pk]),
            {
                "name": "Oleg",
                "kind": "npc",
                "picture": SimpleUploadedFile("x.jpg", b"not an image"),
            },
        )
        self.assertContains(response, "not a picture", status_code=400)
        self.assertFalse(Character.objects.exists())

    def test_leader_can_be_a_character_from_this_kingdom_only(self):
        self.add_character()
        character = Character.objects.get()
        edit_url = reverse("kingdoms:edit", args=[self.kingdom.pk])
        self.client.post(edit_url, sheet_post_data(self.kingdom, ruler_character=character))
        self.assertEqual(self.kingdom.leaders.get(role="ruler").character, character)

        page = self.client.get(reverse("kingdoms:sheet", args=[self.kingdom.pk]))
        self.assertContains(page, "Kesten Garess")
        self.assertContains(page, 'class="character-avatar"')
        entry = self.kingdom.history.get(action=HistoryEntry.Action.KINGDOM_EDITED)
        self.assertEqual(entry.changes["Ruler character"], {"old": None, "new": "Kesten Garess"})

        other = Kingdom.objects.create(name="Elsewhere", access_code="f" * 64)
        stranger = Character.objects.create(kingdom=other, name="Spy")
        response = self.client.post(
            edit_url, sheet_post_data(self.kingdom, general_character=stranger)
        )
        self.assertContains(response, "General character:", status_code=400)

    def test_rename_and_replace_picture(self):
        self.add_character()
        character = Character.objects.get()
        old_file = character.picture.name
        # Old files are deleted once the database change commits.
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("kingdoms:character_edit", args=[self.kingdom.pk, character.pk]),
                {
                    f"character{character.pk}-name": "Kesten",
                    f"character{character.pk}-kind": "pc",
                    f"character{character.pk}-picture": image_upload(),
                },
            )
        character.refresh_from_db()
        self.assertEqual((character.name, character.kind), ("Kesten", "pc"))
        self.assertNotEqual(character.picture.name, old_file)
        self.assertFalse(character.picture.storage.exists(old_file))

    def test_deleting_character_vacates_leader_and_hides_picture(self):
        self.add_character()
        character = Character.objects.get()
        self.kingdom.leaders.filter(role="ruler").update(character=character)
        storage, name = character.picture.storage, character.picture.name
        picture_url = reverse("kingdoms:character_picture", args=[self.kingdom.pk, character.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("kingdoms:character_delete", args=[self.kingdom.pk, character.pk])
            )
        self.assertIsNone(self.kingdom.leaders.get(role="ruler").character)
        # Kept so the character can be restored from the history, but no longer served.
        self.assertTrue(storage.exists(name))
        self.assertEqual(self.client.get(picture_url).status_code, 404)

    def test_leader_dropdown_lists_pcs_and_npcs_without_free_text(self):
        self.add_character(name="Kesten Garess", kind="npc", picture=False)
        self.add_character(name="Amiri", kind="pc", picture=False)
        page = self.client.get(reverse("kingdoms:edit", args=[self.kingdom.pk])).content.decode()
        self.assertIn('<select name="ruler_character"', page)
        self.assertIn(">Amiri</option>", page)
        self.assertIn(">Kesten Garess</option>", page)
        self.assertIn(">Vacant</option>", page)
        self.assertNotIn('<input type="text" name="ruler_character"', page)
