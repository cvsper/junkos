"""
Operator document verification engine.

Closes the vetting hole: previously a hauler uploaded insurance / driver's
license / vehicle registration images and **self-typed** the expiry dates, and
an admin approved them by eyeballing. Nothing checked that the file was the
right kind of document, that it wasn't expired, or that the name matched.

This module runs an automated check on each uploaded document:

  1. A vision model reads the image and returns structured fields
     (document kind, full name, expiration date, policy/license number, ...).
  2. A deterministic rule engine turns those fields into a verdict:
       - verified      : correct doc type, legible, not expired, name matches
       - needs_review  : ambiguous (low confidence, name mismatch, no date) ->
                         a human looks, but with everything pre-extracted
       - rejected      : objectively bad (wrong document, or expired)
  3. The real expiry dates are written back to the Contractor from the
     document itself (no longer trusting self-reported dates), so the daily
     expiry sweep can suspend a hauler the moment a policy lapses.

Engine selection (no new infra — both keys already run in prod):
  - Prefer Anthropic Claude vision if ANTHROPIC_API_KEY is set.
  - Else fall back to OpenAI vision (the key that already powers photo analysis).
  - If neither is set, verification is skipped gracefully and documents are
    routed to manual review (we never auto-approve unverified docs).

Gate policy:
  - We NEVER auto-approve a hauler unless OPERATOR_DOC_AUTOAPPROVE=true AND
    every required document verified cleanly. The safe default is to extract +
    flag + route to a human for the final click.
"""

import base64
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REQUIRED_DOCS = ("insurance", "drivers_license", "vehicle_registration")

DOC_LABELS = {
    "insurance": "auto/commercial liability insurance",
    "drivers_license": "driver's license",
    "vehicle_registration": "vehicle registration",
}

# How close a name must match the applicant before we stop flagging it.
NAME_MATCH_THRESHOLD = 0.62
# Below this model-reported confidence, send to human review rather than trust.
MIN_CONFIDENCE = 0.45
# Warn (not fail) when a document expires within this many days.
EXPIRING_SOON_DAYS = int(os.environ.get("DOC_EXPIRING_SOON_DAYS", "21"))


def _enabled():
    return os.environ.get("OPERATOR_DOC_VERIFY_ENABLED", "true").lower() != "false"


def _autoapprove():
    return os.environ.get("OPERATOR_DOC_AUTOAPPROVE", "").lower() == "true"


def _anthropic_key():
    return os.environ.get("ANTHROPIC_API_KEY")


def _openai_key():
    return os.environ.get("OPENAI_API_KEY")


def _anthropic_model():
    return os.environ.get("DOC_VERIFY_ANTHROPIC_MODEL", "claude-haiku-4-5")


def _openai_model():
    # gpt-4o reads documents notably better than -mini; default up.
    return os.environ.get("DOC_VERIFY_OPENAI_MODEL", "gpt-4o")


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Image loading (handles both S3 https URLs and local /uploads paths)
# ---------------------------------------------------------------------------
def _load_image(url):
    """Return (raw_bytes, mime_type) for a stored document URL, or (None, None).

    Supports the two shapes storage.save_file produces: an https S3 URL, or a
    local "/uploads/<name>" relative path (dev fallback).
    """
    if not url:
        return None, None
    try:
        if url.startswith("http://") or url.startswith("https://"):
            # Prefer authenticated S3 read (handles a private bucket); fall back
            # to a plain HTTPS GET for any other host or if boto3 isn't usable.
            s3_data = _load_from_s3(url)
            if s3_data is not None:
                return s3_data, _guess_mime(url)
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "umuve-doc-verify"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                mime = r.headers.get("Content-Type") or _guess_mime(url)
                return data, mime
        # local path
        name = url.split("/uploads/", 1)[-1].lstrip("/") if "/uploads/" in url else os.path.basename(url)
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "uploads", name
        )
        if os.path.exists(path):
            with open(path, "rb") as fh:
                return fh.read(), _guess_mime(path)
    except Exception:
        logger.exception("doc-verify: failed to load image %s", url)
    return None, None


def _load_from_s3(url):
    """Read an object via boto3 when the URL points at our configured S3 bucket
    (works even if the bucket is private). Returns bytes or None to fall back."""
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket or bucket not in url:
        return None
    try:
        # Key is everything after the bucket host: ".../<bucket>.s3.../<key>"
        key = url.split(".amazonaws.com/", 1)[-1]
        if not key or key == url:
            return None
        import boto3
        region = os.environ.get("AWS_S3_REGION", "us-east-1")
        kwargs = {"region_name": region}
        ak, sk = os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY")
        if ak and sk:
            kwargs["aws_access_key_id"] = ak
            kwargs["aws_secret_access_key"] = sk
        s3 = boto3.client("s3", **kwargs)
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    except Exception:
        logger.warning("doc-verify: S3 read failed for %s, falling back to HTTP", url)
        return None


