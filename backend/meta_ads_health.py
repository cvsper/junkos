"""Is the Meta ad account actually able to spend?

A frozen ad account looks like nothing. Campaigns keep reading ACTIVE, ad sets
keep reading ACTIVE, the ads keep reading ACTIVE — and not one impression is
served, because the account behind them went unsettled over a few dollars. It
happened four times between 2026-08-26 and 2026-09-18, and every single one was
noticed by a human wandering past the numbers, after a day of delivery was
already gone.

So this asks the one question the campaign objects cannot answer: will Meta
take our money right now. One read-only GET, folded into the desk health beat,
alerting through the same path as everything else.

The fix it keeps recommending is deliberate. Paying the balance buys one more
day; a second payment method on the account is what ends the cycle, because the
declines come from the card's fraud filter rejecting repeated FACEBK charges.

Env:
  META_ADS_TOKEN       token with ads_read (falls back to META_ACCESS_TOKEN)
  META_AD_ACCOUNT_ID   act_<id> (defaults to the umuve account)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"
DEFAULT_ACCOUNT = "act_961234110160786"

# Meta's account_status enum, with what each one means for delivery.
STATUS = {
    1:   ("ok",   "active"),
    2:   ("fail", "disabled by Meta"),
    3:   ("fail", "unsettled — an unpaid balance has stopped delivery"),
    7:   ("warn", "pending risk review"),
    8:   ("warn", "pending settlement"),
    9:   ("warn", "in grace period"),
    100: ("fail", "pending closure"),
    101: ("fail", "closed"),
}

FIX = ("Pay it to restart delivery, then add a second payment method "
       "(PayPal) — the card's fraud filter keeps declining FACEBK charges, "
       "and a backup is what stops this recurring.")


def _token():
    return ((os.environ.get("META_ADS_TOKEN") or "").strip()
            or (os.environ.get("META_ACCESS_TOKEN") or "").strip())


def ad_account_check():
    """→ {"state","reason","status","owed","funding"} — never raises.

    state is ok / warn / fail, or warn when we simply cannot tell: a check
    that cannot reach Meta must not read as an account in good standing.
    """
    token = _token()
    if not token:
        return {"state": "warn", "reason": "META_ADS_TOKEN not set — nobody is "
                "watching whether the ad account can spend",
                "status": None, "owed": None, "funding": None}

    account = (os.environ.get("META_AD_ACCOUNT_ID") or DEFAULT_ACCOUNT).strip()
    try:
        import requests
        r = requests.get(
            "{}/{}".format(GRAPH, account),
            params={"fields": "account_status,balance,funding_source_details,disable_reason",
                    "access_token": token},
            timeout=15,
        )
        body = r.json()
    except Exception as e:
        logger.warning("meta ads health: could not reach Meta (%s)", type(e).__name__)
        return {"state": "warn", "reason": "Meta did not answer: " + type(e).__name__,
                "status": None, "owed": None, "funding": None}

    if "error" in body:
        msg = body["error"].get("message", "")[:120]
        return {"state": "warn", "reason": "Meta refused the read: " + msg,
                "status": None, "owed": None, "funding": None}

    status = body.get("account_status")
    # Meta returns balance in minor units, as a string.
    try:
        owed = int(body.get("balance") or 0) / 100.0
    except (TypeError, ValueError):
        owed = None
    funding = (body.get("funding_source_details") or {}).get("display_string")

    state, label = STATUS.get(status, ("warn", "unrecognised status {}".format(status)))
    if state == "fail" and owed:
        reason = "${:.2f} owed — {}. {}".format(owed, label, FIX)
    elif state == "fail":
        reason = "ads are not running: {}".format(label)
    elif owed:
        reason = "{}, ${:.2f} accruing toward the next charge".format(label, owed)
    else:
        reason = "{}, nothing owed".format(label)

    return {"state": state, "reason": reason, "status": status,
            "owed": owed, "funding": funding}
