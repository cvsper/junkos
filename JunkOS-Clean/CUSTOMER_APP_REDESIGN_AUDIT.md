# Umuve Customer App — Redesign Audit

**Date**: 2026-05-14
**Branch**: `main` (5 commits ahead of origin)
**Build**: 14 (Debug verified on iphonesimulator, Xcode 16)
**Scope**: Customer-facing iOS app at `JunkOS-Clean/`
**Direction**: brand-bold + Apple-clean, aligned with web (goumuve.com), Junk Removal only

---

## 1. Executive Summary

The customer app is functional through the booking wizard but had four shippable problems and a deeper design-system drift from the web. **Phase 0 (this drop) fixed the four functional bugs and laid the design-token foundation.** Phases 1–4 in §9 cover the visual redesign on top.

**Phase 0 — landed in commits `9ff8737..dd0d7dc`**

| Area | Before | After |
|------|--------|-------|
| Payment | `PricingEstimate` decoder threw `keyNotFound("subtotal")`; PaymentView fell back to hardcoded $149 | Real backend response decoded; PaymentView shows true line items |
| Keyboard | UIKit constraint spam on every layout pass when typing in address/payment | `.ignoresSafeArea(.keyboard, edges: .bottom)` on the affected `safeAreaInset` content |
| Notifications | APN registration returning 201 logged as failure | iOS accepts any 2xx; backend also normalized to 200 |
| Referrals | `/my-code` returned partial response; iOS decoder warning, no stats shown | Backend now includes `total_referrals` + `credits_earned` inline |
| Service catalog | Auto Transport + Junk Removal mixed; vehicle/dropoff state polluted every screen | Junk Removal only; 555 net lines deleted |
| Design tokens | Slate (blue-tinted) text, red-tinted backgrounds — diverged from web | Pure white surfaces, neutral grayscale (`#171717`/`#4B5563`/`#6B7280`/`#E5E7EB`) matching web |
| Logo | Not bundled into asset catalog | `Image("UmuveLogo")` with auto dark-mode variant (1x/2x/3x) |

---

## 2. Current State Audit

### 2.1 Screen inventory (28 views after Phase 0)

| Folder | Screen | Status |
|--------|--------|--------|
| Root | `WelcomeView` / `EnhancedWelcomeView` | **Duplicate** — pick one, kill the other |
| Root | `HomeView` | Functional, Auto Transport card removed |
| Root | `MainTabView` | Functional, no logo placement |
| Root | `ChatView` | Standalone, untouched |
| Booking | `BookingWizardView` | Multi-step orchestrator |
| Booking | `ServiceSelectionView` / `ServiceSelectionRedesignView` | **Duplicate** — pick one, kill the other |
| Booking | `ServiceTypeSelectionView.swift` (now contains `JunkVolumeSelectionView`) | File kept for pbxproj reference, struct renamed |
| Booking | `AddressInputView` | Pickup-only after Phase 0; needs visual polish |
| Booking | `MapAddressPickerView` | Functional |
| Booking | `PhotoUploadView` | Functional |
| Booking | `DateTimePickerView` | Functional |
| Booking | `ConfirmationView` | **Bug**: still shows legacy `$89+$45+$15=$149` from `ConfirmationViewModel.priceBreakdown` (hardcoded `PriceBreakdown` struct). Needs to read `bookingData.priceBreakdown` like PaymentView now does. |
| Booking | `BookingReviewView` | Functional |
| Booking | `Booking/PaymentView` | Fixed in Phase 0 — real line items |
| Booking | `Booking/BookingSuccessView` | Functional |
| Account | `AccountView` | Functional, no logo |
| Account | `ProfileView` | Overlaps with AccountView — consolidate |
| Account | `OrdersView` | Functional |
| Account | `ReferralView` | Will populate stats after backend redeploy |
| Account | `RatingReviewView` | Functional |
| Tracking | `JobTrackingView`, `Tracking/*` | Functional |
| Auth | `WelcomeAuthView`, `LoginOptionsView`, `EmailLoginView`, `PhoneSignUpView`, `VerificationCodeView` | 5 screens — overly fragmented for a single sign-in journey |

