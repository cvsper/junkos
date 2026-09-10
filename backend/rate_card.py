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

ORANGE = (255, 106, 44)
INK = (17, 20, 26)
MUTED = (96, 104, 116)
FAINT = (150, 156, 166)
LINE = (225, 228, 232)
PAPER = (255, 255, 255)


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


def build_rate_card_pdf(prospect, va_name=None, prices=None, desk_number=None):
    """Return PDF bytes. `prices` is the kit price sheet (label/from rows)."""
    from fpdf import FPDF
    from call_kit import price_sheet, detect_side

    prices = prices or price_sheet()
    va = (va_name or "Tracy").split()[0]
    company = _ascii(prospect.company or "your business")
    city = _ascii(prospect.city or "South Florida")
    contact = _ascii((prospect.contact_name or "").split(" ")[0]) if prospect.contact_name else ""
    phone_line = _local_number(desk_number) if desk_number else "(561) 944-1636"
    today = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    supply = detect_side(prospect) == "supply"

    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    W = pdf.w - 36

    # ---- header band
    pdf.set_fill_color(*INK)
    pdf.rect(0, 0, pdf.w, 34, style="F")
    logo = os.path.join(os.path.dirname(__file__), "static", "brand-logo.png")
    if os.path.exists(logo):
        try:
            pdf.image(logo, x=18, y=8, h=18)
        except Exception:
            pass
    pdf.set_xy(18, 10)
    pdf.set_text_color(*PAPER)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_x(44)
    pdf.cell(0, 8, "Umuve", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(44)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(200, 205, 212)
    pdf.cell(0, 6, "Junk removal & cleanouts for South Florida businesses", new_x="LMARGIN", new_y="NEXT")

    # ---- prepared for
    pdf.set_xy(18, 42)
    pdf.set_text_color(*FAINT)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "RATE CARD PREPARED FOR", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 10, company, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "{} - {}".format(city, today), new_x="LMARGIN", new_y="NEXT")

    # ---- intro line
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
    pdf.multi_cell(W, 6, _ascii(intro))

    # ---- price table (two columns)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*FAINT)
    pdf.cell(0, 5, "ALL-IN PRICES, FROM", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    col_w = W / 2 - 4
    x0 = 18
    y0 = pdf.get_y()
    rows = [p for p in prices if p.get("from") and " per " not in p["label"].lower()
            and not p["label"].lower().startswith("misc")]
    minimum = min([p["from"] for p in rows] or [0])
    if minimum:
        rows.append({"label": "Small loads (bags, boxes, single items)", "from": minimum})
    half = (len(rows) + 1) // 2
    cols = [rows[:half], rows[half:]]
    row_h = 7.2
    for ci, col in enumerate(cols):
        x = x0 + ci * (col_w + 8)
        y = y0
        for p in col:
            pdf.set_xy(x, y)
            pdf.set_font("Helvetica", "", 10.5)
            pdf.set_text_color(*INK)
            pdf.cell(col_w - 22, row_h, _ascii(p["label"]))
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_xy(x + col_w - 22, y)
            pdf.cell(22, row_h, "${}".format(int(p["from"])), align="R")
            pdf.set_draw_color(*LINE)
            pdf.line(x, y + row_h, x + col_w, y + row_h)
            y += row_h
    pdf.set_y(y0 + half * row_h + 3)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*FAINT)
    pdf.multi_cell(W, 4.5, _ascii("Prices are all-in (labor, hauling, disposal, fees). Text a photo of the pile "
                                  "for an exact quote before anyone comes out. Volume rates for standing accounts."))

    # ---- what's included / how to book
    pdf.ln(4)
    y_top = pdf.get_y()
    left_x, right_x = 18, 18 + W / 2 + 4
    pdf.set_xy(left_x, y_top)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ORANGE)
    pdf.cell(col_w, 5, "WHAT'S INCLUDED", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    included = ["Upfront price - no surprises on site",
                "Same or next day in Palm Beach & Broward",
                "Licensed and insured crews",
                "Donation drop-offs where items qualify",
                "Furniture, appliances, mattresses, electronics, debris, hot tubs, pianos"]
    for line in included:
        pdf.set_x(left_x)
        pdf.multi_cell(col_w, 5.2, _ascii("- " + line))
    y_left_end = pdf.get_y()

    pdf.set_xy(right_x, y_top)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ORANGE)
    pdf.cell(col_w, 5, "HOW TO BOOK", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(right_x)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(col_w, 8, phone_line, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(right_x)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    how = ["Call or text - this number takes photos",
           "Ask for {} - your Umuve contact".format(va),
           "goumuve.com/partners for standing accounts",
           "goumuve.com/operators to join as a hauler" if supply else "Realtors: 10% referral credit on every job"]
    for line in how:
        pdf.set_x(right_x)
        pdf.multi_cell(col_w, 5.2, _ascii(line))
    pdf.set_y(max(y_left_end, pdf.get_y()))

    # ---- footer
    pdf.set_y(pdf.h - 22)
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y(), pdf.w - 18, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*FAINT)
    pdf.cell(0, 5, _ascii("Umuve - Licensed & insured - Palm Beach & Broward County, FL - Mon-Sat 7am-7pm, Sun 8am-5pm - goumuve.com"), ln=1, align="C")
    if contact:
        pdf.cell(0, 5, _ascii("Prepared for {} at {} by {} with Umuve.".format(contact, company, va)), ln=1, align="C")

    return bytes(pdf.output())
