"""The dump suggestion never sends a hauler somewhere that can't take the load."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from models import db, User, Contractor, Job, LandfillFacility, TipFee, generate_uuid
import dump_suggest
from seed_landfills import seed_landfill_facilities, FACILITIES

ET = ZoneInfo("America/New_York")
TUESDAY_10AM = datetime(2026, 9, 15, 10, 0, tzinfo=ET)
SUNDAY_10AM = datetime(2026, 9, 13, 10, 0, tzinfo=ET)
LANTANA = (26.60, -80.07)      # a job in Lantana, PBC
DAVIE = (26.07, -80.25)        # a job in Davie, Broward
MIAMI = (25.79, -80.23)        # a job in Wynwood, Dade
STUART = (27.19, -80.25)       # Martin County
COCOA = (28.36, -80.74)        # Brevard


@pytest.fixture(autouse=True)
def seeded(app, db_session):
    seed_landfill_facilities(db.session, LandfillFacility, TipFee, generate_uuid)
    yield


def _driver():
    u = User(id=generate_uuid(), email="dump@test.local", name="Dump Dan", phone="+15615550101", role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved", current_lat=26.60, current_lng=-80.07)
    db.session.add(c); db.session.commit()
    from auth_routes import generate_token
    return {"Authorization": "Bearer " + generate_token(u.id)}


def test_seed_is_idempotent_and_complete():
    n = LandfillFacility.query.count()
    assert n == len(FACILITIES)
    assert seed_landfill_facilities(db.session, LandfillFacility, TipFee, generate_uuid) == 0
    assert LandfillFacility.query.count() == n
    assert TipFee.query.filter_by(effective_to=None).count() > 100


def test_pbc_junk_load_goes_to_the_nearest_swa_station():
    out = dump_suggest.suggest(*LANTANA, category="bulky", tons=0.6, origin_county="palm-beach", now=TUESDAY_10AM)
    pick = out["suggested"]
    assert "Lantana" in pick["facility"]["name"]
    assert pick["rate_per_ton"] == 42.0
    assert pick["est_tip"] == pytest.approx(25.2)
    assert pick["open_now"] is True
    assert any("Open now" in r for r in pick["reasons"])
    assert any("$42.00/ton" in r for r in pick["reasons"])


def test_concrete_is_never_sent_to_a_transfer_station():
    out = dump_suggest.suggest(*LANTANA, category="concrete", tons=0.6, origin_county="palm-beach", now=TUESDAY_10AM)
    names = [r["facility"]["name"] for r in [out["suggested"]] + out["alternatives"]]
    assert all("Transfer Station" not in n for n in names)
    assert all(r["accepts"] for r in [out["suggested"]] + out["alternatives"])
    blocked = {n["name"]: n["blockers"] for n in out["not_eligible"]}
    assert any("Lantana" in n and "Doesn't take concrete" in b[0] for n, b in blocked.items())


def test_account_only_and_permit_sites_are_listed_but_never_suggested():
    out = dump_suggest.suggest(*DAVIE, category="bulky", tons=0.6, origin_county="broward", now=TUESDAY_10AM)
    assert "Oakes Road" in out["suggested"]["facility"]["name"]
    suggested_names = [r["facility"]["name"] for r in [out["suggested"]] + out["alternatives"]]
    assert not any("Monarch" in n or "Reuter" in n for n in suggested_names)
    out = dump_suggest.suggest(*MIAMI, category="bulky", tons=0.6, origin_county="miami-dade", now=TUESDAY_10AM)
    assert "Waste Connections Miami" in out["suggested"]["facility"]["name"]
    assert not any("Landfill" in r["facility"]["name"] and "Dade" in r["facility"]["name"]
                   for r in [out["suggested"]] + out["alternatives"])


def test_broward_landfill_refuses_out_of_county_loads():
    rows = dump_suggest.rank(*DAVIE, category="bulky", tons=0.6, origin_county="palm-beach", now=TUESDAY_10AM)
    lf = next(r for r in rows if "Broward County Landfill" in r["facility"]["name"])
    assert not lf["eligible"] and any("Broward County" in b for b in lf["blockers"])


def test_out_of_county_load_pays_the_swa_penalty_rate():
    rows = dump_suggest.rank(*LANTANA, category="bulky", tons=1.0, origin_county="broward", now=TUESDAY_10AM)
    lantana = next(r for r in rows if "Lantana" in r["facility"]["name"])
    assert lantana["rate_per_ton"] == 156.0 and lantana["rate_note"] == "out-of-county rate"


def test_closed_sites_rank_behind_open_ones_and_say_when_they_open():
    out = dump_suggest.suggest(*LANTANA, category="bulky", tons=0.6, origin_county="palm-beach", now=SUNDAY_10AM)
    pick = out["suggested"]
    # Everything SWA is shut on Sunday; the pick must say so rather than pretend.
    assert pick["open_now"] is False
    assert any("opens tomorrow" in c.lower() for c in pick["caveats"])


def test_north_counties_are_covered():
    out = dump_suggest.suggest(*STUART, category="bulky", tons=0.6, origin_county="martin", now=TUESDAY_10AM)
    assert "Palm City" in out["suggested"]["facility"]["name"]
    assert out["suggested"]["rate_per_ton"] == 53.60
    out = dump_suggest.suggest(*COCOA, category="c_and_d", tons=0.6, origin_county="brevard", now=TUESDAY_10AM)
    assert "Brevard" in out["suggested"]["facility"]["name"]


def test_category_is_inferred_from_the_job_items():
    assert dump_suggest.infer_category([{"name": "sofa"}, {"name": "mattress"}]) == "bulky"
    assert dump_suggest.infer_category([{"name": "sofa"}, {"name": "drywall scraps"}]) == "c_and_d"
    assert dump_suggest.infer_category([{"name": "palm fronds"}, {"name": "tree branches"}]) == "yard"
    assert dump_suggest.infer_category([{"name": "refrigerator"}, {"name": "washer"}]) == "appliance_w_freon"
    assert dump_suggest.county_for(26.60) == "palm-beach"
    assert dump_suggest.county_for(26.07) == "broward"
    assert dump_suggest.county_for(28.36) == "brevard"


def test_endpoint_needs_auth_and_uses_the_job(client):
    assert client.get("/api/driver/dump/suggest?lat=26.6&lng=-80.07").status_code == 401
    hdr = _driver()
    cx = User(id=generate_uuid(), email="cx@dump.test", name="Cx", phone="+15615550990", role="customer")
    db.session.add(cx); db.session.flush()
    job = Job(id=generate_uuid(), customer_id=cx.id, status="started", address="123 Lantana Rd", lat=26.60, lng=-80.07,
              items=[{"name": "sofa"}, {"name": "concrete pavers"}], volume_estimate=9.0, total_price=250.0)
    db.session.add(job); db.session.commit()
    r = client.get("/api/driver/dump/suggest?job_id={}".format(job.id), headers=hdr)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["assumptions"]["category"] == "c_and_d"
    assert body["assumptions"]["origin_county"] == "palm-beach"
    assert body["assumptions"]["tons"] == pytest.approx(0.6)
    assert body["suggested"]["facility"]["name"]
    assert body["suggested"]["reasons"]
    r = client.get("/api/driver/dump/suggest?lat=26.6&lng=-80.07&category=lava", headers=hdr)
    assert r.status_code == 400
    r = client.get("/api/driver/dump/facilities", headers=hdr)
    assert r.status_code == 200 and r.get_json()["count"] == len(FACILITIES)
