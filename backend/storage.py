"""
Unified file storage abstraction for Umuve.

If AWS_S3_BUCKET is set, files are uploaded to S3.
Otherwise, files are saved locally to backend/uploads/ (dev fallback).

Audit F22 — trust boundary for uploads:
- the server decides the MIME type by *content*, never from the client
- images are opened + verified with Pillow, bounded in bytes/dimensions/
  pixels, then re-encoded to JPEG or PNG (drops EXIF/GPS and any trailing
  payload); PDFs are accepted only by magic bytes and only for document
  uploads
- private documents (onboarding prefix) never get a public URL: locally
  they live outside the public ``/uploads`` folder and are served by the
  authenticated ``/api/documents/...`` endpoint; on S3 they are read through
  short-lived presigned URLs (``presigned_url``)
"""

import io
import logging
import os
from dataclasses import dataclass

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read from environment)
# ---------------------------------------------------------------------------
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "us-east-1")

LOCAL_UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads"
)
# Private documents live OUTSIDE the publicly served folder.
LOCAL_PRIVATE_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "private_uploads"
)

MAX_UPLOAD_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_DIM = int(os.environ.get("UPLOAD_MAX_IMAGE_DIM", "8000"))
MAX_IMAGE_PIXELS = int(os.environ.get("UPLOAD_MAX_IMAGE_PIXELS", str(40_000_000)))
JPEG_QUALITY = 88
PRESIGN_EXPIRES = int(os.environ.get("DOCUMENT_URL_TTL_SECONDS", "300"))

# Prefixes whose objects are private documents (license / insurance /
# registration). Anything else is a job/booking photo.
PRIVATE_PREFIXES = {"onboarding", "documents", "private"}

IMAGE_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png")}


class UploadValidationError(ValueError):
    """Raised when an upload is not a safe image / PDF of acceptable size."""


@dataclass
class NormalizedUpload:
    data: bytes
    ext: str            # server-chosen: jpg | png | pdf
    content_type: str   # server-chosen
    kind: str           # image | pdf
    width: int = 0
    height: int = 0


def _use_s3():
    """Return True if S3 is configured and should be used."""
    return bool(AWS_S3_BUCKET)


def _get_s3_client():
    """Return a boto3 S3 client configured from environment variables."""
    import boto3

    kwargs = {"region_name": AWS_S3_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

    return boto3.client("s3", **kwargs)


# ---------------------------------------------------------------------------
# Content sniffing + normalisation
# ---------------------------------------------------------------------------
def sniff_kind(data):
    """'image' | 'pdf' | None from magic bytes only."""
    head = data[:16]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):          # JPEG
        return "image"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):      # PNG
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image"
    if head[:4] in (b"II*\x00", b"MM\x00*"):      # TIFF
        return "image"
    if head.startswith(b"BM"):                    # BMP
        return "image"
    return None


def _declared_kind(filename):
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext == "pdf":
        return "pdf"
    if ext in ("jpg", "jpeg", "png", "webp", "gif", "heic", "heif", "bmp", "tif", "tiff"):
        return "image"
    return None


def normalize_image(data):
    """Open, verify and re-encode ``data``. Returns NormalizedUpload.

    Re-encoding through Pillow strips EXIF (GPS, device ids) and any bytes
    appended after the image end marker.
    """
    from PIL import Image, ImageFile, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()                    # structural check, no decode
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if width <= 0 or height <= 0:
            raise UploadValidationError("image has no pixels")
        if width > MAX_IMAGE_DIM or height > MAX_IMAGE_DIM:
            raise UploadValidationError(
                "image dimensions exceed {}px".format(MAX_IMAGE_DIM))
        if width * height > MAX_IMAGE_PIXELS:
            raise UploadValidationError("image has too many pixels")
        img.load()                        # full decode (bomb-guarded above)
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info)
        out = io.BytesIO()
        if has_alpha:
            img.convert("RGBA").save(out, format="PNG", optimize=True)
            fmt = "PNG"
        else:
            img.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            fmt = "JPEG"
    except UploadValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise UploadValidationError("file is not a valid image") from exc
    ext, ctype = IMAGE_FORMATS[fmt]
    return NormalizedUpload(out.getvalue(), ext, ctype, "image", width, height)


