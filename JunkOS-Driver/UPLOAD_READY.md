# Umuve Pro — Build 41 STAGED (NOT uploaded)

Staged 2026-07-03. Archive + .ipa produced locally. **Nothing has been uploaded.**
Human review required before running the upload command below.

## Build

| Field | Value |
|---|---|
| App | Umuve Pro (driver app) |
| Bundle id | `com.goumuve.pro` |
| ASC app id | `6759131650` |
| Team | `24GH82AX9R` (Gymbuddy LLC) |
| Marketing version | 1.0.0 |
| Build number | **41** (bumped from 40 in `project.yml`, pbxproj regenerated via `xcodegen generate`) |
| Toolchain | Xcode 26.5 (17F42), `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` |

## Artifacts (local)

- Archive: `/Users/sevs/Projects/junkos/JunkOS-Driver/build/UmuvePro-b41.xcarchive`
- IPA: `/Users/sevs/Projects/junkos/JunkOS-Driver/build/export-b41/JunkOS-Driver.ipa` (39.2 MB, Apple Distribution signed)
- Export options used: `ExportOptions-Staging.plist` (`destination=export` — the pre-existing `ExportOptions.plist` has `destination=upload` and was deliberately NOT used)

## Staged upload command (run only after human review)

```bash
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcrun altool --upload-app \
  --type ios \
  --file /Users/sevs/Projects/junkos/JunkOS-Driver/build/export-b41/JunkOS-Driver.ipa \
  --apiKey 3MXH45MMJ6 \
  --apiIssuer 69a6de86-97a7-47e3-e053-5b8c7c11a4d1
```

Key file: `/Users/sevs/.appstoreconnect/private_keys/AuthKey_3MXH45MMJ6.p8` (altool finds it automatically in `~/.appstoreconnect/private_keys/`).

Key mapping: `3MXH45MMJ6` = Gymbuddy LLC ASC key (team `24GH82AX9R`) — confirmed via `app-store/asc.py` and `docs/session-handoff-2026-06-21.md`; it is the key used for all prior Umuve Pro ASC work. `AuthKey_HN2NYSR3BG.p8` appears nowhere in junkos or mori-nori repos — mapping undetermined, not used.

## What changed since last TestFlight build (build 40, `b83eab7`)

```
2008abc Phase 2: Rescue Engine v1 — hauler outcome picker (driver app)
8258d70 Driver app: kill silent failures, honest pay, Stripe gate truth
```

Build 40 shipped: asc.py archive exclusion + offer-race fix. Build 41 adds the
Phase 1 driver fixes (silent-failure kill, honest pay, Stripe gate truth) and the
Phase 2 Rescue Engine outcome picker — exactly the two changes CLAUDE.local.md
flagged as needing a new TestFlight build.

## Deviations from "build bump only"

- `Views/Dashboard/OnlineToggleView.swift` line 62: `.scaleEffect(1.3)` →
  `.scaleEffect(1.3 as CGFloat)`. Xcode 26.5's SDK made the bare literal
  ambiguous (new `CGSize` overload) and the Release archive would not compile
  at all without it. Behavior-identical type disambiguation; flagged for review.

## Notes for reviewer

- `MBXAccessToken` is absent from the built Info.plist — same as the shipped
  build 40 archive (verified against `build/UmuvePro.xcarchive`). No regression,
  but Mapbox navigation token delivery is worth a look before a public release.
- Uncommitted screenshot PNG changes under `app-store/screenshots/` were left
  out of the staging commit on purpose.

## UPLOADED 2026-07-03
Re-cut as marketing version **1.0.1** (build 41) — Apple rejected 1.0.0 because it
must exceed the already-approved App Store version. Upload accepted:
Delivery UUID 92959864-469d-4192-8aad-ca6aceba6199. Processing in ASC → TestFlight.
