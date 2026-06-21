"""
Professional HTML email templates for Umuve.

Every public function returns a complete HTML string ready for sending via
the ``send_email`` helper in ``notifications.py``.

Design tokens:
  - Primary accent: #DC2626 (red)
  - Background:     #fafaf8 (warm off-white)
  - Card:           #ffffff
  - Text dark:      #111827
  - Text muted:     #4b5563 / #6b7280
  - Font stack:     Outfit, DM Sans, Arial, sans-serif

All styles are inlined for maximum email-client compatibility.  No external
resources (fonts, images, scripts) are referenced.
"""

from html import escape as _esc


# ---------------------------------------------------------------------------
# Shared layout helpers
# ---------------------------------------------------------------------------

def _header():
    """Umuve branded header block."""
    return (
        '<div style="text-align:center;margin-bottom:30px;">'
        '<h1 style="color:#DC2626;font-size:28px;margin:0;font-family:\'Outfit\',\'DM Sans\',Arial,sans-serif;font-weight:700;letter-spacing:-0.5px;">Umuve</h1>'
        '<p style="color:#6b7280;margin:5px 0 0;font-size:14px;">Premium Junk Removal</p>'
        '</div>'
    )


def _footer():
    """Umuve footer with company address."""
    return (
        '<div style="text-align:center;margin-top:30px;padding-top:20px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px;line-height:1.6;">'
        '<p style="margin:0 0 4px;">Umuve &mdash; South Florida\'s Premium Junk Removal</p>'
        '<p style="margin:0 0 4px;">Palm Beach &amp; Broward County, FL</p>'
        '<p style="margin:0;">(561) 944-1636 &middot; contact@goumuve.com</p>'
        '</div>'
    )


def _wrap(body_html):
    """Wrap inner content in the common email shell (background, card, header, footer)."""
    return (
        '<!DOCTYPE html>'
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Umuve</title></head>'
        '<body style="margin:0;padding:0;background-color:#f3f4f6;-webkit-text-size-adjust:100%;">'
        '<div style="font-family:\'Outfit\',\'DM Sans\',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fafaf8;padding:40px 20px;">'
        + _header()
        + '<div style="background:#ffffff;border-radius:12px;padding:30px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
        + body_html
        + '</div>'
        + _footer()
        + '</div></body></html>'
    )


def _detail_row(label, value, is_last=False):
    """Single key-value row for detail tables."""
    border = 'border-top:1px solid #FECACA;' if is_last else ''
    pad_top = '12px' if is_last else '8px'
    val_color = '#DC2626' if is_last else '#111827'
    val_size = '20px' if is_last else '14px'
    val_weight = '700' if is_last else '600'
    return (
        '<tr style="{border}">'
        '<td style="padding:{pt} 0 8px;color:#6b7280;font-size:14px;">{label}</td>'
        '<td style="padding:{pt} 0 8px;color:{vc};font-size:{vs};font-weight:{vw};text-align:right;">{value}</td>'
        '</tr>'
    ).format(border=border, pt=pad_top, label=_esc(str(label)),
             value=_esc(str(value)), vc=val_color, vs=val_size, vw=val_weight)


def _detail_table(rows):
    """Red-tinted detail box.  *rows* is a list of (label, value) tuples."""
    inner = ''
    for i, (label, value) in enumerate(rows):
        inner += _detail_row(label, value, is_last=(i == len(rows) - 1))
    return (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:20px;margin:20px 0;">'
        '<table style="width:100%;border-collapse:collapse;">'
        + inner
        + '</table></div>'
    )


def _button(url, label):
    """Call-to-action button."""
    return (
        '<div style="text-align:center;margin:28px 0 12px;">'
        '<a href="{url}" style="display:inline-block;background:#DC2626;color:#ffffff;'
        'text-decoration:none;padding:14px 36px;border-radius:8px;font-size:16px;'
        'font-weight:600;line-height:1;">'.format(url=_esc(str(url)))
        + _esc(str(label))
        + '</a></div>'
    )


# ---------------------------------------------------------------------------
# 1. Booking confirmation
# ---------------------------------------------------------------------------

