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
# Free-text hints only decide when the category says nothing. They must read as
# recruiting language: a demand angle legitimately says "books a vetted hauler".
_SUPPLY_HINTS = ("paid job", "keep the majority", "keep the fare", "send them jobs", "jobs to their",
                 "recruit", "go online", "sign up", "signup", "their truck", "run a truck", "runs a truck",
                 "has a truck", "as a hauler", "join as")
_DEMAND_CATS = ("property", "hoa", "apartment", "commercial", "office", "storage",
                "estate sale", "auction", "thrift", "real estate", "realtor",
                "staging", "probate", "investor", "flipper", "senior", "hotel",
                "restaurant", "school", "church", "contractor", "flooring",
                "restoration", "handyman", "painting", "moving company", "movers")


def detect_side(prospect):
    """supply | demand. The list's explicit side wins, then the category, and
    only a prospect with no recognizable category is judged by the free text
    (why/angle), which is written by a model and can mention haulers either way."""
    explicit = (getattr(prospect, "side", None) or "").strip().lower()
    if explicit in ("supply", "demand"):
        return explicit
    cat = (prospect.category or "").lower()
    if any(k in cat for k in _DEMAND_CATS):
        return "demand"
    if any(k in cat for k in _SUPPLY_CATS):
        return "supply"
    blob = " ".join([prospect.why or "", prospect.angle or ""]).lower()
    if any(k in blob for k in _SUPPLY_HINTS):
        return "supply"
    return "demand"


