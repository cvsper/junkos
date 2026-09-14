# Umuve web continuity draft

Prepared September 12, 2026; verification completed September 13, 2026. This is a local, uncommitted draft in `/Users/sevs/Projects/junkos-web-continuity-draft`, detached at main commit `287ca2b`. The request was: “now do the web version dont make any final changes.” No commit, merge, push, deployment, live payment, or external notification was performed. The original `/Users/sevs/Projects/junkos` checkout remains clean.

The interrupted Pro notification work is now complete and verified. The draft is ready for review; the remaining work is the release integration validation listed below. On September 13, the notification API regression checks passed, and the production browser check exposed an earnings card covering the notification dropdown. Giving that card its own stacking context fixed the blocked clicks. The rebuilt frontend and the extended real-backend browser check both passed. Local test browsers and servers were closed afterward.

The work targets the customer and Pro flows in `platform/`, with additive support in the existing backend. It uses main's Job, Payment, PaymentAttempt, availability, and cancellation services. It does not merge the separate iOS branch or introduce its parallel mobile payment tables. Legacy customer portals, B2B, and admin interfaces are outside this draft.

## Draft behavior

- Customer drafts save the current step, address, items, schedule, contact, price/quote information, and actual photo files in IndexedDB. Signed-in accounts and the browser's guest draft have separate records. Drafts restore immediately, expire after seven days, and report storage errors. Successful checkout clears the draft.
- The schedule step reads server crew availability, disables unavailable windows, handles failed checks, and uses the Eastern Time date range. Availability is a current snapshot, not a reserved slot.
- Checkout saves an immutable request and a random booking request ID before sending anything. The backend derives an owner-scoped Job ID and returns an existing matching booking on retry, including a primary-key conflict from concurrent requests. Changed pickup details cannot silently reuse that request.
- Checkout retains the same payment submission key, booking capability, and payment intent across reloads. “Check saved payment” asks the backend to reconcile the saved intent without card re-entry. Definite booking validation refusals allow editing; unknown outcomes retain recovery information. In-flight work cannot write another account's checkout after an account change.
- Customer photos attach through a booking capability or the owner's authenticated session, using the existing image validation/storage code. The route refuses uploads after checkout.
- Cancellation displays server fee/refund information, rechecks it before the final click, and redisplays a changed outcome for review. Active customer details refresh when the browser returns online/visible and periodically while visible.
- Pro before/after files and uploaded URLs persist per account and pickup. Uploads use the correct `files` multipart field. Failed selections can be retried or removed. Status changes carry the saved proof URLs and version; a retry reads current progress first so a lost response does not repeat an already-applied transition. Assigned pickups require acceptance before progress updates. Photo selection is disabled until saved work is loaded.
- The assigned driver can fetch a pickup directly by ID, including after completion. This closes the missing-endpoint gap that prevented recovery once a completed pickup disappeared from the active and available lists. Other drivers and customer accounts cannot use this endpoint.
- The completion dialog accepts the customer's handoff PIN and keeps validation errors visible for correction. The PIN is sent only for completion and is not persisted in browser storage. A retry reconciles an already-completed job without entering it again. Open price changes still block progress.
- Local photo paths are rendered through the API/proxy, while absolute storage URLs remain usable. This covers Pro proof and customer/Pro job photos. Corrupt PNG checksums produce a validation response rather than an uncaught server error.
- Pro availability and location handling live in the shared layout. Changes survive navigation, connection/location problems are visible, and a lost availability response is reconciled with server status. Location is sent only while online with a visible browser tab, including when a delayed GPS callback arrives after visibility or connectivity changes.
- Socket connections start with polling, matching the backend's enabled transport. WebSocket-first connections previously retried a disabled transport without falling back. See the [Socket.IO transport documentation](https://socket.io/docs/v4/client-options/#transports).
- Pro notifications load from account-scoped backend routes. Individual and bulk read actions are idempotent, persist after reload, and cannot modify another account's notifications. The notification dropdown remains clickable above the earnings card on desktop and at the tested 390-pixel mobile width.
- Pro job cards and completion show the driver's pay instead of the customer charge. Earnings exposes main's payment amounts, payout statuses, period summaries, and history through additive response fields; the legacy earnings payload remains present. Tips are labeled as included in pay.

