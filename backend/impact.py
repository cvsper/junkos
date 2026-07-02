"""
Rescue Engine v1 — disposition preference, driver outcome, and the customer
"impact receipt".

Design constraints (from the product brief, enforced here so no surface can
drift):
  * NEVER claim a partnership with a named charity (Goodwill, Habitat, Red
    Cross, Salvation Army, a church, a shelter, ...). We have no signed
    partners. All copy uses neutral, hedged wording.
  * Everything is an ESTIMATE, never a guarantee ("items MAY be routed toward
    donation or reuse partners", "estimated landfill diversion").
  * One place defines the choices + copy; backend, web, iOS, admin, and ESG all
    read from here (or mirror these exact strings) so they can't diverge.

This module has NO external dependencies and never touches the DB directly —
callers pass in the job (or its fields). Safe to import from anywhere.
"""
from __future__ import annotations

# --- Customer preference (chosen at booking) --------------------------------
# value -> (short label, helper copy shown under the option)
PREFERENCE_CHOICES = {
    "best": (
        "Let Umuve decide",
        "We'll aim for the most responsible option for each item.",
    ),
    "donate": (
        "Donate if usable",
        "Whenever possible, reusable items may be routed toward donation or reuse partners.",
    ),
    "recycle": (
        "Recycle",
        "We'll route recyclable materials to recycling where available.",
    ),
    "dispose": (
        "Dispose",
        "Standard responsible disposal.",
    ),
}
PREFERENCE_DEFAULT = "best"
VALID_PREFERENCES = set(PREFERENCE_CHOICES)

# --- Driver outcome (marked at completion) ----------------------------------
# value -> (label, whether it counts toward landfill diversion)
OUTCOME_CHOICES = {
    "donated":   ("Donated / routed for reuse", True),
    "recycled":  ("Recycled", True),
    "disposed":  ("Disposed", False),
    "mixed":     ("Mixed load (some diverted)", True),
    "could_not": ("Couldn't donate/recycle", False),
}
VALID_OUTCOMES = set(OUTCOME_CHOICES)

# Fraction of a "mixed" load we credit as diverted for estimate purposes.
# Deliberately conservative so we never overstate impact.
MIXED_DIVERSION_WEIGHT = 0.5


def normalize_preference(value):
    """Coerce any input to a valid preference, defaulting to 'best'."""
    v = (value or "").strip().lower()
    return v if v in VALID_PREFERENCES else PREFERENCE_DEFAULT


def normalize_outcome(value):
    """Coerce input to a valid outcome, or None if unrecognized."""
    v = (value or "").strip().lower()
    return v if v in VALID_OUTCOMES else None


def outcome_is_diverted(outcome):
    """True if this outcome kept something out of the landfill."""
    o = normalize_outcome(outcome)
    return bool(o and OUTCOME_CHOICES[o][1])


def _item_count(job):
    try:
        items = job.items or []
        # items can be [{"category":..,"quantity":..}, ...] or plain strings
        total = 0
        for it in items:
            if isinstance(it, dict):
                total += int(it.get("quantity") or 1)
            else:
                total += 1
        return total
    except Exception:
        return 0


def build_impact_summary(job):
    """Return the customer-facing impact-receipt copy for a completed job.

    Estimate-only, no charity names, no guarantees. Returns a short string
    suitable for the completion email / in-app receipt / tracking page, or a
    neutral fallback if the driver didn't mark an outcome.
    """
    outcome = normalize_outcome(getattr(job, "disposition_outcome", None))
    n = _item_count(job)
    items_phrase = "your items" if n != 1 else "your item"

    if outcome == "donated":
        return ("Your hauler marked {items} as reusable — whenever possible, "
                "reusable items may be routed toward donation or reuse "
                "partners. Thanks for helping keep usable items out of the "
                "landfill.").format(items=items_phrase)
    if outcome == "recycled":
        return ("Your hauler marked {items} as recyclable and routed them "
                "toward recycling where available. Thanks for helping reduce "
                "landfill waste.").format(items=items_phrase)
    if outcome == "mixed":
        return ("Your hauler diverted part of this load toward reuse or "
                "recycling where possible, with the rest responsibly "
                "disposed. Thanks for helping reduce landfill waste.")
    if outcome == "could_not":
        return ("We looked at reuse and recycling options for this load, but "
                "responsible disposal was the best fit this time. Thanks for "
                "choosing Umuve.")
    if outcome == "disposed":
        return ("Your pickup was completed and responsibly disposed. Thanks "
                "for choosing Umuve.")
    # No outcome marked — neutral confirmation, no impact claim.
    return "Your pickup is complete. Thanks for choosing Umuve."


def diversion_stats(jobs):
    """Aggregate an estimated-diversion summary over an iterable of jobs.

    Counts a job as (fully) diverted for donated/recycled, half for mixed.
    Returns a dict of counts + an estimated diversion percentage. Estimate
    only — labeled as such everywhere it's surfaced.
    """
    total = 0
    donated = recycled = disposed = mixed = could_not = 0
    diverted_weight = 0.0
    for j in jobs:
        o = normalize_outcome(getattr(j, "disposition_outcome", None))
        if o is None:
            continue
        total += 1
        if o == "donated":
            donated += 1
            diverted_weight += 1.0
        elif o == "recycled":
            recycled += 1
            diverted_weight += 1.0
        elif o == "mixed":
            mixed += 1
            diverted_weight += MIXED_DIVERSION_WEIGHT
        elif o == "disposed":
            disposed += 1
        elif o == "could_not":
            could_not += 1
    pct = round((diverted_weight / total) * 100, 1) if total else 0.0
    return {
        "jobs_with_outcome": total,
        "donated": donated,
        "recycled": recycled,
        "mixed": mixed,
        "disposed": disposed,
        "could_not": could_not,
        "estimated_diversion_percent": pct,
    }
