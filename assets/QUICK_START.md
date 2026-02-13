# Umuve App Store Assets - Quick Start

**Goal:** Generate all App Store assets in under 30 minutes

---

## ⚡ 5-Minute Setup

### Step 1: Generate Icons (2 min)
```bash
open ~/Documents/programs/webapps/junkos/assets/icon/generate-icon.html
```
- Click "Download 1024×1024" button
- Click "Download 180×180" button  
- Click "Download 120×120" button
- Click "Download 60×60" button
- Save all to `assets/icon/` directory

### Step 2: Generate Launch Screens (2 min)
```bash
open ~/Documents/programs/webapps/junkos/assets/launch-screen/generate-launch.html
```
- Click "Download iPhone 16 Pro" button
- Click "Download iPhone 15 Pro" button
- Click "Download iPhone SE" button
- Save all to `assets/launch-screen/` directory

### Step 3: Integrate Assets (1 min)
```bash
cd ~/Documents/programs/webapps/junkos/assets
./setup-assets.sh
# Choose option 1 (Mobile app)
```

---

## 📸 20-Minute Screenshot Capture

### Step 1: Start App (2 min)
```bash
cd ~/Documents/programs/webapps/junkos/mobile
npm start
# Press 'i' to launch iOS simulator
# Select iPhone 16 Pro Max
```

### Step 2: Capture Screens (10 min)
```bash
cd ~/Documents/programs/webapps/junkos/assets/screenshots
./capture-screenshots.sh
```

**Navigate through app and capture:**
1. Welcome screen → Press ENTER
2. Address input → Press ENTER
3. Photo upload → Press ENTER
4. Pricing/estimate → Press ENTER
5. Date/time picker → Press ENTER
6. Confirmation → Press ENTER

### Step 3: Add Text Overlays (8 min)

**Option A: Figma (Recommended)**
1. Import screenshots to Figma
2. Add gradient overlay rectangle (600px height)
   - Gradient: Black 60% → Transparent
3. Add text layers:
   - Title: SF Pro Display Bold, 68pt, White
   - Subtitle: SF Pro Display Regular, 44pt, White 90%
4. Export as PNG (1290×2796)

**Option B: Use Template**
See `screenshots/SCREENSHOT_GUIDE.md` for detailed overlay text and design specs

---

## 📝 Copy Marketing Text (2 min)

### Where to Find
All text is ready in: `assets/marketing-copy/app-store-listing.md`

### What to Copy
- **App Name:** Umuve
- **Subtitle:** Instant Junk Removal Quotes (29 chars)
- **Keywords:** Copy entire 99-char string
- **Description:** Copy full description (3,485 chars)
- **Promotional Text:** Copy 162-char promo

### Where to Paste
Paste into App Store Connect when creating new app listing

---

## 🎯 Text Overlays for Screenshots

Copy these exactly as shown:

### 1. Welcome Screen
**Title:** Get Instant Quotes  
**Subtitle:** Snap a photo and see pricing in seconds

### 2. Address Screen
**Title:** Enter Your Location  
**Subtitle:** We service all of Tampa Bay

### 3. Photo Upload
**Title:** AI-Powered Estimates  
**Subtitle:** Just snap photos of your junk

### 4. Pricing Screen
**Title:** Transparent Pricing  
**Subtitle:** No hidden fees. Ever.

### 5. Schedule Screen
**Title:** Book in 30 Seconds  
**Subtitle:** Same-day pickup available

### 6. Confirmation Screen
**Title:** Real-Time Tracking  
**Subtitle:** Know exactly when we'll arrive

---

## ✅ Final Checklist

### Assets Generated
- [ ] App icon (1024×1024) downloaded
- [ ] App icon (180×180) downloaded
- [ ] App icon (120×120) downloaded
- [ ] App icon (60×60) downloaded
- [ ] Launch screen (16 Pro) downloaded
- [ ] Launch screen (15 Pro) downloaded
- [ ] Launch screen (SE) downloaded
- [ ] Assets integrated into mobile app (ran `setup-assets.sh`)

### Screenshots Captured
- [ ] 01-welcome.png (raw)
- [ ] 02-address.png (raw)
- [ ] 03-photos.png (raw)
- [ ] 04-estimate.png (raw)
- [ ] 05-schedule.png (raw)
- [ ] 06-confirmation.png (raw)
- [ ] All screenshots have text overlays
- [ ] All final screenshots in `screenshots/final/`
- [ ] All screenshots verified at 1290×2796 pixels

### Marketing Copy Ready
- [ ] App name copied
- [ ] Subtitle copied (under 30 chars)
- [ ] Keywords copied (under 100 chars)
- [ ] Description copied (under 4000 chars)
- [ ] Promotional text copied (under 170 chars)
- [ ] URLs ready (privacy, support, marketing)

---

## 🚀 Ready to Upload?

### App Store Connect
1. Go to: https://appstoreconnect.apple.com
2. My Apps → + → New App
3. Upload all assets
4. Paste all text content
5. Submit build from TestFlight
6. Submit for review

### Need Help?
- **Full documentation:** `README.md`
- **Complete checklist:** `DELIVERABLES.md`
- **Screenshot details:** `screenshots/SCREENSHOT_GUIDE.md`
- **All marketing text:** `marketing-copy/app-store-listing.md`

---

## 🎨 Brand Colors (Reference)

```
Primary:    #6366F1  (Indigo)
CTA:        #DC2626  (Emerald)
Background: #F5F3FF  (Lavender)
Text:       #1E1B4B  (Dark Indigo)
```

---

## 🛠️ Troubleshooting

**Icons not showing?**
- Clean build: `Cmd + Shift + K` in Xcode or restart Expo

**Screenshot wrong size?**
- Verify simulator is iPhone 16 Pro Max
- Check: `sips -g pixelWidth -g pixelHeight file.png`

**Generator not loading?**
- Open in Chrome, Safari, or Firefox
- Check JavaScript is enabled

---

**⏱️ Total Time: ~30 minutes**  
**🎯 Result: Complete App Store asset package ready for submission**

Let's ship it! 🚛
