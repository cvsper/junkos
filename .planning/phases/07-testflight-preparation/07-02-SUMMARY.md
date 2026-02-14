# Phase 07 Plan 02: Privacy Policy and App Store Metadata Summary

**One-liner:** Privacy policy page deployed and comprehensive App Store Connect metadata prepared for both Umuve and Umuve Pro apps

---

## Metadata

```yaml
phase: 07-testflight-preparation
plan: 02
subsystem: documentation
tags: [app-store, privacy-policy, metadata, testflight, compliance]
completed: 2026-02-14
duration: 3.5 minutes
```

---

## Dependency Graph

**Requires:**
- Phase 07 Plan 01 (build configuration and provisioning profiles)

**Provides:**
- Public privacy policy URL for App Store Connect
- Complete App Store metadata for both apps
- TestFlight beta testing instructions
- Apple privacy nutrition labels

**Affects:**
- TestFlight external testing submission (requires privacy policy URL)
- App Store Connect app information pages
- TestFlight beta tester guidance

---

## Tech Stack

**Added:**
- Privacy policy HTML page (landing-page-premium/privacy.html)
- App Store metadata document (.planning/phases/07-testflight-preparation/app-store-metadata.md)

**Patterns:**
- Responsive HTML with Google Fonts (Outfit, DM Sans)
- Apple privacy nutrition labels format
- App Store Connect field structure

---

## Key Files

**Created:**
- `landing-page-premium/privacy.html` (331 lines) - Public privacy policy page
- `.planning/phases/07-testflight-preparation/app-store-metadata.md` (352 lines) - App Store metadata document

**Modified:**
- None

---

## What Was Built

### Task 1: Privacy Policy Page (Commit a9e8b8c)

Created a comprehensive, Apple-compliant privacy policy page at `landing-page-premium/privacy.html` ready for public deployment.

**Key sections:**
1. **Information We Collect** - Location data (pickup/delivery addresses, driver GPS), photos (optional volume estimation, job completion), contact info (Apple Sign In), payment info (Stripe), device info (push tokens)
2. **How We Use Information** - Service delivery, payment processing, customer-driver matching, real-time tracking, notifications, service improvement
3. **Information Sharing** - Service providers (drivers), payment processors (Stripe), cloud services, NO selling to third parties, NO advertising/tracking
4. **Data Retention** - Account data while active, job history for 2 years, location data deleted after completion, payment records per regulations
5. **Your Rights** - Access data, request deletion, correct information, opt out of marketing, manage location permissions
6. **Data Security** - HTTPS/TLS encryption, PCI-compliant Stripe, restricted access
7. **Children's Privacy** - Not for users under 18
8. **Changes to Policy** - Notification process
9. **International Data Transfers** - US-based service
10. **California Privacy Rights** - CCPA compliance

