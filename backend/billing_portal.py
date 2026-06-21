"""
B2B Commercial Portal — Stripe billing (Spec 04 §8).

Two responsibilities:
  1. Bootstrap the catalog: create Product + Price rows for Starter/Pro/
     Enterprise tiers in Stripe (or report the existing IDs). Idempotent —
     we look up by name before creating. Price IDs land in
     `portal_billing_config.json` so the app can subscribe orgs without
     hitting the Stripe API every time.
  2. Subscribe an org: find-or-create the Stripe customer, attach a
     subscription at the chosen tier, and store the resulting IDs on Org.

Usage:
    STRIPE_API_KEY=sk_test_... python billing_portal.py bootstrap
    STRIPE_API_KEY=sk_test_... python billing_portal.py subscribe <org_id> <tier>

The webhook handler is registered under /portal/v1/billing/webhook — it only
cares about invoice.paid, invoice.payment_failed, and
customer.subscription.updated (to sync tier + status).
"""

import json
import logging
import os
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Portal tier catalog — spec §8.
TIERS = {
    "starter": {
        "name": "Umuve Portal — Starter",
        "description": "1 property, 3 users, 10 pickups incl, $65/overage",
        "monthly_cents": 49900,
        "overage_cents": 6500,
    },
    "pro": {
        "name": "Umuve Portal — Pro",
        "description": "Up to 25 properties, 15 users, 60 pickups incl, $55/overage",
        "monthly_cents": 199900,
        "overage_cents": 5500,
    },
    "enterprise": {
        "name": "Umuve Portal — Enterprise",
        "description": "Unlimited properties/users, 150 pickups incl, $45/overage, net-30",
        "monthly_cents": 499900,
        "overage_cents": 4500,
    },
}

CONFIG_PATH = Path(
    os.environ.get(
        "PORTAL_BILLING_CONFIG",
        os.path.join(os.path.dirname(__file__), "portal_billing_config.json"),
    )
)


