"""The hauler-facing pages must actually arrive styled.

These two screens — the job offer a hauler taps from an SMS, and the console a
phone-only hauler runs the job from — shipped for months under
`default-src 'none'`, which silently dropped their inline <style> block. The
markup was fine; the browser threw the CSS away and every hauler saw raw HTML
while being asked to drive to a stranger's address.

So these tests assert the two halves that have to stay true together:
  1. the CSP on those paths permits same-origin CSS, and
  2. the pages carry no inline styles, which that CSP would still refuse.
Either one alone is a page that looks broken.
"""
import re

import pytest


HAULER_PATHS = ("/o/sometoken", "/w/sometoken")


def _csp(client, path):
    return client.get(path).headers.get("Content-Security-Policy", "")


@pytest.mark.parametrize("path", HAULER_PATHS)
def test_csp_allows_same_origin_css(client, path):
    csp = _csp(client, path)
    assert "style-src 'self'" in csp, (
        "{} is served '{}' — a stylesheet link will be dropped".format(path, csp))
    assert "default-src 'none'" not in csp


@pytest.mark.parametrize("path", HAULER_PATHS)
def test_csp_still_refuses_inline_styles(client, path):
    """The permission we granted is deliberately narrow: files, not inline."""
    assert "'unsafe-inline'" not in _csp(client, path)


@pytest.mark.parametrize("path", HAULER_PATHS)
def test_pages_carry_no_inline_styles(client, path):
    html = client.get(path).get_data(as_text=True)
    assert "<style" not in html, "{} still has an inline <style> block".format(path)
    assert not re.search(r'\sstyle\s*=\s*"', html), (
        "{} still has an inline style attribute".format(path))


@pytest.mark.parametrize("path", HAULER_PATHS)
def test_pages_link_the_stylesheet(client, path):
    html = client.get(path).get_data(as_text=True)
    assert '/static/hauler.css' in html


def test_the_stylesheet_is_actually_served(client):
    r = client.get("/static/hauler.css")
    assert r.status_code == 200
    css = r.get_data(as_text=True)
    # The tokens the pages are drawn with; if these go, the page is not Umuve.
    for token in ("--canvas:#E4E5E9", "--ink:#17181C", "--go:#1F9D55", ".payout"):
        assert token in css


def test_an_unclaimable_offer_still_says_what_happens_next(client):
    """A dead link is a moment for direction, not a shrug."""
    html = client.get("/o/definitely-not-a-real-token").get_data(as_text=True)
    assert "isn't valid" in html
    assert "/static/hauler.css" in html