def _guess_mime(name):
    n = (name or "").lower()
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".webp"):
        return "image/webp"
    if n.endswith(".pdf"):
        return "application/pdf"
    return "image/jpeg"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
def _extraction_prompt(doc_type, expected_name):
    label = DOC_LABELS.get(doc_type, doc_type)
    return (
        "You are a document-verification assistant for a junk-removal marketplace "
        "vetting independent haulers. You are looking at ONE uploaded document that "
        "is supposed to be the hauler's {label}.\n\n"
        "Read the document carefully and return ONLY a JSON object (no markdown, no "
        "prose) with exactly these keys:\n"
        "{{\n"
        '  "document_kind": one of "insurance" | "drivers_license" | '
        '"vehicle_registration" | "other",  // what this document ACTUALLY is\n'
        '  "is_legible": boolean,            // can you read the key fields?\n'
        '  "full_name": string,             // person/business name on the document, "" if none\n'
        '  "expiration_date": string,       // ISO YYYY-MM-DD if shown, else ""\n'
        '  "effective_date": string,        // ISO YYYY-MM-DD if shown, else ""\n'
        '  "id_number": string,             // policy #, DL #, or plate/registration #, "" if none\n'
        '  "issuer": string,                // insurer / state / DMV, "" if none\n'
        '  "is_auto_or_commercial_liability": boolean, // ONLY meaningful for insurance; else false\n'
        '  "tampering_signs": boolean,      // obvious edits, mismatched fonts, screenshot of a screen\n'
        '  "confidence": number,            // 0..1, your overall confidence in this reading\n'
        '  "notes": string                  // one short sentence, anything an admin should know\n'
        "}}\n\n"
        "The hauler's name on file is: \"{name}\". Report full_name as printed on the "
        "document regardless. Dates MUST be ISO YYYY-MM-DD; if only month/year is "
        "shown use the last day of that month. If a field is absent, use \"\" (or "
        "false/0). Do not guess values that are not visible."
    ).format(label=label, name=expected_name or "(unknown)")


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------
def _call_anthropic(img_bytes, mime, prompt):
    from anthropic import Anthropic
    client = Anthropic(api_key=_anthropic_key())
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    if mime == "application/pdf":
        source_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }
    else:
        media_type = mime if mime in ("image/jpeg", "image/png", "image/webp", "image/gif") else "image/jpeg"
        source_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    resp = client.messages.create(
        model=_anthropic_model(),
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": [source_block, {"type": "text", "text": prompt}]}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts), "anthropic:" + _anthropic_model()


def _call_openai(img_bytes, mime, prompt):
    from openai import OpenAI
    client = OpenAI(api_key=_openai_key())
    if mime == "application/pdf":
        # gpt-4o vision can't ingest a raw PDF here; signal caller to route to review.
        raise ValueError("pdf_unsupported_openai")
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    data_uri = "data:{};base64,{}".format(
        mime if mime.startswith("image/") else "image/jpeg", b64
    )
    resp = client.chat.completions.create(
        model=_openai_model(),
        max_tokens=1024,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri, "detail": "high"}},
            ],
        }],
    )
    return (resp.choices[0].message.content or ""), "openai:" + _openai_model()


def _extract_fields(img_bytes, mime, prompt):
    """Run the available vision model; return (parsed_dict, engine, raw_text)."""
    last_err = None
    # Prefer Claude, fall back to OpenAI.
    attempts = []
    if _anthropic_key():
        attempts.append(_call_anthropic)
    if _openai_key():
        attempts.append(_call_openai)
    for fn in attempts:
        try:
            raw, engine = fn(img_bytes, mime, prompt)
            parsed = _parse_json(raw)
            if parsed is not None:
                return parsed, engine, raw
            last_err = "unparseable model output"
        except Exception as exc:
            last_err = str(exc)
            logger.warning("doc-verify: %s failed: %s", getattr(fn, "__name__", "model"), exc)
    return None, None, (last_err or "no vision model configured")


