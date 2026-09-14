"""Text a photo, get a FIRM price — so the number has to be right, and a guess
must never go out as one.

sevs, 14 Sep: "now do the photo to price promise". The promise is that the
price we text is the price you pay for what is in the photo.
"""
import os
from unittest import mock

import pytest

from models import db, Job, User, generate_uuid
from models_quote import PhotoQuote
import photo_quote


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "DESK_VA_NAME": "Tracy",
                                      "FRONTEND_URL": "https://app.goumuve.com"}):
        yield
    PhotoQuote.query.delete(); Job.query.delete(); User.query.delete()
    db.session.commit()


def _read(items, confidence=0.9, stairs=False, unclear=None):
    return {"items": [{"category": c, "quantity": q, "description": d, "confidence": confidence}
                      for c, q, d in items],
            "confidence": confidence, "stairs": stairs, "unclear": unclear or []}


# --- the bug that made a "firm" price unsafe -------------------------------

def test_a_category_the_model_invents_is_mapped_to_a_real_price():
    """The old prompt asked for "sectional"; the price table has no such key, so
    it fell through to a $25 unit and quoted $119 for a $193 sofa."""
    assert photo_quote.normalize_category("sectional") == "sofa_sectional"
    assert photo_quote.normalize_category("grey leather sectional") == "sofa_sectional"
    assert photo_quote.normalize_category("Coffee Table") == "table_coffee"
    assert photo_quote.normalize_category("recliner") == "chair_recliner"
    assert photo_quote.normalize_category("TV") == "tv_flatscreen"
    assert photo_quote.normalize_category("fridge") == "refrigerator"
    assert photo_quote.normalize_category("boxes of clothes") == "general"
    assert photo_quote.normalize_category("") == "general"
    assert photo_quote.normalize_category("unicorn") == "general"
    # everything it maps to must be priceable
    from routes.booking import CATEGORY_PRICES
    for word in list(photo_quote.SYNONYMS) + ["sectional", "fridge", "unicorn"]:
        assert photo_quote.normalize_category(word) in CATEGORY_PRICES


def test_the_prompt_can_only_name_categories_we_can_price():
    from routes.booking import CATEGORY_PRICES
    prompt = photo_quote._prompt("")
    listed = prompt.split("Use ONLY these category values:\n")[1].split("\n")[0]
    assert set(c.strip() for c in listed.split(",")) == set(CATEGORY_PRICES)


def test_a_sectional_is_priced_as_a_sectional():
    est = photo_quote.price([{"category": photo_quote.normalize_category("sectional"), "quantity": 1}])
    assert est["total"] > 180                      # not the $119 the old flow sent


# --- the confidence gate ---------------------------------------------------

def test_a_clear_photo_gets_a_firm_price_and_the_promise():
    with mock.patch.object(photo_quote, "analyze", return_value=_read([("sofa_sectional", 1, "grey sectional"),
                                                                      ("mattress", 2, "queen mattresses")])), \
         mock.patch.object(photo_quote, "_send", return_value=True) as send, \
         mock.patch.object(photo_quote, "_alert"):
        q = photo_quote.handle_photos("+15615550142", "how much?", ["https://x/1.jpg"])
    assert q.status == "quoted" and q.price and q.sent_at and q.asked
    body = send.call_args[0][1]
    assert "your price for what's in the photo" in body
    assert "all in" in body and "nothing added on the day" in body
    assert "Anything not pictured we price and you approve before it goes on the truck" in body
    assert "any stairs, and anything not in the photo" in body
    assert q.ref in body and "STOP" in body
    assert "estimate" not in body.lower()          # it is a price, not an estimate


def test_an_unsure_photo_goes_to_a_person_not_out_as_a_price():
    with mock.patch.object(photo_quote, "analyze",
                           return_value=_read([("general", 5, "a pile")], confidence=0.4)), \
         mock.patch.object(photo_quote, "_send", return_value=True) as send, \
         mock.patch.object(photo_quote, "_alert") as alert:
        q = photo_quote.handle_photos("+15615550142", "", ["https://x/1.jpg"])
    assert q.status == "needs_human"
    body = send.call_args[0][1]
    assert "firm price rather than a guess" in body and "Tracy" in body
    assert "$" not in body                         # no number goes out
    assert alert.call_count == 1


def test_something_it_could_not_see_also_goes_to_a_person():
    with mock.patch.object(photo_quote, "analyze",
                           return_value=_read([("sofa", 1, "sofa")], confidence=0.95,
                                              unclear=["a pile behind the sofa is cut off"])), \
         mock.patch.object(photo_quote, "_send", return_value=True), \
         mock.patch.object(photo_quote, "_alert"):
        q = photo_quote.handle_photos("+15615550142", "", ["https://x/1.jpg"])
    assert q.status == "needs_human" and q.price                 # priced for the desk, not sent


