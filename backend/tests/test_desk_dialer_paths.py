"""Every way of starting a call on the Call Desk must go through the one
shared dialer, or the call is never registered and the keypad can't send
tones. Tracy hit exactly that on 14 Sep: calling back a missed call reached
a phone tree ("press 2 for sales") with no keypad anywhere, because only the
prospect card's own dial path registered the call."""
import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parent.parent
DIAL_SCRIPTS = ("desk-inbound.js", "desk-leads.js", "desk-work.js", "desk-dialpad.js")


def _read(name):
    return (BACKEND / "static" / name).read_text()


def test_the_page_exposes_one_shared_dialer():
    page = (BACKEND / "va_calls.py").read_text()
    assert "window.__deskDial = function(to, opts)" in page
    # it must register the call the keypad reads, and announce the state change
    assert "window.__deskActiveCall = call" in page
    assert 'CustomEvent("desk:call"' in page
    # and the card's own path goes through it too, so there is only one behaviour
    start = page[page.index("function startDeskCall("):]
    start = start[:start.index("\n  }")]
    assert "window.__deskDial(" in start and "device.connect(" not in start


def test_no_panel_dials_the_device_behind_the_dialers_back():
    for name in DIAL_SCRIPTS:
        src = _read(name)
        assert "window.__deskDial" in src, "{} never uses the shared dialer".format(name)
        for m in re.finditer(r"\.connect\(\{\s*params", src):
            before = src[max(0, m.start() - 700):m.start()]
            assert "__deskDial" in before, (
                "{}: a .connect({{params…}}) at char {} is not behind a __deskDial fallback — "
                "that call would have no strip and no keypad".format(name, m.start()))


def test_keypad_sends_tones_through_the_registered_call():
    src = _read("desk-dialpad.js")
    assert "window.__deskActiveCall" in src and "call.sendDigits(k)" in src
    assert 'getElementById("cs-keypad")' in src          # reachable from the call strip
    assert 'window.addEventListener("desk:call"' in src   # and it learns when a call goes live


def test_the_call_strip_offers_the_keypad():
    page = (BACKEND / "va_calls.py").read_text()
    assert 'id="cs-keypad"' in page and "Keypad" in page
    assert ".callstrip.live .cs-key{" in page              # highlighted while connected
