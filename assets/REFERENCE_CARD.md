# Umuve App Store Assets - Reference Card

**Keep this open while working** 📌

---

## 🎨 Brand Colors (Copy-Paste Ready)

```
Primary:    #6366F1
Secondary:  #818CF8
CTA:        #DC2626
Background: #F5F3FF
Text:       #1E1B4B
Muted:      #64748B
White:      #FFFFFF
```

---

## 📱 Required Asset Sizes

### Icons
- ✅ 1024×1024 (App Store)
- ✅ 180×180 (iPhone @3x)
- ✅ 120×120 (iPhone @2x)
- ✅ 60×60 (Settings @3x)

### Launch Screens
- ✅ 1290×2796 (iPhone 16 Pro)
- ✅ 1179×2556 (iPhone 15 Pro)
- ✅ 750×1334 (iPhone SE)

### Screenshots
- ✅ 1290×2796 (6 images)

---

## 📸 Screenshot Overlay Text

### 01-welcome.png
**Get Instant Quotes**  
Snap a photo and see pricing in seconds

### 02-address.png
**Enter Your Location**  
We service all of Tampa Bay

### 03-photos.png
**AI-Powered Estimates**  
Just snap photos of your junk

### 04-estimate.png
**Transparent Pricing**  
No hidden fees. Ever.

### 05-schedule.png
**Book in 30 Seconds**  
Same-day pickup available

### 06-confirmation.png
**Real-Time Tracking**  
Know exactly when we'll arrive

---

## 📝 App Store Text (Copy-Paste)

### App Name
```
Umuve
```

### Subtitle (29 chars)
```
Instant Junk Removal Quotes
```

### Keywords (99 chars)
```
junk removal,hauling,declutter,waste,furniture removal,trash pickup,dump,moving,cleanup,recycling
```

### URLs
```
Privacy: https://goumuve.com/privacy
Support: https://goumuve.com/support
Marketing: https://goumuve.com
```

### Categories
- Primary: Lifestyle
- Secondary: Productivity

### Age Rating
```
4+
```

---

## ⚡ Quick Commands

### Generate Icons
```bash
open ~/Documents/programs/webapps/junkos/assets/icon/generate-icon.html
```

### Generate Launch Screens
```bash
open ~/Documents/programs/webapps/junkos/assets/launch-screen/generate-launch.html
```

### Integrate Assets
```bash
cd ~/Documents/programs/webapps/junkos/assets
./setup-assets.sh
```

### Start Mobile App
```bash
cd ~/Documents/programs/webapps/junkos/mobile
npm start
```

### Capture Screenshots
```bash
cd ~/Documents/programs/webapps/junkos/assets/screenshots
./capture-screenshots.sh
```

---

## 🎯 Typography for Overlays