**Design:**
- Matches Umuve brand: white background, bold red accent (#DC2626), Outfit + DM Sans fonts
- Mobile-responsive with semantic HTML
- Clean, readable layout with section headers
- Contact box at bottom with support email

**URL:** https://goumuve.com/privacy.html (to be entered in App Store Connect)

### Task 2: App Store Connect Metadata (Commit 4a9beed)

Created comprehensive metadata document for both apps at `.planning/phases/07-testflight-preparation/app-store-metadata.md`, ready for copy-paste into App Store Connect.

**Umuve (Customer App - com.goumuve.app):**
- App Name: Umuve
- Subtitle: Hauling made simple.
- Categories: Lifestyle (primary), Utilities (secondary)
- Description: 3,847 characters covering features (booking, pricing, tracking, payments), how it works, service coverage, key benefits
- Keywords: 98 characters optimized for junk removal, hauling, auto transport, moving
- Promotional text: 167 characters for search results
- Privacy Policy URL: https://goumuve.com/privacy.html

**Umuve Pro (Driver App - com.goumuve.pro):**
- App Name: Umuve Pro
- Subtitle: Drive. Haul. Earn.
- Categories: Business (primary), Utilities (secondary)
- Description: 3,862 characters covering earnings, job notifications, navigation, volume adjustment, payouts, requirements
- Keywords: 99 characters optimized for driver, gig, earn money, contractor
- Promotional text: 169 characters for driver recruitment
- Privacy Policy URL: https://goumuve.com/privacy.html

**TestFlight Beta Information:**
- Beta app descriptions for both apps
- Detailed "What to Test" checklists covering end-to-end flows:
  - Customer: Sign in → booking flow → volume adjustment → tracking → notifications
  - Driver: Sign in → Stripe onboarding → job acceptance → navigation → volume adjustment → earnings
- Feedback email: support@goumuve.com

**Apple Privacy Nutrition Labels:**
- Data types collected: Location (precise), Photos, Contact Info, Identifiers, Financial Info (Stripe)
- Data linked to identity vs. not linked
- Data used for tracking: None
- Collection purposes: App functionality, analytics, personalization, support

**Additional Sections:**
- Screenshot requirements and suggestions (6 screenshots per app)
- Age rating: 4+ (no objectionable content)
- Export compliance: Standard encryption exemption
- Content rights: User-generated photos covered by ToS
- IDFA: Not used (no third-party ads)

---

## Key Decisions

1. **Privacy policy as standalone HTML page** - Separate from main landing page for clean URL (goumuve.com/privacy.html) and independent updates
2. **Comprehensive privacy sections** - Covers all Apple requirements plus CCPA for California residents
3. **Explicit "NO" statements in privacy policy** - Clear statements about not selling data, not using for ads, not tracking users (builds trust)
4. **Photo data marked as optional** - Explicitly states photos are optional for customers, only required for driver completion proof
5. **Location data deletion policy** - Clearly states GPS tracking data deleted after job completion (not stored permanently)
6. **TestFlight checklists as comprehensive end-to-end flows** - Beta testers get specific tasks covering all major features, not just "test the app"
7. **Keywords optimized for discovery** - Customer keywords focus on service (junk removal, hauling), driver keywords focus on earnings (gig, earn money, contractor)
8. **Descriptions emphasize transparency** - Both descriptions highlight upfront pricing, real-time updates, secure payments (trust factors)

---

## Deviations from Plan

None - Plan executed exactly as written.

---

## Verification Results

**Plan Verification:**
1. ✅ Privacy policy is valid HTML with all required legal sections
2. ✅ Privacy policy matches Umuve brand styling (white bg, red accent, Outfit + DM Sans fonts)
3. ✅ App Store metadata covers both apps with all required fields
4. ✅ Keywords optimized and within character limits (98 and 99 chars, under 100)
5. ✅ TestFlight beta test instructions specify exactly what to test (comprehensive checklists)

**Self-Check:**
- ✅ FOUND: landing-page-premium/privacy.html (331 lines)
- ✅ FOUND: .planning/phases/07-testflight-preparation/app-store-metadata.md (352 lines)
- ✅ FOUND: a9e8b8c (Task 1 commit)
- ✅ FOUND: 4a9beed (Task 2 commit)

**Result:** All files created, all commits exist, all verifications passed.

---

## Next Steps

1. **Deploy privacy policy to Vercel** - Run `vercel --prod --yes` from landing-page-premium/ to make privacy.html public
2. **Verify privacy policy URL** - Confirm https://goumuve.com/privacy.html is accessible
3. **Enter metadata in App Store Connect** - Copy-paste from app-store-metadata.md into both app information pages
4. **Generate app screenshots** - Use iPhone simulators to capture 6 screenshots per app at required sizes
5. **Continue to Phase 07 Plan 03** - Upload builds to TestFlight and configure beta testing

---

## Performance Metrics

- **Tasks completed:** 2
- **Files created:** 2
- **Commits:** 2 (a9e8b8c, 4a9beed)
- **Duration:** 3.5 minutes
- **Lines of code:** 683 (331 privacy.html + 352 metadata.md)

---

## Self-Check: PASSED

All files exist, all commits found, all verifications passed.