# ---------------------------------------------------------------------------
# Config persistence — small JSON file; product/price IDs are public-safe
# ---------------------------------------------------------------------------
def _load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ---------------------------------------------------------------------------
# Bootstrap: create products + prices in Stripe (idempotent)
# ---------------------------------------------------------------------------
def bootstrap(stripe_api_key=None):
    """Create or reuse Stripe products + prices for all tiers. Returns the
    full config dict. Requires stripe SDK; skips if not installed."""
    try:
        import stripe
    except ImportError:
        raise SystemExit(
            "stripe SDK not installed. Run: pip install stripe"
        )

    stripe.api_key = stripe_api_key or os.environ.get("STRIPE_API_KEY", "")
    if not stripe.api_key:
        raise SystemExit("STRIPE_API_KEY not set")

    cfg = _load_config()
    cfg.setdefault("tiers", {})

    for tier, meta in TIERS.items():
        existing = cfg["tiers"].get(tier, {})
        product_id = existing.get("product_id")
        base_price_id = existing.get("base_price_id")

        if not product_id:
            products = stripe.Product.list(limit=100)
            match = next(
                (p for p in products.auto_paging_iter() if p.name == meta["name"]),
                None,
            )
            if match:
                product_id = match.id
            else:
                p = stripe.Product.create(
                    name=meta["name"],
                    description=meta["description"],
                    metadata={"tier": tier, "source": "portal_bootstrap"},
                )
                product_id = p.id

        if not base_price_id:
            prices = stripe.Price.list(product=product_id, limit=10)
            match = next(
                (
                    pr
                    for pr in prices.auto_paging_iter()
                    if pr.unit_amount == meta["monthly_cents"]
                    and pr.recurring
                    and pr.recurring.interval == "month"
                ),
                None,
            )
            if match:
                base_price_id = match.id
            else:
                pr = stripe.Price.create(
                    product=product_id,
                    unit_amount=meta["monthly_cents"],
                    currency="usd",
                    recurring={"interval": "month"},
                    nickname="{} Monthly".format(tier),
                )
                base_price_id = pr.id

        cfg["tiers"][tier] = {
            "product_id": product_id,
            "base_price_id": base_price_id,
            "monthly_cents": meta["monthly_cents"],
            "overage_cents": meta["overage_cents"],
        }

    cfg["bootstrapped_at"] = datetime.utcnow().isoformat()
    _save_config(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Subscribe: find-or-create customer + subscription for an org
# ---------------------------------------------------------------------------
def subscribe_org(org_id, tier=None, stripe_api_key=None):
    """Create a Stripe Customer + Subscription for an org. Idempotent: if
    the org already has a stripe_subscription_id we reuse it."""
    try:
        import stripe
    except ImportError:
        raise SystemExit("stripe SDK not installed")

    from models import db, Org

    stripe.api_key = stripe_api_key or os.environ.get("STRIPE_API_KEY", "")
    if not stripe.api_key:
        raise SystemExit("STRIPE_API_KEY not set")

    org = db.session.get(Org, org_id)
    if not org:
        raise SystemExit("org {} not found".format(org_id))
    tier = tier or org.tier
    if tier not in TIERS:
        raise SystemExit("invalid tier {}".format(tier))

    cfg = _load_config()
    price_id = cfg.get("tiers", {}).get(tier, {}).get("base_price_id")
    if not price_id:
        raise SystemExit(
            "no price_id for tier {}. Run bootstrap first.".format(tier)
        )

    if not org.stripe_customer_id:
        customer = stripe.Customer.create(
            email=org.billing_email,
            name=org.name,
            metadata={"org_id": org.id, "source": "portal"},
        )
        org.stripe_customer_id = customer.id

    if org.stripe_subscription_id:
        sub = stripe.Subscription.retrieve(org.stripe_subscription_id)
    else:
        sub = stripe.Subscription.create(
            customer=org.stripe_customer_id,
            items=[{"price": price_id}],
            collection_method="send_invoice"
            if tier == "enterprise"
            else "charge_automatically",
            days_until_due=30 if tier == "enterprise" else None,
            metadata={"org_id": org.id, "tier": tier},
        )
        org.stripe_subscription_id = sub.id

    org.tier = tier
    org.status = "active"
    db.session.commit()
    return {"customer_id": org.stripe_customer_id, "subscription_id": sub.id}


# ---------------------------------------------------------------------------
# Flask webhook blueprint: /portal/v1/billing/webhook
# ---------------------------------------------------------------------------
def push_portal_invoice_to_stripe(org, portal_invoice, line_items):
    """Create + finalize a Stripe invoice for a generated PortalInvoice.

    Uses collection_method=send_invoice on the org's net terms, so it works for
    B2B without a saved card (Stripe emails a hosted, payable invoice). The
    /webhook handler flips PortalInvoice -> paid / past_due via stripe_invoice_id.

    Returns the Stripe invoice id, or None if it can't push yet (no Stripe
    customer on the org, no API key, or a zero total). Never raises.
    """
    try:
        if not org or not getattr(org, "stripe_customer_id", None):
            return None
        if (portal_invoice.total_cents or 0) <= 0:
            return None
        import stripe
        key = os.environ.get("STRIPE_SECRET_KEY")
        if not key:
            return None
        stripe.api_key = key

        # Pending invoice items on the customer (one per non-zero line).
        for li in line_items:
            amt = int(li.amount_cents or 0)
            if amt <= 0:
                continue
            stripe.InvoiceItem.create(
                customer=org.stripe_customer_id,
                amount=amt,
                currency="usd",
                description=(li.description or "Pickup")[:200],
            )

        inv = stripe.Invoice.create(
            customer=org.stripe_customer_id,
            collection_method="send_invoice",
            days_until_due=int(getattr(org, "net_terms_days", None) or 30),
            auto_advance=True,
            metadata={
                "portal_invoice_id": portal_invoice.id,
                "number": portal_invoice.number,
            },
        )
        # Finalize so it's issued (and emailed for send_invoice).
        stripe.Invoice.finalize_invoice(inv.id)
        return inv.id
    except Exception:
        logger.exception(
            "push_portal_invoice_to_stripe failed for org=%s invoice=%s",
            getattr(org, "id", "?"), getattr(portal_invoice, "id", "?"),
        )
        return None


def create_checkout_session(org, tier, success_url, cancel_url):
    """Stripe Checkout (subscription mode) — collects a card AND starts the
    org's subscription in one hosted flow. Returns the Checkout URL. The
    checkout.session.completed webhook captures customer+subscription onto the
    org and flips it active. This is the self-serve path (vs. subscribe_org,
    which creates a subscription with no payment method)."""
    if tier not in TIERS:
        raise ValueError("invalid tier {}".format(tier))
    import stripe
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    stripe.api_key = key
    cfg = _load_config()
    price_id = cfg.get("tiers", {}).get(tier, {}).get("base_price_id")
    if not price_id:
        raise RuntimeError("no price for tier {} — run bootstrap first".format(tier))
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"org_id": org.id, "tier": tier},
        "subscription_data": {"metadata": {"org_id": org.id, "tier": tier}},
        "allow_promotion_codes": True,
    }
    if org.stripe_customer_id:
        params["customer"] = org.stripe_customer_id
    elif org.billing_email:
        params["customer_email"] = org.billing_email
    return stripe.checkout.Session.create(**params).url


def create_billing_portal_session(org, return_url):
    """Stripe Customer Portal link so an org can manage its card, subscription,
    and invoices. Requires an existing Stripe customer."""
    if not org or not org.stripe_customer_id:
        raise RuntimeError("org has no Stripe customer yet")
    import stripe
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    stripe.api_key = key
    return stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id, return_url=return_url
    ).url


billing_portal_bp = Blueprint(
    "billing_portal", __name__, url_prefix="/portal/v1/billing"
)