### 2.2 Architecture

- **Pattern**: MVVM with `@EnvironmentObject BookingData` shared across the wizard. Reasonable.
- **State drift**: `BookingData` has a 18-property `Legacy Properties (TEMPORARY — Phase 2 refactor)` block (`isCommercialBooking`, `selectedRooms`, `cleanoutType`, `recurringFrequency`, etc.) that the TODO claims is interim but has lived for the entire commit history. Most of it is unused after Auto Transport removal.
- **Two pricing types**: `PricingEstimate` (Codable, real API) and `PriceBreakdown` (legacy local struct hardcoded to $149). PaymentView now uses the former; ConfirmationView still uses the latter (audit gap, §3.2).
- **Networking**: `APIClient.swift` singleton, async/await, snake_case→camelCase via `JSONDecoder.keyDecodingStrategy`. Solid.
- **Tests**: `JunkOSTests/` exists with ViewModelTests + APIClientTests + Mocks. Currently expects `PriceBreakdown.basePrice/total` and the old `PricingEstimate` shape (`subtotal`) — **tests will fail to compile/run against Phase 0 changes; needs an update pass before re-enabling CI**.

### 2.3 Design system inventory

`JunkOS/Design/DesignSystem.swift` is the single source of truth (after Phase 0).

| Token | Value | Source of truth |
|-------|-------|-----------------|
| `umuvePrimary` | `#DC2626` | Matches web `--brand` / `--color-accent` ✓ |
| `umuveBackground` | `#FFFFFF` | Matches web page bg ✓ |
| `umuveSurfaceElevated` | `#F9FAFB` | Matches web `gray-50` ✓ |
| `umuveText` | `#171717` | Matches web `gray-900` ✓ |
| `umuveTextMuted` | `#4B5563` | Matches web `gray-600` ✓ |
| `umuveBorder` | `#E5E7EB` | Matches web `gray-200` ✓ |
| `heroFont` | SF Pro Rounded 40pt heavy | System font; web uses Outfit 800. **Gap**: see §3.3 |
| `bodyFont` | SF Pro 16pt regular | System font; web uses DM Sans 400. **Gap**: see §3.3 |
| `priceFont` | SF Pro Rounded 28pt heavy | Custom for emphasis |
| Spacing | 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 | Consistent |
| Radius | 8 / 12 / 16 / 20 / 999 | Consistent |

**Reusable components present**: `UmuvePrimaryButtonStyle`, `UmuveSecondaryButtonStyle`, `UmuveCard`, `ScreenHeader`, `ProgressDots`, `HapticManager`.
**Components missing**: `UmuveTextField` (every screen rolls its own), `UmuveBadge`, `UmuveLogoView` (smart wrapper to size + tint the asset), `UmuveSectionHeader`, `UmuveEmptyState` (exists in `Components/EmptyStates/` but undersized).

---

## 3. Gap Analysis

### 3.1 Web parity gaps

Web booking flow (`platform/src/stores/booking-store.ts`):
**Address → Photos → Items → Schedule → Estimate → Payment** (6 steps, sequential)

iOS booking flow (`BookingWizardView`):
**JunkVolumeSelection → AddressInput → DateTimePicker → PhotoUpload → ConfirmationView → PaymentView** (different order, different step boundaries)

**Decision needed**: align iOS to web's 6-step order, or hold iOS's flow and align web later. Web is the published surface — iOS should match. Phase 2 work.

| Web behavior | iOS today | Action |
|---|---|---|
| Items step (7 categories with quantity steppers) | Volume tier picker (1/4, 1/2, 3/4, full truck) | Replace volume tier with category+quantity, or surface both |
| Promo code entry on Estimate step | Not present | Add — `referralCode` already wired in `BookingData` legacy block |
| Trust pill "Same-Day Service Available" | Absent | Add to Welcome + Home |
| Hero copy: "Hauling made simple." | Absent | Use in Welcome |
| Donate/recycle-first messaging | Absent | Add to BookingReview / Confirmation |

### 3.2 Functional gaps still present after Phase 0