def _parse_json(raw):
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        # last-ditch: grab the outermost {...}
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------
def _parse_date(value):
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def _name_score(a, b):
    if not a or not b:
        return None
    a2 = re.sub(r"[^a-z ]", "", a.lower()).strip()
    b2 = re.sub(r"[^a-z ]", "", b.lower()).strip()
    if not a2 or not b2:
        return None
    # token-overlap OR sequence ratio, whichever is kinder (handles "Bob" vs
    # "Robert Smith", business-name-vs-person, middle names, etc.)
    ta, tb = set(a2.split()), set(b2.split())
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return max(overlap, SequenceMatcher(None, a2, b2).ratio())


def _evaluate(doc_type, fields, expected_name):
    """Turn extracted fields into (status, reasons, expiry_dt, name_score, confidence)."""
    reasons = []
    fields = fields or {}
    kind = (fields.get("document_kind") or "").lower()
    confidence = _coerce_float(fields.get("confidence"), default=0.0)
    expiry_dt = _parse_date(fields.get("expiration_date"))
    name_score = _name_score(fields.get("full_name"), expected_name)

    hard_fail = False
    needs_review = False

    # 1. Right kind of document for the slot?
    if kind and kind != "other" and kind != doc_type:
        reasons.append(
            "Uploaded a {} where a {} is required.".format(
                DOC_LABELS.get(kind, kind), DOC_LABELS.get(doc_type, doc_type)
            )
        )
        hard_fail = True
    elif kind in ("", "other"):
        reasons.append("Could not confirm this is a {}.".format(DOC_LABELS.get(doc_type, doc_type)))
        needs_review = True

    # 2. Legibility / tampering
    if fields.get("tampering_signs"):
        reasons.append("Possible tampering or a screenshot-of-a-screen — needs a human look.")
        needs_review = True
    if fields.get("is_legible") is False or confidence < MIN_CONFIDENCE:
        reasons.append("Document is hard to read (low confidence) — re-upload a clear photo.")
        needs_review = True

    # 3. Insurance must actually be auto/commercial liability
    if doc_type == "insurance" and kind == "insurance" and not fields.get("is_auto_or_commercial_liability"):
        reasons.append("Insurance doesn't look like auto/commercial liability coverage.")
        needs_review = True

    # 4. Expiry — the whole point
    if expiry_dt is None:
        reasons.append("No expiration date could be read from the document.")
        needs_review = True
    else:
        now = _now()
        if expiry_dt < now:
            reasons.append("EXPIRED on {}.".format(expiry_dt.date().isoformat()))
            hard_fail = True
        elif expiry_dt < now + timedelta(days=EXPIRING_SOON_DAYS):
            reasons.append("Expires soon — {}.".format(expiry_dt.date().isoformat()))

    # 5. Name match (informational for registration; vehicles can be owned by an LLC)
    if name_score is not None and name_score < NAME_MATCH_THRESHOLD:
        msg = "Name on document doesn't clearly match the applicant."
        reasons.append(msg)
        if doc_type == "drivers_license":
            needs_review = True  # for a DL, identity mismatch matters more

    if hard_fail:
        status = "rejected"
    elif needs_review:
        status = "needs_review"
    else:
        status = "verified"
        if not reasons:
            reasons.append("All checks passed.")
    return status, reasons, expiry_dt, name_score, confidence


def _coerce_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Single-document verification
# ---------------------------------------------------------------------------
def verify_one(doc_type, url, expected_name):
    """Verify one document. Returns a result dict (never raises)."""
    result = {
        "doc_type": doc_type,
        "document_url": url,
        "status": "error",
        "reasons": [],
        "extracted": {},
        "expiry_date": None,
        "name_match_score": None,
        "confidence": None,
        "engine": None,
        "raw_excerpt": "",
    }
    if not url:
        result["status"] = "needs_review"
        result["reasons"] = ["No document uploaded."]
        return result

    img, mime = _load_image(url)
    if img is None:
        result["reasons"] = ["Could not load the uploaded file."]
        return result

    prompt = _extraction_prompt(doc_type, expected_name)
    fields, engine, raw = _extract_fields(img, mime, prompt)
    result["engine"] = engine
    result["raw_excerpt"] = (raw or "")[:1000]

    if fields is None:
        # PDF-on-openai or model failure -> human review, not a silent pass.
        result["status"] = "needs_review"
        result["reasons"] = ["Automated read unavailable ({}). Manual review needed.".format(raw[:120] if raw else "no engine")]
        return result

    status, reasons, expiry_dt, name_score, confidence = _evaluate(doc_type, fields, expected_name)
    result["status"] = status
    result["reasons"] = reasons
    result["extracted"] = fields
    result["expiry_date"] = expiry_dt
    result["name_match_score"] = name_score
    result["confidence"] = confidence
    return result


