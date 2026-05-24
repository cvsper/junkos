# Umuve Pro — App Store Connect Metadata

Bundle: `com.goumuve.pro` · Display name: **Umuve Pro** · Version 1.0.0 build 5

---

## App Information

- **Primary Category**: Business
- **Secondary Category**: Productivity
- **Privacy Policy URL**: `https://goumuve.com/privacy`
- **Support URL**: `https://goumuve.com`
- **Marketing URL** (optional): `https://goumuve.com/drive`  *(or leave blank if /drive doesn't exist yet)*

---

## Localization — English (U.S.)

### Name (30 char)
```
Umuve Pro
```

### Subtitle (30 char)
```
For Umuve drivers & haulers
```

### Promotional Text (170 char — editable anytime without re-review)
```
Accept jobs, navigate to pickups, capture before/after photos, and track your earnings — all in one place. Built for Umuve contractors.
```

### Description (4000 char)
```
Umuve Pro is the driver and contractor app for the Umuve junk removal platform.

This app is for active Umuve contractors only. To get started, you must first be approved as an Umuve driver. Apply at goumuve.com/drive.

WHAT YOU CAN DO
• Receive job offers in real time
• Accept or decline jobs with full pricing, address, and item details before you commit
• Turn-by-turn navigation built right into the app — no need to switch between apps
• Capture before-and-after photos at each job site
• Mark jobs in progress and complete them with one tap
• Track your daily, weekly, and lifetime earnings
• View your ratings and customer feedback
• Update your availability and service area
• Get paid out on schedule

REAL-TIME COORDINATION
Stay connected to dispatch with low-latency updates. The app keeps your location synced during active jobs so customers know when you're on the way, and route changes propagate instantly.

BUILT FOR THE ROAD
Big, glove-friendly buttons. High-contrast colors that read in sunlight. Background location so you stay tracked even when the phone is in your pocket between stops.

REQUIREMENTS
• You must be an approved Umuve contractor with a verified vehicle and insurance
• iOS 17.0 or later
• Active cellular data
• Location services enabled (always)

QUESTIONS
Contractor support: drive@goumuve.com
Phone: (561) 944-1636

Not a contractor yet? Apply at goumuve.com/drive.
```

### Keywords (100 char, no spaces after commas)
```
junk removal,hauling,driver,contractor,gig,delivery,umuve,jobs,earnings,dispatch
```

---

## App Review Information

- **First Name**: Shamar
- **Last Name**: Donaldson
- **Phone**: +1 561-944-1636
- **Email**: se7nz7@gmail.com
- **Demo Account**: REQUIRED — create a test contractor account before submitting
  - Apple needs to log in and see real driver screens
  - Pre-create on backend: `driver-test@goumuve.com` / strong password
  - Mark account as approved contractor with at least one assigned demo job so they can see the active-job flow
- **Notes for reviewer**:
  ```
  This is a companion app for approved Umuve contractors. The main customer-facing app is "Umuve" (com.goumuve.app) which handles bookings — Umuve Pro is for the drivers who fulfill those bookings. To test the full experience, please use the demo credentials provided. The account is pre-seeded with a sample job so you can walk through accepting → navigating → completing.
  ```

---

## Export Compliance
- **Uses non-exempt encryption?** No (HTTPS only, no proprietary crypto)

---

## App Privacy Nutrition Label

### Data Collected — linked to identity, for App Functionality
- Contact Info: Name, Email, Phone Number
- Location: Precise Location (job pickup/dropoff)
- Location: Coarse Location (service area)
- User Content: Photos (before/after job photos)
- Identifiers: User ID, Device ID
- Diagnostics: Crash data *(only if you wire up crashlytics — leave unchecked otherwise)*
- Financial Info: Payment Info (payout details — processed by Stripe Connect)

### NOT Used to Track You
All data above → "No" to tracking.

---

## Screenshots Required

Same dimensions as customer app:
- **6.5" iPhone**: 1284×2778 (or 1242×2688)
- **13" iPad**: 2064×2752

Recommended capture flow (5 screens):
1. Home / dashboard (today's earnings + active job)
2. Job offer modal (accept/decline)
3. In-app navigation (Mapbox view en route)
4. Active job — photo capture
5. Earnings screen (weekly breakdown)

Same trick as customer app works: capture on iPhone, resize for 6.5" slot, center on red canvas for iPad slot.

---

## Pre-Submission Checklist

- [ ] Demo contractor account created and tested on real device
- [ ] At least one demo job seeded for that account
- [ ] Apple Sign In tested on real device (was a customer-app blocker — test here too)
- [ ] Stripe Connect onboarding tested end-to-end
- [ ] Background location works through a real trip (test by driving somewhere)
- [ ] Push notifications wired and delivering (driver gets pinged on new offer)
- [ ] Screenshots captured at the right device sizes
- [ ] Privacy Policy URL still 200 (`https://goumuve.com/privacy`)
