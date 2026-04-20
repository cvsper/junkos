"""
Ops Supervisor — Redis Streams event bus (spec 11 §9, v1).

Event ingestion posts to stream ``ops:events``. Workers in consumer group
``ops-supervisor`` pull the events and hand them to the LangGraph workflow.

If ``REDIS_URL`` is unset:
  * ``publish()`` logs a warning and invokes the workflow inline (degraded
    single-process mode). This keeps local dev and tests simple.
  * ``consume()`` raises, because a worker without a broker is a logic bug.

Message shape on the stream:
    {
      "event_id": "<ops_events.id>",
      "published_at": "<iso8601>",
    }

The worker re-reads the full ``OpsEvent`` row from the database — we
deliberately keep the message envelope tiny so a schema change on the event
row never invalidates queued messages.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


STREAM_NAME = "ops:events"
CONSUMER_GROUP = "ops-supervisor"
DEFAULT_CONSUMER_NAME = "worker-1"


# ---------------------------------------------------------------------------
# Lazy Redis client
# ---------------------------------------------------------------------------
_redis_client = None  # module-level cache


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "") or ""


def get_client(*, force_new: bool = False):
    """Return a connected Redis client or None if REDIS_URL is unset."""
    global _redis_client
    if _redis_client is not None and not force_new:
        return _redis_client

    url = _redis_url()
    if not url:
        return None

    try:
        import redis  # noqa: WPS433 - lazy import
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
        # ping() is fast and catches misconfiguration early.
        _redis_client.ping()
        return _redis_client
    except Exception:
        logger.exception("ops_event_bus: failed to connect to Redis (%s)", url)
        _redis_client = None
        return None


def ensure_group(*, client=None) -> bool:
    """Create the consumer group if it does not exist. Idempotent."""
    client = client or get_client()
    if client is None:
        return False
    try:
        client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="$", mkstream=True)
        logger.info("ops_event_bus: created consumer group %s on %s",
                    CONSUMER_GROUP, STREAM_NAME)
    except Exception as exc:
        # BUSYGROUP = already exists; swallow it.
        msg = str(exc)
        if "BUSYGROUP" in msg or "already exists" in msg.lower():
            return True
        logger.warning("ops_event_bus: xgroup_create failed (%s) — "
                       "stream may not exist yet", exc)
        return False
    return True


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------
def publish(event, *, client=None, inline_handler: Optional[Callable] = None) -> str:
    """Publish ``event`` to the stream. If Redis is unavailable, invokes
    ``inline_handler`` synchronously and returns a sentinel id.

    ``inline_handler`` defaults to ``run_situation_workflow`` from
    ``ops_langgraph``. Tests inject a fake handler.
    """
    envelope = {
        "event_id": getattr(event, "id", "") or "",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    client = client if client is not None else get_client()

    if client is None:
        logger.warning(
            "ops_event_bus: REDIS_URL missing — running workflow inline for event %s",
            envelope["event_id"],
        )
        handler = inline_handler
        if handler is None:
            from ops_langgraph import run_situation_workflow
            handler = run_situation_workflow
        try:
            handler(envelope["event_id"])
        except Exception:
            logger.exception("ops_event_bus: inline handler failed")
        return "inline:{}".format(envelope["event_id"])

    try:
        msg_id = client.xadd(STREAM_NAME, {"payload": json.dumps(envelope)})
        return msg_id
    except Exception:
        logger.exception("ops_event_bus: xadd failed, falling back to inline")
        handler = inline_handler
        if handler is None:
            from ops_langgraph import run_situation_workflow
            handler = run_situation_workflow
        try:
            handler(envelope["event_id"])
        except Exception:
            logger.exception("ops_event_bus: inline handler failed (post-xadd)")
        return "inline:{}".format(envelope["event_id"])


# ---------------------------------------------------------------------------
# Consume
# ---------------------------------------------------------------------------
def consume(
    handler: Callable,
    *,
    client=None,
    consumer_name: str = DEFAULT_CONSUMER_NAME,
    block_ms: int = 5000,
    count: int = 10,
    max_iterations: Optional[int] = None,
) -> int:
    """Consume events from the stream with ack-on-success semantics.

    Returns the number of messages successfully processed. ``max_iterations``
    is the number of XREADGROUP calls to make (useful for tests); None means
    run forever.
    """
    client = client if client is not None else get_client()
    if client is None:
        raise RuntimeError("ops_event_bus.consume: REDIS_URL not configured")

    ensure_group(client=client)

    processed = 0
    iterations = 0
    while True:
        iterations += 1
        try:
            resp = client.xreadgroup(
                CONSUMER_GROUP,
                consumer_name,
                streams={STREAM_NAME: ">"},
                count=count,
                block=block_ms,
            )
        except Exception:
            logger.exception("ops_event_bus: xreadgroup failed, sleeping")
            time.sleep(1.0)
            if max_iterations is not None and iterations >= max_iterations:
                break
            continue

        if not resp:
            if max_iterations is not None and iterations >= max_iterations:
                break
            continue

        for _stream, entries in resp:
            for msg_id, fields in entries:
                payload_raw = fields.get("payload") if isinstance(fields, dict) else None
                if payload_raw is None:
                    # redis-py returns list-of-tuples in some configs
                    try:
                        payload_raw = dict(fields).get("payload")
                    except Exception:
                        payload_raw = None
                try:
                    envelope = json.loads(payload_raw) if payload_raw else {}
                except Exception:
                    envelope = {}
                event_id = envelope.get("event_id")
                try:
                    handler(event_id)
                    client.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                    processed += 1
                except Exception:
                    logger.exception(
                        "ops_event_bus: handler failed for msg_id=%s event_id=%s",
                        msg_id, event_id,
                    )
                    # Leave the message un-acked so PEL retry can pick it up.

        if max_iterations is not None and iterations >= max_iterations:
            break

    return processed


__all__ = [
    "publish",
    "consume",
    "ensure_group",
    "get_client",
    "STREAM_NAME",
    "CONSUMER_GROUP",
    "DEFAULT_CONSUMER_NAME",
]