def test_vision_down_never_guesses():
    with mock.patch.object(photo_quote, "analyze", return_value=None), \
         mock.patch.object(photo_quote, "_send", return_value=True) as send, \
         mock.patch.object(photo_quote, "_alert"):
        q = photo_quote.handle_photos("+15615550142", "", ["https://x/1.jpg"])
    assert q.status == "needs_human" and "$" not in send.call_args[0][1]


def test_stairs_seen_in_the_photo_are_already_in_the_price():
    flat = photo_quote.price([{"category": "sofa", "quantity": 1}])["total"]
    with mock.patch.object(photo_quote, "analyze",
                           return_value=_read([("sofa", 1, "sofa")], stairs=True)), \
         mock.patch.object(photo_quote, "_send", return_value=True) as send, \
         mock.patch.object(photo_quote, "_alert"):
        q = photo_quote.handle_photos("+15615550142", "", ["https://x/1.jpg"])
    assert q.addons.get("stair_flights") == 1 and q.price > flat
    assert "Includes the stairs" in send.call_args[0][1]


# --- the two questions, answered ------------------------------------------

def test_reading_their_answer():
    assert photo_quote.parse_answer("no")["stair_flights"] == 0
    assert photo_quote.parse_answer("nope that's it")["stair_flights"] == 0
    assert photo_quote.parse_answer("2nd floor")["stair_flights"] == 1
    assert photo_quote.parse_answer("3rd floor, no elevator")["stair_flights"] == 2
    assert photo_quote.parse_answer("it's up one flight of stairs")["stair_flights"] == 1
    assert photo_quote.parse_answer("yes stairs")["stair_flights"] == 1
    assert photo_quote.parse_answer("no stairs")["stair_flights"] == 0
    assert photo_quote.parse_answer("also a washer and dryer")["more"]
    assert photo_quote.parse_answer("no")["more"] is None


def _quoted(digits="5615550142"):
    with mock.patch.object(photo_quote, "analyze", return_value=_read([("sofa", 1, "sofa")])), \
         mock.patch.object(photo_quote, "_send", return_value=True), \
         mock.patch.object(photo_quote, "_alert"):
        return photo_quote.handle_photos("+1" + digits, "", ["https://x/1.jpg"])


def test_stairs_in_a_reply_re_price_and_re_send():
    q = _quoted()
    before = q.price
    with mock.patch.object(photo_quote, "_send", return_value=True) as send:
        out = photo_quote.handle_reply("+15615550142", "3rd floor no elevator")
    assert out.id == q.id and out.status == "answered"
    assert out.addons["stair_flights"] == 2 and out.price > before
    assert "all in" in send.call_args[0][1]


def test_an_extra_item_in_a_reply_goes_to_a_person():
    q = _quoted()
    with mock.patch.object(photo_quote, "_send", return_value=True) as send, \
         mock.patch.object(photo_quote, "_alert") as alert:
        out = photo_quote.handle_reply("+15615550142", "also a washer and dryer in the garage")
    assert out.status == "needs_human" and alert.call_count == 1
    assert "Tracy will add that" in send.call_args[0][1]


def test_an_unrelated_text_is_left_for_normal_routing():
    assert photo_quote.handle_reply("+15619990000", "what are your hours") is None


# --- the desk sees them, and the promise is measured -----------------------

def test_a_photo_quote_is_the_first_thing_in_the_lead_list():
    _quoted()
    from leads import collect
    rows, broken = collect()
    assert "photo" not in broken
    assert rows and rows[0]["kind"] == "photo" and rows[0]["source_label"] == "Photo quote"
    assert rows[0]["quote_price"] and rows[0]["phone_digits"] == "5615550142"


def test_booking_then_completing_records_whether_the_price_held():
    q = _quoted()
    u = User(id=generate_uuid(), name="Dana", phone="+15615550142", email="d@t.local", role="customer")
    db.session.add(u); db.session.flush()
    job = Job(id=generate_uuid(), customer_id=u.id, status="pending", address="12 Palm Way",
              items=[{"category": "sofa", "quantity": 1}], total_price=q.price,
              confirmation_code="PQ1")
    db.session.add(job); db.session.commit()

    assert photo_quote.link_job(job, ref=q.ref).id == q.id
    db.session.refresh(q); assert q.status == "booked" and q.job_id == job.id

    job.total_price = q.price + 40.0                    # an approved on-site add-on
    db.session.commit()
    with mock.patch.object(photo_quote, "_alert") as alert:
        photo_quote.record_final(job)
    db.session.refresh(q)
    assert q.final_price == q.price + 40.0 and q.drift == 40.0
    assert alert.call_count == 1                        # drift that big is worth knowing

    rep = photo_quote.drift_report(30)
    assert rep["booked"] == 1 and rep["completed"] == 1 and rep["avg_drift"] == 40.0


def test_admin_report_is_gated(client):
    assert client.get("/api/admin/photo-quotes").status_code == 401