def booking_confirmation_html(customer_name, booking_id, address, date, time, total):
    """Return HTML for a booking-confirmed email."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    short_id = str(booking_id)[:8] if booking_id else 'N/A'
    try:
        total_fmt = '${:.2f}'.format(float(total))
    except (TypeError, ValueError):
        total_fmt = '$0.00'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Booking Confirmed!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">Your junk removal is scheduled. Here are your details:</p>'
    ).format(name=name)

    body += _detail_table([
        ('Booking ID', '#{}'.format(short_id)),
        ('Address', address or 'TBD'),
        ('Date', date or 'TBD'),
        ('Time', time or 'TBD'),
        ('Total', total_fmt),
    ])

    body += (
        '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
        'We\'ll send you a reminder 24 hours before your appointment. '
        'Need to reschedule? Reply to this email or call us at '
        '<strong>(561) 944-1636</strong>.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 2. Driver / crew assigned
# ---------------------------------------------------------------------------

def booking_assigned_html(customer_name, driver_name, truck_type, eta):
    """Return HTML for a driver-assigned notification."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    driver = _esc(str(driver_name)) if driver_name else 'Your driver'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Your Crew Is Assigned!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">Great news &mdash; a crew has been assigned to your upcoming pickup.</p>'
    ).format(name=name)

    body += _detail_table([
        ('Driver', driver),
        ('Truck', _esc(str(truck_type)) if truck_type else 'Standard'),
        ('ETA', _esc(str(eta)) if eta else 'TBD'),
    ])

    body += (
        '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
        'We\'ll notify you again once your driver is en route. '
        'If you have any questions, call us at <strong>(561) 944-1636</strong>.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 3. Driver en route
# ---------------------------------------------------------------------------

def driver_en_route_html(customer_name, driver_name, eta_minutes):
    """Return HTML for a driver-on-the-way notification."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    driver = _esc(str(driver_name)) if driver_name else 'Your driver'
    try:
        minutes = int(eta_minutes)
    except (TypeError, ValueError):
        minutes = None

    eta_text = '{} minutes'.format(minutes) if minutes else 'shortly'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Your Driver Is On The Way!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        '<strong>{driver}</strong> is headed to your location and should arrive in '
        '<strong>{eta}</strong>.</p>'
    ).format(name=name, driver=driver, eta=_esc(eta_text))

    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:24px;margin:20px 0;text-align:center;">'
        '<p style="color:#6b7280;font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.5px;">Estimated Arrival</p>'
        '<p style="color:#DC2626;font-size:36px;font-weight:700;margin:0;">{eta}</p>'
        '</div>'
    ).format(eta=_esc(eta_text))

    body += (
        '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
        'Please make sure the items are accessible. '
        'If you need to reach your driver, call us at <strong>(561) 944-1636</strong>.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 4. Job completed
# ---------------------------------------------------------------------------

def job_completed_html(customer_name, booking_id, total, rating_url):
    """Return HTML for a job-completed email with a rating CTA."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    short_id = str(booking_id)[:8] if booking_id else 'N/A'
    try:
        total_fmt = '${:.2f}'.format(float(total))
    except (TypeError, ValueError):
        total_fmt = '$0.00'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Job Complete!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Your junk removal (Booking <strong>#{id}</strong>) has been completed. '
        'We hope everything went smoothly!</p>'
    ).format(name=name, id=_esc(short_id))

    body += _detail_table([
        ('Booking ID', '#{}'.format(short_id)),
        ('Total Charged', total_fmt),
    ])

    if rating_url:
        body += (
            '<p style="color:#4b5563;font-size:14px;line-height:1.6;text-align:center;">'
            'We\'d love your feedback &mdash; it only takes 30 seconds:</p>'
        )
        body += _button(rating_url, 'Rate Your Experience')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'Thank you for choosing Umuve!</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 5. Payment receipt
# ---------------------------------------------------------------------------

def payment_receipt_html(customer_name, booking_id, amount, payment_method_last4, date):
    """Return HTML for a payment receipt."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    short_id = str(booking_id)[:8] if booking_id else 'N/A'
    try:
        amt_fmt = '${:.2f}'.format(float(amount))
    except (TypeError, ValueError):
        amt_fmt = '$0.00'

    last4 = _esc(str(payment_method_last4)) if payment_method_last4 else '****'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Payment Receipt</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Here\'s the receipt for your recent Umuve service.</p>'
    ).format(name=name)

    body += _detail_table([
        ('Booking ID', '#{}'.format(short_id)),
        ('Date', _esc(str(date)) if date else 'N/A'),
        ('Payment Method', 'Card ending in {}'.format(last4)),
        ('Amount Paid', amt_fmt),
    ])

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;">'
        'If you have billing questions, reply to this email or call '
        '<strong>(561) 944-1636</strong>.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 5b. Quick-checkout payment receipt (for pay-link / invoice payments)
# ---------------------------------------------------------------------------

def quick_checkout_receipt_html(customer_name, customer_email, amount,
                                 description, customer_company='',
                                 customer_address='', payment_intent_id=''):
    """Return HTML for a quick-checkout payment receipt email."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    try:
        amt_fmt = '${:.2f}'.format(float(amount))
    except (TypeError, ValueError):
        amt_fmt = '$0.00'

    short_ref = _esc(str(payment_intent_id)[-8:]) if payment_intent_id else 'N/A'

    body = (
        '<div style="text-align:center;margin-bottom:24px;">'
        '<div style="width:64px;height:64px;border-radius:50%;background:#f0fdf4;'
        'display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;">'
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20 6L9 17l-5-5"/></svg></div>'
        '<h2 style="color:#111827;margin:0 0 8px;font-size:24px;">Payment Received</h2>'
        '<p style="color:#6b7280;margin:0;font-size:15px;">Thank you for your payment, {name}!</p>'
        '</div>'
    ).format(name=name)

    # Detail rows
    rows = [('Service', _esc(str(description)))]
    if customer_company:
        rows.append(('Company', _esc(str(customer_company))))
    if customer_address:
        rows.append(('Pickup Location', _esc(str(customer_address))))
    rows.append(('Reference', '#{}'.format(short_ref)))
    rows.append(('Amount Paid', amt_fmt))

    body += _detail_table(rows)

    # What's included
    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:20px;margin:20px 0;">'
        '<h3 style="color:#111827;margin:0 0 12px;font-size:15px;">What\'s Included</h3>'
        '<div style="color:#4b5563;font-size:14px;line-height:2;">'
        '&#10003; Loading &amp; Labor<br>'
        '&#10003; Disposal &amp; Recycling<br>'
        '&#10003; Same-Day / Next-Day Service<br>'
        '&#10003; Licensed &amp; Insured</div>'
        '</div>'
    )

    body += (
        '<p style="color:#4b5563;line-height:1.6;font-size:14px;">'
        'Our team will be in touch to confirm your pickup details. '
        'If you have any questions, reply to this email or call us.</p>'
    )

    body += _button('tel:+15619441636', 'Call Us: (561) 944-1636')

    body += (
        '<p style="color:#6b7280;font-size:12px;line-height:1.6;text-align:center;margin-top:16px;">'
        'This receipt was sent to {email}. Keep it for your records.</p>'
    ).format(email=_esc(str(customer_email)))

    return _wrap(body)


