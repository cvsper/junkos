"""Call Kit — what the VA needs mid-call, keyed to who is on the line.

Two sides walk through the Call Desk:
  demand  — businesses that generate junk (property managers, estate sales,
            storage, realtors, movers-as-referrers) → sell them Umuve.
  supply  — haulers, dumpster outfits, demo crews, appliance dealers with
            trucks → recruit them as operators.

The kit gives the VA, per prospect: a talk track (discover → pitch → close),
objection replies, a fact sheet she can answer from, live prices from the
pricing engine, and one-tap lookups. All copy lives here, server-side, so it
stays consistent with what the site and the info pack promise.

Facts are sourced from the public operators/partners pages and the pricing
engine — keep them in sync when those change.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# --- side detection --------------------------------------------------------
_SUPPLY_CATS = ("junk", "haul", "dumpster", "debris", "demo", "demolition", "tree",
                "land clear", "pressure", "appliance dealer", "appliance sales",
                "scratch", "refurb", "recycler", "scrap", "fletes", "mudanza",
                "cleanout crew", "removal")
_SUPPLY_HINTS = ("truck", "paid job", "operator", "hauler", "sign up", "signup",
                 "recruit", "jobs to", "send them jobs", "keep the fare", "go online")
_DEMAND_CATS = ("property", "hoa", "apartment", "commercial", "office", "storage",
                "estate sale", "auction", "thrift", "real estate", "realtor",
                "staging", "probate", "investor", "flipper", "senior", "hotel",
                "restaurant", "school", "church", "contractor", "flooring",
                "restoration", "handyman", "painting", "moving company", "movers")


def detect_side(prospect):
    cat = (prospect.category or "").lower()
    blob = " ".join([prospect.why or "", prospect.angle or ""]).lower()
    if any(k in cat for k in _SUPPLY_CATS):
        return "supply"
    if any(k in blob for k in _SUPPLY_HINTS):
        return "supply"
    if any(k in cat for k in _DEMAND_CATS):
        return "demand"
    return "demand"


# --- demand: talk tracks per segment --------------------------------------
_DEMAND_TRACKS = {
    "property": {
        "discover": [
            "How many doors do you manage, and how often does a move-out leave stuff behind?",
            "Who handles that today — maintenance, a hauler, or whoever's available?",
            "What does a slow turnover cost you in lost rent?",
        ],
        "pitch": ("One number for every cleanout. Manager texts us the unit, we quote it "
                  "up front from photos, and it's rentable again in about 24 hours. "
                  "Standing accounts get volume rates and one monthly invoice."),
        "close": ("Can I put a rate card on file so your managers have the number? "
                  "Who should I send it to?"),
    },
    "storage": {
        "discover": [
            "When a unit goes to auction or gets abandoned, what happens to the leftovers?",
            "How many of those a month, roughly?",
            "How long does a unit sit before it's rentable again?",
        ],
        "pitch": ("We turn an abandoned unit back into a rentable one in about 24 hours. "
                  "Flat, upfront price — your manager texts us the unit number and it's handled."),
        "close": "Can I send your manager a rate card so it's on file for the next one?",
    },
    "estate": {
        "discover": [
            "How many sales a month, and what's left over after a typical one?",
            "Who clears the house now — the family, or do you bring someone in?",
            "Have you ever lost a booking because the family needed a full-service clear-out?",
        ],
        "pitch": ("You close the sale Saturday, we clear the house Monday, the family gets "
                  "the keys back. Upfront pricing, donation drop-offs where items qualify — "
                  "you look full-service without owning a truck."),
        "close": "Want me to send the partner page so you can quote it on your next sale?",
    },
    "realtor": {
        "discover": [
            "When a listing or an estate needs a cleanout before it can move, who do you send them to?",
            "How often does that come up — a couple a month?",
        ],
        "pitch": ("Give your sellers one number: upfront price, insured local pros, gone same "
                  "or next day. Realtors get a 10% referral credit on every job."),
        "close": "Can I text you the referral link so it's in your phone for the next listing?",
    },
    "flipper": {
        "discover": [
            "How many properties a month, and how do you clear them before demo starts?",
            "Is your crew hauling, or are you paying for dumpsters that sit half-empty?",
        ],
        "pitch": ("We quote from photos and clear it same or next day, so your crew starts "
                  "demo on day one. No dumpster permit, no sitting rental."),
        "close": "Send me the address of your next one and I'll get you a price today.",
    },
    "senior": {
        "discover": [
            "When a client downsizes, what happens to everything that doesn't move with them?",
            "Do families ask you for someone, or do they figure it out alone?",
        ],
        "pitch": ("We handle the haul-away leg: respectful crews, upfront pricing, donation "
                  "drop-offs. You stay the trusted face; we do the lifting."),
        "close": "Can I send you a one-pager you can hand to families?",
    },
    "mover": {
        "discover": [
            "How often do customers ask you to take stuff they don't want moved?",
            "What do you tell them today?",
        ],
        "pitch": ("Hand them our number and keep the move. We pick up the leftovers on your "
                  "schedule — upfront price, same or next day."),
        "close": "Want a card for your crews to hand out? I can text the link now.",
    },
    "contractor": {
        "discover": [
            "How do you get rid of tear-out debris now — dumpster, your own truck, a guy?",
            "How many jobs a month generate a load?",
        ],
        "pitch": ("Upfront price from a photo, pickup same or next day, no dumpster sitting "
                  "in the driveway. Your crew stays on the job."),
        "close": "Send me a photo of your current pile and I'll price it while we're on the phone.",
    },
}
_DEMAND_TRACKS["thrift"] = {
    "discover": [
        "What happens to donations you can't sell — how often does that pile up?",
        "Who hauls it now, and what does that run you?",
    ],
    "pitch": ("Scheduled pickups of the overflow, upfront price, gone the same day. "
              "Standing accounts get volume rates."),
    "close": "Can I set up a standing pickup day and send the rate card?",
}

_DEMAND_SEGMENT_KEYS = [
    (("property", "hoa", "apartment", "commercial", "office", "institution", "hotel"), "property"),
    (("storage",), "storage"),
    (("real estate", "staging", "probate", "realtor", "broker"), "realtor"),
    (("estate", "auction", "antiques"), "estate"),
    (("thrift", "donation"), "thrift"),
    (("investor", "flipper"), "flipper"),
    (("senior",), "senior"),
    (("moving", "mover"), "mover"),
    (("contractor", "flooring", "restoration", "handyman", "painting", "roof"), "contractor"),
]


def demand_segment(category):
    c = (category or "").lower()
    for keys, name in _DEMAND_SEGMENT_KEYS:
        if any(k in c for k in keys):
            return name
    return "property"


_DEMAND_OBJECTIONS = [
    ("We already have a guy.",
     "Great — most people do. Keep him. We're the backup for when he's slow, booked, or "
     "it's a bigger job than one truck. Can I leave a rate card on file so you have a second number?"),
    ("Just send me something.",
     "Happy to. What's the best cell or email for it? And so I send the right thing — "
     "is it mostly move-outs, or bigger cleanouts?"),
    ("How much?",
     "Depends on what's in the pile, but you get the exact price up front before anyone "
     "comes out. To give you a feel: a sofa is ${sofa} all-in, a mattress ${mattress}. "
     "Text me a photo and I'll price it right now."),
    ("Not interested.",
     "No problem. One quick thing before I go — if a tenant leaves a unit full next month, "
     "who do you call? ... I'll text you our number so it's there if that day comes."),
    ("Who is this? How did you get my number?",
     "It's {va} with Umuve — we're a local junk-removal service in Palm Beach and Broward. "
     "Your business is listed publicly; I'm calling the property people in the area to make "
     "sure they have a fast option for cleanouts."),
    ("Call me back later.",
     "Sure. When's better — tomorrow morning or afternoon? I'll put it on my calendar. "
     "(Then tap Call back → pick the time.)"),
    ("We use a dumpster.",
     "Dumpsters are great for big demo. For a move-out or a few rooms, we're usually cheaper "
     "than the rental plus the permit, and nothing sits in the lot. Want me to price your "
     "next one against it?"),
    ("Are you insured?",
     "Yes — licensed and insured, and every crew is vetted. Happy to send the certificate "
     "with the rate card."),
]

_DEMAND_ANSWERS = [
    ("How fast?", "Same or next day in Palm Beach and Broward. Book by text or phone; we confirm a window."),
    ("How do they pay?", "Card on file or invoice for standing accounts. Price is fixed up front — no surprises on site."),
    ("What do we take?", "Furniture, appliances, mattresses, electronics, office gear, yard waste, construction debris, hot tubs, pianos, pool tables."),
    ("What we don't take", "Hazardous waste, paint, chemicals, tires, asbestos, anything with fuel still in it."),
    ("Insured?", "Licensed and insured. Certificate available on request."),
    ("Where?", "Palm Beach and Broward County. West Palm Beach is home base."),
    ("Hours", "Mon–Sat 7am–7pm, Sun 8am–5pm."),
    ("Realtor referral", "10% referral credit on every job a realtor sends."),
    ("Photo quote", "They text a photo of the pile to our number and get a price back in about 30 seconds."),
    ("Standing accounts", "Volume rates, one monthly invoice, a dedicated number. Rate card on request."),
]

# --- supply: recruiting haulers -------------------------------------------
_SUPPLY_TRACK = {
    "opener": ("Hi, this is {va} with Umuve. We send paid junk-removal jobs to local hauling "
               "companies in Palm Beach and Broward — customers book and pay us, you do the haul "
               "and keep the majority. Do you have a truck out most days?"),
    "discover": [
        "How many trucks, and how many jobs a week are you doing now?",
        "Where do most of your jobs come from — referrals, ads, marketplaces?",
        "Would you take more jobs if they came to your phone already booked and paid?",
    ],
    "pitch": ("Customer books and pays on our platform. The job hits your phone with the price "
              "and the address — you accept the ones you want. Price is set up front, you keep "
              "the majority of every job, and you can cash out the same day. No monthly fee, "
              "no contract; walk away anytime."),
    "close": ("Setup takes about two minutes on your phone — I'll text you the link right now. "
              "What's the best cell for it?"),
}

_SUPPLY_OBJECTIONS = [
    ("What's the catch? What do you take?",
     "We keep a fee off each job and you keep the majority — on a $200 job you'd see about $150. "
     "The customer already paid, so you're never chasing money."),
    ("I've got enough work.",
     "Then take zero jobs — there's no minimum. Most guys keep us for slow weeks and the jobs "
     "near where they already are. Costs nothing to be on the list."),
    ("Is this like TaskRabbit / Thumbtack? I pay for leads?",
     "No lead fees. You never pay us. The customer pays, we pass you the job already booked."),
    ("I don't do apps.",
     "You don't need one to start. Text JOBS to our number and we send job offers by text; "
     "you reply to grab one. The app comes later if you want it."),
    ("When do I get paid?",
     "Standard payouts are free and hit your bank; instant cash-out to a debit card the same "
     "day for a small fee. Payouts run through Stripe."),
    ("Do I need insurance?",
     "You need to be a legit business with a truck. We ask for your license and insurance "
     "when you set up — we review within 24 hours."),
    ("Send me the info.",
     "Doing it now — what's the best cell? It's a two-minute setup link; you can look before "
     "you decide."),
    ("Not interested.",
     "All good. If a slow week hits, text JOBS to our number and you're on the list in a "
     "minute. I'll send it so you have it."),
]

_SUPPLY_ANSWERS = [
    ("What they keep", "The majority of every job. Example on the site: $200 job → $150 to the hauler."),
    ("Getting paid", "Stripe payouts. Standard is free; instant cash-out same day for a small fee."),
    ("No app needed", "Text JOBS to the Umuve number → job offers by text, reply to accept. App optional."),
    ("Setup", "goumuve.com/operators — about two minutes. We review within 24 hours."),
    ("What they need", "A truck, a legit business, license and insurance on file."),
    ("Where the jobs are", "Palm Beach and Broward. Most volume in West Palm Beach right now."),
    ("What jobs look like", "Furniture, appliances, mattresses, cleanouts. Price set up front; they see it before accepting."),
    ("Fees", "No monthly fee, no lead fees, no contract."),
    ("Who books", "Customers book and pay through Umuve — the hauler never chases payment."),
]

_PRICE_ITEMS = [
    ("Sofa", "sofa"), ("Sectional", "sofa_sectional"), ("Mattress", "mattress"),
    ("Bed set", "bed_set"), ("Refrigerator", "refrigerator"), ("Washer + dryer", "washer_dryer_set"),
    ("Dresser", "dresser"), ("Desk (large)", "desk_large"), ("Flat-screen TV", "tv_flatscreen"),
    ("Treadmill", "treadmill"), ("Riding mower", "lawn_mower_riding"), ("Hot tub", "hot_tub"),
    ("Pool table", "pool_table"), ("Piano", "piano"),
]
_BULK_ITEMS = [
    ("Yard waste, per bag/bundle", "yard_waste"),
    ("Construction debris, per unit", "construction"),
    ("Misc. item", "general"),
]


def _estimate_total(category, quantity=1):
    """All-in price for one item via the real engine; None if it can't price it."""
    try:
        from routes.booking import calculate_estimate
        res = calculate_estimate([{"category": category, "quantity": quantity}]) or {}
        for k in ("total", "total_price", "grand_total", "estimated_total", "customer_total"):
            v = res.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return round(float(v))
    except Exception:
        logger.debug("kit price via engine failed for %s", category, exc_info=True)
    return None


