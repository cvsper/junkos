# Umuve App Store Assets

This directory contains all assets needed for App Store submission and iOS app integration.

## 📁 Directory Structure

```
assets/
├── icon/                    # App icons (all sizes)
│   ├── generate-icon.html   # Icon generator (open in browser)
│   └── [generated PNGs]
│
├── launch-screen/           # Launch/splash screens
│   ├── generate-launch.html # Launch screen generator
│   └── [generated PNGs]
│
├── screenshots/             # App Store screenshots
│   ├── SCREENSHOT_GUIDE.md  # Capture instructions
│   └── final/               # Final overlaid screenshots (1290×2796)
│
└── marketing-copy/          # App Store text content
    └── app-store-listing.md # Complete listing copy
```

---

## 🚀 Quick Start

### 1. Generate App Icon
```bash
open assets/icon/generate-icon.html
```
- Download all icon sizes (1024, 180, 120, 60)
- Icons use brand colors: Primary #6366F1, CTA #DC2626
- Simple truck design, iOS-native aesthetic

### 2. Generate Launch Screens
```bash
open assets/launch-screen/generate-launch.html
```
- Download for iPhone 16 Pro, 15 Pro, SE
- Branded splash with logo + tagline

### 3. Capture Screenshots
Follow `screenshots/SCREENSHOT_GUIDE.md`:
- Launch iPhone 16 Pro Max simulator
- Navigate through app and capture 6 key screens
- Add text overlays showcasing features
- Export as 1290×2796 PNG files

### 4. Use Marketing Copy
All App Store text is in `marketing-copy/app-store-listing.md`:
- App name: **Umuve**
- Subtitle: **Instant Junk Removal Quotes** (29 chars)
- Keywords: 99 characters optimized for ASO
- Description: ~3,485 characters with features & benefits
- What's New section for version 1.0.0

---

## 📱 Integration with Xcode

### Add Icons to Assets.xcassets

#### For React Native/Expo project:
```bash
cd ~/Documents/programs/webapps/junkos/mobile

# Replace default icon
cp ../assets/icon/umuve-icon-1024.png ./assets/icon.png

# Update app.json
```

#### For Native iOS project:
```bash
cd ~/Documents/programs/webapps/junkos/ios-native/Umuve

# Open in Xcode
open ../Umuve.xcodeproj

# In Xcode:
# 1. Select Assets.xcassets in Project Navigator
# 2. Select AppIcon
# 3. Drag and drop icon files into appropriate slots:
#    - 1024x1024 → App Store
#    - 180x180 → iPhone App (60pt @3x)
#    - 120x120 → iPhone App (60pt @2x)
#    - 80x80 → Spotlight (40pt @2x)
#    - 60x60 → Settings (20pt @3x)
```

### Add Launch Screen

#### React Native/Expo:
```json
// app.json
{
  "expo": {
    "splash": {
      "image": "./assets/launch-screen/umuve-launch-16pro.png",
      "resizeMode": "contain",
      "backgroundColor": "#F5F3FF"
    }
  }
}
```

#### Native iOS:
1. Open `LaunchScreen.storyboard` in Xcode
2. Add UIImageView
3. Import launch screen image to Assets.xcassets
4. Set image in storyboard

---

## 🎨 Design System

### Brand Colors
```
Primary:    #6366F1 (Indigo 500)
Secondary:  #818CF8 (Indigo 400)
CTA:        #DC2626 (Emerald 500)
Background: #F5F3FF (Lavender)
Text:       #1E1B4B (Indigo 950)
Muted:      #64748B (Slate 500)
```

### Typography
- **System Font:** SF Pro (iOS native)
- **Headings:** SF Pro Display, Bold
- **Body:** SF Pro Text, Regular
- **UI Elements:** SF Rounded (optional, for friendly vibe)

### Icon Design
- **Style:** Minimalist, geometric
- **Symbol:** Simplified truck silhouette
- **Wheels:** Emerald accent (#DC2626)
- **Background:** Indigo gradient (#6366F1 → #818CF8)
- **Works at:** 29×29, 40×40, 60×60, and larger

---

## 📋 App Store Submission Checklist

### Before Upload
- [ ] All icon sizes generated and added to Assets.xcassets
- [ ] Launch screen configured in Xcode/app.json
- [ ] 6 screenshots captured with text overlays (1290×2796)
- [ ] App name: "Umuve" (verified available on App Store)
- [ ] Subtitle: "Instant Junk Removal Quotes"
- [ ] Keywords optimized (99 chars)
- [ ] Description polished (~3,485 chars)
- [ ] Privacy Policy URL: https://goumuve.com/privacy
- [ ] Support URL: https://goumuve.com/support
- [ ] App category: Lifestyle (primary), Productivity (secondary)
- [ ] Age rating: 4+
- [ ] Test build uploaded to TestFlight
- [ ] Beta testers invited

### App Store Connect
1. Log in to https://appstoreconnect.apple.com
2. Select "My Apps" → "+" → "New App"
3. Fill in app information:
   - Platform: iOS
   - Name: Umuve
   - Primary Language: English (U.S.)
   - Bundle ID: (from Xcode)
   - SKU: UMUVE-001
4. Upload screenshots (6 images, 1290×2796)
5. Upload app icon (1024×1024, no alpha channel)
6. Paste description, keywords, subtitle
7. Add support/privacy URLs
8. Select categories
9. Set pricing (Free)
10. Submit for review

---

## 🔧 Troubleshooting

### Icon doesn't appear in simulator
- Clean build: `Cmd + Shift + K` in Xcode
- Reset simulator: Device → Erase All Content and Settings
- Rebuild and reinstall app

### Launch screen shows default
- Verify image is in Assets.xcassets
- Check LaunchScreen.storyboard references correct image
- Clean build folder: `Cmd + Shift + Alt + K`

### Screenshots wrong size
- Simulator must be iPhone 16 Pro Max
- Check with: `sips -g pixelWidth -g pixelHeight file.png`
- Expected: 1290 × 2796 pixels

### Icon generator not working
- Open in modern browser (Chrome, Safari, Firefox)
- Enable JavaScript
- Check browser console for errors
- Use download buttons after canvas renders

---

## 📚 Resources

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [App Store Screenshot Specifications](https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications)
- [App Icon Guidelines](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- [SF Symbols App](https://developer.apple.com/sf-symbols/) (alternative icon exploration)

---

## 🎯 Next Steps

1. **Generate all assets** using the HTML generators
2. **Capture app screenshots** following the guide
3. **Add overlays** to screenshots in Figma or Photoshop
4. **Integrate icons** into Xcode Assets.xcassets
5. **Test in simulator** to verify icons and launch screen
6. **Prepare App Store Connect** with all marketing copy
7. **Upload to TestFlight** for beta testing
8. **Submit for review** when ready

---

**Need help?** Review the individual README files in each subdirectory for detailed instructions.

**Brand consistency:** All assets use the Umuve design system. Keep the premium, trustworthy, modern vibe throughout.