# ---------------------------------------------------------------------------
# 6. Welcome
# ---------------------------------------------------------------------------

def welcome_html(name):
    """Return HTML for a welcome / signup email."""
    display_name = _esc(str(name)) if name else 'there'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Welcome to Umuve!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Thanks for signing up! We\'re South Florida\'s premium junk removal service, '
        'and we can\'t wait to help you reclaim your space.</p>'
    ).format(name=display_name)

    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:24px;margin:20px 0;">'
        '<h3 style="color:#111827;margin:0 0 12px;font-size:16px;">Here\'s what you can do:</h3>'
        '<ul style="color:#4b5563;padding-left:20px;margin:0;line-height:2;">'
        '<li>Book a pickup in under 2 minutes</li>'
        '<li>Upload photos for an instant estimate</li>'
        '<li>Track your driver in real time</li>'
        '<li>Pay securely online</li>'
        '</ul></div>'
    )

    body += _button('https://goumuve.com/book', 'Book Your First Pickup')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'Questions? Just reply to this email or call <strong>(561) 944-1636</strong>.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 6a. Job status update (generic — covers assigned, en_route, arrived, completed, cancelled)
# ---------------------------------------------------------------------------

_STATUS_HEADLINES = {
    'assigned':  'A Driver Has Been Assigned',
    'accepted':  'Your Driver Has Accepted the Job',
    'en_route':  'Your Driver Is On The Way',
    'arrived':   'Your Driver Has Arrived',
    'started':   'Junk Removal In Progress',
    'completed': 'Your Pickup Is Complete!',
    'cancelled': 'Your Booking Has Been Cancelled',
}

_STATUS_DESCRIPTIONS = {
    'assigned':  'A driver has been assigned to your upcoming pickup and will contact you when it\'s time.',
    'accepted':  'Your driver has confirmed and accepted the job. They\'ll be heading your way soon.',
    'en_route':  'Your driver is on the way to your location. Please make sure items are accessible.',
    'arrived':   'Your driver has arrived at the pickup location. Please meet them if possible.',
    'started':   'The removal is underway! Your driver is loading up the junk right now.',
    'completed': 'All done! Your junk has been hauled away. We hope everything went smoothly.',
    'cancelled': 'This booking has been cancelled. If this was a mistake, please contact us to rebook.',
}

_STATUS_ICONS = {
    'assigned':  '&#x1F69A;',  # truck
    'accepted':  '&#x2705;',   # check
    'en_route':  '&#x1F3CE;',  # racing car
    'arrived':   '&#x1F4CD;',  # pin
    'started':   '&#x1F4AA;',  # bicep
    'completed': '&#x1F389;',  # party popper
    'cancelled': '&#x274C;',   # cross
}


def job_status_update_html(customer_name, job_id, status, driver_name=None):
    """Return HTML for a generic job-status-change email.

    Covers: assigned, accepted, en_route, arrived, started, completed, cancelled.
    """
    name = _esc(str(customer_name)) if customer_name else 'there'
    short_id = str(job_id)[:8] if job_id else 'N/A'
    status_lower = (status or '').lower()

    headline = _STATUS_HEADLINES.get(status_lower, 'Job Status Update')
    description = _STATUS_DESCRIPTIONS.get(status_lower, 'Your job status has been updated to {}.'.format(_esc(status_lower)))
    icon = _STATUS_ICONS.get(status_lower, '&#x1F4E6;')

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">{icon} {headline}</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">{desc}</p>'
    ).format(icon=icon, headline=_esc(headline), name=name, desc=description)

    rows = [
        ('Booking ID', '#{}'.format(short_id)),
        ('Status', status_lower.replace('_', ' ').title()),
    ]
    if driver_name:
        rows.insert(1, ('Driver', _esc(str(driver_name))))

    body += _detail_table(rows)

    if status_lower == 'completed':
        body += (
            '<p style="color:#4b5563;font-size:14px;line-height:1.6;text-align:center;">'
            'We\'d love your feedback &mdash; it helps us improve!</p>'
        )
    elif status_lower == 'cancelled':
        body += (
            '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
            'If you\'d like to rebook, visit our website or call us at '
            '<strong>(561) 944-1636</strong>.</p>'
        )
    else:
        body += (
            '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
            'Questions? Reply to this email or call <strong>(561) 944-1636</strong>.</p>'
        )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 6b. Pickup reminder (24 hours before scheduled pickup)
