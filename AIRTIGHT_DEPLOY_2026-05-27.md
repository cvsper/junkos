# Airtight Deploy Checklist — 2026-05-27 → 28

> Generated overnight after the Weston-Sy missed-job incident.
> Reads top-to-bottom; do steps in order. Total time: ~25 min of actual work
> + automatic deploy time.

---

## 🌅 Open-the-laptop summary

Last night's incident exposed a stack of single points of failure. Eleven
changes shipped across two repos. **Most of this is dormant until you flip
two env vars on Render.** Once those go in, every defense activates.

| Tier | What | Status |
|------|------|--------|
| **Triage** | Refund Sy, draft response | ✅ done by sevs |
| **Original 9** | Fix A/B/C + outreach prep + Vapi prompt | ✅ shipped in code, awaiting deploy |
| **Tier 1 (A/B/C)** | No-show watchdog, inbound SMS bypass, morning brief | ✅ shipped |
| **Tier 2 (D/E/F)** | Vapi health monitor, review monitor scaffold, Stripe auth-only scaffold | ✅ D shipped, E+F scaffolded |
| **Tier 3 (G/H/I)** | Dynamic geofence, tracking page, mystery shop | ✅ G+I shipped, H backend shipped (frontend TODO) |

---

## 1️⃣ Two env vars on Render — the unlock (5 min)

Open Render → `junkos-backend` → Environment → add:

| Key | Value | Why |
|-----|-------|-----|
| `ADMIN_PHONE` | your cell, E.164 (`+1XXXXXXXXXX`) | Activates SMS for every alert below |
| `ADMIN_EMAIL` | `se7nz7@gmail.com` (or `contact@goumuve.com`) | Activates email for every alert below |

Click **Save Changes** → Render auto-redeploys.

> ⚠️ Without these, every alert in this deploy logs into the void. THIS is
> the single highest-leverage step. Do it first.

---

## 2️⃣ Run the DB migration (2 min)

The no-show watchdog needs two new boolean columns on `jobs`. After Render
redeploys with the new code:

```
# Render Shell tab:
python migrate.py
```

Expected output line: `Added column noshow_t30_alerted to jobs` and
`Added column noshow_late_alerted to jobs`. Safe to re-run; idempotent.

---

## 3️⃣ Wire the new cron jobs in Render (5 min)

Render → `junkos-backend` → Cron Jobs → **New Cron Job** for each:

| Name | Schedule (UTC) | Command |
|------|----------------|---------|
| `noshow-watchdog` | `*/5 * * * *` | `python noshow_watchdog.py` |
| `vapi-health` | `7 * * * *` | `python vapi_health_monitor.py` |
| `morning-brief` | `0 11 * * *` | `python morning_brief.py` |
| `mystery-shop` | `23 12 * * *` | `python mystery_shop.py` |

Each is independent; you can add them one at a time.

---

## 4️⃣ Push the Vapi assistant changes (1 min)

The Vapi system-prompt update + the new `schedule_callback` tool live in
`vapi_setup.py` but the Vapi assistant still runs the OLD config. One
command pushes the new one to your live assistant:

```
cd /Users/sevs/Projects/junkos/backend
VAPI_API_KEY=<your_key> python vapi_setup.py update 91198234-25c8-450a-9075-854509e9e59d
```

Expected output: `Assistant 91198234-... updated successfully.`

After that, Maya:
- Treats complaints / missed-appointment calls as URGENT
- Captures a `schedule_callback` (with `urgency="high"`) BEFORE any transfer
- Never ends a call with an unresolved complaint without taking a message

---

## 5️⃣ Confirm what `+1-561-888-3427` routes to (your call)

This is the `OPERATOR_PHONE` Maya transfers to — and the published support
number on your emails. If it's your cell and you don't answer (work hours,
phone off), customers see "the AI hung up." Three options, pick one:

- **Cheapest:** point it at a virtual receptionist service (Smith.ai, Ruby,
  CallRail) — ~$100-200/mo, 24/7 answer.