# --- demand: talk tracks per segment --------------------------------------
# The structure every demand call follows, from the data (reports/Umuve B2B
# phone close tactics.md): reason-for-call opener with the brand spelled and
# the recording notice; the ROLE question before anything else; one 30–40s
# burst; the TRIGGER question that surfaces a job; the price floor when asked;
# a two-slot close; the cell captured and the text sent on the line. The old
# closes ("can I put a rate card on file?") are the ask a leasing agent can
# say yes to without anything happening — 124 of those, 0 jobs.
_DEMAND_TRACKS = {
    "property": {
        "role": ("Who handles your turns when a unit's left full — the maintenance supervisor "
                 "or the community manager? … Could you put me through, or what's their name and cell?"),
        "burst": ("We're the trash-out crew for a few communities near you{anchor}. When a unit's "
                  "left full — or there's a pile at the dumpster enclosure — we're there same or next "
                  "day, you get a firm price before the truck rolls, and the unit's rentable again "
                  "about 24 hours sooner than waiting on a rental dumpster. COI and W-9 go to you today."),
        "trigger": ("Anything sitting in a unit right now — a trash-out, a set-out, a mattress by the "
                    "dumpster? … When's your next move-out?"),
        "close": "I can have a crew there {slot1} or {slot2} — which works?",
        "discover": [
            "Who handles your turns when a unit's left full — maintenance supervisor or community manager?",
            "Anything sitting in a unit right now, or at the dumpster enclosure?",
            "When's your next move-out?",
        ],
        "pitch": ("Trash-outs and set-outs for communities near you: firm price before the truck "
                  "rolls, same or next day, COI and W-9 on file today."),
    },
    "storage": {
        "role": "Who handles the abandoned units — the property manager or the district manager?",
        "burst": ("We clear auctioned and abandoned units for storage facilities near you{anchor}: "
                  "firm price from a photo, same or next day, and the unit's rentable again "
                  "the same week."),
        "trigger": "Any units cut and waiting to be cleared right now? … When's the next auction?",
        "close": "I can have a crew there {slot1} or {slot2} — which works?",
        "discover": ["Who handles abandoned units?", "Any units waiting to be cleared right now?", "When's the next auction?"],
        "pitch": "Abandoned-unit clearouts, firm price from a photo, same or next day.",
    },
    "estate": {
        "role": "Are you the one who books the clear-out after a sale, or is that the family?",
        "burst": ("You close the sale Saturday, we clear the house Monday and the family gets the "
                  "keys back — firm price up front, donation drop-offs where things qualify."),
        "trigger": "Is there a sale wrapping up this week or next that'll need a clear-out?",
        "close": "Want me to hold {slot1} for that house? Or {slot2}?",
        "discover": ["Who books the clear-out after a sale?", "A sale wrapping up this week or next?"],
        "pitch": "Post-sale clear-outs, firm price up front, donation drop-offs.",
    },
    "realtor": {
        "role": "Are you the listing agent, or do you handle the estate side too?",
        "burst": ("When a listing or an estate needs a cleanout before it can move, your sellers "
                  "get one number: firm price up front, insured local crew, gone same or next day — "
                  "and you get a 10% referral credit on every job."),
        "trigger": "Anything on your desk right now that needs to be cleared before it can list?",
        "close": "I'll text you the referral link now — and for that listing, {slot1} or {slot2}?",
        "discover": ["Listing agent or estate side too?", "Anything right now that needs clearing before it lists?"],
        "pitch": "One number for sellers: firm price, insured crew, same or next day, 10% referral credit.",
    },
    "flipper": {
        "role": "Are you running the crews yourself, or is there a project manager I should talk to?",
        "burst": ("We quote from photos and clear it same or next day so your crew starts demo on "
                  "day one — no dumpster permit, no rental sitting half-empty."),
        "trigger": "What's the next property you're clearing? Got photos?",
        "close": "Send me the address and photos and I'll have a firm number back today — crew {slot1} or {slot2}?",
        "discover": ["Who runs the crews?", "What's the next property you're clearing?"],
        "pitch": "Photo quote, cleared same or next day, no dumpster permit.",
    },
    "senior": {
        "role": "Are you the one coordinating the move, or is there a family member I should loop in?",
        "burst": ("We handle the haul-away leg of a downsize: respectful crew, firm price up front, "
                  "donation drop-offs. You stay the trusted face; we do the lifting."),
        "trigger": "Is there a move coming up this month where the family will need the leftovers gone?",
        "close": "Want me to hold {slot1} for that move? Or {slot2}?",
        "discover": ["Who coordinates the move?", "A move this month with leftovers?"],
        "pitch": "Haul-away for downsizes: respectful crew, firm price, donation drop-offs.",
    },
    "mover": {
        "role": "Are you the owner, or the dispatcher who books the trucks?",
        "burst": ("When your customer has stuff that isn't moving with them, we take it the same day "
                  "— you look full-service, and you keep 10% of every job you send."),
        "trigger": "Any moves this week where the customer's leaving stuff behind?",
        "close": "I'll text you the referral link now — and for that move, {slot1} or {slot2}?",
        "discover": ["Owner or dispatcher?", "Any moves this week leaving stuff behind?"],
        "pitch": "Same-day haul-away for your customers' leftovers; 10% referral.",
    },
    "contractor": {
        "role": "Are you the one who books the haul-off, or your project manager?",
        "burst": ("Debris and demo haul-off, firm price from a photo, same or next day — so the "
                  "job site isn't waiting on a rental dumpster."),
        "trigger": "What's on the site right now that needs to go? … Got a photo?",
        "close": "Crew {slot1} or {slot2}?",
        "discover": ["Who books the haul-off?", "What's on the site now that needs to go?"],
        "pitch": "Debris haul-off, firm price from a photo, same or next day.",
    },
    "generic": {
        "role": "Who handles it when there's a pile that needs to go — you, or someone on your team?",
        "burst": ("We're the junk-removal crew for businesses near you{anchor}: firm price before the "
                  "truck rolls, same or next day, COI and W-9 on file today."),
        "trigger": "Anything sitting there right now that needs to go?",
        "close": "I can have a crew there {slot1} or {slot2} — which works?",
        "discover": ["Who handles it when there's a pile?", "Anything sitting there right now?"],
        "pitch": "Firm price before the truck rolls, same or next day, insured crew.",
    },
}

# Said in red, in the kit. Each one is in the transcripts, and each one is
# the moment the call stopped going anywhere.
_FORBIDDEN = [
    ("\"Did I catch you at a bad time?\"", "the lowest-converting opener measured (0.9%). Say the reason for the call."),
    ("\"That's what we do though.\"", "a rebuttal to 'we have someone'. Pause, then ask how that's working out."),
    ("\"No problem / okay\" after an objection", "it ends the call. Ask a question instead."),
    ("\"Can I leave a card on file?\" as the close", "a leasing agent can say yes to it and nothing happens. Ask for a date."),
    ("\"How many doors do you manage?\" before the trigger question", "discovery before they've told you there's a pile."),
    ("\"Umuve\" without spelling it", "it transcribes as 'you move'. U-M-U-V-E, trucks in West Palm."),
]

# When they ask. Floor plus structure plus the free look — never "it depends".
_PRICE_LINE = ("$119 covers a few pieces. A full unit the crew prices on the spot and leaves at no "
               "charge if it doesn't work for you. Text me a photo and I'll give you a firm number in minutes.")