# ---------------------------------------------------------------------------

def pickup_reminder_html(customer_name, job_id, address, date, time):
    """Return HTML for a 24-hour pickup reminder email."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    short_id = str(job_id)[:8] if job_id else 'N/A'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">&#x23F0; Pickup Reminder</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Just a friendly reminder that your junk removal pickup is '
        '<strong>tomorrow</strong>! Here are the details:</p>'
    ).format(name=name)

    body += _detail_table([
        ('Booking ID', '#{}'.format(short_id)),
        ('Address', _esc(str(address)) if address else 'TBD'),
        ('Date', _esc(str(date)) if date else 'TBD'),
        ('Time', _esc(str(time)) if time else 'TBD'),
    ])

    body += (
        '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
        'padding:16px;margin:20px 0;">'
        '<p style="color:#92400e;margin:0;font-size:14px;line-height:1.6;">'
        '<strong>Preparation tips:</strong></p>'
        '<ul style="color:#92400e;padding-left:20px;margin:8px 0 0;font-size:13px;line-height:1.8;">'
        '<li>Make sure all items are accessible and easy to reach</li>'
        '<li>Clear a path from the items to the nearest door or garage</li>'
        '<li>Disconnect any appliances ahead of time</li>'
        '<li>Move vehicles if the items are in the garage or driveway</li>'
        '</ul></div>'
    )

    body += (
        '<p style="color:#4b5563;font-size:14px;line-height:1.6;">'
        'Need to reschedule? Call us at <strong>(561) 944-1636</strong> '
        'or reply to this email as soon as possible.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 7. Password reset
# ---------------------------------------------------------------------------

def abandoned_booking_reminder_html(customer_name, booking_url):
    """Return HTML for a 2-hour abandoned booking reminder email."""
    name = _esc(str(customer_name)) if customer_name else 'there'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">You left something behind!</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'It looks like you started booking a junk removal but didn\'t finish. '
        'No worries &mdash; your details are still saved and ready for you.</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Completing your booking only takes a minute, and we\'ll have your '
        'space cleared out in no time.</p>'
    ).format(name=name)

    body += _button(booking_url or '#', 'Complete Your Booking')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'Questions? Reply to this email or call <strong>(561) 888-3427</strong>.</p>'
    )

    return _wrap(body)


def b2b_dunning_html(org_name, invoice_number, amount, manage_url):
    """Dunning email — a B2B invoice payment failed; recurring service paused."""
    name = _esc(str(org_name)) if org_name else 'there'
    inv = _esc(str(invoice_number)) if invoice_number else ''
    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Payment needs attention</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'We couldn\'t process payment for invoice <strong>{inv}</strong> '
        '(${amt:.2f}). To avoid interruption, recurring pickups are paused until '
        'this is resolved.</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'Update your payment method to resume service right away.</p>'
    ).format(name=name, inv=inv, amt=float(amount or 0))
    body += _button(manage_url or '#', 'Update Payment Method')
    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'Questions? Reply to this email or call <strong>(561) 888-3427</strong>.</p>'
    )
    return _wrap(body)


def abandoned_booking_incentive_html(customer_name, booking_url, promo_code):
    """Return HTML for a 24-hour abandoned booking incentive email with promo code."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    code = _esc(str(promo_code)) if promo_code else 'COMEBACK10'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Here\'s 10% off to finish your booking</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'We noticed you haven\'t completed your junk removal booking yet. '
        'We\'d love to help you get that space cleared &mdash; so here\'s a little nudge:</p>'
    ).format(name=name)

    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:24px;margin:20px 0;text-align:center;">'
        '<p style="color:#6b7280;font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.5px;">Your Promo Code</p>'
        '<p style="color:#DC2626;font-size:32px;font-weight:700;margin:0;letter-spacing:2px;">{code}</p>'
        '<p style="color:#6b7280;font-size:13px;margin:8px 0 0;">10% off your first pickup</p>'
        '</div>'
    ).format(code=code)

    body += _button(booking_url or '#', 'Claim Your Discount')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'This offer won\'t last forever. Book now and save!</p>'
    )

    return _wrap(body)


def abandoned_booking_final_html(customer_name, booking_url):
    """Return HTML for a 72-hour final abandoned booking email."""
    name = _esc(str(customer_name)) if customer_name else 'there'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">We saved your spot</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'This is your last reminder &mdash; your junk removal booking is still waiting for you. '
        'We\'ve held onto your details so you can pick up right where you left off.</p>'
    ).format(name=name)

    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:24px;margin:20px 0;text-align:center;">'
        '<p style="color:#DC2626;font-size:18px;font-weight:600;margin:0 0 8px;">500+ pickups completed in South Florida</p>'
        '<p style="color:#6b7280;font-size:14px;margin:0;line-height:1.6;">'
        'Our customers love the speed and care we bring to every job. '
        'Join hundreds of happy homeowners who\'ve already reclaimed their space.</p>'
        '</div>'
    )

    body += _button(booking_url or '#', 'Book Now')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'If you\'ve already booked or no longer need service, feel free to ignore this email.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 7. Password reset
