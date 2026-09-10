"""
File Upload API routes for Umuve.
Handles photo uploads for job documentation and authenticated delivery of
private operator documents (audit F22).
"""

import os
from flask import Blueprint, request, jsonify, send_from_directory, redirect
from werkzeug.utils import secure_filename

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Contractor
from auth_routes import require_auth
import storage
from storage import (
    save_file, UploadValidationError, presigned_url, local_private_path,
    local_private_name, s3_key_from_url,
)
from extensions import limiter

upload_bp = Blueprint("upload", __name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 10


def _allowed_file(filename):
    """Check if a filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.app_errorhandler(UploadValidationError)
def _upload_validation_error(exc):
    """Any route that calls storage.save_file gets a clean 400, never a 500."""
    return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# POST /api/upload/photos  (auth required)
# ---------------------------------------------------------------------------
@upload_bp.route("/api/upload/photos", methods=["POST"])
@limiter.limit("5 per minute")
@require_auth
def upload_photos(user_id):
    """
    Upload one or more photos (multipart/form-data).

    Form field: files (multiple)
    Constraints:
        - Max 10 files per request
        - Max 10 MB per file
        - Allowed types: jpg, jpeg, png, webp — decided by CONTENT, not the
          declared name/MIME. Images are re-encoded (EXIF stripped) so the
          stored file is always a plain JPEG or PNG.
    Returns: { success, urls: [ ... ] }
    """
    if "files" not in request.files:
        return jsonify({"error": "No files provided. Use the 'files' form field."}), 400

    files = request.files.getlist("files")

    if len(files) == 0:
        return jsonify({"error": "No files provided"}), 400

    if len(files) > MAX_FILES:
        return jsonify({"error": "Maximum {} files allowed per upload".format(MAX_FILES)}), 400

    urls = []
    errors = []

    for file in files:
        if not file or not file.filename:
            errors.append({"file": "unknown", "error": "Empty file"})
            continue

        if not _allowed_file(file.filename):
            errors.append({
                "file": file.filename,
                "error": "File type not allowed. Accepted: jpg, png, webp",
            })
            continue

        try:
            url = save_file(file, prefix="uploads", filename=file.filename, kind="image")
        except UploadValidationError as exc:
            errors.append({"file": file.filename, "error": str(exc)})
            continue
        urls.append(url)

    response = {"success": True, "urls": urls}
    if errors:
        response["errors"] = errors

    status_code = 201 if urls else 400
    if not urls and errors:
        response["success"] = False
        response["error"] = "No files were uploaded successfully"

    return jsonify(response), status_code


# ---------------------------------------------------------------------------
# GET /uploads/<filename>  (public -- serve uploaded PHOTOS only)
# ---------------------------------------------------------------------------
@upload_bp.route("/uploads/<filename>", methods=["GET"])
def serve_upload(filename):
    """Serve a previously uploaded public photo (never a private document)."""
    safe_name = secure_filename(filename)
    folder = storage.LOCAL_UPLOAD_FOLDER
    if not safe_name or not os.path.isfile(os.path.join(folder, safe_name)):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(folder, safe_name)


# ---------------------------------------------------------------------------
# Private documents: authenticated, short-lived delivery
# ---------------------------------------------------------------------------
_DOC_ATTRS = {
    "insurance": "insurance_document_url",
    "drivers_license": "drivers_license_url",
    "vehicle_registration": "vehicle_registration_url",
    # legacy columns still populated by /api/drivers registration
    "license": "license_url",
    "insurance_legacy": "insurance_url",
}


def _can_view_contractor_docs(user_id, contractor):
    user = db.session.get(User, user_id)
    if not user:
        return False
    if user.role == "admin":
        return True
    return contractor is not None and contractor.user_id == user_id


def _deliver(stored_url):
    """302 to a presigned S3 URL, or stream a local private file."""
    if not stored_url:
        return jsonify({"error": "Document not on file"}), 404
    if s3_key_from_url(stored_url):
        signed = presigned_url(stored_url)
        if signed:
            resp = redirect(signed, code=302)
            resp.headers["Cache-Control"] = "no-store"
            return resp
    name = local_private_name(stored_url) or (
        stored_url.rsplit("/", 1)[-1] if stored_url.startswith("/uploads/") else None
    )
    if name:
        path = local_private_path(name)
        folder = storage.LOCAL_PRIVATE_FOLDER
        if path is None and os.path.isfile(os.path.join(storage.LOCAL_UPLOAD_FOLDER, secure_filename(name))):
            # Documents uploaded before the private folder existed.
            folder = storage.LOCAL_UPLOAD_FOLDER
            path = os.path.join(folder, secure_filename(name))
        if path:
            resp = send_from_directory(folder, os.path.basename(path), as_attachment=False)
            resp.headers["Cache-Control"] = "no-store"
            return resp
    return jsonify({"error": "Document not available"}), 404


@upload_bp.route("/api/documents/contractor/<contractor_id>/<doc_type>", methods=["GET"])
@require_auth
def get_contractor_document(user_id, contractor_id, doc_type):
    """Admin or the contractor themself: fetch one onboarding document."""
    attr = _DOC_ATTRS.get(doc_type)
    if not attr:
        return jsonify({"error": "Unknown document type"}), 404
    contractor = db.session.get(Contractor, contractor_id)
    if not contractor or not _can_view_contractor_docs(user_id, contractor):
        # 404 for both missing and forbidden: don't confirm contractor ids.
        return jsonify({"error": "Not found"}), 404
    return _deliver(getattr(contractor, attr, None))


@upload_bp.route("/api/documents/file/<name>", methods=["GET"])
@require_auth
def get_private_file(user_id, name):
    """Local-storage fallback: serve a private file to admin or its owner."""
    safe = secure_filename(name)
    if not safe:
        return jsonify({"error": "Not found"}), 404
    stored = "/api/documents/file/{}".format(safe)
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404
    if user.role != "admin":
        owner = user.contractor_profile
        owned = owner is not None and any(
            getattr(owner, attr, None) == stored for attr in _DOC_ATTRS.values()
        )
        if not owned:
            return jsonify({"error": "Not found"}), 404
    return _deliver(stored)
