"""Reusable editorial / case-file email template.

Aesthetic: looks like a one-page letter pinned to a truck-yard wall, not a
Mailchimp template. Off-white paper, black masthead, big tabloid serif
headline, monospace 'case file' chrome. Operator-to-operator tone.

All styles inline. System fonts only (Georgia / Helvetica Neue / Courier New)
so it renders the same in Gmail, Outlook, Apple Mail without web font calls.

Use for any cold-outreach email — pass content, get HTML.
"""
from __future__ import annotations
from typing import Sequence


def render_editorial_letter(
    *,
    headline_html: str,
    eyebrow: str,
    paragraphs: Sequence[str],
    cta_text: str,
    cta_link: str,
    signature_name: str = "Shamar",
    signature_role: str = "FOUNDER · UMUVE · goumuve.com",
    masthead_brand: str = "UMUVE",
    masthead_meta: str = "DISPATCH No. 01 / 2026",
    label_strip: str = "CASE FILE · ONE OPERATOR TO ANOTHER",
    footer_left: str = "SENT DIRECT · NO AUTORESPONDER",
    footer_right: str = "REPLY “STOP” · I’M GONE",
    accent_color: str = "#DC2626",
) -> str:
    """Build the full HTML email.

    Args:
        headline_html: The big tabloid headline. HTML allowed (use <em>, <br/>,
            and a <span style="color:{accent}"> for accent characters).
        eyebrow: Tiny mono label above the headline (e.g. "SUBJECT · TOPIC").
        paragraphs: Body copy — list of HTML strings, rendered as <p>s.
        cta_text: Button label (will be uppercased visually via letter-spacing).
        cta_link: Button href.
        signature_name: Italic serif signature line.
        signature_role: Mono caption under signature.
        masthead_brand / masthead_meta: Top black bar contents.
        label_strip: Red strip under masthead.
        footer_left / footer_right: Mono lines at bottom.
        accent_color: Single accent (default Umuve red).
    """
    body_paragraphs = "".join(
        f'<p style="margin:0 0 18px;font-family:Georgia,\'Times New Roman\',serif;'
        f'font-size:18px;line-height:1.7;color:#0a0a0a">{p}</p>'
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#1a1a1a;font-family:Georgia,'Times New Roman',serif;color:#0a0a0a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#1a1a1a">
<tr><td align="center" style="padding:28px 12px">

  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#f5f1ea;border:1px solid #0a0a0a">

    <tr><td style="background:#0a0a0a;padding:18px 32px">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:#f5f1ea;font-size:22px;font-weight:900;letter-spacing:0.06em">{masthead_brand}</td>
        <td align="right" style="font-family:'Courier New',Courier,monospace;color:#888888;font-size:10px;letter-spacing:0.18em">{masthead_meta}</td>
      </tr></table>
    </td></tr>

    <tr><td style="background:{accent_color};padding:7px 32px;font-family:'Courier New',Courier,monospace;color:#ffffff;font-size:10px;letter-spacing:0.22em;font-weight:700">{label_strip}</td></tr>

    <tr><td style="padding:48px 40px 32px">

      <p style="margin:0 0 14px;font-family:'Courier New',Courier,monospace;font-size:11px;letter-spacing:0.18em;color:#666666">{eyebrow}</p>

      <h1 style="margin:0 0 24px;font-family:Georgia,'Times New Roman',serif;font-size:42px;line-height:1.05;font-weight:400;color:#0a0a0a;letter-spacing:-0.02em">{headline_html}</h1>

      <table cellpadding="0" cellspacing="0" border="0" width="80"><tr><td style="border-top:3px solid {accent_color};height:3px;line-height:3px;font-size:0">&nbsp;</td></tr></table>

      <div style="margin-top:36px">{body_paragraphs}</div>

      <table cellpadding="0" cellspacing="0" border="0" style="margin-top:14px"><tr><td style="background:#0a0a0a">
        <a href="{cta_link}" style="display:inline-block;padding:16px 30px;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:12px;color:#f5f1ea;text-decoration:none;font-weight:700;letter-spacing:0.18em">{cta_text}</a>
      </td></tr></table>

      <p style="margin:52px 0 4px;font-family:Georgia,'Times New Roman',serif;font-size:20px;font-style:italic;color:#0a0a0a">&mdash; {signature_name}</p>
      <p style="margin:0;font-family:'Courier New',Courier,monospace;font-size:11px;color:#666666;letter-spacing:0.1em">{signature_role}</p>

    </td></tr>

    <tr><td style="background:#0a0a0a;padding:16px 32px">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="font-family:'Courier New',Courier,monospace;color:#666666;font-size:10px;letter-spacing:0.12em">{footer_left}</td>
        <td align="right" style="font-family:'Courier New',Courier,monospace;color:#666666;font-size:10px;letter-spacing:0.12em">{footer_right}</td>
      </tr></table>
    </td></tr>

  </table>

</td></tr>
</table>
</body></html>"""
