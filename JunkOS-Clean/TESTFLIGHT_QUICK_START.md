# TestFlight Quick Start - TL;DR

**Get Umuve on TestFlight in 30 minutes (once Apple Dev account is approved)**

---

## Prerequisites

- ✅ Apple Developer Program membership ($99/year) - [Sign up](https://developer.apple.com/programs/enroll/)
- ✅ Xcode installed
- ✅ Umuve project builds successfully

---

## 5-Step Deployment

### 1️⃣ Set Up Signing (2 minutes)

```bash
# Open project
open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
```

**In Xcode:**
1. Select project (blue icon) → Target "Umuve"
2. Go to **"Signing & Capabilities"** tab
3. ✅ Check **"Automatically manage signing"**
4. Select your **Team** from dropdown
5. Verify **Bundle ID:** `com.goumuve.app`
6. Should show green checkmark ✅

---

### 2️⃣ Create App in App Store Connect (3 minutes)

**Go to:** https://appstoreconnect.apple.com

1. **My Apps** → **+ button** → **New App**
2. Fill in:
   - **Platform:** iOS
   - **Name:** Umuve
   - **Primary Language:** English (U.S.)
   - **Bundle ID:** `com.goumuve.app`
   - **SKU:** `junkos-ios-app`
3. **Click "Create"**

---

### 3️⃣ Add App Information (5 minutes)

**In your new app:**

1. **App Information** tab:
   - **Privacy Policy URL:** `https://goumuve.com/privacy` (create this page first!)
   - **Subtitle:** "Junk Removal Made Easy"
   - **Category:** Lifestyle
   - **Age Rating:** 4+

2. **Pricing:** Free

---

### 4️⃣ Archive & Upload (10 minutes)

**In Xcode:**

1. Select **"Any iOS Device (arm64)"** (top toolbar)
2. **Product → Clean Build Folder** (⌘⇧K)
3. **Product → Archive** (wait ~2-5 minutes)
4. When Organizer opens:
   - Select your archive
   - Click **"Distribute App"**
   - Choose **"App Store Connect"**
   - Select **"Upload"**
   - Click **"Next" → "Upload"**
5. Wait for upload (~5 minutes)
6. **Success!** 🎉

---

### 5️⃣ Configure TestFlight (10 minutes)

**Go to App Store Connect** → **TestFlight tab**

1. **Wait for build processing** (10-30 min) - you'll get an email

2. **Click on your build (1.0 - 1)**

3. **Provide Export Compliance:**
   - Click "Manage"
   - **Q:** "Does your app use cryptography?"
   - **A:** NO (unless using custom encryption)
   - Auto-completes ✅

4. **Add Test Information:**
   - Scroll to "Test Information"
   - Click "Edit" next to "What to Test"
   - Add description for beta testers
   - Add **Feedback Email**
   - Click "Save"

5. **Add Internal Testers (optional):**
   - Click "Internal Testing" in sidebar
   - Add team members
   - They get instant access!

6. **Add External Testers:**
   - Click "External Testing"
   - Create group: "Beta Testers"
   - Click "Add Build"
   - Submit for Beta Review (~24 hours)
   - Once approved, add tester emails

---

## Inviting Testers

### Option A: Individual Emails

1. **TestFlight** → **External Testing** → **Beta Testers group**
2. Click **"+" next to Testers**
3. Click **"Add New Testers"**
4. Paste email addresses (one per line)
5. Click **"Add"**

### Option B: Public Link

1. **In your testing group**
2. Click **"Enable Public Link"**
3. Copy link → Share anywhere
4. Link looks like: `https://testflight.apple.com/join/ABC123`

---

## Testers Installation

**Testers receive an email with:**

1. Link to install **TestFlight app** (if they don't have it)
2. Invitation to test **Umuve**
3. **Redeem Code** (or direct link)

**Installation steps:**
1. Install TestFlight from App Store
2. Open invitation email
3. Tap "View in TestFlight" or enter code
4. Tap "Install"
5. Done! 🎉

---

## Sending Feedback

**Testers can send feedback by:**

1. **Shake device** while using app
2. Tap **"Send Beta Feedback"**
3. Add comment + optional screenshot
4. Tap **"Send"**

**You receive feedback in:**
- App Store Connect → TestFlight → Feedback tab
- Email (to your feedback email address)

---

## Releasing New Builds

**When you fix bugs or add features:**

1. **Increment build number:**
   ```bash
   cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
   agvtool next-version -all  # Build 1 → 2
   ```

2. **Archive & upload again** (Step 4 above)

3. **Wait for processing**

4. **Add to testing groups:**
   - Internal: Auto-distributed (if enabled)
   - External: Click "Add Build" in group

5. **No review needed** for subsequent builds (unless major changes)

---

## Troubleshooting (Quick Fixes)

### "No signing certificate found"
```
Fix: Xcode → Preferences → Accounts → Download Manual Profiles
```

### "Bundle ID not found"
```
Fix: Go to App Store Connect, verify Bundle ID matches Xcode exactly
```

### "Upload stuck at 'Preparing...'"
```
Fix: Restart Xcode and try again
```

### "Missing Compliance" warning
```
Fix: Click "Manage" → Answer "NO" to encryption question → Done
```

### Build not showing in TestFlight
```
Fix: Wait 10-30 minutes for processing. Check email for issues.
```

---

## Command Cheat Sheet

```bash
# Navigate to project
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean

# Open in Xcode
open JunkOS.xcodeproj

# Increment build number
agvtool next-version -all

# Clean build
xcodebuild clean -project JunkOS.xcodeproj -scheme Umuve

# Check configuration
xcodebuild -project JunkOS.xcodeproj -showBuildSettings | grep -E "PRODUCT_BUNDLE_IDENTIFIER|MARKETING_VERSION|CURRENT_PROJECT_VERSION"
```

---

## Timeline

| Task | Time |
|------|------|
| Set up signing | 2 min |
| Create app in App Store Connect | 3 min |
| Add app info | 5 min |
| Archive & upload | 10 min |
| Build processing | 10-30 min |
| Export compliance | 2 min |
| TestFlight config | 5 min |
| **TOTAL** | **~45 min** |

*Plus 24 hours for Beta App Review (first external build only)*

---

## Success Checklist

- ✅ App uploaded to App Store Connect
- ✅ Build processing completed
- ✅ Export compliance done
- ✅ Test information added
- ✅ Internal testers invited (optional)
- ✅ External build submitted for review
- ✅ Beta App Review approved (~24h)
- ✅ External testers invited
- ✅ Testers successfully installed app
- ✅ Feedback coming in

---

## What's Next?

1. **Monitor feedback** (App Store Connect → TestFlight → Feedback)
2. **Track crashes** (App Store Connect → TestFlight → Crashes)
3. **Iterate** (fix bugs, add features, release new builds)
4. **Prepare for App Store** (screenshots, description, keywords)
5. **Submit for review** when ready for public launch

---

## Helpful Links

- **App Store Connect:** https://appstoreconnect.apple.com
- **TestFlight Docs:** https://developer.apple.com/testflight/
- **Apple Developer:** https://developer.apple.com/account

---

## Need More Detail?

See [TESTFLIGHT_SETUP_GUIDE.md](./TESTFLIGHT_SETUP_GUIDE.md) for comprehensive walkthrough.

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed solutions to common issues.

See [CODE_SIGNING_GUIDE.md](./CODE_SIGNING_GUIDE.md) for deep dive on certificates and profiles.

---

**Status:** ✅ Ready to ship!

**Questions?** Check the full guide or email: support@goumuve.com
