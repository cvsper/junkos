# Umuve customer app — build 25 resubmission notes

Build 24 was rejected on 2026-05-15 for:
1. **Guideline 2.1** — PassKit linked but no visible Apple Pay integration found
2. **Guideline 5.1.2(i)** — Privacy nutrition label claimed tracking (Name, Photos, Device ID) but app doesn't use ATT framework

Both fixed for build 25.

---

## Resolution Center reply (paste in App Store Connect → App Review → Resolution Center)

> Thanks for the detailed review.
>
> **Guideline 2.1 — Apple Pay:** Apple Pay is now surfaced as a dedicated "Buy with Apple Pay" button on the booking review screen (final step of the booking flow), above the "Pay $X" button. It appears whenever the device supports Apple Pay. Tapping it launches the Stripe Payment Sheet pre-configured with our merchant identifier `merchant.com.goumuve.app`, which presents the native Apple Pay authorization sheet.
>
> To reach this screen in build 25:
> 1. Sign in (or use demo account)
> 2. Tap "Get a Quote" on the home screen
> 3. Complete the wizard: pick a service, add at least one item, enter an address, pick a date/time
> 4. The final step is "Review Your Estimate" — the Apple Pay button is at the bottom of that screen, just above the "Pay $X" button
>
> **Guideline 5.1.2(i) — Privacy/Tracking:** We've updated the App Privacy information in App Store Connect. The app does not link any user data with third-party data for advertising and does not share data with data brokers. Name, Photos/Videos, and Device ID are collected for App Functionality only and are no longer marked as "Used to Track You." No ATT prompt is needed because the app does not track per Apple's definition.
>
> Thanks again — happy to clarify anything else.

---

## App Review Information — Notes field (paste in App Store Connect → App Information → App Review Information → Notes)

```
Apple Pay is integrated via Stripe's Payment Sheet. To find the Apple Pay button:

1. Sign in with demo account: [your demo credentials here]
2. From Home, tap "Get a Quote"
3. Walk through the booking wizard (service type → items → address → date/time)
4. On the final "Review Your Estimate" screen, scroll to the bottom — the black "Buy with Apple Pay" button sits directly above the "Pay $X" button
5. Tapping it triggers the Stripe Payment Sheet which presents native Apple Pay

Merchant ID: merchant.com.goumuve.app

The app does NOT use App Tracking Transparency because it does not engage in tracking as defined by Apple — no third-party advertising data linking, no data broker sharing. The App Privacy nutrition label reflects this.
```

---

## App Store Connect — App Privacy section fixes

Path: App Store Connect → Umuve → App Privacy → Edit each data type below:

| Data Type | Used to Track You? | Linked to Identity? | Purposes |
|---|---|---|---|
| Name | **No** | Yes | App Functionality, Account Management |
| Email | No | Yes | App Functionality, Account Management |
| Phone Number | No | Yes | App Functionality, Customer Support |
| Photos or Videos | **No** | Yes | App Functionality |
| Precise Location | No | Yes | App Functionality |
| Coarse Location | No | Yes | App Functionality |
| User ID | No | Yes | App Functionality |
| Device ID | **No** | Yes | App Functionality |
| Payment Info | No | Yes | App Functionality |

The three Apple flagged are bolded. Save → publish privacy update.

---

## Demo account (for App Review)

Apple will need working credentials. Before resubmitting, verify:

- [ ] Demo customer account exists on production backend (or staging if reviewable)
- [ ] Credentials documented in App Review Notes
- [ ] Demo account can complete the booking flow end-to-end on iOS

If you don't have a demo account yet, create one now — Apple will reject again if they can't log in.
