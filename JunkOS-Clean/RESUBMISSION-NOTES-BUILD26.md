# Umuve customer app — build 26 resubmission notes

Build 25 was rejected on 2026-05-16 (Submission `f1bd808b-2789-48d5-b085-98bea01f9a39`) for:

1. **Guideline 5.1.1(v)** — App supports account creation but doesn't include in-app account deletion
2. **Guideline 2.1** — Apple's reviewer asked for an *Apple Pay Issuer* card-add demo. This is a misclassification; we're a *merchant accepting* Apple Pay through Stripe, not an issuer

Both addressed below. Build 26 adds in-app account deletion. Issue 2 needs a Resolution Center reply, not a new build.

---

## Issue 1 — Account Deletion (5.1.1(v))

### What was added in build 26

- **Account → Delete Account** — small underlined link under "Log Out"
- Tapping it opens a full-screen explanatory sheet listing exactly what gets removed (profile, sign-out, anonymization of bookings, end of notifications) plus a `Delete My Account` button and a `Keep My Account` button
- Tapping `Delete My Account` triggers a destructive iOS alert ("Delete account?") with `Cancel` and `Delete Forever` actions
- On confirmation the iOS app calls `DELETE /api/auth/me`; on success the user is signed out and returned to the welcome screen

### Backend behavior (deployed before build 26)

`DELETE /api/auth/me` now does a real deletion, not a deactivation:

- Nulls `email`, `phone`, `name`, `password_hash`, `apple_id`, `avatar_url`, `stripe_customer_id`, `referral_code`
- Sets `status = 'deleted'`
- Deletes all device push tokens
- Existing JWTs for the user are rejected on next request (`require_auth` checks status)
- The user row itself is retained (anonymized) to preserve foreign-key integrity on historical bookings and ratings; the user can no longer be identified or re-logged-in

This matches Apple's note that "only offering to temporarily deactivate or disable an account is insufficient."

### Screen recording for the Notes field

Apple wants a recording on a physical device showing:

1. Sign in (use demo account)
2. Navigate to Account tab
3. Scroll past Log Out, tap "Delete Account"
4. Walk through the sheet
5. Tap "Delete My Account" → confirm "Delete Forever"
6. App returns to the welcome/sign-in screen
7. Try to log back in with the same credentials → fails (no account)

Save the recording (.mov/.mp4), upload somewhere shareable (e.g., Loom, Google Drive with link-share), and paste the URL into App Review Information → Notes.

---

## Issue 2 — Apple Pay misclassification (2.1)

Apple's reviewer wrote:

> "As an Apple Pay Issuer, all the Apple Pay functionality. Ensure the demo video shows a new card being added to the wallet."

This is a misclassification. We are **not** an Apple Pay Issuer (a bank that provisions payment cards into Wallet via PassKit). We are a **merchant** that accepts Apple Pay as a payment method for service bookings, processed through Stripe.

### Resolution Center reply (paste verbatim)

> Thank you for the review.
>
> Regarding guideline 5.1.1(v) — account deletion has been added to the Account tab in build 26. Tap **Account → Delete Account** below Log Out. A confirmation sheet explains the consequences and a destructive alert confirms before deletion. A screen recording of the full flow is linked in the Notes field of App Review Information.
>
> Regarding guideline 2.1 — we believe there is a misclassification here. Umuve is **not an Apple Pay Issuer.** We do not provision payment cards into Apple Wallet via PassKit. We are a **merchant** offering on-demand junk-removal services, and Apple Pay is one of the payment methods we accept from customers (processed through Stripe). The PassKit framework is linked solely so customers can tap "Buy with Apple Pay" on the booking-review screen to authorize a payment, and Stripe's Payment Sheet presents the standard Apple Pay authorization sheet using our merchant identifier `merchant.com.goumuve.app`. There are no card-add, wallet-pass, or card-provisioning flows in the app — those are issuer responsibilities and we are not an issuer.
>
> To demonstrate our Apple Pay integration as a merchant, please:
>
> 1. Sign in with the demo account (credentials in App Review Information → Notes)
> 2. From Home tap **Get a Quote**
> 3. Complete the booking wizard (service → items → address → date/time)
> 4. On the final **Review Your Estimate** screen, the black **Buy with Apple Pay** button is directly above the **Pay $X** button
> 5. Tapping it presents the Stripe Payment Sheet, which surfaces the standard Apple Pay authorization sheet
>
> If a different demo is required, please let us know what additional functionality you need to see — we want to be sure we're addressing the right concern.
>
> Thanks again.

---

## Pre-resubmit checklist

- [ ] Backend `DELETE /api/auth/me` deployed on Render (check `https://junkos-backend.onrender.com/api/health` and confirm the new commit `770a626` shows on Render's dashboard)
- [ ] Build 26 uploaded to App Store Connect, processed, attached to the version
- [ ] Demo account credentials in App Review Information → Notes
- [ ] Screen recording of deletion flow uploaded and linked in Notes
- [ ] Resolution Center reply pasted (text above)
- [ ] App Privacy nutrition label still shows the build-25 fixes (Name/Photos/Device ID → Not Used to Track You)
- [ ] Hit **Add for Review** → **Submit**