- **ConfirmationView shows fake $149**. The screen between DateTimePicker and Payment still displays the legacy hardcoded `PriceBreakdown` from `ConfirmationViewModel`. The real estimate is already in `bookingData.priceBreakdown` (`PricingEstimate`). One-screen refactor — Phase 1.
- **Apple Sign In `error 1000` / `AKAuthenticationError -7022`** — observed in simulator only. Requires verification on a real device signed into iCloud before treating as a bug. Likely not actually broken.
- **Tests reference removed types** (`PriceBreakdown.basePrice`, old `PricingEstimate.subtotal`). Test target won't compile against Phase 0 changes.

### 3.3 HIG / platform gaps

| HIG concern | Current | Target |
|---|---|---|
| Dynamic Type | Not audited | Test xSmall → accessibility5 on every screen |
| VoiceOver labels | Inconsistent (some buttons missing labels) | Pass via `ios-accessibility` skill checklist |
| Reduce Motion | Animations don't check `accessibilityReduceMotion` | Wrap animations per `swiftui-animation` skill guidance |
| Dark mode | Tokens support it; per-screen behavior untested | Audit every screen in both modes |
| Tap targets | Some category cards <44pt at smaller text sizes | Enforce 44pt minimum |
| Custom fonts | System SF Pro; web uses Outfit/DM Sans | **Decision**: bundle the two Google Fonts (free, ~200KB combined) to match web exactly, OR commit to SF Pro Rounded as the iOS-native rendition of the brand. Recommendation: commit to system fonts — Apple-clean half of the brief — and reserve custom font work for a future native-vs-web differentiation moment. |
| SF Symbols | Used consistently | Adopt symbol effects (`.bounce.up`, `.pulse`) for selection feedback via `swiftui-animation` skill |
| Dynamic Island | Not integrated | Phase 3 — show active job status in Dynamic Island |
| Haptics | `HapticManager` exists | Audit usage — every primary CTA + every success/error state should haptic |

### 3.4 Code drift / dead weight

| Item | Action |
|---|---|
| `EnhancedWelcomeView` vs `WelcomeView` | Delete the unused one |
| `ServiceSelectionRedesignView` vs `ServiceSelectionView` | Delete the unused one |
| `BookingData.Legacy Properties` block (18 props) | Audit each, delete what nothing reads |
| `PriceBreakdown` legacy struct | Delete after `ConfirmationView` migrates to `PricingEstimate` |
| `Service.all = []` (empty stub) | Delete |
| `ServiceTier`, `CleanoutType`, `WeightCategory`, `RecurringFrequency` enums | Audit — likely unused after Auto Transport removal |
| `ServiceTypeSelectionView.swift` (filename) | Rename file (and pbxproj ref) to `JunkVolumeSelectionView.swift` — currently misleading |

---

## 4. Unified Design System Spec (target state)

### 4.1 Color (existing — keep)

```swift
// Brand
umuvePrimary       #DC2626   // CTA, accents
umuvePrimaryLight  #EF4444   // hover/active states
umuvePrimaryDark   #B91C1C   // pressed

// Surfaces
umuveBackground       white
umuveSurface          white
umuveSurfaceElevated  #F9FAFB

// Text
umuveText            #171717
umuveTextMuted       #4B5563
umuveTextTertiary    #6B7280

// UI
umuveBorder    #E5E7EB
umuveDivider   #F3F4F6

// Semantic
umuveSuccess  #10B981
umuveWarning  #F59E0B
umuveError    #DC2626  (intentionally same as brand)
umuveInfo     #3B82F6
```

### 4.2 Typography (target)

```
heroFont      SF Pro Rounded  40pt  heavy   — brand moments only
displayFont   SF Pro Rounded  34pt  bold    — empty states, success
h1Font        SF Pro Rounded  28pt  bold    — screen titles
h2Font        SF Pro Rounded  22pt  semibold
h3Font        SF Pro          18pt  semibold
bodyFont      SF Pro          16pt  regular
bodySmallFont SF Pro          14pt  regular
captionFont   SF Pro          13pt  medium
smallFont     SF Pro          11pt  medium
priceFont     SF Pro Rounded  28pt  heavy   — totals, hero prices
```

