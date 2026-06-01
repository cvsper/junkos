# Revenue Pipe — End-to-End Audit (Nathan's first PBC job)

**Date:** 2026-06-01
**Scope:** Prove a real Palm Beach County booking flows booking → dispatch → driver
work → payout, in **assign** mode, with Nathan (approved + online independent hauler,
seeded at West Palm Beach `26.7153, -80.0534`) as the only contractor.
**Method:** Static code trace + a hermetic dry-run harness
(`backend/scripts/test_pipe_dryrun.py`) that exercises the real `dispatcher` and
`routes/payments` logic against in-memory SQLite. No prod, no Stripe, no Twilio.

---

## VERDICT: GO — with TWO hard preconditions

The pipe is **sound end-to-end in code** and the dry-run passes all 13 checks
(coverage gate, assign-mode dispatch, lifecycle transitions, payout deferral +
pay + idempotency). A WPB booking will reach completion and pay Nathan **provided**:

1. **`DISPATCH_MODE` is actually `assign` in the Render dashboard.**
   `render.yaml:30-31` declares `DISPATCH_MODE=broadcast` (blueprint-managed
   default). The task says prod is `assign`. **These disagree.** If the dashboard
   value is missing/blueprint-synced, prod is running **broadcast**, where the
   native driver app *cannot claim offers* (open task #26) — Nathan would only be
   able to accept via the SMS web link `/o/<token>`. **Verify before onboarding.**
   (Risk #1.)

2. **Nathan completes Stripe Connect onboarding before — or shortly after — his
   first completion.** Payout is correctly *deferred* (`pending_connect`) if he
   hasn't, and a 6-hourly sweep retries, so he still gets paid once he connects.
   No money is lost; it's just delayed. (Risk #3.)

Everything else in the pipe is hardened (every dispatch/payout side-effect is
wrapped so it "never raises", coverage gate fails open, payout is idempotent).

---

## Step-by-step trace (file:line)

### 1. Booking → Job creation — `routes/booking.py`
- `POST /api/booking` → `create_booking()` (`booking.py:689`).
- **Geofence gate** (county-level): `is_in_service_area(lat,lng)` (`booking.py:731`,
  impl `geofencing.py:59`). WPB `(26.7153,-80.0534)` is inside both the bounding
  box (`geofencing.py:15-20`: S 25.30 < 26.7153 < N 26.97; W -80.85 < -80.0534 <
  E -79.85) and the polygon (vertices 7–8 trace the WPB coast, `geofencing.py:41-44`).
  **PASSES.**
- **Coverage gate** (supply-level): `has_active_coverage(lat,lng)` (`booking.py:749`,
  impl `dispatcher.py:640`). Returns True if *any* `approval_status="approved"`
  contractor's last-known location is within `MAX_RADIUS_MILES=30` (`dispatcher.py:30`).
  Independent of `is_online`. With Nathan approved @ WPB → **PASSES** for a PBC
  booking. If no hauler in range → no charge, lead saved as
  `no_coverage_waitlist`, admin alerted (`booking.py:773-833`).
- Job created `status="pending"`, Payment `payment_status="pending"`
  (`booking.py:932-963`). Guest checkout creates/links a `User` (`booking.py:902-929`).
- `_notify_nearby_contractors(job)` (`booking.py:966`, impl `:1173`) sends in-app +
  APNs + socket alerts to nearby online approved haulers. **Note:** this is a
  *pre-payment* courtesy ping, not the dispatch.
- **Dry-run confirms:** coverage gate returns False with no hauler, True once
  Nathan seeded, False for NYC.

### 2. Payment → confirm → dispatch — `routes/payments.py`
- Client (iOS `PaymentService.swift` + web `platform/src/lib/api.ts`) uses
  `create-intent-simple` (`payments.py:394`) then **`confirm-simple`**
  (`payments.py:465`). The auth'd `/confirm` (`payments.py:119`) is **not** used by
  any client.
- `confirm_simple_payment()` marks payment `succeeded`, flips job `pending→confirmed`
  (`payments.py:497-507`), then **fires auto-dispatch in the background**
  (`payments.py:512-517`): `auto_assign_job_async(job.id, app)`.
- Stripe webhook `payment_intent.succeeded` is a redundant safety net that ALSO
  triggers dispatch (`payments.py:973-979`). Good — dispatch fires whether the
  client confirms or the webhook lands first (dispatch is guarded against
  double-assign via `if job.driver_id` checks).

### 3. Dispatch (assign mode) — `dispatcher.py`
- `auto_assign_job()` (`dispatcher.py:323`): if `DISPATCH_MODE=="broadcast"` it
  delegates to `broadcast_job()` (`:334`); otherwise the assign path runs.
- Guards: skips if already assigned or status not in `("confirmed","pending")`
  (`:345-356`).
- `find_best_operator(job)` (`:192`): query = `is_online=True,
  approval_status="approved"`, scoped to independent haulers
  (`is_operator=False, operator_id IS NULL`) for non-operator jobs (`:204-217`).
  Disqualifiers: schedule conflict (`:233`), distance > 30 mi (`:248`), truck too
  small (`:259`). Nathan has no truck_capacity set → capacity score is neutral
  (`_capacity_score` returns 1.0 when `volume_estimate` is None, `:114-122`) — he
  is **not** disqualified. Scores by distance/rating/capacity/experience, returns
  top 3.
- Assign top candidate: sets `driver_id`, `status="assigned"`, commits
  (`:373-419`), then SMS to driver (`_sms_operator_assigned`, `:522`), APNs push
  (`:425-439`), customer email (`:442-457`), socket events (`:459-485`). All
  wrapped — none can roll back the assignment.
- **No operators?** `_notify_admin_no_operators(job)` (`:366`, impl `:558`) — SMS
  + email to ADMIN_PHONE/ADMIN_EMAIL. **If neither is set, logs at error level
  only** (the job sits unassigned, silently). (Risk #4.)
- **Dry-run confirms:** Nathan is the sole candidate, job flips to `assigned`,
  driver SMS fires (dev-log), and an **offline** hauler is correctly NOT assigned.

### 4. Driver receives + works — `routes/drivers.py`
- `GET /api/drivers/jobs/available` (`:154`): requires `approval_status="approved"`
  (`:162`), returns pending/confirmed jobs in radius **plus jobs already assigned
  to this contractor** (`:170-178`) — so Nathan's assigned job shows up for him.
- `GET /api/drivers/jobs/current` (`:211`) returns his active job.
- `accept_job` (`:230`) accepts `pending|confirmed|assigned` → `accepted`
  (`:253-257`). Notifies customer (push/email/socket).
- `update_job_status` (`:356`) enforces a transition table
  (`VALID_STATUS_TRANSITIONS`, `:347`):
  `assigned→accepted→en_route→arrived→started→completed`. On `completed`
  (`:389-468`): sets `completed_at`, increments `total_jobs`, handles referral
  payouts, resets win-back, warns if proof photos missing.
- **Dry-run confirms:** the full `assigned→completed` chain is valid and
  completion persists.

### 5. Payout — `routes/payments.py` `attempt_payout()` (`:178`)
- Fires automatically on completion inside `update_job_status`
  (`drivers.py:491-497`) — *after* the completion commit, so a payout hiccup can
  never roll back the completion.
- Idempotent: returns `already_paid` if `payout_status=="paid"` (`:203`); guards
  for payment-not-succeeded, no driver, etc.
- **No Stripe Connect?** Sets `payout_status="pending_connect"`, returns
  `no_connect` — **not** a hard failure (`:219-230`). The 6-hourly sweep
  `_sweep_pending_payouts` (`scheduler.py:31`, registered `:335`) retries until he
  connects. Payout = `driver_payout_amount` = 80% of total
  (commission 20% `payments.py:25`).
- With a connect id + Stripe key: `stripe.Transfer.create(... destination=
  contractor.stripe_connect_id ...)` (`:235-240`); failure → `payout_status=failed`.
  In dev (no key) it marks `paid` without a real transfer.
- **Dry-run confirms:** deferral → `pending_connect`, then `paid` once connected,
  then `already_paid` on re-call.

### 6. Notifications
- **Assignment SMS to driver:** `_sms_operator_assigned` (`dispatcher.py:522`) uses
  `contractor.user.phone`. Sends "New job assigned! … Open the app to accept."
  via `sms_service.send_sms_async`. Twilio gated on `TWILIO_ACCOUNT_SID/AUTH_TOKEN/
  PHONE_NUMBER` (`sms_service.py:25-28,106`); falls back to a dev log if unset.
- **Push to driver:** APNs `send_push_notification` (`dispatcher.py:425`).
- Customer gets booking-confirmed + driver-assigned + en-route/arrived/started/
  completed emails/SMS/push along the way.

---

## Risks, ranked, with exact fixes

### Risk #1 — `DISPATCH_MODE` blueprint says `broadcast`, task says prod is `assign` (BLOCKER until verified)
`render.yaml:30-31` sets `broadcast`. In broadcast mode the **native driver app
cannot claim a JobOffer** (open task #26) — Nathan could only accept via the SMS
web link `/o/<token>` (`routes/offers.py:68`). If the dashboard value is unset or
blueprint-synced, prod is broadcast and the in-app accept Nathan expects won't work.
- **Fix:** In Render → umuve-backend → Environment, confirm `DISPATCH_MODE=assign`
  explicitly (dashboard overrides blueprint). Search logs for the dispatch path on
  the next test booking: assign mode logs `DISPATCH: job … -> contractor …`
  (`dispatcher.py:378`); broadcast logs `BROADCAST: job … offered to N haulers`
  (`:981`). If you intend broadcast, tell Nathan to accept via the **SMS link**,
  not the app, until task #26 ships.

### Risk #2 — No-coverage / no-operator alert is silent if ADMIN_PHONE & ADMIN_EMAIL both unset (HIGH)
`_notify_admin_no_operators` and `_notify_admin_no_coverage_lead`
(`dispatcher.py:591-597, 691-697`) only **log at error level** when neither contact
is configured. A paid-but-unassignable job (e.g. Nathan briefly offline at confirm
time) would sit silently. The dry-run reproduced this exact log line.
- **Fix:** Set `ADMIN_PHONE` (and ideally `ADMIN_EMAIL`) in Render before
  onboarding Nathan. Per task #1 this was done once — **re-verify it's still set.**

### Risk #3 — Payout deferred until Stripe Connect onboarding (EXPECTED, not a bug — operational)
Nathan **must** complete Stripe Connect onboarding or his payout sits as
`pending_connect`. The deferral + sweep handle it gracefully (he still gets paid
when he connects), but the sweep only runs if `ENABLE_SCHEDULER=true`
(`scheduler.py:285`). `render.yaml:25-26` sets it true — confirm in dashboard.
- **Fix:** Have Nathan run `POST /api/payments/connect/create-account` →
  `POST /api/payments/connect/account-link` and finish onboarding **before** his
  first job. Confirm `ENABLE_SCHEDULER=true` so the retry sweep is live.

### Risk #4 — Twilio must be live for the assignment SMS (MEDIUM)
If Twilio creds are unset/invalid (history: a 401 killed all SMS, task #24),
Nathan gets no assignment SMS — in assign mode he'd only see the job via app push
or by opening `jobs/available`. Memory says Twilio is restored; verify.
- **Fix:** Confirm `TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER` set and valid. The
  6-hourly `_check_twilio_health` (`scheduler.py:18,346`) will email-alert on a
  billing suspension.

### Risk #5 — `propose_volume_adjustment` KeyError (LOW — not on the happy path, but a latent crash)
`drivers.py:724` reads `result["grand_total"]`, but `calculate_estimate` returns
`"total"` (`booking.py:525`), never `grand_total`. Any driver who proposes an
on-site volume adjustment from `arrived` status hits a `KeyError` → 500. Not on
Nathan's first happy-path flow, but a real crash if he uses the feature.
- **Fix:** Change `result["grand_total"]` → `result["total"]` in
  `routes/drivers.py:724`. (Out of scope for this read-only audit — logged here.)

### Risk #6 — Daily mystery-shop cron is not in the repo (LOW — observability gap)
`mystery_shop.py` is a standalone script (docstring says Render cron
`23 12 * * *`), but it is **not** in `render.yaml` (no cron/job service) and **not**
in APScheduler (`scheduler.py` registers 6 jobs; mystery-shop isn't one). So it
only runs if a Render dashboard cron was configured out-of-band (unverifiable from
the repo). See "Mystery-shop status" below.

---

## Mystery-shop (Tier 3-I) status

`backend/mystery_shop.py` — what it covers (all read-only, **no card charge, no
real SMS**):
1. `GET /api/service-area` returns polygon.
2. `GET /api/service-area/dynamic` returns live contractor coverage.
3. `POST /api/service-area/check` WPB → `in_service_area: true`.
4. Same, NYC → `false` (geofence-still-gating).
5. `GET /api/tracking/code/AAAAAAAA` → 404 (route reachable).
6. `POST /api/booking` with NYC coords → 400 "outside our service area".

On any failure it SMS/emails ADMIN_PHONE/ADMIN_EMAIL and exits 2.

**Does it pass today?** Cannot assert from the repo — it hits live prod over HTTP,
and this audit does not touch prod. Its checks are well-formed and aligned with
the current routes. **Two caveats:**
- It only validates the *funnel up to booking-create*; it does **not** test
  dispatch, driver lifecycle, or payout (by design — see its docstring). So a
  green mystery-shop does NOT prove Nathan's payout works. This audit's dry-run
  fills that gap.
- It likely **isn't scheduled** in this repo (Risk #6). If you want the daily
  guarantee, add a Render cron service or an APScheduler job.

---

## Manual test plan (sevs — real low-$ test booking)

> Goal: one real $79 booking flows to completion + pays Nathan, zero surprises.
> Use a real card you control; you can refund yourself after.

**Pre-flight (do these first):**
1. Render → umuve-backend → Environment: confirm `DISPATCH_MODE` (see Risk #1),
   `ADMIN_PHONE`/`ADMIN_EMAIL`, `ENABLE_SCHEDULER=true`, Twilio creds, `STRIPE_SECRET_KEY`.
2. Onboard Nathan: approve him (`approval_status=approved`), have him finish Stripe
   Connect (`/connect/create-account` → `/connect/account-link`), set him
   **online**, and confirm his GPS is near WPB (`PUT /api/drivers/location`).
3. Verify coverage: `POST /api/service-area/check` with a WPB-area coord → expect
   `in_service_area: true` AND `GET /api/service-area/dynamic` shows ≥1 circle.

**The booking:**
4. As a customer (app or web), book the smallest job (1 sofa = $89, or set up a
   $79 floor item) at a real PBC address near Nathan. Use a card you own.
5. Pay. Watch: customer gets booking-confirmed; **Nathan gets an assignment SMS +
   push** within seconds (assign mode). Render logs show
   `DISPATCH: job … -> contractor <nathan>`.
6. As Nathan in the driver app: the job appears in `jobs/available` /
   `jobs/current`. Accept → en_route → arrived → started → completed, advancing
   each via the app (or `PUT /api/drivers/jobs/<id>/status`).
7. On completion: Render logs show `Auto-payout for job …: paid` (if Connect done)
   or `pending_connect` (if not). Check `GET /api/payments/earnings` for Nathan —
   his 80% should appear; `payout_status` should be `paid`.
8. If `pending_connect`: have Nathan finish Connect, then either wait ≤6h for the
   sweep or `POST /api/payments/payout/<job_id>` to force it.
9. Refund yourself via Stripe if this was a self-test.

**Abort conditions:** if step 5 shows no candidate (admin "no operator" alert) →
Nathan wasn't online/approved/in-range at confirm time. Fix and re-book.

---

## Automated dry-run

`backend/scripts/test_pipe_dryrun.py` — hermetic, in-memory SQLite, no network.
Run: `cd backend && python scripts/test_pipe_dryrun.py` (needs flask +
flask-sqlalchemy + pyjwt; exit 0 = pass). Verified **13/13 PASS** on 2026-06-01:
coverage gate (yes/no), assign-mode dispatch to Nathan, offline-hauler rejection,
full lifecycle transition validity, payout deferral → pay → idempotency. It
imports the **real** `dispatcher` and `routes/payments` code, so logic drift will
surface here.
