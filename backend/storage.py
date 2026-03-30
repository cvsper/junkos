"""
Unified file storage abstraction for Umuve.

If AWS_S3_BUCKET is set, files are uploaded to S3.
Otherwise, files are saved locally to backend/uploads/ (dev fallback).
"""

import os
import logging

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


def save_file(file, prefix="uploads", filename=None):
    """Save a file and return its public URL.

    Parameters
    ----------
    file : werkzeug.datastructures.FileStorage
        The uploaded file object.
    prefix : str
        S3 key prefix or local subdirectory (default ``"uploads"``).
    filename : str | None
        The filename to use. If ``None``, uses ``file.filename``.

    Returns
    -------
    str
        The public URL of the saved file.
    """
    from models import generate_uuid

    name = filename or file.filename or "file"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
    unique_name = "{}.{}".format(generate_uuid(), ext)
    safe_name = secure_filename(unique_name)

    if _use_s3():
        return _save_to_s3(file, safe_name, prefix)
    else:
        return _save_locally(file, safe_name)


def _save_to_s3(file, safe_name, prefix):
    """Upload a file to S3 and return the public URL."""
    s3 = _get_s3_client()
    key = "{}/{}".format(prefix.strip("/"), safe_name) if prefix else safe_name

    # Determine content type
    content_type = file.content_type or "application/octet-stream"

    file.seek(0)
    s3.upload_fileobj(
        file,
        AWS_S3_BUCKET,
        key,
        ExtraArgs={
            "ContentType": content_type,
        },
    )

    url = "https://{}.s3.{}.amazonaws.com/{}".format(
        AWS_S3_BUCKET, AWS_S3_REGION, key
    )
    logger.info("Uploaded %s to S3: %s", safe_name, url)
    return url


def _save_locally(file, safe_name):
    """Save a file to the local uploads directory and return a relative URL."""
    if not os.path.exists(LOCAL_UPLOAD_FOLDER):
        os.makedirs(LOCAL_UPLOAD_FOLDER, exist_ok=True)

    filepath = os.path.join(LOCAL_UPLOAD_FOLDER, safe_name)
    file.seek(0)
    file.save(filepath)

    url = "/uploads/{}".format(safe_name)
    logger.debug("Saved %s locally: %s", safe_name, filepath)
    return url