### Titles
- Font: SF Pro Display Bold
- Size: 68pt
- Color: White (#FFFFFF)

### Subtitles
- Font: SF Pro Display Regular
- Size: 44pt
- Color: White 90% (#FFFFFF E6)

### Gradient Overlay
- Height: 600px (top)
- Color 1: rgba(0, 0, 0, 0.6)
- Color 2: rgba(0, 0, 0, 0)
- Direction: Top → Bottom

---

## ✅ Pre-Flight Checklist

### Before Opening Generators
- [ ] Chrome/Safari/Firefox browser ready
- [ ] Download folder cleared/organized
- [ ] Read QUICK_START.md

### Icon Generation
- [ ] Opened generate-icon.html
- [ ] Downloaded 1024×1024
- [ ] Downloaded 180×180
- [ ] Downloaded 120×120
- [ ] Downloaded 60×60
- [ ] Saved to assets/icon/

### Launch Screen Generation
- [ ] Opened generate-launch.html
- [ ] Downloaded iPhone 16 Pro
- [ ] Downloaded iPhone 15 Pro
- [ ] Downloaded iPhone SE
- [ ] Saved to assets/launch-screen/

### Asset Integration
- [ ] Ran setup-assets.sh
- [ ] Verified icon.png copied
- [ ] Verified splash.png copied
- [ ] Checked app in simulator

### Screenshot Capture
- [ ] Mobile app running (iPhone 16 Pro Max)
- [ ] Ran capture-screenshots.sh
- [ ] Captured all 6 screens
- [ ] Verified all 1290×2796
- [ ] Added text overlays in Figma
- [ ] Exported to screenshots/final/

### Marketing Copy
- [ ] Copied app name
- [ ] Copied subtitle (checked 30 char limit)
- [ ] Copied keywords (checked 100 char limit)
- [ ] Copied description (checked 4000 char limit)
- [ ] Copied promotional text
- [ ] Prepared all URLs

### App Store Connect
- [ ] Account ready
- [ ] New app created
- [ ] Icon uploaded (1024×1024)
- [ ] 6 screenshots uploaded (in order)
- [ ] All text pasted
- [ ] Categories selected
- [ ] URLs entered
- [ ] Build uploaded from TestFlight
- [ ] Submitted for review

---

## 🚨 Common Mistakes

❌ Using icon with alpha channel (1024×1024 must have no transparency)  
❌ Wrong screenshot size (must be exactly 1290×2796)  
❌ Subtitle over 30 characters  
❌ Keywords over 100 characters  
❌ Description over 4000 characters  
❌ Screenshots not in correct order  
❌ Text overlays too small to read  
❌ Forgetting to update app.json backgroundColor

---

## 📊 Character Limits

| Field | Limit | Current |
|-------|-------|---------|
| App Name | 30 | 6 ✅ |
| Subtitle | 30 | 29 ✅ |
| Keywords | 100 | 99 ✅ |
| Description | 4000 | 3485 ✅ |
| Promotional | 170 | 162 ✅ |
| What's New | 4000 | ~300 ✅ |

---

## 🎨 Figma Quick Template

1. Create frame: 1290 × 2796
2. Import screenshot as background
3. Add rectangle (top 600px):
   - Fill: Linear gradient, vertical
   - Stop 1: #000000, 60% opacity
   - Stop 2: #000000, 0% opacity
4. Add title text:
   - Font: SF Pro Display Bold
   - Size: 68pt
   - Color: #FFFFFF
   - Position: 120px from top
5. Add subtitle text:
   - Font: SF Pro Display Regular
   - Size: 44pt
   - Color: #FFFFFF E6
   - Position: 200px from top
6. Export: PNG, 1x, no compression

---

## 📱 Device Selection

**For Screenshots:**
- Simulator: iPhone 16 Pro Max
- Display: 6.7" (1290×2796)
- Scale: 3x (@3x)

**To Verify:**
```bash
xcrun simctl list devices | grep "iPhone 16 Pro Max"
```

---

## 🔍 Verify Asset Dimensions

```bash
# Check icon
sips -g pixelWidth -g pixelHeight icon.png

# Check screenshot
sips -g pixelWidth -g pixelHeight screenshot.png

# Batch check
for f in screenshots/final/*.png; do
  echo "$f:"
  sips -g pixelWidth -g pixelHeight "$f"
done
```

---

## 📞 File Locations

```
Icon generators:       assets/icon/generate-icon.html
Launch generators:     assets/launch-screen/generate-launch.html
Setup script:          assets/setup-assets.sh
Screenshot script:     assets/screenshots/capture-screenshots.sh
Screenshot guide:      assets/screenshots/SCREENSHOT_GUIDE.md
Marketing copy:        assets/marketing-copy/app-store-listing.md
Full docs:             assets/README.md
Quick start:           assets/QUICK_START.md
Complete checklist:    assets/DELIVERABLES.md
```

---

**Print this page or keep it open while working!** 📌

**🚛 Umuve - Let's ship it!**