## Validation

- **143 backend tests passed on September 13** across the continuity tests (including notification account isolation) and existing pricing, payments, dispatch, availability, ported behavior, and realtime/upload suites. Tests used the guarded disposable SQLite database, with external booking notifications mocked. Six warnings were an intentional duplicate-key test warning and existing SQLAlchemy deprecation warnings.
- TypeScript `tsc --noEmit --incremental false` passed.
- ESLint passed with no errors on changed frontend files. Existing plain-image warnings remain; the new hook dependency warnings were resolved.
- Agent-browser checks passed for booking rendering, unavailable slots, schedule/contact/photo restoration, lost booking response recovery with the identical request, saved payment confirmation without another intent, failed Pro photo recovery, proof attachment, lost status response reconciliation, driver pay, cancellation re-disclosure, mobile width, account isolation, and location callbacks across navigation.
- **One opt-in production browser integration test passed on September 13** against the real Flask application and disposable database. It exercised photo uploads and delivery after reload, missing/incorrect/valid handoff PINs, completion after a lost response, removal of saved proof work, actual earnings records, authenticated Socket.IO polling, and notification listing/individual read/bulk read persistence. Database assertions verified a single completion and payout-hook call, both driver notifications marked read, and a different driver's notification still unread. No browser runtime errors or missing API routes occurred. The initial notification check reproduced a blocked click; the final run passed after the earnings card stacking fix.
- Payment browser tests use an injected Stripe stand-in. Location callback tests use simulated coordinates. These establish local UI/API behavior; live Stripe/3DS/wallets, physical GPS, realtime socket delivery, email/SMS, and production storage remain unverified here.
- **Production build passed on September 13**, including TypeScript/lint checks and generation of all 85 pages. This was built with loopback API/socket URLs and the local fixture publishable key; it is a production-mode test build, not a release artifact. Existing image/hook warnings and the local Node 26 `localStorage` warning remain. No import/export warnings remain in the final build.
- `git diff --check` passed. Nothing was committed, merged, pushed, or deployed.

## Review images

All images use local test data. They are screenshots of the app, not proposed static mockups.

- [Mobile booking and availability](web-draft/umuve-web-mobile.png)
- [Desktop schedule](web-draft/umuve-web-schedule.png)
- [Checkout confirmation](web-draft/umuve-web-checkout.png)
- [Pro completion and driver payout](web-draft/umuve-web-pro.png)
- [Cancellation result](web-draft/umuve-web-cancellation.png)
- [Earnings](web-draft/umuve-web-earnings.png)
- [Desktop notifications over earnings, using real local API data](web-draft/umuve-web-notifications-desktop.png)
- [Mobile notifications after marking one as read](web-draft/umuve-web-notifications-mobile.png)

## Run the local checks

The fixture only binds loopback and never calls external services. No `.env` or dependency manifest was changed. Local dependencies were copied from the original checkout.

From the draft root, start the fixture:

```sh
node platform/scripts/web-continuity-fixture.mjs
```

From `platform/`, start the preview:

```sh
NEXT_PUBLIC_API_URL=http://127.0.0.1:3108 NEXT_PUBLIC_WS_URL=http://127.0.0.1:3108 NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_local_fixture NEXT_TELEMETRY_DISABLED=1 npm run dev -- --hostname 127.0.0.1 --port 3107
```

The fake key works only with the injected test browser script; it is not a usable Stripe credential. The preview is test data, not a staging or production deployment. The `web-continuity-browser-init.js` file is never imported into the application.

