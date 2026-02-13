# Xcode Certificates Setup for Umuve

## 🎯 Goal
Generate Apple Developer certificates so you can build and deploy Umuve to TestFlight and App Store.

**Time Required:** 10 minutes (Xcode does most of the work automatically)

---

## 📋 Prerequisites

✅ Apple Developer account active  
✅ Xcode installed (latest version recommended)  
✅ Bundle ID registered: `com.goumuve.app`  

---

## 🚀 Step-by-Step Setup

### Step 1: Open Xcode Preferences

1. Open **Xcode**
2. Go to **Xcode menu** → **Settings** (or **Preferences** on older Xcode)
3. Click the **Accounts** tab

---

### Step 2: Add Your Apple ID

1. Click the **"+"** button (bottom left)
2. Select **"Apple ID"**
3. Enter your Apple Developer account credentials:
   - Apple ID email
   - Password
4. Click **"Sign In"**

**Expected Result:** Your account appears in the list with your name and team

---

### Step 3: Manage Certificates

1. Select your Apple ID from the list
2. Select your **Team** (your name or company name)
3. Click **"Manage Certificates..."** button

**What you'll see:** A dialog showing your existing certificates (may be empty)

---

### Step 4: Create iOS Distribution Certificate

1. Click the **"+"** button (bottom left of certificate dialog)
2. Select **"Apple Distribution"**
3. Wait 3-5 seconds while Xcode generates the certificate

**Expected Result:** 
- A new certificate appears: "Apple Distribution: [Your Name]"
- Shows expiration date (1 year from today)

4. Click **"Done"**

---

### Step 5: Verify Certificate Was Created

1. Go to https://developer.apple.com/account/resources/certificates/list
2. You should see:
   - **Apple Distribution** certificate
   - Created today
   - Expires in 1 year

**If you see it → Success! ✅**

---

## 🔐 What Just Happened?

Xcode automatically:
1. ✅ Generated a private key on your Mac
2. ✅ Created a Certificate Signing Request (CSR)
3. ✅ Sent CSR to Apple
4. ✅ Downloaded the signed certificate
5. ✅ Installed it in your Mac Keychain

**You're now authorized to sign iOS apps for distribution!**

---

## 🧪 Test Your Setup

### Option A: Quick Test (Recommended)

```bash
# List your signing identities
security find-identity -v -p codesigning

# Expected output includes:
# "Apple Distribution: [Your Name] (TEAMID)"
```

**If you see "Apple Distribution" → You're good to go! ✅**

---

### Option B: Full Test with Mobile App

```bash
cd ~/Documents/programs/webapps/junkos/mobile

# Install dependencies (if not done yet)
npm install

# Configure EAS (Expo Application Services)
npx eas-cli login    # Login with Expo account
npx eas build:configure

# This creates eas.json config file
```

**Follow the prompts:**
- Platform: iOS
- Bundle identifier: com.goumuve.app
- Apple Team ID: (Xcode will auto-fill)

**Expected:** Configuration completes without errors

---

## 📱 Provisioning Profiles (Auto-Handled)

**Good news:** When you build with Expo EAS, provisioning profiles are created automatically. You don't need to manually create them!

**How it works:**
1. You run `eas build --platform ios`
2. EAS asks Apple to create a provisioning profile
3. Profile links your certificate + Bundle ID + device IDs
4. Profile is used to sign the app

**You only need the Distribution Certificate (which you just created).**

---

## 🚨 Common Issues & Fixes

### "No valid signing identity"

**Problem:** Xcode can't find your certificate

**Fix:**
```bash
# Verify certificate is installed
security find-identity -v -p codesigning

# If missing, go back to Xcode → Manage Certificates → Create again
```

### "Certificate has expired"

**Problem:** Old certificate (>1 year old)

**Fix:**
1. Go to https://developer.apple.com/account/resources/certificates/list
2. Revoke the old certificate
3. Generate new one in Xcode (Step 4 above)

### "Team not found"

**Problem:** Apple Developer account not properly linked

**Fix:**
1. Go to https://developer.apple.com/account/
2. Verify your membership is active ($99/year paid)
3. Remove Apple ID from Xcode and re-add it

### "Provisioning profile doesn't include signing certificate"

**Problem:** Profile created before certificate

**Fix:**
```bash
# Delete old profiles, they'll regenerate
rm -rf ~/Library/MobileDevice/Provisioning\ Profiles/*

# Then rebuild app
```

---

## 📋 Certificates Checklist

Before building for TestFlight:

- [ ] Apple Developer account active and paid
- [ ] Apple ID added to Xcode Accounts
- [ ] "Apple Distribution" certificate created
- [ ] Certificate visible at developer.apple.com
- [ ] Bundle ID registered: com.goumuve.app
- [ ] Xcode recognizes your team

**All checked? → You're ready to build! ✅**

---

## 🎯 Next Steps After Setup

### 1. Build for TestFlight
```bash
cd ~/Documents/programs/webapps/junkos/mobile
eas build --platform ios
```

This will:
- Use your Distribution Certificate
- Create a provisioning profile automatically
- Build the app for TestFlight
- Take ~15-20 minutes

### 2. Submit to TestFlight
```bash
eas submit --platform ios
```

This will:
- Upload the build to App Store Connect
- Make it available for internal testing
- Notify your testers via email

---

## 🔒 Security Best Practices

### Backup Your Certificate

**Important:** If you lose your certificate, you'll need to revoke and create a new one (which invalidates existing builds).

**How to backup:**
1. Open **Keychain Access** app
2. Search for "Apple Distribution"
3. Right-click certificate → **Export**
4. Save as `.p12` file with a strong password
5. Store in secure location (1Password, LastPass, etc.)

**When to use backup:**
- Setting up new Mac
- Sharing with team members
- CI/CD setup

---

## 👥 Team Setup (If You Have Multiple Developers)

**For now:** You're the only one building, so you're good.

**Later (if needed):**
1. Invite team members to Apple Developer account
2. Each creates their own "Apple Development" certificate (for testing)
3. You (admin) keep the "Apple Distribution" certificate for releases

---

## 📞 Help Resources

**Official Apple Docs:**
- https://developer.apple.com/support/certificates/

**If Stuck:**
- Share screenshot of Xcode Accounts tab
- Share output of: `security find-identity -v -p codesigning`
- I'll help debug!

---

## ✅ Verification Complete

Once you've completed all steps above:

**Test command:**
```bash
security find-identity -v -p codesigning | grep "Apple Distribution"
```

**Expected output:**
```
1) ABC123DEF456 "Apple Distribution: Your Name (TEAM12345)"
```

**If you see this → Certificate setup is COMPLETE! 🎉**

You're ready to build and deploy to TestFlight!

---

**Last Updated:** 2026-02-06  
**Status:** Ready to execute on your Mac with Xcode
