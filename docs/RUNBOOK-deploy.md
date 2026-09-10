# Deploy runbook — Umuve backend

Audience: whoever is holding the pager. Written to be followed at 2am without
reading anything else first.

- **Production**: `umuve-backend` on Render, deploys from `main`.
- **Staging**: `umuve-backend-staging` on Render, deploys from `staging`.
- Both are defined in `render.yaml`. Both run **one** web worker with the
  scheduler in-process (`ENABLE_SCHEDULER=true`).

```bash
# push to staging first; merging to main deploys production
git push origin main:staging
```

---

## 1. What /api/ready covers

`healthCheckPath` points at **`/api/ready`**, not `/api/health`. Render will
not promote a release whose readiness check fails.

| Check | Source | Blocks the deploy? |
|---|---|---|
| Database connectivity | `SELECT 1` | **Yes** |
| Core schema | `SELECT id FROM jobs / payments LIMIT 1` | **Yes** |
| Stripe configured | `routes.payments.payments_ready()` | **Yes, in production only** |
| Scheduler alive | heartbeat + last-run stamps (`scheduler.scheduler_status()`) | **Yes, when `ENABLE_SCHEDULER=true`** |
| Webhook secrets | `webhook_guard.webhook_secrets_ready()` | No — reports `unknown` when the module is absent |
| Upload storage | `storage._use_s3()` | No — local-disk fallback is degraded, not fatal |

`GET /api/ready` returns `200` with `{"ready": true}` or `503` with a
`blocking` array naming what failed. `GET /api/health` stays shallow: it is
**always 200** while the process can serve a request, and carries a `ready`
hint plus the version.

```bash
curl -s https://umuve-backend.onrender.com/api/ready | jq '{ready, blocking}'
curl -s https://umuve-backend.onrender.com/api/health | jq
```

**Verify the version after every deploy.** A push that fails to boot leaves the
previous release serving, and the API keeps answering — which has already cost
us four days of believing a change was live when it was not:

```bash
curl -s https://umuve-backend.onrender.com/api/health | jq -r .version
```

---

## 2. Release job order — expand / contract

Schema changes ship in two deploys, never one. The rule exists because there is
a window where old and new code are both running (Render starts the new
instance before retiring the old one).

**Deploy 1 — expand (backwards compatible):**

1. Add the new column/table as **nullable, or with a default**.
   `backend/migrate.py` is the only migration path: append to
   `COLUMN_MIGRATIONS` (columns) or the `NEW_TABLES_*` / `NEW_TABLE_NAMES`
   lists (tables). It is idempotent and runs on boot.
2. New code **writes both** old and new fields; **reads the old** one.
3. Deploy. Confirm `/api/ready` is green and backfill any existing rows.

**Deploy 2 — contract:**

4. Switch reads to the new field.
5. Only once nothing reads the old field: stop writing it, then drop it in a
   later release.

Never combine a rename with a code change. A rename is: add new → backfill →
dual-write → switch reads → drop old. Four deploys, not one.

**Startup migrations are fatal in production.** If `run_migrations()` raises,
the worker refuses to boot (`server.py`, startup block) and Render keeps the
previous instance serving. This is deliberate: booting with a schema that does
not match the code produces scattered 500s on money endpoints while the deploy
reports success. Fix the migration and redeploy; the log line starts with
`FATAL: startup migration failed`.

To run migrations manually against a live database:

```bash
curl -X POST -H "X-Admin-Secret: $ADMIN_SEED_SECRET" \
  https://umuve-backend.onrender.com/api/run-migrate/$ADMIN_SEED_SECRET
```

---

## 3. Rollback

Fastest first.

**A. Roll back the release (no schema change involved) — ~2 minutes**

1. Render dashboard → `umuve-backend` → **Events**.
2. Find the last known-good deploy → **Rollback to this deploy**.
3. Confirm: `curl .../api/health | jq -r .version` shows the old version, and
   `/api/ready` returns 200.

**B. Roll back through git (when you want main to reflect reality)**

```bash
git revert --no-edit <bad-sha>
git push origin main            # Render redeploys automatically
```

Prefer `revert` over force-pushing `main`: a force push desynchronises anyone
else's checkout and the staging branch.

**C. The release included a migration**

Do **not** roll the schema back. Expand/contract exists precisely so the old
code still runs against the new schema — roll back the *code* (A or B) and
leave the added column/table in place. Dropping a column that the previous
release is mid-write on loses data.

