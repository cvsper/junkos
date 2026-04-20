"""
B2B Commercial Portal — ESG capture (Spec 04 §9.5).

Adds two org columns via portal_v1_migrations.COLUMN_MIGRATIONS:

  * orgs.esg_report_enabled    BOOLEAN DEFAULT FALSE
  * orgs.esg_contact_email     VARCHAR(160)

Since we're not allowed to edit `models.py`, ESG reads/writes use raw SQL
against the live `orgs` table — the ORM's Org class doesn't know these
columns exist, which is fine because the ESG endpoint is the only
consumer.

`build_esg_report(org_id, month, year)` is the pure function; the Flask
route wrapper lives in routes/portal_v1.py.
"""

import calendar as _cal
import datetime as _dt

from sqlalchemy import and_, func, text

from models import db, Job


# Carbon intensity constant — rough per-tonne CO2e equivalent for
# landfill-diverted junk.  Spec §9.5: "use tonnage * 0.57 as rough
# constant."  Units: tonnes CO2e per tonne of material.
CO2E_PER_TONNE = 0.57


def _month_range(month, year):
    start = _dt.datetime(year, month, 1)
    last_day = _cal.monthrange(year, month)[1]
    end = _dt.datetime(year, month, last_day, 23, 59, 59)
    return start, end


def get_org_esg_settings(org_id):
    """Return {'esg_report_enabled': bool, 'esg_contact_email': str|None}.

    Reads raw from the `orgs` table so we don't need the columns to be
    mapped on the Org model.  If the columns don't exist yet (pre-
    migration) we return defaults instead of raising.
    """
    try:
        row = db.session.execute(
            text(
                "SELECT esg_report_enabled, esg_contact_email "
                "FROM orgs WHERE id = :oid"
            ),
            {"oid": org_id},
        ).fetchone()
    except Exception:
        return {"esg_report_enabled": False, "esg_contact_email": None}

    if row is None:
        return {"esg_report_enabled": False, "esg_contact_email": None}

    return {
        "esg_report_enabled": bool(row[0]) if row[0] is not None else False,
        "esg_contact_email": row[1],
    }


def set_org_esg_settings(org_id, enabled=None, contact_email=None):
    """Patch the two ESG columns via raw SQL."""
    sets = []
    params = {"oid": org_id}
    if enabled is not None:
        sets.append("esg_report_enabled = :enabled")
        params["enabled"] = bool(enabled)
    if contact_email is not None:
        sets.append("esg_contact_email = :email")
        params["email"] = contact_email
    if not sets:
        return
    db.session.execute(
        text("UPDATE orgs SET {} WHERE id = :oid".format(", ".join(sets))),
        params,
    )
    db.session.commit()


def build_esg_report(org_id, month, year):
    """Compute the ESG payload for a given org-month.

    Fields:
      * total_jobs            : int (status='completed' in window)
      * total_tonnage         : float (sum of Job.volume_estimate; treat
                                cubic-yard estimates as tonnes for the
                                MVP — the spec notes this is rough)
      * diverted_percent      : float 0..100 (placeholder: 100% diverted
                                assumption until landfill routing ties in)
      * co2e_tonnes           : float (tonnage * CO2E_PER_TONNE)
      * period                : {'month', 'year', 'start', 'end'}
    """
    period_start, period_end = _month_range(month, year)

    q = (
        db.session.query(
            func.count(Job.id),
            func.coalesce(func.sum(Job.volume_estimate), 0.0),
        )
        .filter(
            and_(
                Job.org_id == org_id,
                Job.status == "completed",
                Job.completed_at != None,  # noqa: E711
                Job.completed_at >= period_start,
                Job.completed_at <= period_end,
            )
        )
    )
    total_jobs, total_tonnage = q.one()
    total_tonnage = float(total_tonnage or 0.0)

    # Diversion rate placeholder.  Once LandfillRouting (spec 06) writes a
    # `diverted_tonnes` column on Job, replace with a real ratio.
    diverted_percent = 100.0 if total_jobs > 0 else 0.0

    co2e_tonnes = round(total_tonnage * CO2E_PER_TONNE, 3)

    return {
        "org_id": org_id,
        "period": {
            "month": month,
            "year": year,
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "total_jobs": int(total_jobs or 0),
        "total_tonnage": round(total_tonnage, 3),
        "diverted_percent": diverted_percent,
        "co2e_tonnes": co2e_tonnes,
        "co2e_per_tonne_assumed": CO2E_PER_TONNE,
    }