def _base_price(category):
    try:
        from routes.booking import CATEGORY_PRICES
        sizes = CATEGORY_PRICES.get(category) or {}
        return sizes.get("default") or (list(sizes.values()) or [None])[0]
    except Exception:
        return None


def price_sheet():
    rows = []
    for label, cat in _PRICE_ITEMS + _BULK_ITEMS:
        allin = _estimate_total(cat)
        base = _base_price(cat)
        if allin is None and base is None:
            continue
        rows.append({"label": label, "from": allin if allin is not None else round(float(base)),
                     "base": round(float(base)) if base is not None else None})
    return rows


def lookup_links(prospect):
    name = (prospect.company or "").strip()
    city = (prospect.city or "").strip()
    q = quote_plus(" ".join([name, city, "FL"]).strip())
    digits = "".join(ch for ch in (prospect.phone or "") if ch.isdigit())[-10:]
    links = [
        {"label": "Google", "url": "https://www.google.com/search?q=" + q},
        {"label": "Maps + reviews", "url": "https://www.google.com/maps/search/" + q},
        {"label": "Sunbiz (FL registry)", "url": "https://www.google.com/search?q=" + quote_plus("site:sunbiz.org " + name)},
    ]
    if len(digits) == 10:
        links.append({"label": "Who owns this number", "url": "https://www.google.com/search?q=" + quote_plus(
            "\"({}) {}-{}\"".format(digits[:3], digits[3:6], digits[6:]))})
    return links