# ---------------------------------------------------------------------------
# Contractor-level orchestration
# ---------------------------------------------------------------------------
# Maps doc_type -> the Contractor URL attribute and expiry attribute.
_DOC_FIELDS = {
    "insurance": ("insurance_document_url", "insurance_expiry"),
    "drivers_license": ("drivers_license_url", "license_expiry"),
    "vehicle_registration": ("vehicle_registration_url", "vehicle_registration_expiry"),
}


def verify_contractor(app, contractor_id):
    """Verify all uploaded documents for a contractor, persist results, and
    update the contractor's verification summary + onboarding gate.

    Runs inside its own app context (safe to call from a background thread).
    Returns a summary dict.
    """
    with app.app_context():
        from models import db, Contractor, User, Notification, OperatorDocumentVerification, generate_uuid

        contractor = db.session.get(Contractor, contractor_id)
        if not contractor:
            return {"error": "contractor not found"}

        if not _enabled():
            logger.info("doc-verify disabled; skipping %s", contractor_id)
            return {"skipped": True, "reason": "OPERATOR_DOC_VERIFY_ENABLED=false"}

        user = contractor.user
        expected_name = (user.name if user else "") or ""

        contractor.documents_verification_status = "verifying"
        db.session.commit()

        per_doc = {}
        any_rejected = False
        any_review = False
        all_present = True

        for doc_type, (url_attr, expiry_attr) in _DOC_FIELDS.items():
            url = getattr(contractor, url_attr, None)
            if not url:
                all_present = False
            res = verify_one(doc_type, url, expected_name)
            per_doc[doc_type] = res

            # Persist / upsert the verification row.
            row = (
                db.session.query(OperatorDocumentVerification)
                .filter_by(contractor_id=contractor.id, doc_type=doc_type)
                .first()
            )
            if not row:
                row = OperatorDocumentVerification(
                    id=generate_uuid(), contractor_id=contractor.id, doc_type=doc_type
                )
                db.session.add(row)
            row.document_url = url
            row.status = res["status"]
            row.reasons = res["reasons"]
            row.extracted = res["extracted"]
            row.expiry_date = res["expiry_date"]
            row.name_match_score = res["name_match_score"]
            row.confidence = res["confidence"]
            row.engine = res["engine"]
            row.raw_excerpt = res["raw_excerpt"]

            # Write the REAL expiry back to the contractor (authoritative over self-report).
            if res["expiry_date"] is not None:
                setattr(contractor, expiry_attr, res["expiry_date"])

            if res["status"] == "rejected":
                any_rejected = True
            elif res["status"] != "verified":
                any_review = True

        # Overall verification status
        if not all_present:
            overall = "flagged"
            any_review = True
        elif any_rejected:
            overall = "failed"
        elif any_review:
            overall = "flagged"
        else:
            overall = "passed"

        contractor.documents_verification_status = overall
        contractor.documents_verified_at = _now()

        # ---- Apply the onboarding gate ----
        summary_reasons = _summarize(per_doc)
        if overall == "passed":
            if _autoapprove():
                contractor.onboarding_status = "approved"
                contractor.onboarding_completed_at = _now()
                contractor.approval_status = "approved"
                contractor.rejection_reason = None
                _notify_user(
                    db, Notification, generate_uuid, contractor,
                    "onboarding_approved", "You're approved!",
                    "Your documents passed verification. You can go online and accept jobs.",
                )
            else:
                contractor.onboarding_status = "under_review"
                _notify_admins(
                    db, User, Notification, generate_uuid, contractor,
                    "Docs verified — ready to approve",
                    "{}'s documents passed automated verification. One click to approve.".format(expected_name or "A hauler"),
                )
        elif overall == "failed":
            # Objective failure (expired / wrong document). Don't approve; tell
            # the hauler exactly what to fix. They can re-upload (resets status).
            contractor.onboarding_status = "rejected"
            contractor.rejection_reason = summary_reasons
            _notify_user(
                db, Notification, generate_uuid, contractor,
                "onboarding_rejected", "Document issue",
                "We couldn't verify your documents: {} Please re-upload.".format(summary_reasons),
            )
            _notify_admins(
                db, User, Notification, generate_uuid, contractor,
                "Docs failed verification",
                "{}: {}".format(expected_name or "A hauler", summary_reasons),
            )
        else:  # flagged -> human in the loop
            contractor.onboarding_status = "under_review"
            _notify_admins(
                db, User, Notification, generate_uuid, contractor,
                "Docs need review",
                "{} needs a manual check: {}".format(expected_name or "A hauler", summary_reasons),
            )

        contractor.updated_at = _now()
        db.session.commit()

        logger.info("doc-verify %s -> %s", contractor_id, overall)
        return {
            "contractor_id": contractor_id,
            "overall": overall,
            "autoapproved": overall == "passed" and _autoapprove(),
            "documents": {k: {"status": v["status"], "reasons": v["reasons"]} for k, v in per_doc.items()},
        }


