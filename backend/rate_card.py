"""Branded one-page rate card PDF, personalized to a prospect.

"Send us something" gets a real document: the company's name on it, the
live engine prices, what's included, how to book. Built with fpdf2 (pure
Python). Served from a signed URL so it can be texted as a link and
attached to email; the signature keeps prospect ids from being enumerable.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone

RED = (197, 34, 34)
INK = (17, 20, 26)
BAND = (43, 44, 48)
MUTED = (96, 108, 128)
FAINT = (138, 147, 162)
LINE = (222, 225, 230)
PAPER = (255, 255, 255)

# Authored stroke glyphs for the trust row (24-box, red stroke).
_ICON = {
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/><path d="M7 14h2M11 14h2M15 14h2M7 17.5h2M11 17.5h2"/>',
    "leaf": '<path d="M5 19C5 10 10 5 20 4c0 10-4 15-13 15z"/><path d="M5 19c3-5 6-8 10-10"/>',
    "people": '<circle cx="12" cy="7" r="3"/><circle cx="5" cy="10" r="2.2"/><circle cx="19" cy="10" r="2.2"/><path d="M7 20v-2a5 5 0 0 1 10 0v2z"/><path d="M1.5 18v-1.5a3.5 3.5 0 0 1 4.5-3.4M22.5 18v-1.5a3.5 3.5 0 0 0-4.5-3.4"/>',
    "pin": '<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>',
}


def _svg(name, color="#C52222", stroke=1.9):
    import io
    body = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
            '<g fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{p}</g></svg>'
            ).format(c=color, w=stroke, p=_ICON[name])
    return io.BytesIO(body.encode("utf-8"))


def _secret():
    return (os.environ.get("RATE_CARD_SECRET") or os.environ.get("SECRET_KEY")
            or os.environ.get("TRIXIE_ASSISTANT_PASSCODE") or "umuve-rate-card")


def sign(prospect_id):
    return hmac.new(_secret().encode(), ("rate-card:" + prospect_id).encode(),
                    hashlib.sha256).hexdigest()[:24]


def check_sig(prospect_id, sig):
    return hmac.compare_digest(sign(prospect_id), str(sig or ""))


def public_url(prospect_id):
    base = (os.environ.get("BACKEND_URL") or "https://junkos-backend.onrender.com").rstrip("/")
    return "{}/rate-card/{}.pdf?s={}".format(base, prospect_id, sign(prospect_id))


def _ascii(s):
    """fpdf2 core fonts are Latin-1: swap the punctuation we like to use."""
    return (str(s or "").replace("—", "-").replace("–", "-")
            .replace("’", "'").replace("‘", "'")
            .replace("“", '"').replace("”", '"').replace("·", "-")
            .encode("latin-1", "replace").decode("latin-1"))


def _local_number(e164):
    d = "".join(ch for ch in (e164 or "") if ch.isdigit())[-10:]
    return "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else (e164 or "")


def _spaced(pdf, text, spacing):
    pdf.set_char_spacing(spacing)
    w = pdf.get_string_width(text) + spacing * max(0, len(text) - 1) * 25.4 / 72
    return w


def build_rate_card_pdf(prospect, va_name=None, prices=None, desk_number=None):
    """Return PDF bytes. `prices` is the kit price sheet (label/from rows).

    One Letter page: dark brand band, the prospect's name, two price columns
    with a rule between them, what's included / how to book, a trust row,
    the truck-and-skyline hero, and a dark footer band."""
    from fpdf import FPDF
    from call_kit import price_sheet, detect_side

    prices = prices or price_sheet()
    va = (va_name or "Tracy").split()[0]
    company = _ascii(prospect.company or "your business")
    city = _ascii(prospect.city or "South Florida")
    contact = _ascii((prospect.contact_name or "").split(" ")[0]) if prospect.contact_name else ""
    phone_line = _local_number(desk_number) if desk_number else "(844) 435-6005"
    today = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    supply = detect_side(prospect) == "supply"
    here = os.path.dirname(__file__)

    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    PW = pdf.w
    W = PW - 36
    x0 = 18

    def img(path_or_buf, **kw):
        try:
            pdf.image(path_or_buf, **kw)
        except Exception:
            pass

    # ---- brand band -------------------------------------------------------
    BAND_H = 30
    pdf.set_fill_color(*BAND)
    pdf.rect(0, 0, PW, BAND_H, style="F")
    logo = os.path.join(here, "static", "brand-logo.png")
    if os.path.exists(logo):
        img(logo, x=x0, y=4.5, h=21)
    pdf.set_text_color(*PAPER)
    pdf.set_font("Helvetica", "B", 25)
    pdf.set_xy(x0 + 27, 6.5)
    pdf.cell(80, 10, "Umuve")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(214, 218, 224)
    pdf.set_xy(x0 + 27, 17)
    pdf.cell(80, 5, "Junk removal & cleanouts for South Florida businesses")
    # right: service strip with a red rule, then the line
    pdf.set_font("Helvetica", "B", 6.3)
    pdf.set_text_color(*PAPER)
    strip = "RESIDENTIAL   |   COMMERCIAL   |   PROPERTY CLEANOUTS"
    sw = _spaced(pdf, strip, 0.6)
    pdf.set_xy(PW - 18 - sw, 8.5)
    pdf.cell(sw, 4, strip)
    pdf.set_draw_color(*RED)
    pdf.set_line_width(0.6)
    pdf.line(PW - 18 - sw, 14.2, PW - 18, 14.2)
    pdf.set_font("Helvetica", "", 6.3)
    pdf.set_text_color(214, 218, 224)
    tag = "CLEAR SPACE. MOVE FORWARD."
    tw = _spaced(pdf, tag, 1.2)
    pdf.set_xy(PW - 18 - sw + (sw - tw) / 2, 17.5)
    pdf.cell(tw, 4, tag)
    pdf.set_char_spacing(0)

    # ---- prepared for ------------------------------------------------------
    pdf.set_xy(x0, BAND_H + 9)
    pdf.set_text_color(*FAINT)
    pdf.set_font("Helvetica", "B", 8)
    _spaced(pdf, "RATE CARD PREPARED FOR", 0.5)
    pdf.cell(0, 5, "RATE CARD PREPARED FOR", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_text_color(*INK)
    size = 24 if len(company) <= 26 else (20 if len(company) <= 36 else 16)
    pdf.set_font("Helvetica", "B", size)
    pdf.cell(0, 11, company, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "{} - {}".format(city, today), new_x="LMARGIN", new_y="NEXT")

    # ---- intro ----------------------------------------------------------------
    pdf.ln(3)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "", 11)
    if supply:
        intro = ("Umuve sends booked, paid junk-removal jobs to local hauling companies. "
                 "These are the prices customers pay per item; you keep the majority of every job, "
                 "paid to your debit card the same day the job is marked complete.")
    else:
        intro = ("One number for every cleanout. You get the exact price up front, "
                 "pickup same or next day, and one invoice a month for standing accounts.")
    pdf.multi_cell(W, 5.8, _ascii(intro), align="L")

    # ---- price columns ----------------------------------------------------------
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*FAINT)
    _spaced(pdf, "ALL-IN PRICES, FROM", 0.5)
    pdf.set_x(x0 + 2)
    pdf.cell(0, 5, "ALL-IN PRICES, FROM", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.ln(0.5)
    rows = [p for p in prices if p.get("from") and " per " not in p["label"].lower()
            and not p["label"].lower().startswith("misc")]
    minimum = min([p["from"] for p in rows] or [0])
    if minimum:
        rows.append({"label": "Small loads (bags, boxes, single items)", "from": minimum})
    half = (len(rows) + 1) // 2
    cols = [rows[:half], rows[half:]]
    gutter = 14
    col_w = (W - gutter) / 2
    row_h = 6.8
    y0 = pdf.get_y()
    for ci, col in enumerate(cols):
        x = x0 + ci * (col_w + gutter)
        y = y0
        for p in col:
            pdf.set_xy(x + 2, y)
            pdf.set_font("Helvetica", "", 10.5)
            pdf.set_text_color(*INK)
            pdf.cell(col_w - 26, row_h, _ascii(p["label"]))
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_xy(x + col_w - 24, y)
            pdf.cell(22, row_h, "${}".format(int(p["from"])), align="R")
            pdf.set_draw_color(*LINE)
            pdf.set_line_width(0.25)
            pdf.line(x + 2, y + row_h, x + col_w - 2, y + row_h)
            y += row_h
    table_h = half * row_h
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.35)
    pdf.line(x0 + col_w + gutter / 2, y0 - 1, x0 + col_w + gutter / 2, y0 + table_h + 1)
    pdf.set_y(y0 + table_h + 3)
    pdf.set_font("Helvetica", "I", 8.6)
    pdf.set_text_color(*MUTED)
    pdf.set_x(x0 + 2)
    pdf.multi_cell(W - 4, 4.4, _ascii("Prices are all-in (labor, hauling, disposal, fees). Text a photo of the pile "
                                      "for an exact quote before anyone comes out. Volume rates for standing accounts."))

    # ---- what's included / how to book ---------------------------------------
    pdf.ln(3.5)
    y_top = pdf.get_y()
    left_x, right_x = x0 + 2, x0 + col_w + gutter
    pdf.set_xy(left_x, y_top)
    pdf.set_font("Helvetica", "B", 13.5)
    pdf.set_text_color(*RED)
    _spaced(pdf, "WHAT'S INCLUDED", 0.9)
    pdf.cell(col_w, 7, "WHAT'S INCLUDED", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_draw_color(*RED)
    pdf.set_line_width(0.6)
    pdf.line(left_x, y_top + 8, left_x + 14, y_top + 8)
    pdf.set_y(y_top + 11)
    pdf.set_font("Helvetica", "", 10.2)
    pdf.set_text_color(*INK)
    included = ["Upfront price - no surprises on site",
                "Same or next day pickup in Palm Beach & Broward",
                "Licensed and insured crews",
                "Donation drop-offs where items qualify",
                "Furniture, appliances, mattresses, electronics, debris, hot tubs, pianos"]
    for line in included:
        pdf.set_x(left_x + 1)
        pdf.multi_cell(col_w - 2, 5.1, _ascii("-  " + line), align="L")
    y_left_end = pdf.get_y()

    pdf.set_xy(right_x, y_top)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*RED)
    pdf.cell(col_w, 7, "HOW TO BOOK", new_x="LMARGIN", new_y="NEXT")
    pdf.line(right_x, y_top + 8, right_x + 14, y_top + 8)
    pdf.set_xy(right_x, y_top + 10)
    pdf.set_font("Helvetica", "B", 25)
    pdf.set_text_color(*INK)
    pdf.cell(col_w, 10.5, phone_line, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(right_x)
    pdf.set_font("Helvetica", "", 10.2)
    pdf.set_text_color(*MUTED)
    how = ["Call or text - this number takes photos",
           "Ask for {} - your Umuve contact".format(va),
           "goumuve.com/partners for standing accounts",
           "goumuve.com/operators to join as a hauler" if supply else "Realtors: 10% referral credit on every job"]
    for line in how:
        pdf.set_x(right_x)
        pdf.multi_cell(col_w, 5.1, _ascii(line), align="L")
    y_cols_end = max(y_left_end, pdf.get_y())
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.35)
    pdf.line(x0 + col_w + gutter / 2, y_top + 1, x0 + col_w + gutter / 2, y_cols_end)

    # ---- trust row --------------------------------------------------------------
    FOOT_H = 16
    HERO_NAT = 32.9                      # the strip's natural height at page width
    ty = y_cols_end + 5
    # the hero gives way to the copy: shorter band, cropped from the sky down, never an overlap
    HERO_H = max(18, min(HERO_NAT, pdf.h - FOOT_H - (ty + 25)))
    hero_y = pdf.h - FOOT_H - HERO_H
    cells = [("shield", "LICENSED & INSURED", "Your property is protected"),
             ("calendar", "SAME OR NEXT DAY", "Fast, reliable service"),
             ("leaf", "DONATE & RECYCLE", "We keep usable items out of landfills"),
             ("people", "TRUSTED BY BUSINESSES", "Property managers, HOAs, realtors & more")]
    cw = W / 4
    for i, (icon, title, sub) in enumerate(cells):
        cx = x0 + i * cw
        img(_svg(icon), x=cx + cw / 2 - 4.5, y=ty, w=9)
        pdf.set_xy(cx, ty + 10.8)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        _spaced(pdf, title, 0.4)
        pdf.cell(cw, 4.5, title, align="C")
        pdf.set_char_spacing(0)
        pdf.set_xy(cx + 3, ty + 15.4)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(cw - 6, 3.8, sub, align="C")
        if i:
            pdf.set_draw_color(*LINE)
            pdf.set_line_width(0.3)
            pdf.line(cx, ty + 1, cx, ty + 21)

    # ---- hero + footer band ---------------------------------------------------
    hero = os.path.join(here, "static", "rate-card-hero.jpg")
    if os.path.exists(hero):
        try:
            with pdf.rect_clip(x=0, y=hero_y, w=PW, h=HERO_H):
                pdf.image(hero, x=0, y=hero_y + HERO_H - HERO_NAT, w=PW)
        except Exception:
            img(hero, x=0, y=hero_y, w=PW, h=HERO_H)
    pdf.set_fill_color(*BAND)
    pdf.rect(0, pdf.h - FOOT_H, PW, FOOT_H, style="F")
    fy = pdf.h - FOOT_H
    img(_svg("pin", color="#FFFFFF", stroke=1.8), x=x0, y=fy + 4.5, w=7)
    pdf.set_text_color(*PAPER)
    pdf.set_font("Helvetica", "", 8.2)
    pdf.set_xy(x0 + 9, fy + 3.6)
    pdf.cell(90, 4.5, _ascii("Umuve - Licensed & insured - Palm Beach & Broward County, FL"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(x0 + 9, fy + 8.2)
    pdf.cell(90, 4.5, _ascii("Mon-Sat 7am-7pm, Sun 8am-5pm - goumuve.com"))
    pdf.set_font("Helvetica", "B", 6.4)
    tags = ["JUNK REMOVAL. CLEANER PROPERTIES.", "STRONGER COMMUNITIES."]
    tw2 = max(_spaced(pdf, t, 0.7) for t in tags)
    for i, t in enumerate(tags):
        pdf.set_xy(PW - 18 - tw2, fy + 3.4 + i * 3.6)
        pdf.cell(tw2, 3.4, t, align="R")
    pdf.set_char_spacing(0)
    if contact:
        pdf.set_font("Helvetica", "I", 6.8)
        pdf.set_text_color(214, 218, 224)
        pdf.set_xy(PW - 18 - tw2, fy + 10.6)
        pdf.cell(tw2, 3.4, _ascii("Prepared for {} by {} with Umuve.".format(contact, va)), align="R")
    pdf.set_draw_color(120, 122, 128)
    pdf.set_line_width(0.3)
    pdf.line(PW - 18 - tw2 - 7, fy + 4, PW - 18 - tw2 - 7, fy + FOOT_H - 4)

    return bytes(pdf.output())
