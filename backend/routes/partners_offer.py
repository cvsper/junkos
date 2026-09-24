"""The partner request page's two endpoints. Public, signed.

A prospect's booking link is /partners/start?p=<id>&s=<sig>. The page asks
here who the link belongs to (and that records the open), and posts the
request back. Nothing here prices or books: it puts a fully-described
request in front of a person.
"""
from flask import Blueprint, jsonify, request

from models import db, CallProspect

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

partners_bp = Blueprint("partners_offer", __name__)
_rl = limiter.limit("60 per hour; 10 per minute") if limiter is not None else (lambda f: f)


def _prospect():
    from first_job import check_sig
    pid = (request.args.get("p") or (request.get_json(silent=True) or {}).get("p") or "").strip()
    sig = (request.args.get("s") or (request.get_json(silent=True) or {}).get("s") or "").strip()
    if not pid or not check_sig(pid, sig):
        return None
    return db.session.get(CallProspect, pid)


@partners_bp.route("/api/partners/offer", methods=["GET"])
@_rl
def partner_offer():
    from first_job import offer_info, record_open
    p = _prospect()
    if p is None:
        return jsonify({"error": "This link isn't valid. Text the desk and we'll send a fresh one."}), 404
    record_open(p)
    return jsonify(offer_info(p)), 200


@partners_bp.route("/api/partners/request", methods=["POST"])
@_rl
def partner_request():
    from first_job import pickup_request
    p = _prospect()
    if p is None:
        return jsonify({"error": "This link isn't valid. Text the desk and we'll send a fresh one."}), 404
    cb, why = pickup_request(p, request.get_json(silent=True) or {})
    if cb is None:
        return jsonify({"error": why}), 400
    from first_job import offer_info
    info = offer_info(p)
    return jsonify({"ok": True, "request_id": cb.id, "desk_number": info["desk_number"], "va_name": info["va_name"]}), 200
