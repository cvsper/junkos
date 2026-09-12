"""Loop guard for the main-number SMS bot.

On 9/11 the desk texted ~75 property-management office lines from the main
toll-free number. Twenty of them run texting platforms that auto-reply
("Thanks for contacting X. Reply START to receive SMS"), Maya's SMS bot
answered every one, and the two robots traded ~1,100 texts in six hours.

Three rules, applied in routes/sms_webhook.py before anything replies:
  1. looks_automated(body)  — recognisable auto-responder text gets silence.
  2. prospects get silence   — a known desk prospect is Tracy's conversation;
                               the text lands in the desk thread, the bot stays out.
  3. reply_allowed(digits)   — at most REPLY_CAP conversational replies per
                               sender per hour, and GLOBAL_CAP per hour overall,
                               so an unrecognised loop dies within minutes.
The counters are in-process (Render runs one worker); a restart resets them,
which is fine — rule 1 and 2 catch the known shapes without any state.
"""
import collections
import logging
import re
import threading
import time

logger = logging.getLogger(__name__)

REPLY_CAP = 4          # conversational replies per sender per hour
GLOBAL_CAP = 60        # conversational replies per hour across all senders
WINDOW_S = 3600

_AUTOMATED = [
    r"\breply\s+(start|yes|y)\b[^.]{0,60}\b(receive|consent|opt|sms|text|message)",
    r"\bthanks?\s+for\s+(contacting|texting|reaching\s+out\s+to|messaging)\b",
    r"\b(can'?t|cannot|unable\s+to|not\s+able\s+to)\s+(be\s+)?receiv",
    r"\bauto[\s-]?(reply|response|responder|mated)\b",
    r"\bout\s+of\s+(the\s+)?office\b",
    r"\b(do\s+not|don'?t)\s+reply\b|\bunmonitored\b|\bno[\s-]?reply\b",
    r"\bthis\s+(number|line|phone)\s+(is\s+not|does\s+not|doesn'?t|cannot|can'?t)\b",
    r"\bmsg\s*(&|and)\s*data\s+rates\b",
    r"\bno\s+live\s+caller\b|\bautomated\s+(message|loop)\b",
    r"\bwe(?:'ll|\s+will)\s+(get\s+back\s+to\s+you|be\s+in\s+touch|respond)\b[^.]{0,30}\b(shortly|soon|within|as\s+soon)",
    r"\b(you\s+are|you'?re)\s+now\s+(subscribed|opted\s+in)\b",
]
_AUTOMATED_RE = [re.compile(p, re.I) for p in _AUTOMATED]

_lock = threading.Lock()
_per_sender = collections.defaultdict(collections.deque)
_global = collections.deque()


def looks_automated(body):
    """True when the text reads like a texting-platform auto-responder."""
    text = " ".join((body or "").split())
    if not text:
        return False
    return any(rx.search(text) for rx in _AUTOMATED_RE)


def _prune(dq, now):
    while dq and now - dq[0] > WINDOW_S:
        dq.popleft()


def reply_allowed(digits):
    """May the bot send one more conversational reply to this sender?"""
    now = time.monotonic()
    with _lock:
        dq = _per_sender[digits]
        _prune(dq, now)
        _prune(_global, now)
        if len(dq) >= REPLY_CAP:
            logger.warning("SMS bot: sender ...%s hit %d replies/hour — silenced", digits[-4:], REPLY_CAP)
            return False
        if len(_global) >= GLOBAL_CAP:
            logger.error("SMS bot: %d replies/hour across all senders — silenced (loop?)", GLOBAL_CAP)
            return False
        return True


def note_reply(digits):
    now = time.monotonic()
    with _lock:
        _per_sender[digits].append(now)
        _global.append(now)


def _reset():
    with _lock:
        _per_sender.clear()
        _global.clear()