All should adopt `Dynamic Type` via `.font(.system(size: X, weight: Y))` → migrate to `Font.TextStyle` variants for accessibility scaling. Future work.

### 4.3 Components to add (Phase 1)

```swift
UmuveLogoView(size: .nav | .hero | .splash)  // 32 / 80 / 200pt, auto dark variant
UmuveTextField(label, text, error, icon)     // standard input — kill the ad-hoc HStacks
UmuveBadge(.success | .warning | .info, text)
UmuveSectionHeader(title, action: ...)
UmuveTrustPill(icon, text)                   // "Same-Day Service Available" style
UmuveSurgeChip(reason)                       // shown on price breakdown
```

### 4.4 Motion

- Default: `.smooth` (iOS 17+) for navigation transitions, `.snappy` for selection.
- Wizard step transitions: `matchedGeometryEffect` on the progress dots.
- Selection feedback: `.symbolEffect(.bounce.up, value: selected)`.
- Success: `.symbolEffect(.bounce, options: .speed(0.8))` on checkmark.
- Reduce Motion: every `withAnimation` block gated on `@Environment(\.accessibilityReduceMotion)`.

---

## 5. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Test target broken after Phase 0 model changes | M | Fix tests in Phase 1.1; flag CI is currently red |
| Backend changes (push.py + referrals.py) need Render redeploy to take effect | M | Deploy after iOS push so live iOS doesn't drift; or atomic deploy |
| Pricing API may add fields we don't tolerate | L | All new fields in `PricingEstimate` are `let` non-optional only for `total`; the rest are optional. Adding new optional fields backend-side is safe. |
| Hardcoded `$149` still on ConfirmationView confuses users between Estimate and Payment | H | Phase 1.0 priority — single-screen fix |
| Apple Sign In may genuinely be broken on device (not just simulator) | M | Verify on real device before TestFlight push |
| Auto Transport URL endpoints might still be hit by older iOS clients in field | L | Backend still serves them; no removal scheduled |
| Custom font decision impacts every screen | L | Recommendation: commit to system fonts (§3.3); revisit only if user explicitly wants Outfit/DM Sans |
| Codex may flag the legacy `PriceBreakdown` struct as dead code, but `ConfirmationViewModel` still references it | L | Expected — will resolve in Phase 1.0 |

---

## 6. Phase 1 — Hot Path Redesign

**Goal**: every screen the user touches between opening the app and completing payment is on-brand, web-parity, and HIG-correct.

### 6.1 Single-screen fixes (do first, low risk)

1. **ConfirmationView**: replace `viewModel.priceBreakdown` (legacy) with `bookingData.priceBreakdown` (`PricingEstimate`) — mirrors PaymentView pattern.
2. **Tests**: update `ConfirmationViewModelTests` + `APIClientTests` to use new `PricingEstimate` shape.
3. **Delete duplicates**: pick one of `WelcomeView`/`EnhancedWelcomeView`; one of `ServiceSelectionView`/`ServiceSelectionRedesignView`. Delete the loser.
4. **Rename** `ServiceTypeSelectionView.swift` → `JunkVolumeSelectionView.swift` + pbxproj ref.
5. **Prune** `BookingData.Legacy Properties` block — keep only `customerEmail/Name/Phone` + `referralCode`; delete the rest.

### 6.2 Visual redesign — booking flow

For each screen below: new layout, design tokens, logo placement, haptics, animations, Dynamic Type, dark mode, error/empty/loading states.

| Order | Screen | Notes |
|---|---|---|
| 1 | `WelcomeView` | Hero with logo, "Hauling made simple." headline, "Book Online Now" primary CTA, "(561) 944-1636" secondary, trust pill |
| 2 | `JunkVolumeSelection` | 4 truck cards with fill-level icons; spring entrance; haptic on tap |
| 3 | `AddressInputView` | Already pickup-only; needs polish — autocomplete dropdown styling, mini-map preview as snapshot (not live `Map`) |
| 4 | `PhotoUploadView` | Drag-to-reorder, instant compression preview, retry per-photo on failure |
| 5 | `DateTimePickerView` | Compact calendar + slot grid; surge indicator on weekend/same-day slots (from `PricingEstimate.surgeReasons`) |
| 6 | `ConfirmationView` | Real `PricingEstimate` line items; donate/recycle messaging; promo code field |
| 7 | `PaymentView` | Apple Pay primary (fix the 392vs375 constraint warning), card secondary; trust badges |
| 8 | `BookingSuccessView` | Confetti + ETA + "Track Job" deep link via `PhaseAnimator` |