def _summarize(per_doc):
    bits = []
    for doc_type, res in per_doc.items():
        if res["status"] != "verified":
            label = DOC_LABELS.get(doc_type, doc_type)
            why = "; ".join(res["reasons"][:2]) or res["status"]
            bits.append("{}: {}".format(label, why))
    return " | ".join(bits) or "see details"


def _notify_user(db, Notification, gen_id, contractor, ntype, title, body):
    try:
        db.session.add(Notification(
            id=gen_id(), user_id=contractor.user_id, type=ntype,
            title=title, body=body,
            data={"contractor_id": contractor.id},
        ))
    except Exception:
        logger.exception("doc-verify: user notify failed")


def _notify_admins(db, User, Notification, gen_id, contractor, title, body):
    try:
        for admin in User.query.filter_by(role="admin").all():
            db.session.add(Notification(
                id=gen_id(), user_id=admin.id, type="onboarding_verification",
                title=title, body=body,
                data={"contractor_id": contractor.id,
                      "verification_status": contractor.documents_verification_status},
            ))
    except Exception:
        logger.exception("doc-verify: admin notify failed")


# ---------------------------------------------------------------------------
# Daily expiry sweep (scheduler)
# ---------------------------------------------------------------------------
def run_expiry_sweep(app):
    """Suspend any active hauler whose insurance / license / registration has
    lapsed, and remind those expiring soon. Keeps the marketplace from ever
    dispatching an uninsured truck. Runs in its own app context.
    """
    with app.app_context():
        from models import db, Contractor, User, Notification, generate_uuid

        now = _now()
        soon = now + timedelta(days=EXPIRING_SOON_DAYS)
        checks = [
            ("insurance_expiry", "insurance"),
            ("license_expiry", "driver's license"),
            ("vehicle_registration_expiry", "vehicle registration"),
        ]

        # Only look at haulers who can currently take work.
        contractors = (
            db.session.query(Contractor)
            .filter(Contractor.approval_status == "approved")
            .all()
        )

        suspended, reminded = [], []
        for c in contractors:
            expired_docs, soon_docs = [], []
            for attr, label in checks:
                exp = getattr(c, attr, None)
                if exp is None:
                    continue
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    expired_docs.append((label, exp))
                elif exp < soon:
                    soon_docs.append((label, exp))

            if expired_docs:
                reason = "; ".join(
                    "{} expired {}".format(lbl, dt.date().isoformat()) for lbl, dt in expired_docs
                )
                c.is_online = False
                c.approval_status = "suspended"
                c.documents_verification_status = "failed"
                c.rejection_reason = "Coverage lapsed — {}".format(reason)
                c.updated_at = now
                _notify_user(
                    db, Notification, generate_uuid, c,
                    "account_suspended", "Action needed: coverage expired",
                    "Your {} — re-upload current documents to get back online.".format(reason),
                )
                _notify_admins(
                    db, User, Notification, generate_uuid, c,
                    "Hauler suspended — coverage lapsed",
                    "{}: {}".format((c.user.name if c.user else c.id), reason),
                )
                suspended.append(c.id)
            elif soon_docs:
                # Remind only on threshold days so we don't DM daily.
                days_left = min(int((dt - now).total_seconds() // 86400) for _, dt in soon_docs)
                if days_left in (EXPIRING_SOON_DAYS, 7, 3, 1):
                    reason = "; ".join(
                        "{} expires {}".format(lbl, dt.date().isoformat()) for lbl, dt in soon_docs
                    )
                    _notify_user(
                        db, Notification, generate_uuid, c,
                        "coverage_expiring", "Heads up: coverage expiring soon",
                        "Your {} — upload renewed documents to avoid going offline.".format(reason),
                    )
                    reminded.append(c.id)

        db.session.commit()
        logger.info("expiry-sweep: %d suspended, %d reminded", len(suspended), len(reminded))
        return {"suspended": suspended, "reminded": reminded}