The installed agent-browser 0.37.1 entrypoint on this machine is `/Users/sevs/.npm/_npx/6de2aa2fded2970c/node_modules/agent-browser/bin/agent-browser.js`. Set `AGENT_BROWSER_CLI` to that path (or the entrypoint of another local install), then run from the draft root:

```sh
export AGENT_BROWSER_CLI=/Users/sevs/.npm/_npx/6de2aa2fded2970c/node_modules/agent-browser/bin/agent-browser.js
node platform/scripts/check-web-continuity.mjs initial
node platform/scripts/check-web-continuity.mjs booking
node platform/scripts/check-web-continuity.mjs driver
node platform/scripts/check-web-continuity.mjs cancel
node platform/scripts/check-web-continuity.mjs review
node platform/scripts/check-web-continuity.mjs earnings
```

The script uses its own `umuve-web-checks` browser session, restricts browser destinations to loopback, and deliberately changes only fixture records. `presence` reruns just the location/navigation check; `inspect` prints the current test page. Screenshot files are written to `/private/tmp/umuve-web-*.png`.

Backend checks use the already available local Python environment:

```sh
/Users/sevs/Projects/junkos-umuve-ios-seamless/backend/.venv/bin/python -m pytest backend/tests/test_web_continuity.py backend/tests/test_audit_pricing.py backend/tests/test_audit_payments.py backend/tests/test_audit_dispatch.py backend/tests/test_availability.py backend/tests/test_ported_from_codex.py -q -o addopts=
```

The `addopts` override skips the repository's unrelated coverage-plugin requirement; it does not bypass the disposable database guard.

Include `backend/tests/test_audit_realtime.py` to reproduce the expanded 143-test run.

## Repeat the production verification

Build from `platform/` with the loopback configuration:

```sh
NEXT_PUBLIC_API_URL=http://127.0.0.1:3108 NEXT_PUBLIC_WS_URL=http://127.0.0.1:3108 NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_local_fixture NEXT_TELEMETRY_DISABLED=1 npm run build
```

From the draft root, with ports 3107 and 3108 free:

```sh
AGENT_BROWSER_CLI=/Users/sevs/.npm/_npx/6de2aa2fded2970c/node_modules/agent-browser/bin/agent-browser.js UMUVE_TEST_PYTHON=/Users/sevs/Projects/junkos-umuve-ios-seamless/backend/.venv/bin/python node platform/scripts/check-web-production.mjs
```

The runner starts the production frontend, runs `backend/tests/test_web_browser.py` against the real Flask app and a disposable database, then starts the deterministic API fixture and runs the recovery checks. It closes its browsers and servers afterward. The opt-in backend browser test uses `UMUVE_WEB_BROWSER=1`; ordinary pytest runs skip it.

Append `--backend-only` to run just the production frontend/real Flask browser check. This was the September 13 verification after the notification fix; the deterministic recovery stages last passed on September 12.

The real-backend check validates image decoding, local photo delivery after reload, missing/incorrect/valid PIN handling, an interrupted completion, saved-work removal, earnings records, authenticated polling, and notification read actions on desktop/mobile. It also checks that only one completion and one call to the mocked payout hook occur and that another driver's notification remains unread. Outbound payments and notifications are mocked. The separate `presence-delayed` fixture check simulates GPS callbacks after hiding the tab or losing connectivity.

## Before any release

This remains a draft. Review the diff and run live integration checks in an appropriate test environment, then obtain authorization before merging or deploying. Real Stripe wallets/3DS, browser storage quota behavior, physical device location permissions, S3 media delivery, and production socket delivery still need integration validation. The loopback build must be rebuilt with the intended environment before any release.

Recovery is local to this browser origin/account, not a cross-device queue. Browser background execution is not guaranteed. Media uploads are not exactly-once: a lost upload response or partially successful batch can store duplicate images when retried, even though known uploaded URLs are reused. Separate tabs can still start distinct booking requests; the backend deduplicates matching saved request IDs, not all identical carts. Main's existing payment-attempt age limits and completion/PIN requirements still apply.