### 6.3 Acceptance criteria (Phase 1)

- ✅ Build succeeds on iphonesimulator + iphoneos (real device verification on Apple Sign In)
- ✅ Tests pass
- ✅ Zero constraint warnings in console on full booking flow walkthrough
- ✅ Pricing displayed on ConfirmationView matches PaymentView matches actual charge
- ✅ Every primary CTA has haptic feedback
- ✅ Every screen renders correctly at xSmall and accessibility3 Dynamic Type sizes
- ✅ Every screen renders correctly in dark mode
- ✅ Logo present and themed correctly on Welcome + MainTabView + Auth flow

---

## 7. Phase 2 — Web Flow Parity

- Reorder wizard to match web's 6-step flow (Address → Photos → Items → Schedule → Estimate → Payment).
- Replace volume tier with web's items+quantity stepper model.
- Match copy: "Book junk removal online in 3 minutes", category names, button text.
- Donate-first messaging on Estimate review.

---

## 8. Phase 3 — Surfaces Around the Hot Path

- `MainTabView` redesign with SF Symbol effects on tab selection.
- `HomeView`: quick re-book card, last-booking summary, upcoming pickup card.
- `OrdersView` + `JobTrackingView`: timeline UI, real-time updates, driver card, map snapshot.
- Dynamic Island integration for in-progress jobs.
- Auth flow consolidation: 5 screens → 2 (welcome + verification).
- `AccountView`/`ProfileView` consolidation.

---

## 9. Phase 4 — Polish & Ship

- Animations pass (every transition uses spring; reduce-motion respected).
- Accessibility pass (VoiceOver labels, Dynamic Type, contrast).
- Dark mode pass.
- Empty/error/loading states for every screen.
- Delete remaining dead code.
- Bump build to 15; ship full redesign to TestFlight.

---

## 10. Deferred / Out of Scope

- **Auto Transport reintroduction** — kept off iOS; backend code still serves the routes for the web. Reintroduce later as a separate service with its own flow.
- **iPad layout** — no specific iPad work; rely on natural scaling.
- **Apple Watch / widgets** — not in scope.
- **Multi-language** — not in scope (iOS-accessibility skill includes localization helpers if ever needed).
- **Custom fonts (Outfit / DM Sans)** — see §3.3; defer indefinitely.

---

## 11. References

- Web brand audit: agent report 2026-05-14, sources in `landing-page-premium/index.html`, `platform/src/styles/globals.css`, `portal/app/globals.css`
- Backend pricing contract: `backend/routes/pricing.py`, `backend/routes/booking.py:408-531` (`calculate_estimate`)
- iOS pricing model: `JunkOS/Models/BookingModels.swift:82-105`
- iOS design tokens: `JunkOS/Design/DesignSystem.swift`
- Phase 0 commits: `9ff8737..dd0d7dc`
- Installed skills: `.agents/skills/{mobile-ios-design,ios-hig-design,sleek-design-mobile-apps,swiftui-animation,ios-accessibility,find-skills}`

---

*This document is the source of truth for the iOS customer app redesign. Update it as decisions land.*

---

## 12. Codex Review Findings (2026-05-14)

Reviewer flagged seven gaps after Phase 0. Status reflects work in the follow-up commit on top of `dd0d7dc`.