def _require_admin(f):
    """Admin-only guard (mirrors routes/admin.py)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        from auth_routes import require_auth
        from models import db, User

        @require_auth
        def inner(user_id, *a, **kw):
            user = db.session.get(User, user_id)
            if not user or user.role != "admin":
                return jsonify({"error": "Admin access required"}), 403
            return f(user_id=user_id, *a, **kw)

        return inner(*args, **kwargs)
    return wrapper


@billing_portal_bp.route("/bootstrap", methods=["POST"])
@_require_admin
def bootstrap_route(user_id):
    """Admin-triggered: create/verify Stripe tier products + prices.

    Idempotent — reuses existing IDs and just reports them on re-run. Returns
    the resulting tier->price config so you can confirm it in one call instead
    of shelling into the server. Requires STRIPE_SECRET_KEY on the server.
    """
    try:
        cfg = bootstrap()
        return jsonify({"success": True, "config": cfg}), 200
    except Exception as e:
        logging.getLogger(__name__).exception("billing bootstrap failed")
        return jsonify({"success": False, "error": str(e)}), 502


@billing_portal_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe events relevant to portal subscriptions."""
    try:
        import stripe
    except ImportError:
        return jsonify({"error": "stripe unavailable"}), 503

    from models import db, Org, PortalInvoice

    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET_PORTAL", "")
    try:
        if secret:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        else:
            event = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        logger.warning("portal stripe webhook rejected: %s", exc)
        return jsonify({"error": "invalid_signature"}), 400

    etype = event["type"] if isinstance(event, dict) else event.type
    data = (
        event["data"]["object"]
        if isinstance(event, dict)
        else event.data.object
    )

    if etype == "checkout.session.completed":
        # Self-serve subscribe finished — capture the Stripe customer +
        # subscription onto the org and activate it.
        meta = (data.get("metadata") if isinstance(data, dict) else data.metadata) or {}
        org_id = meta.get("org_id")
        org = db.session.get(Org, org_id) if org_id else None
        if org:
            cust = data.get("customer") if isinstance(data, dict) else data.customer
            sub = data.get("subscription") if isinstance(data, dict) else data.subscription
            if cust:
                org.stripe_customer_id = cust
            if sub:
                org.stripe_subscription_id = sub
            if meta.get("tier"):
                org.tier = meta["tier"]
            org.status = "active"
            db.session.commit()

    elif etype == "customer.subscription.updated":
        sub_id = data.get("id") if isinstance(data, dict) else data.id
        status = data.get("status") if isinstance(data, dict) else data.status
        org = (
            db.session.query(Org).filter_by(stripe_subscription_id=sub_id).first()
        )
        if org:
            mapping = {
                "active": "active",
                "past_due": "past_due",
                "canceled": "churned",
                "unpaid": "past_due",
                "paused": "paused",
                "trialing": "trial",
            }
            org.status = mapping.get(status, org.status)
            db.session.commit()

    elif etype == "invoice.paid":
        stripe_invoice_id = (
            data.get("id") if isinstance(data, dict) else data.id
        )
        inv = (
            db.session.query(PortalInvoice)
            .filter_by(stripe_invoice_id=stripe_invoice_id)
            .first()
        )
        if inv:
            inv.status = "paid"
            inv.paid_at = datetime.utcnow()
            db.session.commit()

    elif etype == "invoice.payment_failed":
        stripe_invoice_id = (
            data.get("id") if isinstance(data, dict) else data.id
        )
        inv = (
            db.session.query(PortalInvoice)
            .filter_by(stripe_invoice_id=stripe_invoice_id)
            .first()
        )
        if inv:
            inv.status = "past_due"
            org = db.session.get(Org, inv.org_id)
            if org:
                org.status = "past_due"  # holds recurring job-gen (Stage 5)
            db.session.commit()
            # Dunning: tell the org payment failed + how to fix it. Never raises.
            try:
                if org and org.billing_email:
                    from notifications import send_email
                    from email_templates import b2b_dunning_html
                    manage_url = os.environ.get("PORTAL_URL", "https://portal.goumuve.com") + "/settings"
                    send_email(
                        org.billing_email,
                        "Action needed: your Umuve payment failed",
                        b2b_dunning_html(org.name, inv.number,
                                         (inv.total_cents or 0) / 100.0, manage_url),
                    )
            except Exception:
                logger.exception("dunning email failed for org=%s", getattr(org, "id", "?"))

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "bootstrap":
        cfg = bootstrap()
        print(json.dumps(cfg, indent=2))
        return
    if argv[0] == "subscribe" and len(argv) >= 2:
        org_id = argv[1]
        tier = argv[2] if len(argv) >= 3 else None
        # Boot Flask app context so SQLAlchemy session works.
        from server import app
        with app.app_context():
            result = subscribe_org(org_id, tier)
            print(json.dumps(result, indent=2))
        return
    print("Unknown command. Use `bootstrap` or `subscribe <org_id> [tier]`.")
    sys.exit(1)


if __name__ == "__main__":
    main()