# ---------------------------------------------------------------------------

def password_reset_html(name, reset_url):
    """Return HTML for a password-reset email with a clickable link."""
    display_name = _esc(str(name)) if name else 'there'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Reset Your Password</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'We received a request to reset your Umuve password. '
        'Click the button below to choose a new one:</p>'
    ).format(name=display_name)

    body += _button(reset_url or '#', 'Reset Password')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;">'
        'This link expires in <strong>1 hour</strong>. '
        'If you didn\'t request a password reset, you can safely ignore this email.</p>'
    )

    body += (
        '<p style="color:#9ca3af;font-size:12px;line-height:1.6;word-break:break-all;">'
        'If the button doesn\'t work, copy and paste this URL into your browser:<br>'
        '<a href="{url}" style="color:#DC2626;">{url}</a></p>'
    ).format(url=_esc(str(reset_url or '')))

    return _wrap(body)


# ---------------------------------------------------------------------------
# 8. Abandoned booking drip — 1-hour follow-up
# ---------------------------------------------------------------------------

def abandoned_drip_1h_html(name=None, items=None, resume_url=None):
    """1-hour abandoned booking follow-up — 'Still thinking it over?'"""
    greeting = "Hi {}".format(_esc(name)) if name else "Hi there"
    items_text = ""
    if items and isinstance(items, list):
        count = sum(i.get("quantity", 1) for i in items if isinstance(i, dict))
        items_text = '<p style="color:#4b5563;font-size:15px;">You had <strong>{} item{}</strong> ready for pickup.</p>'.format(count, "s" if count != 1 else "")

    btn = ""
    if resume_url:
        btn = '<div style="text-align:center;margin:25px 0;"><a href="{}" style="display:inline-block;padding:14px 32px;background:#DC2626;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;">Finish Your Booking</a></div>'.format(_esc(resume_url))

    body = (
        '<h2 style="color:#111827;font-size:22px;margin:0 0 15px;">{}, still thinking it over?</h2>'
        '<p style="color:#4b5563;font-size:15px;line-height:1.6;">We noticed you started a junk removal booking but didn\'t finish. No worries — your items are saved and ready to go.</p>'
        '{}'
        '{}'
        '<p style="color:#6b7280;font-size:14px;margin-top:20px;">Questions? Reply to this email or call us at (561) 944-1636.</p>'
    ).format(greeting, items_text, btn)
    return _wrap(body)


# ---------------------------------------------------------------------------
# 9. Abandoned booking drip — 24-hour follow-up
# ---------------------------------------------------------------------------

def abandoned_drip_24h_html(name=None, estimated_price=None, resume_url=None):
    """24-hour abandoned booking follow-up — social proof + urgency."""
    greeting = "Hi {}".format(_esc(name)) if name else "Hi there"
    price_text = ""
    if estimated_price:
        price_text = '<p style="color:#4b5563;font-size:15px;">Your estimated pickup was just <strong>${:.0f}</strong> — that\'s up to 25% less than the big guys.</p>'.format(float(estimated_price))

    btn = ""
    if resume_url:
        btn = '<div style="text-align:center;margin:25px 0;"><a href="{}" style="display:inline-block;padding:14px 32px;background:#DC2626;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;">Complete Your Booking</a></div>'.format(_esc(resume_url))

    body = (
        '<h2 style="color:#111827;font-size:22px;margin:0 0 15px;">{}, your junk won\'t remove itself!</h2>'
        '{}'
        '<p style="color:#4b5563;font-size:15px;line-height:1.6;">Hundreds of South Florida homeowners trust Umuve for fast, affordable junk removal. Most pickups are completed within 48 hours of booking.</p>'
        '{}'
        '<p style="color:#6b7280;font-size:14px;margin-top:20px;">We\'re here to help — (561) 944-1636</p>'
    ).format(greeting, price_text, btn)
    return _wrap(body)


# ---------------------------------------------------------------------------
# 10. Abandoned booking drip — 72-hour follow-up (last chance + discount)
# ---------------------------------------------------------------------------

def abandoned_drip_72h_html(name=None, resume_url=None):
    """72-hour abandoned booking follow-up — last chance with discount hint."""
    greeting = "Hi {}".format(_esc(name)) if name else "Hi there"

    btn = ""
    if resume_url:
        btn = '<div style="text-align:center;margin:25px 0;"><a href="{}" style="display:inline-block;padding:14px 32px;background:#DC2626;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;">Book Now</a></div>'.format(_esc(resume_url))

    body = (
        '<h2 style="color:#111827;font-size:22px;margin:0 0 15px;">{}, last chance — we\'d love to help</h2>'
        '<p style="color:#4b5563;font-size:15px;line-height:1.6;">This is our last nudge — we promise! If you still need junk removed, we\'re the fastest and most affordable option in South Florida.</p>'
        '<div style="background:#fef3c7;border-radius:8px;padding:16px;margin:20px 0;">'
        '<p style="color:#92400e;font-size:15px;margin:0;"><strong>Limited offer:</strong> Use code <strong>COMEBACK10</strong> for 10% off your first pickup.</p>'
        '</div>'
        '{}'
        '<p style="color:#6b7280;font-size:14px;margin-top:20px;">Need help? Just reply to this email.</p>'
    ).format(greeting, btn)
    return _wrap(body)