| # | Finding | Root Cause | Status | Notes |
|---|---|---|---|---|
| 1 | Home service cards do not pass selection into booking | `BookingWizardView` instantiated its own `@StateObject BookingData`, shadowing Home's `@EnvironmentObject` — any pre-seeded service was silently dropped. Defensive `onAppear` in `JunkVolumeSelection` masked the bug while only one service existed. | ✅ **Fixed** | `BookingWizardView.init(prefilledService:)` added; `HomeView` now passes `.junkRemoval` explicitly. Pattern survives the future re-introduction of additional services. |
| 2 | Some redesigned screens inactive/dead | `EnhancedWelcomeView` and `ProfileView` only referenced in their own `#Preview` blocks. `ServiceSelectionRedesignView` still has a live caller in `MapAddressPickerView:141` so it's a shim, not dead. | 🟡 **Partial** | Findings logged. Files left on disk this commit (pbxproj surgery deferred). Phase 1 cleanup: delete `EnhancedWelcomeView` + `ProfileView` (+ their pbxproj refs); decide whether to rewire `MapAddressPickerView` → `BookingWizardView` directly and retire the shim. |
| 3 | Search UI visual only | `HomeView.searchText` `@State` was bound to a TextField but read nowhere; the service categories list below ignored it. With Junk Removal as the only service, real search wouldn't make sense anyway. | ✅ **Fixed** | Search bar removed from HomeView. Revisit when the service catalog expands. |
| 4 | Account/payment methods placeholder | `AccountView` opens a sheet that explains "Payment methods will be added during your first booking" — acceptable holding pattern given the backend has no payment-management endpoints. **`ProfileView` is the actual problem**: 9 rows with empty `action: {}` closures (Edit Profile, Notifications, Location, Language, About, Cert, Privacy, Terms, Contact). | 🟡 **Partial** | AccountView's pattern accepted. ProfileView is dead (see #2) — deleting it removes all 9 broken rows. Payment method management is a Phase 3 feature. |
| 5 | Orders hides API errors | `OrdersView.loadBookings` set `errorMessage` on catch but body never rendered it — both "no bookings" and "API failed" rendered the same empty state. | ✅ **Fixed** | New `errorState(message:)` view with retry button. Body precedence: loading → error → empty → list. `loadBookings` clears prior error before each attempt. |
| 6 | Guest mode inconsistent | No explicit guest entry point. `currentUser?.id == "guest"` is a fallback state checked ad-hoc. Behavior matrix: Home/Booking/Account/Orders allow guests (with various CTAs); Referral fails silently for guests; Chat unprotected. | 🔴 **Decision pending** | Recommendation below. Not coded in this commit — needs product call. |
| 7 | UI tests stale | Tests reference `PriceBreakdown.basePrice/total` and the old `PricingEstimate.subtotal` field — won't compile after Phase 0. | 🔴 **Open** | Listed in §3.2 already. Test refactor is its own commit (Phase 1.1 in §6.1). |

### 12.1 Guest mode — proposed policy (needs product approval)

| Surface | Policy | Rationale |
|---|---|---|
| Home, Booking wizard end-to-end | **Allow guest** | Conversion-critical. Web allows anonymous booking too. |
| ConfirmationView, PaymentView | **Allow guest** with inline `name/email/phone` capture | Already works this way; aligns with web. |
| OrdersView | **Show "Sign in to see your bookings" CTA** (not empty state, not warning banner) | Guest has no orders to see by definition; current warning banner is correct in spirit but reads as a half-feature. |
| ReferralView | **Hard-redirect to sign-in** | Referral codes are tied to user accounts. Anonymous referral makes no sense. |
| ChatView | **Hard-redirect to sign-in** | Messages need a recipient identity. |
| AccountView | **Show "Create account to save bookings" CTA** with sign-in option | Already does this — keep. |

**Single rule of thumb**: any feature that requires a persistent user identity (orders history, referrals, chat, saved payment methods) hard-gates on sign-in; any pre-purchase action (browsing, booking, paying) supports guest.

### 12.2 Follow-up commits planned

1. `feat(ios): wire home → booking selection, remove dead search, surface orders errors` — this commit
2. `chore(ios): delete dead screens (EnhancedWelcomeView, ProfileView) + pbxproj prune` — Phase 1.1
3. `test(ios): align tests with Phase 0 PricingEstimate shape` — Phase 1.1
4. `feat(ios): guest mode policy enforcement (Orders/Referral/Chat)` — pending product call

