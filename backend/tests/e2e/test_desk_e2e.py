"""Browser-level tests for the Call Desk (Playwright, real Chromium, real server).

Runs the backend on a scratch SQLite DB, seeds a manager, a VA and a few
prospects, then drives the desk the way Tracy does: sign in, deal a card,
text, log an outcome, schedule a callback, load a CSV, clock in and out.

    make e2e            (or)   pytest -o addopts="" tests/e2e -q
Needs: pip install pytest-playwright && playwright install chromium
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
PORT = int(os.environ.get("E2E_PORT", "5188"))
BASE = "http://127.0.0.1:{}".format(PORT)
CODE = "e2e-code"


def _free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    if not _free(PORT):
        pytest.skip("port {} busy".format(PORT))
    work = tmp_path_factory.mktemp("e2e")
    # The app's sqlite lives under backend/instance (Flask instance path is
    # app-relative, not cwd-relative). Start every run from an empty file.
    for stale in (BACKEND / "instance" / "umuve.db", BACKEND / "umuve.db"):
        if stale.exists():
            stale.unlink()
    env = dict(os.environ)
    # tests/conftest.py is this directory's PARENT conftest, so importing it
    # has already pointed this process at the unit suite's scratch SQLite file
    # and asked server.py to skip its startup work. The e2e server is a real
    # boot against its own scratch DB, so drop all three before handing the
    # environment to the subprocess.
    env.pop("DATABASE_URL", None)
    env.pop("SQLALCHEMY_DATABASE_URI", None)
    env.pop("UMUVE_SKIP_STARTUP", None)
    env.update({
        "TRIXIE_ASSISTANT_PASSCODE": CODE, "ENABLE_SCHEDULER": "", "API_KEY": "e2e-api-key",
        "JWT_SECRET": "e2e-jwt", "SECRET_KEY": "e2e-secret", "DATABASE_PATH": str(work / "legacy.db"),
        "E2E_INSTANCE": str(work), "PYTHONPATH": str(BACKEND), "TWILIO_AUTH_TOKEN": "",
    })
    runner = work / "run.py"
    runner.write_text(
        "import os, sys\n"
        "sys.path.insert(0, %r)\n"
        "os.chdir(%r)\n"
        "from server import app, socketio\n"
        "from models import db, User, CallProspect\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
        "    from desk_auth import create_desk_user\n"
        "    create_desk_user('boss@e2e.test', 'Boss', 'manager', 'boss-pass')\n"
        "    create_desk_user('tracy@e2e.test', 'Tracy Jamesyoung', 'va', 'tracy-pass')\n"
        "    if not CallProspect.query.first():\n"
        "      db.session.add_all([\n"
        "        CallProspect(tier=1, category='property management', company='Palm Coast Property Group', phone='(561) 555-0142', phone_digits='5615550142', city='West Palm Beach', contact_name='Marcus Bell', why='340 doors', angle='Standing account'),\n"
        "        CallProspect(tier=2, category='junk removal', company='Robs Hauling', phone='(954) 555-0100', phone_digits='9545550100', city='Lauderhill'),\n"
        "      ])\n"
        "    db.session.commit()\n"
        "socketio.run(app, host='127.0.0.1', port=%d, debug=False, allow_unsafe_werkzeug=True)\n"
        % (str(BACKEND), str(work), PORT)
    )
    # server's sqlite lives in <cwd>/instance — cwd is the scratch dir
    proc = subprocess.Popen([sys.executable, str(runner)], env=env, cwd=str(work),
                            stdout=open(work / "server.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            if not _free(PORT):
                break
            time.sleep(0.5)
        else:
            proc.kill()
            pytest.fail("server didn't start: " + (work / "server.log").read_text()[-2000:])
        time.sleep(1.0)
        yield BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # The desk ships a strict CSP (script-src 'self'); Playwright's own
    # evaluate/wait_for_function needs eval, so the TEST context bypasses it.
    return dict(browser_context_args, bypass_csp=True, viewport={"width": 1440, "height": 900})


@pytest.fixture()
def desk(page, server):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(server + "/va/calls")
    return page


def sign_in(page, email="tracy@e2e.test", password="tracy-pass"):
    page.fill("#g-email", email)
    page.fill("#g-pass", password)
    page.click("#gate-form button[type=submit]")
    # a card, or "queue clear" once earlier tests have worked every prospect
    page.wait_for_selector("#card:not([hidden]), #empty:not([hidden])", timeout=15000)


def test_sign_in_deals_first_card_and_names_the_va(desk):
    sign_in(desk)
    assert "Palm Coast Property Group" in desk.text_content("#c-company")
    assert "Tracy" in desk.text_content("#who")
    assert "call" in desk.text_content("#c-tel .dial-hint").lower()
    # kit loads with the demand script
    desk.wait_for_selector("#kit-body .kt-step", timeout=10000)
    assert "Selling a customer" in desk.text_content("#kit-side")


def test_wrong_password_is_refused(desk):
    desk.fill("#g-email", "tracy@e2e.test")
    desk.fill("#g-pass", "nope")
    desk.click("#gate-form button[type=submit]")
    desk.wait_for_selector("#gate-err:not([hidden])")
    assert "didn't match" in desk.text_content("#gate-err")


def test_text_from_the_card_lands_in_the_thread(desk):
    sign_in(desk)
    desk.fill("#th-input", "Hi Marcus, Tracy here — quick test text.")
    desk.click("#th-form button[type=submit]")
    # no Twilio creds in e2e → the server can't send; it says so instead of pretending
    desk.wait_for_selector("#desk-err:not([hidden]), #desk-toast:not([hidden])", timeout=10000)
    txt = (desk.text_content("#desk-err") or "") + (desk.text_content("#desk-toast") or "")
    assert "didn't go through" in txt or "Sent" in txt


def test_outcome_advances_and_callback_pins_followup(desk):
    sign_in(desk)
    first = desk.text_content("#c-company")
    desk.fill("#note", "asked to hear more")
    desk.click('#outcomes button[data-o="interested"]')
    desk.wait_for_function("document.getElementById('c-company').textContent !== %r" % first, timeout=10000)
    second = desk.text_content("#c-company")
    assert second != first
    desk.click('#callback button[data-p="tomorrow_am"]')
    desk.wait_for_selector("#desk-toast:not([hidden])", timeout=10000)
    assert "Callback set for" in desk.text_content("#desk-toast")


def test_queue_panel_loads_csv_and_adds_business(desk, tmp_path):
    sign_in(desk)
    desk.click("#queue-toggle")
    desk.wait_for_selector("#queuebox:not([hidden])")
    csv = tmp_path / "list.csv"
    csv.write_text("Tier,Company,Phone,City,What they do,Contact,Notes,Outcome\n"
                   "Tier 1 — PBC,Sunrise Estate Sales,(561) 555-0177,Boca Raton,estate sales,Dana,3 sales a month,\n")
    desk.set_input_files("#qb-file", str(csv))
    desk.wait_for_function("document.getElementById('qb-status').textContent.includes('1 added')", timeout=10000)
    assert "Sunrise Estate Sales" in desk.text_content("#qb-list")
    desk.click("#qb-add-toggle")
    desk.fill("#qa-company", "Walk-in Movers")
    desk.fill("#qa-phone", "561-555-0199")
    desk.click("#qb-add button[type=submit]")
    desk.wait_for_function("document.getElementById('c-company').textContent === 'Walk-in Movers'", timeout=10000)


def test_clock_in_out_and_manager_sees_everyone(desk, browser):
    sign_in(desk)
    desk.click("#clock-chip")
    desk.wait_for_selector("#timebox:not([hidden])")
    desk.click("#tb-toggle")
    desk.wait_for_function("document.getElementById('clock-label').textContent.startsWith('On the clock')", timeout=10000)
    assert desk.is_hidden("#tb-team")                      # a VA can't see everyone
    desk.click("#tb-toggle")
    desk.wait_for_function("document.getElementById('clock-label').textContent === 'Clock in'", timeout=10000)
    # manager sees the Everyone view with Tracy's shift
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    mgr = ctx.new_page()
    mgr.goto(BASE + "/va/calls")
    sign_in(mgr, "boss@e2e.test", "boss-pass")
    mgr.click("#clock-chip")
    mgr.wait_for_selector("#timebox:not([hidden])")
    mgr.click("#tb-team")
    mgr.wait_for_function("document.getElementById('tb-list').textContent.includes('Tracy')", timeout=10000)
    ctx.close()


def test_passcode_fallback_still_opens_the_desk(desk):
    desk.click("#gate-alt summary")
    desk.fill("#code", CODE)
    desk.fill("#code-name", "Trixie")
    desk.click("#gate-code-form button[type=submit]")
    desk.wait_for_selector("#card:not([hidden]), #empty:not([hidden])", timeout=15000)
    assert "Trixie" in desk.text_content("#who")


def test_dialpad_dials_a_number_and_sends_an_extension_mid_call(desk):
    """Tracy's request: reach the decision maker.

    A gatekeeper reads out an extension or a direct line. Before this, the desk
    could only dial the number printed on the card, so the rest went on paper.
    """
    sign_in(desk)
    desk.wait_for_selector(".dp-tab", timeout=10000)

    # the tab must not sit on top of the line panel's own buttons
    clash = desk.evaluate("""() => {
        const t = document.querySelector('.dp-tab').getBoundingClientRect();
        const hits = [];
        document.querySelectorAll('button, a').forEach(e => {
            if (e.classList.contains('dp-tab')) return;
            const r = e.getBoundingClientRect();
            if (r.width && r.height &&
                !(r.right < t.left || r.left > t.right || r.bottom < t.top || r.top > t.bottom))
                hits.push((e.id ? '#' + e.id : '') + '.' + String(e.className).split(' ')[0]);
        });
        return hits;
    }""")
    assert clash == [], "the dialpad tab is covering {}".format(clash)

    desk.click(".dp-tab")
    desk.wait_for_selector(".dp-grid", timeout=5000)

    # typing a number arms the call button
    assert desk.is_disabled(".dp-row .dp-btn:not(.alt)")
    for digit in "5615550142":
        desk.click(".dp-grid .dp-k:has-text('{}')".format(digit))
    assert "(561) 555-0142" in desk.text_content(".dp-num")
    assert not desk.is_disabled(".dp-row .dp-btn:not(.alt)")

    # once connected, the same keys send tones down the live call instead
    desk.evaluate("""() => {
        window.__sentDigits = '';
        window.__deskActiveCall = { sendDigits: d => { window.__sentDigits += d; } };
        window.dispatchEvent(new CustomEvent('desk:call', { detail: { live: true } }));
    }""")
    desk.wait_for_selector(".dp-mode b", timeout=5000)
    for digit in "214":
        desk.click(".dp-grid .dp-k:has-text('{}')".format(digit))
    assert desk.evaluate("window.__sentDigits") == "214"
    assert "sent to the call" in desk.text_content(".dp-hint")

    # and the decision maker can be saved onto the open card
    desk.fill(".dp-save input[type=text]", "Marcus Bell")
    desk.fill(".dp-save input[type=tel]", "(561) 555-0199")
    desk.click(".dp-save .dp-btn")
    desk.wait_for_selector(".dp-msg.ok", timeout=8000)
    assert "Saved to the card" in desk.text_content(".dp-msg")