def build_kit(prospect, va_name=None, side=None):
    va = (va_name or "Tracy").split()[0]
    side = side if side in ("supply", "demand") else detect_side(prospect)
    prices = price_sheet()
    by_label = {p["label"]: p["from"] for p in prices}
    fmt = {"va": va, "sofa": by_label.get("Sofa", "—"), "mattress": by_label.get("Mattress", "—")}
    if side == "supply":
        t = _SUPPLY_TRACK
        track = {"opener": t["opener"].format(va=va), "discover": t["discover"],
                 "pitch": t["pitch"], "close": t["close"], "segment": "hauler"}
        objections = [{"say": s, "reply": r.format(**fmt)} for s, r in _SUPPLY_OBJECTIONS]
        answers = [{"q": q, "a": a} for q, a in _SUPPLY_ANSWERS]
        price_note = "What customers pay per item — the hauler keeps the majority of each."
    else:
        seg = demand_segment(prospect.category)
        t = _DEMAND_TRACKS[seg]
        from va_calls import opener_for
        track = {"opener": opener_for(prospect.category).format(va=va), "discover": t["discover"],
                 "pitch": t["pitch"], "close": t["close"], "segment": seg}
        objections = [{"say": s, "reply": r.format(**fmt)} for s, r in _DEMAND_OBJECTIONS]
        answers = [{"q": q, "a": a} for q, a in _DEMAND_ANSWERS]
        price_note = "All-in prices from the live engine. Quote these as 'from' — photos set the exact number."
    return {
        "side": side,
        "detected_side": detect_side(prospect),
        "track": track,
        "objections": objections,
        "answers": answers,
        "prices": prices,
        "price_note": price_note,
        "lookup": lookup_links(prospect),
    }