# ---------------------------------------------------------------------------
# 11. Customer winback (7+ days after last completed job)
# ---------------------------------------------------------------------------

def winback_html(customer_name, promo_code=None):
    """Return HTML for a winback email targeting past customers."""
    name = _esc(str(customer_name)) if customer_name else 'there'
    code = _esc(str(promo_code)) if promo_code else 'COMEBACK10'

    body = (
        '<h2 style="color:#111827;margin:0 0 12px;font-size:22px;">Still have stuff to get rid of?</h2>'
        '<p style="color:#4b5563;line-height:1.6;">Hi {name},</p>'
        '<p style="color:#4b5563;line-height:1.6;">'
        'It\'s been a while since your last pickup with Umuve. If you\'ve got more '
        'junk piling up, we\'re ready to haul it away &mdash; fast.</p>'
    ).format(name=name)

    body += (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;'
        'padding:24px;margin:20px 0;text-align:center;">'
        '<p style="color:#6b7280;font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.5px;">Welcome Back Offer</p>'
        '<p style="color:#DC2626;font-size:32px;font-weight:700;margin:0;letter-spacing:2px;">{code}</p>'
        '<p style="color:#6b7280;font-size:13px;margin:8px 0 0;">10% off your next pickup</p>'
        '</div>'
    ).format(code=code)

    body += (
        '<div style="margin:20px 0;">'
        '<h3 style="color:#111827;font-size:16px;margin:0 0 12px;">Popular This Season</h3>'
        '<table style="width:100%;border-collapse:collapse;">'
        '<tr>'
        '<td style="padding:8px;background:#f9fafb;border-radius:6px;text-align:center;width:25%;">'
        '<p style="color:#111827;font-weight:600;font-size:14px;margin:0 0 4px;">Garage Cleanout</p>'
        '<p style="color:#DC2626;font-size:13px;margin:0;">from $249</p></td>'
        '<td style="width:4%;"></td>'
        '<td style="padding:8px;background:#f9fafb;border-radius:6px;text-align:center;width:25%;">'
        '<p style="color:#111827;font-weight:600;font-size:14px;margin:0 0 4px;">Yard Waste</p>'
        '<p style="color:#DC2626;font-size:13px;margin:0;">from $89</p></td>'
        '<td style="width:4%;"></td>'
        '<td style="padding:8px;background:#f9fafb;border-radius:6px;text-align:center;width:25%;">'
        '<p style="color:#111827;font-weight:600;font-size:14px;margin:0 0 4px;">Furniture</p>'
        '<p style="color:#DC2626;font-size:13px;margin:0;">from $89</p></td>'
        '<td style="width:4%;"></td>'
        '<td style="padding:8px;background:#f9fafb;border-radius:6px;text-align:center;width:25%;">'
        '<p style="color:#111827;font-weight:600;font-size:14px;margin:0 0 4px;">Appliances</p>'
        '<p style="color:#DC2626;font-size:13px;margin:0;">from $75</p></td>'
        '</tr></table></div>'
    )

    body += _button('https://goumuve.com/book', 'Book a Pickup')

    body += (
        '<p style="color:#6b7280;font-size:13px;line-height:1.6;text-align:center;">'
        'Know someone who needs junk removed? Refer a friend and earn <strong>$10</strong> '
        'for every completed pickup.</p>'
    )

    return _wrap(body)


# ---------------------------------------------------------------------------
# 12. Operator recruitment sequence (5 emails)
# ---------------------------------------------------------------------------

def _operator_signature():
    """Shared signature block for operator recruitment emails."""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e5e7eb;margin-top:8px;">'
        '<tr><td style="padding:20px 0 0;">'
        '<p style="font-size:15px;color:#1a1a1a;margin:0 0 4px;font-weight:600;">The Umuve Team</p>'
        '<p style="font-size:14px;color:#777;margin:0;">Hauling made simple. &nbsp;|&nbsp; '
        '<a href="tel:+15619441636" style="color:#DC2626;text-decoration:none;">(561) 944-1636</a> &nbsp;|&nbsp; '
        '<a href="https://goumuve.com" style="color:#DC2626;text-decoration:none;">goumuve.com</a></p>'
        '</td></tr></table>'
    )


def _operator_wrap(body_html):
    """Wrap operator recruitment email content (simpler layout, no card)."""
    return (
        '<div style="font-family:\'Helvetica Neue\',Helvetica,Arial,sans-serif;'
        'max-width:560px;margin:0 auto;color:#1a1a1a;">'
        '<p style="text-align:center;margin:0 0 24px;">'
        '<img src="https://goumuve.com/logo-full.png" alt="Umuve" width="140" style="height:auto;"></p>'
        + body_html
        + _operator_signature()
        + '</div>'
    )


