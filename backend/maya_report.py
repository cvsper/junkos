"""Why isn't Maya closing?

Every Maya call is already stored (CallLog: ended reason, duration, tools
used, whether a booking was created, summary, transcript). Nobody had ever
rolled it up. This is the roll-up: how calls end, how often a quote turns
into a booking, and the summaries of the ones that didn't — so the answer
comes from the calls themselves rather than a guess.

Manager-only: summaries and transcripts are customer conversations.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from models import db, CallLog
from desk_auth import require_desk, MANAGER_ROLES

logger = logging.getLogger(__name__)
maya_bp = Blueprint("maya_report", __name__)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def report(days=30, samples=8):
    since = _now() - timedelta(days=days)
    calls = (CallLog.query.filter(CallLog.created_at >= since)
             .order_by(CallLog.created_at.desc()).limit(1000).all())
    total = len(calls)
    ended = Counter((c.status or "unknown") for c in calls)
    tools = Counter()
    for c in calls:
        for t in (c.tools_used or []):
            tools[t] += 1
    quoted = sum(1 for c in calls if "get_price_estimate" in (c.tools_used or []))
    booked = sum(1 for c in calls if c.booking_created)
    transferred = sum(1 for c in calls if "transfer_with_context" in (c.tools_used or []))
    callbacks = sum(1 for c in calls if "schedule_callback" in (c.tools_used or []))
    durations = [c.duration_seconds for c in calls if c.duration_seconds]
    short = sum(1 for d in durations if d < 20)

    # The ones that got a price and still didn't book — that is where the
    # answer lives.
    lost = [c for c in calls
            if "get_price_estimate" in (c.tools_used or []) and not c.booking_created]
    lost_samples = [{
        "when": c.created_at.isoformat() + "Z" if c.created_at else None,
        "seconds": c.duration_seconds,
        "ended": c.status,
        "sentiment": c.sentiment,
        "summary": (c.summary or "")[:400],
    } for c in lost[:samples]]

    return {
        "days": days, "calls": total,
        "quoted": quoted, "booked": booked, "transferred": transferred, "callbacks": callbacks,
        "close_rate": round(100.0 * booked / quoted, 1) if quoted else None,
        "quote_rate": round(100.0 * quoted / total, 1) if total else None,
        "avg_seconds": round(sum(durations) / len(durations)) if durations else None,
        "under_20s": short,
        "ended_reasons": ended.most_common(8),
        "tools": tools.most_common(10),
        "lost_after_quote": len(lost),
        "lost_samples": lost_samples,
    }


@maya_bp.route("/api/va/maya/report", methods=["POST"])
@require_desk(MANAGER_ROLES)
def maya_report(ident):
    data = request.get_json(silent=True) or {}
    try:
        days = max(1, min(int(data.get("days") or 30), 120))
    except (TypeError, ValueError):
        days = 30
    return jsonify(report(days)), 200
