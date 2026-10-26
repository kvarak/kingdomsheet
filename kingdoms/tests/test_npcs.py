import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .. import pictures
from ..models import HistoryEntry, Kingdom, Npc
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


class NpcTests(TestCase):
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
        self.npcs_url = reverse("kingdoms:npcs", args=[self.kingdom.pk])

    def add_npc(self, client=None, name="Kesten Garess", picture=True):
        data = {"name": name}
        if picture:
            data["picture"] = image_upload()
        return (client or self.client).post(
            reverse("kingdoms:npc_add", args=[self.kingdom.pk]), data
        )

    def test_add_npc_with_picture_served_to_members_only(self):
        self.assertRedirects(self.add_npc(), self.npcs_url)
        npc = Npc.objects.get(name="Kesten Garess")
        self.assertTrue(npc.picture.name.endswith(".webp"))

        picture_url = reverse("kingdoms:npc_picture", args=[self.kingdom.pk, npc.pk])
        response = self.client.get(picture_url)
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(self.client_class().get(picture_url).status_code, 404)

        page = self.client.get(self.npcs_url)
        self.assertContains(page, picture_url)
        self.assertTrue(self.kingdom.history.filter(action=HistoryEntry.Action.NPC_ADDED).exists())

    def test_nav_links_to_npcs_on_kingdom_pages(self):
        response = self.client.get(reverse("kingdoms:sheet", args=[self.kingdom.pk]))
        self.assertContains(response, f'<a href="{self.npcs_url}">NPCs</a>', html=True)

    def test_unprotected_names_cannot_add_npcs(self):
        visitor = self.client_class()
        visitor.post(reverse("kingdoms:join_link", args=[self.kingdom.access_code]))
        visitor.post(reverse("kingdoms:names"), {"display_name": "Bob", "next": "/"})
        self.add_npc(client=visitor)
        self.assertFalse(Npc.objects.exists())

    def test_bad_picture_shows_an_error(self):
        response = self.client.post(
            reverse("kingdoms:npc_add", args=[self.kingdom.pk]),
            {"name": "Oleg", "picture": SimpleUploadedFile("x.jpg", b"not an image")},
        )
        self.assertContains(response, "not a picture", status_code=400)
        self.assertFalse(Npc.objects.exists())

    def test_leader_can_be_an_npc_from_this_kingdom_only(self):
        self.add_npc()
        npc = Npc.objects.get()
        edit_url = reverse("kingdoms:edit", args=[self.kingdom.pk])
        self.client.post(edit_url, sheet_post_data(self.kingdom, ruler_npc=npc))
        self.assertEqual(self.kingdom.leaders.get(role="ruler").npc, npc)

        page = self.client.get(reverse("kingdoms:sheet", args=[self.kingdom.pk]))
        self.assertContains(page, "Kesten Garess")
        self.assertContains(page, 'class="npc-avatar"')
        entry = self.kingdom.history.get(action=HistoryEntry.Action.KINGDOM_EDITED)
        self.assertEqual(entry.changes["Ruler npc"], {"old": None, "new": "Kesten Garess"})

        other = Kingdom.objects.create(name="Elsewhere", access_code="f" * 64)
        stranger = Npc.objects.create(kingdom=other, name="Spy")
        response = self.client.post(edit_url, sheet_post_data(self.kingdom, general_npc=stranger))
        self.assertContains(response, "General npc:", status_code=400)

    def test_rename_and_replace_picture(self):
        self.add_npc()
        npc = Npc.objects.get()
        old_file = npc.picture.name
        # Old files are deleted once the database change commits.
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("kingdoms:npc_edit", args=[self.kingdom.pk, npc.pk]),
                {f"npc{npc.pk}-name": "Kesten", f"npc{npc.pk}-picture": image_upload()},
            )
        npc.refresh_from_db()
        self.assertEqual(npc.name, "Kesten")
        self.assertNotEqual(npc.picture.name, old_file)
        self.assertFalse(npc.picture.storage.exists(old_file))

    def test_deleting_npc_vacates_leader_and_removes_picture(self):
        self.add_npc()
        npc = Npc.objects.get()
        self.kingdom.leaders.filter(role="ruler").update(npc=npc)
        storage, name = npc.picture.storage, npc.picture.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("kingdoms:npc_delete", args=[self.kingdom.pk, npc.pk]))
        self.assertIsNone(self.kingdom.leaders.get(role="ruler").npc)
        self.assertFalse(storage.exists(name))
