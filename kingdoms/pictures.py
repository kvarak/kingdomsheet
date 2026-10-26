"""NPC pictures: every upload is checked, downscaled and re-encoded before it is stored.

Storing small WebP files keeps disk, memory and bandwidth low on a Raspberry Pi. Re-encoding
also strips metadata such as GPS positions from phone photos.
"""

import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Refuse huge images before decoding them, so one upload cannot exhaust the Pi's memory.
MAX_SOURCE_PIXELS = 40_000_000
MAX_SIDE = 512
QUALITY = 80
ALLOWED_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}
CONTENT_TYPE = "image/webp"


def downscale(upload):
    """Return the upload as a WebP no larger than MAX_SIDE, or raise ValidationError."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"Pictures can be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(upload) as image:
            if image.format not in ALLOWED_FORMATS:
                raise ValidationError("Upload a JPEG, PNG, GIF or WebP picture.")
            if image.width * image.height > MAX_SOURCE_PIXELS:
                raise ValidationError("That picture is too large. Use a smaller one.")
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            output = BytesIO()
            image.save(output, format="WEBP", quality=QUALITY)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValidationError("That file is not a picture we can read.") from error
    return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.webp")
