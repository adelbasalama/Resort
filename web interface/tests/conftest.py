import io

import pytest
from PIL import Image

from waste_sorting.storage import Repository
from waste_sorting.uploads import ImageUpload


@pytest.fixture
def image():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "green").save(buffer, format="PNG")
    return ImageUpload(buffer.getvalue(), "photo.png")


@pytest.fixture
def repository(tmp_path):
    return Repository(str(tmp_path / "test.sqlite3"))