- **Cheaper:** hire one overseas VA on Upwork/Onlinejobs.ph — ~$300-500/mo.
- **Free, riskier:** keep it on your cell, accept that off-hours = no answer
  (now mitigated by the new "take a message first" prompt).

---

## 6️⃣ Frontend / platform TODOs (you do when ready)

Backend ships the APIs; the Next.js platform still needs:

- **Tracking page** — `/track/[code]/page.tsx` calling
  `GET /api/tracking/code/<code>`. Add the link to the booking confirmation
  email.
- **Coverage overlay** — call `GET /api/service-area/dynamic` from the
  booking map to show customers which areas have live coverage.
- **Support number prominence** — put your Twilio inbound number on the
  booking confirmation email + app help page with: *"For urgent issues
  text us at XXX-XXX-XXXX — goes straight to the owner."*

---

## 📁 What shipped — file index

### Backend (`/Users/sevs/Projects/junkos/backend`)

| File | What | Type |
|------|------|------|
| `dispatcher.py` | Hardened `_notify_admin_no_operators` (dual-channel); new `has_active_coverage`; new `_notify_admin_no_coverage_lead`; new `_notify_admin_late_job` | edit |
| `routes/booking.py` | Coverage gate after geofence — waitlist response, no charge for uncovered areas | edit |
| `routes/vapi.py` | `_handle_schedule_callback` now dual-channel + urgency-aware | edit |
| `routes/sms_webhook.py` | Support detection forks inbound SMS to ADMIN before Vapi | edit |
| `vapi_setup.py` | New CRITICAL "Complaints/Missed Appointments" prompt section + `schedule_callback` tool definition + revised transfer protocol | edit |
| `routes/service_area.py` | New `GET /api/service-area/dynamic` route | edit |
| `routes/tracking.py` | New public `GET /api/tracking/code/<code>` for customer page | edit |
| `geofencing.py` | New `get_dynamic_coverage_summary()` | edit |
| `models.py` | New `noshow_t30_alerted`, `noshow_late_alerted` Boolean columns on Job | edit |
| `migrate.py` | Migration entries for the two new columns | edit |
| `noshow_watchdog.py` | **NEW** — T-30 ping + T+15 escalation cron | new |
| `support_router.py` | **NEW** — Vapi-bypass support SMS detector & forwarder | new |
| `morning_brief.py` | **NEW** — daily 4-section email cron (anti-silent-failure) | new |
| `vapi_health_monitor.py` | **NEW** — hourly cron; alerts on consec/rate failed calls | new |
| `review_monitor.py` | **NEW** — scaffold for Google/Yelp/App Store monitoring | new |
| `payment_auth_capture.py` | **NEW** — Stripe authorize-only helpers (scaffold, not wired) | new |
| `mystery_shop.py` | **NEW** — daily synthetic test of the public API surface | new |

### Marketing / outreach

| File | What |
|------|------|
| `marketing/outreach/CALL_SHEET_2026-05-27.md` | 3-target call list (Ryan / Milena / Brooks) + 20-sec script + Sequence-D commands |

---

## ✅ Sanity verification after deploy

Once steps 1-4 are done, verify the stack by hitting these from a browser:

- `https://junkos-backend.onrender.com/api/service-area/dynamic` → JSON with `contractor_count`
- `https://junkos-backend.onrender.com/api/tracking/code/AAAAAAAA` → 404 (proves route is wired)

And manually trigger one of the new cron jobs from Render Shell to make sure
nothing's wrong with the import chain:

```
python morning_brief.py
```

You should get an email to ADMIN_EMAIL within ~30 seconds. If you do, the
entire alert pipeline is live and working.

---

## 🎯 The actual win

Before today: one customer paid for a job we couldn't fulfill, the alert
silently went to a void, and you found out via her angry email.

After this deploy: even if the contractor doesn't show, even if Vapi hangs
up, even if Twilio fails — **the morning brief will surface it the next
day, and three other layers will probably catch it sooner.** Defense in
depth.

Sleep well — go close the supply gate when you wake up. 🏗