def operator_recruitment_1_html(first_name=None, area=None):
    """Email 1 — The Hook (Day 1). Subject: You have a truck. We have customers."""
    name = _esc(str(first_name)) if first_name else 'there'
    region = _esc(str(area)) if area else 'Palm Beach & Broward'

    body = (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">Hey {name},</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'We\'re <strong>Umuve</strong> &mdash; a new junk removal platform based in South Florida. '
        'We connect homeowners who need junk hauled with independent operators like you who have '
        'the trucks and the muscle to get it done.</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'Think of us like Uber, but for junk removal. We spend money on Google ads, SEO, and '
        'social media to bring in customers across {region}. When someone books a pickup, we send '
        'the job to you. You show up, load the truck, and get paid.</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 20px;">'
        '<strong>You focus on hauling. We handle everything else</strong> &mdash; marketing, '
        'booking, customer service, payments, and scheduling.</p>'
    ).format(name=name, region=region)

    # Value props card
    body += (
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;'
        'border-radius:12px;border:1px solid #e5e7eb;margin:0 0 24px;">'
        '<tr><td style="padding:24px;">'
        '<table width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; Jobs sent to your phone &mdash; accept what you want</td></tr>'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; You keep <strong style="color:#DC2626;font-size:17px;">85%</strong> of every job</td></tr>'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; <strong>Same-day payouts</strong> to your bank</td></tr>'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; No franchise fees, no monthly costs</td></tr>'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; No contracts &mdash; stop anytime</td></tr>'
        '<tr><td style="padding:8px 0;font-size:15px;color:#1a1a1a;">&#10003;&nbsp; Keep your existing clients &mdash; we add more</td></tr>'
        '</table></td></tr></table>'
    )

    # Earnings banner
    body += (
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#DC2626,#E11D48);'
        'border-radius:12px;margin:0 0 24px;">'
        '<tr><td style="padding:28px;text-align:center;">'
        '<p style="font-size:13px;color:rgba(255,255,255,0.85);margin:0 0 6px;text-transform:uppercase;'
        'letter-spacing:1px;font-weight:600;">What our operators earn</p>'
        '<p style="font-size:36px;font-weight:800;color:#ffffff;margin:0 0 6px;">$2,800 &ndash; $4,200</p>'
        '<p style="font-size:14px;color:rgba(255,255,255,0.9);margin:0;">per week in {region}</p>'
        '</td></tr></table>'
    ).format(region=region)

    body += (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 24px;text-align:center;">'
        'All you need is a truck. We bring the customers.</p>'
        '<p style="text-align:center;margin:0 0 28px;">'
        '<a href="https://goumuve.com/operators" style="display:inline-block;background:#DC2626;'
        'color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;'
        'font-size:16px;">See the Full Breakdown &#8594;</a></p>'
        '<p style="font-size:15px;line-height:1.7;margin:0 0 24px;color:#555;">'
        'Interested? Just reply to this email &mdash; or check out '
        '<a href="https://goumuve.com/operators" style="color:#DC2626;font-weight:600;'
        'text-decoration:none;">goumuve.com/operators</a>. Takes 3 minutes to apply.</p>'
    )

    return _operator_wrap(body)


def operator_recruitment_2_html(first_name=None, area=None):
    """Email 2 — Social Proof (Day 3). Subject: This hauler made $4,200 last week on Umuve."""
    name = _esc(str(first_name)) if first_name else 'there'

    body = (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">Hey {name},</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'Wanted to share what a few of our operators are pulling in:</p>'
    ).format(name=name)

    # Earnings table
    body += (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;'
        'border-radius:12px;margin:0 0 20px;overflow:hidden;">'
        '<tr style="background:#f9fafb;">'
        '<td style="padding:12px 16px;font-weight:600;font-size:14px;color:#6b7280;">Operator</td>'
        '<td style="padding:12px 16px;font-weight:600;font-size:14px;color:#6b7280;">Area</td>'
        '<td style="padding:12px 16px;font-weight:600;font-size:14px;color:#6b7280;text-align:right;">Last Week</td></tr>'
        '<tr><td style="padding:12px 16px;font-size:15px;">Carlos R.</td>'
        '<td style="padding:12px 16px;font-size:15px;">Boca Raton</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">$2,800</td></tr>'
        '<tr style="background:#f9fafb;"><td style="padding:12px 16px;font-size:15px;">Marcus T.</td>'
        '<td style="padding:12px 16px;font-size:15px;">Fort Lauderdale</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">$4,200</td></tr>'
        '<tr><td style="padding:12px 16px;font-size:15px;">David L.</td>'
        '<td style="padding:12px 16px;font-size:15px;">West Palm Beach</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">$3,100</td></tr>'
        '</table>'
    )

    body += (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'The math is simple: average job pays <strong>$187</strong>. You keep <strong>85%</strong> '
        '= <strong>$159 in your pocket</strong>. Most jobs take 30&ndash;60 minutes.</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'At 3&ndash;4 jobs a day, that\'s <strong>$2,800&ndash;$4,200/week</strong>.</p>'
        '<p style="text-align:center;margin:0 0 28px;">'
        '<a href="https://goumuve.com/operators" style="display:inline-block;background:#DC2626;'
        'color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;'
        'font-size:16px;">Apply Now &mdash; Start This Week &#8594;</a></p>'
    )

    return _operator_wrap(body)


