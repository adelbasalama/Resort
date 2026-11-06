import io

import pytest
from PIL import Image

from waste_sorting.uploads import ImageUpload, MAX_BYTES, UploadError


def test_valid_png(image):
    assert image.validate()
    assert image.mime_type == "image/png"


@pytest.mark.parametrize("extension", ["jpg", "jpeg", "JPG"])
def test_jpeg(extension):
    content = io.BytesIO()
    Image.new("RGB", (20, 20)).save(content, "JPEG")
    upload = ImageUpload(content.getvalue(), f"item.{extension}")
    assert upload.validate() and upload.mime_type == "image/jpeg"


@pytest.mark.parametrize("content,name", [
    (b"", "empty.png"), (b"not a photo", "fake.png"),
    (b"<svg></svg>", "image.svg"), (b"x" * (MAX_BYTES + 1), "large.jpg"),
], ids=["empty", "invalid", "unsupported", "oversized"])
def test_bad_uploads(content, name):
    with pytest.raises(UploadError):
        ImageUpload(content, name).validate()


def test_disguised_extension(image):
    image.filename = "fake.jpg"
    with pytest.raises(UploadError, match="extension"):
        image.validate()


def test_corrupt_png(image):
    image.content = image.content[:35]
    with pytest.raises(UploadError):
        image.validate()