def _read_capped(file, max_bytes):
    file.seek(0)
    data = file.read(max_bytes + 1)
    file.seek(0)
    if data is None:
        data = b""
    if len(data) > max_bytes:
        raise UploadValidationError(
            "file exceeds maximum size of {} MB".format(max_bytes // (1024 * 1024)))
    if not data:
        raise UploadValidationError("empty file")
    return data


def validate_upload(file, kind=None, filename=None, max_bytes=None):
    """Validate + normalise an uploaded file by content.

    kind: "image" (photos — only images accepted), "document" (images or
    PDF), or None to derive the expectation from the declared extension.
    The sniffed content must match the declared category or the upload is
    rejected ("MIME spoof").
    """
    max_bytes = max_bytes or MAX_UPLOAD_BYTES
    data = _read_capped(file, max_bytes)
    sniffed = sniff_kind(data)
    if sniffed is None:
        raise UploadValidationError("unsupported file content (expected an image or PDF)")

    name = filename or getattr(file, "filename", None) or ""
    declared = _declared_kind(name)
    if declared is not None and declared != sniffed:
        raise UploadValidationError(
            "file content ({}) does not match its extension".format(sniffed))

    if kind is None:
        kind = "document" if declared == "pdf" else "image"
    if kind == "image":
        if sniffed != "image":
            raise UploadValidationError("only image files are accepted here")
        return normalize_image(data)
    if kind == "document":
        if sniffed == "pdf":
            return NormalizedUpload(data, "pdf", "application/pdf", "pdf")
        return normalize_image(data)
    raise UploadValidationError("unknown upload kind {!r}".format(kind))


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
def save_file(file, prefix="uploads", filename=None, kind=None, private=None):
    """Validate, normalise and store a file; return its access URL/path.

    Parameters
    ----------
    file : werkzeug.datastructures.FileStorage (or any .read()/.seek() object)
    prefix : S3 key prefix / logical folder. ``onboarding`` etc. are private.
    filename : declared name (only its extension is consulted, for
        mismatch detection). The stored name is always a fresh UUID plus the
        server-chosen extension.
    kind : "image" | "document" | None (derive from declared extension)
    private : force private storage; defaults to ``prefix in PRIVATE_PREFIXES``

    Raises UploadValidationError when the content is not a safe image/PDF.

    Returns the public URL for photos, or — for private documents — the S3
    object URL (bucket must not be world-readable; use ``presigned_url``)
    or the authenticated local path ``/api/documents/file/<name>``.
    """
    from models import generate_uuid

    declared_name = filename or getattr(file, "filename", None) or ""
    normalized = validate_upload(file, kind=kind, filename=declared_name)
    if private is None:
        private = (prefix or "").strip("/").split("/")[0] in PRIVATE_PREFIXES

    safe_name = secure_filename("{}.{}".format(generate_uuid(), normalized.ext))

    if _use_s3():
        return _save_to_s3(normalized, safe_name, prefix)
    return _save_locally(normalized, safe_name, private)


def _save_to_s3(normalized, safe_name, prefix):
    """Upload bytes to S3 with the server-selected content type."""
    s3 = _get_s3_client()
    key = "{}/{}".format(prefix.strip("/"), safe_name) if prefix else safe_name

    s3.upload_fileobj(
        io.BytesIO(normalized.data),
        AWS_S3_BUCKET,
        key,
        ExtraArgs={
            "ContentType": normalized.content_type,
            "ContentDisposition": "inline; filename=\"{}\"".format(safe_name),
        },
    )

    url = "https://{}.s3.{}.amazonaws.com/{}".format(
        AWS_S3_BUCKET, AWS_S3_REGION, key
    )
    logger.info("Uploaded %s to S3: %s", safe_name, url)
    return url


def _save_locally(normalized, safe_name, private=False):
    """Write bytes under the public or private local folder."""
    folder = LOCAL_PRIVATE_FOLDER if private else LOCAL_UPLOAD_FOLDER
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, safe_name)
    with open(filepath, "wb") as fh:
        fh.write(normalized.data)
    if private:
        url = "/api/documents/file/{}".format(safe_name)
    else:
        url = "/uploads/{}".format(safe_name)
    logger.debug("Saved %s locally: %s", safe_name, filepath)
    return url


# ---------------------------------------------------------------------------
# Private document delivery helpers
# ---------------------------------------------------------------------------
def s3_key_from_url(url):
    """Object key when ``url`` points at OUR bucket, else None."""
    if not url or not AWS_S3_BUCKET or not url.startswith("https://"):
        return None
    host_part = "{}.s3".format(AWS_S3_BUCKET)
    if host_part not in url.split("/", 3)[2]:
        return None
    key = url.split(".amazonaws.com/", 1)[-1]
    return key if key and key != url else None


def presigned_url(stored_url, expires=None):
    """Short-lived GET URL for an object in our bucket, or None."""
    key = s3_key_from_url(stored_url)
    if not key:
        return None
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": AWS_S3_BUCKET, "Key": key},
        ExpiresIn=expires or PRESIGN_EXPIRES,
    )


def local_private_path(name):
    """Absolute path of a private local document, or None if absent/unsafe."""
    safe = secure_filename(name or "")
    if not safe:
        return None
    path = os.path.join(LOCAL_PRIVATE_FOLDER, safe)
    return path if os.path.isfile(path) else None


def local_private_name(stored_url):
    """Basename when ``stored_url`` is a local private document path."""
    if stored_url and stored_url.startswith("/api/documents/file/"):
        return stored_url.rsplit("/", 1)[-1]
    return None