def operator_recruitment_3_html(first_name=None):
    """Email 3 — Objection Killer (Day 5). Subject: 'What's the catch?' — here's the honest answer."""
    name = _esc(str(first_name)) if first_name else 'there'

    body = (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">Hey {name},</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 20px;">'
        'Fair question. Here\'s the honest breakdown:</p>'
    ).format(name=name)

    # FAQ-style objection handling
    faqs = [
        ("What does Umuve take?", "15% of each job. That's it. No monthly fees, no signup cost, no hidden charges."),
        ("Am I locked in?", "No contracts. You can stop accepting jobs anytime. No penalties, no notice period."),
        ("Do I lose my existing clients?", "Nope. Keep every client you already have. We just send you more."),
        ("What do I need?", "A truck (pickup, box truck, or trailer), valid driver's license, and basic liability insurance."),
        ("When do I get paid?", "Same day. Every job payment hits your bank within hours of completion."),
    ]

    for q, a in faqs:
        body += (
            '<div style="margin:0 0 16px;padding:16px;background:#f9fafb;border-radius:8px;">'
            '<p style="font-size:15px;font-weight:700;color:#111827;margin:0 0 6px;">{q}</p>'
            '<p style="font-size:15px;color:#4b5563;margin:0;line-height:1.6;">{a}</p>'
            '</div>'
        ).format(q=_esc(q), a=_esc(a))

    body += (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 24px;">'
        'No catch. Just a platform that sends you paying customers.</p>'
        '<p style="text-align:center;margin:0 0 28px;">'
        '<a href="https://goumuve.com/operators" style="display:inline-block;background:#DC2626;'
        'color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;'
        'font-size:16px;">Apply in 3 Minutes &#8594;</a></p>'
    )

    return _operator_wrap(body)


def operator_recruitment_4_html(first_name=None, area=None):
    """Email 4 — Urgency (Day 7). Subject: 3 operator spots left in {area}."""
    name = _esc(str(first_name)) if first_name else 'there'
    region = _esc(str(area)) if area else 'your area'

    body = (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">Hey {name},</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 20px;">'
        'Quick update &mdash; we\'re capping the number of operators per zone to make sure '
        'everyone gets enough jobs. Here\'s where things stand:</p>'
    ).format(name=name)

    # Zone availability
    body += (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;'
        'border-radius:12px;margin:0 0 20px;overflow:hidden;">'
        '<tr style="background:#f9fafb;">'
        '<td style="padding:12px 16px;font-weight:600;font-size:14px;color:#6b7280;">Zone</td>'
        '<td style="padding:12px 16px;font-weight:600;font-size:14px;color:#6b7280;text-align:right;">Spots Left</td></tr>'
        '<tr><td style="padding:12px 16px;font-size:15px;">West Palm Beach</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">3</td></tr>'
        '<tr style="background:#f9fafb;"><td style="padding:12px 16px;font-size:15px;">Boca Raton</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">2</td></tr>'
        '<tr><td style="padding:12px 16px;font-size:15px;">Fort Lauderdale</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">4</td></tr>'
        '<tr style="background:#f9fafb;"><td style="padding:12px 16px;font-size:15px;">Coral Springs</td>'
        '<td style="padding:12px 16px;font-size:15px;font-weight:700;color:#DC2626;text-align:right;">3</td></tr>'
        '</table>'
    )

    body += (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'Once a zone is full, new applicants go on a waitlist. If {region} is your area, '
        'now\'s the time.</p>'
        '<p style="text-align:center;margin:0 0 28px;">'
        '<a href="https://goumuve.com/operators" style="display:inline-block;background:#DC2626;'
        'color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;'
        'font-size:16px;">Claim Your Spot &#8594;</a></p>'
    ).format(region=region)

    return _operator_wrap(body)


def operator_recruitment_5_html(first_name=None):
    """Email 5 — Last Chance (Day 10). Subject: Last email — $3K/week opportunity closing."""
    name = _esc(str(first_name)) if first_name else 'there'

    body = (
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">Hey {name},</p>'
        '<p style="font-size:16px;line-height:1.7;margin:0 0 16px;">'
        'This is the last email I\'ll send about this. Here\'s the full picture:</p>'
    ).format(name=name)

    # Simple breakdown
    steps = [
        ("1. You have a truck", "Pickup, box truck, or trailer &mdash; any works."),
        ("2. We send you customers", "We spend money on ads so you don\'t have to."),
        ("3. You show up and haul", "Average job takes 30&ndash;60 minutes."),
        ("4. You keep 85%", "Avg job = $187. Your cut = $159."),
        ("5. Same-day payout", "Money hits your bank the same day."),
        ("6. No fees, no contracts", "Walk away anytime. Zero risk."),
    ]

    for title, desc in steps:
        body += (
            '<p style="font-size:15px;line-height:1.7;margin:0 0 8px;">'
            '<strong>{title}</strong> &mdash; {desc}</p>'
        ).format(title=title, desc=desc)

    body += (
        '<p style="font-size:16px;line-height:1.7;margin:16px 0 24px;">'
        'No more follow-ups after this. If you\'re interested, the link is below.</p>'
        '<p style="text-align:center;margin:0 0 28px;">'
        '<a href="https://goumuve.com/operators" style="display:inline-block;background:#DC2626;'
        'color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;'
        'font-size:16px;">Last Chance &mdash; Apply Now &#8594;</a></p>'
    )

    return _operator_wrap(body)