If the migration itself is the problem (it partially applied), fix forward:
write a corrective entry in `migrate.py` and deploy. Never hand-edit
production schema without recording the same change in `migrate.py`, or the
next boot will diverge.

---

## 4. Database restore drill

Render Postgres keeps point-in-time recovery on paid plans. **Run this drill
quarterly** — an untested backup is a belief, not a backup.

1. Render dashboard → `umuve-db` → **Recovery** → pick a timestamp
   (5 minutes ago is fine for a drill).
2. Restore into a **new** database instance. Never restore over production.
3. Point a scratch service at it and confirm the data is real:

   ```bash
   export DATABASE_URL='<restored instance connection string>'
   python3 - <<'EOF'
   import os, psycopg2
   c = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")
   cur = c.cursor()
   for t in ("users", "jobs", "payments", "contractors"):
       cur.execute("SELECT count(*) FROM %s" % t)
       print(t, cur.fetchone()[0])
   cur.execute("SELECT max(created_at) FROM jobs")
   print("newest job:", cur.fetchone()[0])
   EOF
   ```

4. Record in the drill log: timestamp restored to, wall-clock time taken, row
   counts, and the newest row's timestamp (this is your real RPO).
5. Delete the restored instance.

**Never** point the test suite or any script at a production URL. The suite
pins itself to a per-session scratch SQLite file and aborts if it finds itself
bound to anything else (`backend/tests/conftest.py`), but scripts are on you:
`backend/delete_via_sql.py` and friends read `DATABASE_URL` from the
environment and refuse to run without it.

---

## 5. CI gates

Everything below must be green before a merge, and all of them block.

| Workflow | Runs on | Gates |
|---|---|---|
| `backend.yml` | push to `main`/`staging`, PRs | flake8, import check, full unit suite |
| `secret-scan.yml` | push, PRs | gitleaks, working tree + commit range |
| `security-scan.yml` → `dependency-gate` | push to `main`/`staging`, PRs | `pip-audit`, `audit-ci` (high + critical) |

The unit suite, exactly as CI runs it:

```bash
cd backend && uv run --python 3.12 \
  --with-requirements requirements.txt --with pytest --with pytest-mock \
  python -m pytest -o addopts="" -p no:cacheprovider tests -q \
    --deselect tests/test_portal --ignore=tests/e2e
```

Browser end-to-end tests are separate and start a real server on port 5188:

```bash
cd backend && pytest -o addopts="" tests/e2e -q     # needs pytest-playwright
```

### Known triaged findings

These are allowlisted so the gates can block *new* problems today. Each is a
debt with a named fix — clear them, do not extend the list casually.

- **Backend dependencies** (`pip-audit`, ignore list in `security-scan.yml`):
  `werkzeug 3.0.1`, `pyjwt 2.10.1`, `gunicorn`, `python-dotenv` are behind
  their fixed releases. Bumping pyjwt changes token validation and werkzeug
  changes the WSGI stack, so it is its own change with its own test run.
- **PostCSS inside Next 15.5.25** (`audit-ci`, allowlist in each app's
  `audit-ci.jsonc`): fixed only in Next 16.3.4, which needs React 19.
  Build-time exposure only — both apps compile first-party CSS only.

---

## 6. Environment variables

Set on the host (Render → Environment). Never committed — the repo is public
and `secret-scan.yml` blocks credentials at the door.

Required in production: `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, `API_KEY`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ADMIN_SEED_SECRET`.

Push notifications (see `backend/push_notifications.py`):

| Variable | Default | Purpose |
|---|---|---|
| `APNS_KEY_ID` | — | 10-char key id from Apple |
| `APNS_TEAM_ID` | — | Apple developer team id |
| `APNS_AUTH_KEY_PATH` | — | path to the `.p8` key |
| `APNS_BUNDLE_ID_CUSTOMER` | `com.goumuve.app` | APNs topic for the customer app |
| `APNS_BUNDLE_ID_DRIVER` | `com.goumuve.pro` | APNs topic for Umuve Pro |

The two apps have different topics and a token is only valid for its own. Each
`device_tokens` row carries `app` and `environment`, and the sender picks the
topic and the sandbox/production gateway per device.

Test-only: `UMUVE_SKIP_STARTUP=1` imports the app without creating schema,
running migrations, seeding or starting the scheduler. It is what stops the
test suite from mutating a real database. Never set it on a real service — the
app would boot with no schema management at all.
