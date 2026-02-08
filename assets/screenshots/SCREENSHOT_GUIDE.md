# App Store Screenshots Guide

## Overview
Capture 6 key screens from the JunkOS mobile app showcasing the complete user journey.

**Device:** iPhone 16 Pro Max  
**Resolution:** 1290×2796 pixels (6.7" display)  
**Format:** PNG

---

## Required Screenshots (in order)

### 1. **Welcome/Onboarding Screen**
**Filename:** `01-welcome.png`

**Content:**
- JunkOS logo and branding
- Hero tagline: "Book junk removal in 3 taps"
- Social proof badges (5-star rating, jobs completed)
- CTA button: "Get Started"

**Text Overlay (top):**
> **Get Instant Quotes**  
> Snap a photo and see pricing in seconds

---

### 2. **Address Input Screen**
**Filename:** `02-address.png`

**Content:**
- Address form with fields pre-filled (example data)
- Map preview (optional)
- Progress indicator (Step 1 of 5)
- "Next" button

**Text Overlay (top):**
> **Enter Your Location**  
> We service all of Tampa Bay

---

### 3. **Photo Upload Screen**
**Filename:** `03-photos.png`

**Content:**
- Camera interface or photo grid
- Example photos of junk items (furniture, boxes)
- "Add More Photos" button
- AI analysis indicator

**Text Overlay (top):**
> **AI-Powered Estimates**  
> Just snap photos of your junk

---

### 4. **Service Selection / Pricing Screen**
**Filename:** `04-estimate.png`

**Content:**
- AI-generated estimate with breakdown
- Service options (e.g., "Standard Removal", "Recycling Priority")
- Transparent pricing details
- Total cost displayed prominently

**Text Overlay (top):**
> **Transparent Pricing**  
> No hidden fees. Ever.

---

### 5. **Date/Time Selection Screen**
**Filename:** `05-schedule.png`

**Content:**
- Calendar interface showing available dates
- Time slot selection (showing same-day availability)
- Selected date/time highlighted

**Text Overlay (top):**
> **Book in 30 Seconds**  
> Same-day pickup available

---

### 6. **Confirmation / Tracking Screen**
**Filename:** `06-confirmation.png`

**Content:**
- Booking confirmation details
- Map with driver location (if tracking feature exists)
- Estimated arrival time
- Driver profile (photo, rating)
- Contact/chat options

**Text Overlay (top):**
> **Real-Time Tracking**  
> Know exactly when we'll arrive

---

## Capture Instructions

### Step 1: Set up simulator
```bash
# Open Xcode and launch iPhone 16 Pro Max simulator
open -a Simulator

# Or use React Native/Expo
cd ~/Documents/programs/webapps/junkos/mobile
npm start
# Then press 'i' for iOS simulator
```

### Step 2: Navigate to each screen
- Use the app to progress through each step
- Fill in example data (use realistic Tampa addresses)
- Take screenshots at key moments

### Step 3: Capture screenshots
**Method 1: Simulator (Mac)**
- `Cmd + S` to save screenshot
- Screenshots save to Desktop by default

**Method 2: xcrun**
```bash
xcrun simctl io booted screenshot screenshot.png
```

### Step 4: Verify dimensions
```bash
sips -g pixelWidth -g pixelHeight screenshot.png
# Should show: 1290 x 2796
```

---

## Text Overlay Design

### Tools
- **Figma** (recommended): Import screenshots, add text layers
- **Sketch**: Native Mac app for design
- **Photoshop**: Professional option
- **Canva**: Web-based, beginner-friendly

### Typography
- **Font:** SF Pro Display (iOS native font)
- **Title size:** 64-72pt, Bold
- **Subtitle size:** 40-48pt, Regular
- **Color:** White text with dark gradient overlay (80% opacity)

### Layout
- Position text overlay in top 25% of screen
- Add gradient overlay behind text for readability:
  - Top: `rgba(0, 0, 0, 0.6)`
  - Bottom: `rgba(0, 0, 0, 0)` (fade to transparent)

### Example Overlay Structure
```
┌─────────────────────────┐
│  [Gradient Overlay]     │
│  Title Text (Bold)      │
│  Subtitle (Regular)     │
│                         │
│  [App Screenshot]       │
│                         │
│                         │
│                         │
│                         │
└─────────────────────────┘
```

---

## Quick Figma Template

### Create overlay in Figma:
1. Create frame: 1290×2796px
2. Import screenshot as background
3. Add rectangle overlay (top 600px):
   - Gradient: Linear, Top to Bottom
   - Stop 1: `#000000` at 0%, 60% opacity
   - Stop 2: `#000000` at 100%, 0% opacity
4. Add text layers:
   - Title: SF Pro Display, Bold, 68pt, White
   - Subtitle: SF Pro Display, Regular, 44pt, White (#FFFFFF 90%)
5. Export as PNG at 1x resolution

---

## Alternative: Add overlays with ImageMagick

```bash
# Install ImageMagick (if not installed)
brew install imagemagick

# Add text overlay to screenshot
convert 01-welcome.png \
  -gravity North \
  -background 'rgba(0,0,0,0.6)' \
  -splice 0x400 \
  -font 'SF-Pro-Display-Bold' \
  -pointsize 68 \
  -fill white \
  -annotate +0+120 'Get Instant Quotes' \
  -pointsize 44 \
  -font 'SF-Pro-Display-Regular' \
  -annotate +0+200 'Snap a photo and see pricing in seconds' \
  01-welcome-overlay.png
```

---

## Checklist

- [ ] All 6 screenshots captured at 1290×2796
- [ ] Realistic demo data used (Tampa addresses, example items)
- [ ] Text overlays added with proper typography
- [ ] Images saved as PNG
- [ ] File naming convention followed (01-welcome.png, etc.)
- [ ] Images optimized for web (compressed without quality loss)
- [ ] Screenshots reviewed for visual consistency

---

## App Store Optimization Tips

1. **First screenshot matters most** - Make the welcome screen compelling
2. **Show value immediately** - Highlight AI estimates and instant booking
3. **Use consistent branding** - Match colors and fonts to app design
4. **Minimize text** - Let visuals tell the story, use text to enhance
5. **Test on device** - View screenshots on actual iPhone to check readability

---

## Final Export

Once complete, export all 6 screenshots and place them in:
```
~/Documents/programs/webapps/junkos/assets/screenshots/final/
```

Then create a preview set for App Store Connect upload.
