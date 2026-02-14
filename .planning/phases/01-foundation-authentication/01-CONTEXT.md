# Phase 1: Foundation & Authentication - Context

**Gathered:** 2026-02-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Both iOS apps (Umuve customer + Umuve Pro driver) get secure authentication with Apple Sign In, JWT token management via Keychain, and an authenticated networking layer. Onboarding screens introduce each app before sign-in. No booking, pricing, or job features — just auth infrastructure and first-launch experience.

</domain>

<decisions>
## Implementation Decisions

### Sign-in experience
- 2-3 onboarding screens before sign-in screen on first launch only
- Clean and minimal tone — simple illustrations with brief descriptions
- Customer app onboarding highlights the core flow: 1) Book a pickup, 2) Track your driver, 3) Done — hauling made simple
- Driver app onboarding highlights earning: 1) Get jobs nearby, 2) Set your schedule, 3) Earn on your terms
- Auth wall: must sign in before accessing any app functionality (no guest browsing)
- Same sign-in screen layout for both apps, different branding (Umuve vs Umuve Pro)
- Apple Sign In is the only button — no other auth options, no explanation text, no "Learn More"
- No post-auth profile setup — Apple Sign In provides name/email, go straight into the app

### Session handling
- 30-day token expiry with silent background refresh
- User stays signed in across app restarts via Keychain-stored JWT
- Silent token refresh when token expires mid-use — user never sees re-auth
- Sign-out button in Settings/Profile screen
- Offline launch shows cached state with an 'offline' banner, retries in background

### Auth error states
- Sign-in failure: inline error message below button ("Something went wrong. Try again.") — stay on sign-in screen
- Role conflict: same Apple ID cannot be both customer and driver — block with message: "This account is registered as a customer. Contact support to become a driver."
- Backend down during sign-in: retry 2-3 times silently, then show error if still failing
- No explanation needed for why Apple Sign In is the only option

### Multi-device policy
- Allow concurrent sessions on multiple devices with same account
- Driver state syncs in real-time across devices via push/WebSocket
- No device management UI for v1
- Reinstall + sign-in restores previous account and state seamlessly

### Claude's Discretion
- Onboarding illustration style and exact copy
- Exact sign-in screen layout and spacing
- Token refresh implementation details (refresh token vs re-auth)
- Offline banner design and retry timing
- Error message copy beyond what's specified above

</decisions>

<specifics>
## Specific Ideas

- Onboarding screens should feel native iOS — PageTabViewStyle dots at bottom, swipeable
- Sign-in screen: Umuve logo/wordmark at top, "Sign in with Apple" button centered, clean white background with red accent
- The driver app should feel distinct from customer — "Umuve Pro" branding signals it's the professional/driver side

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-authentication*
*Context gathered: 2026-02-13*