# Captured before the goodbye, every time.
_CAPTURE = "What's the best cell to text that to? … You'll see it land now — reply Y and you're set."

_DEMAND_SEGMENT_KEYS = [
    (("moving", "mover", "movers", "fletes", "mudanza"), "mover"),
    (("property", "hoa", "apartment", "commercial", "office", "institution", "hotel"), "property"),
    (("storage",), "storage"),
    (("real estate", "staging", "probate", "realtor", "broker"), "realtor"),
    (("estate", "auction", "antiques"), "estate"),
    (("thrift", "donation"), "thrift"),
    (("investor", "flipper"), "flipper"),
    (("senior",), "senior"),
    (("contractor", "flooring", "restoration", "handyman", "painting", "roof"), "contractor"),
]


def demand_segment(category):
    c = (category or "").lower()
    for keys, name in _DEMAND_SEGMENT_KEYS:
        if any(k in c for k in keys):
            return name
    return "property"


# defuse → calibrated question → small ask. Top reps answer an objection
# with a question 54% of the time (vs 31%); half of cold-call objections are
# reflexive and dissolve on the second sentence.
_DEMAND_OBJECTIONS = [
    ("We already have someone.",
     "That's okay — most communities do, and we're usually the second number. "
     "How's that working out when you've got two turns in the same week? … "
     "Let us take one unit as the backup: firm price, same or next day, and I'll send the COI today."),
    ("Maintenance handles it.",
     "Makes sense — most places start there. What does a turn cost you when your tech spends the "
     "afternoon dragging a sofa to the dumpster instead of fixing the next unit? … "
     "Give us the next full unit and keep your guys on make-readies."),
    ("Corporate approves vendors.",
     "Right — so the packet's the first step. Which portal do you use, Compliance Depot, VendorCafe "
     "or NetVendor? I'll get the COI and W-9 in today. … And a one-off under five hundred you can "
     "usually authorize on site — is there a unit right now?"),
    ("Just send me your info.",
     "Happy to — which do you need first, the COI or the rate card, and whose name goes on it? "
     "What's the best cell to text it to? … And while I've got you: anything sitting in a unit right now?"),
    ("How much?",
     _PRICE_LINE),
    ("Not interested / not now.",
     "Fair enough. Is it the timing, or is this just not a priority right now? … "
     "When's your next move-out? I'll check in that week — nothing before."),
    ("Who is this?",
     "It's {va} — I'm the booking desk for Umuve, U-M-U-V-E, our trucks are in West Palm. "
     "I'm calling the maintenance supervisors at communities near you."),
    ("Call me back later.",
     "Sure. Tomorrow morning or afternoon? … I'll put it on my calendar — and who should I ask for?"),
    ("We use a dumpster.",
     "Dumpsters are great for a demo. For a move-out or a few rooms we're usually cheaper than the "
     "rental plus the permit, and nothing sits in the lot. Want me to price your next one against it?"),
    ("Are you insured? Send the COI.",
     "Yes — licensed and insured, and the COI names your owner and management company as additional "
     "insured. Whose name goes on it, and where do I send it?"),
    ("I'm not the right person.",
     "No worries — who is? The maintenance supervisor or the community manager? … "
     "Could you put me through, or give me their name and cell?"),
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
     "The same day. When the job is marked complete, your share goes to your debit card that "
     "day — we cover the instant fee. No invoices, no waiting on the customer."),
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
    ("Getting paid", "Paid to their debit card the same day the job is marked complete. Umuve covers the instant fee. Phone-only haulers: Zelle the same day."),
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
        t = _DEMAND_TRACKS.get(seg) or _DEMAND_TRACKS["generic"]
        from close_desk import _slots
        slot1, slot2 = _slots()
        anchor = (" off " + prospect.city) if getattr(prospect, "city", None) else ""
        opener = ("Hi, this is {va} — I'm the booking desk for Umuve, that's U-M-U-V-E, our trucks are "
                  "in West Palm. Quick heads-up, this call's recorded for quality. How have you been? "
                  "The reason for my call is —").format(va=va)
        track = {"opener": opener, "role": t["role"], "burst": t["burst"].format(anchor=anchor),
                 "trigger": t["trigger"], "price": _PRICE_LINE,
                 "close": t["close"].format(slot1=slot1, slot2=slot2), "capture": _CAPTURE,
                 "discover": t["discover"], "pitch": t["pitch"], "segment": seg,
                 "forbidden": [{"line": a, "why": b} for a, b in _FORBIDDEN]}
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
