import io
import warnings

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000


class UploadError(ValueError):
    pass


class ImageUpload:
    """An in-memory photo with controlled access to its upload state."""

    def __init__(self, content: bytes, filename: str, mime_type: str = "") -> None:
        self.set_content(content)
        self.set_filename(filename)
        self.set_mime_type(mime_type)

    def get_content(self) -> bytes:
        return self._content

    def set_content(self, content: bytes) -> None:
        if not isinstance(content, bytes):
            raise TypeError("Image content must be bytes.")
        self._content = content
        self._mime_type = ""

    def get_filename(self) -> str:
        return self._filename

    def set_filename(self, filename: str) -> None:
        if not isinstance(filename, str):
            raise TypeError("Image filename must be a string.")
        self._filename = filename
        self._mime_type = ""

    def get_mime_type(self) -> str:
        return self._mime_type

    def set_mime_type(self, mime_type: str) -> None:
        if mime_type not in {"", "image/png", "image/jpeg"}:
            raise ValueError("Image MIME type must be PNG or JPEG.")
        self._mime_type = mime_type

    # Properties preserve the attribute interface used by the UI and clients.
    content = property(get_content, set_content)
    filename = property(get_filename, set_filename)
    mime_type = property(get_mime_type, set_mime_type)

    @property
    def size_bytes(self):
        return len(self.content)

    def validate(self) -> bool:
        if not self.content:
            raise UploadError("This image is empty. Choose another JPG or PNG photo.")
        if self.size_bytes > MAX_BYTES:
            raise UploadError("Your photo is too large. Choose an image of 10 MB or less.")
        extension = self.filename.rsplit(".", 1)[-1].lower()
        if extension not in {"jpg", "jpeg", "png"}:
            raise UploadError("Choose a JPG, JPEG or PNG image.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(self.content)) as image:
                    expected = "PNG" if extension == "png" else "JPEG"
                    if image.format != expected:
                        raise UploadError("The file contents do not match its image extension.")
                    if image.width * image.height > MAX_PIXELS:
                        raise UploadError("This image has too many pixels. Resize it below 25 megapixels.")
                    self.mime_type = "image/png" if image.format == "PNG" else "image/jpeg"
                    image.verify()
                with Image.open(io.BytesIO(self.content)) as image:
                    image.load()
        except UploadError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise UploadError("We could not read this image. Try another JPG or PNG photo.") from exc
        return True
