# Umuve Splash Screen Specification

iOS launch screen requirements and design specifications for Umuve app.

---

## Overview

The splash screen (launch screen) is the first thing users see when opening your app. iOS guidelines recommend a simple, static screen that matches your app's initial UI to provide a seamless transition.

**Design Philosophy**: Clean, branded, with quick perception of loading progress.

---

## iOS Launch Screen Requirements

### Technical Specifications

1. **Format**: Storyboard (.storyboard) or SwiftUI
2. **File**: `LaunchScreen.storyboard` or `Launch Screen.storyboard`
3. **Location**: Xcode project root / Resources folder
4. **Size**: Adaptive for all device sizes
5. **Content**: Static only (no animations, videos, or dynamic content)

### iOS Human Interface Guidelines

✅ **Do**:
- Use simple, clean design
- Match your app's first screen
- Use brand colors consistently
- Keep text to minimum (app name or logo)
- Design for all device sizes (adaptive layout)

❌ **Don't**:
- Don't use "Loading..." text
- Don't add progress indicators
- Don't show ads or promotional content
- Don't change launch screen frequently
- Don't include text that requires localization

---

## Umuve Launch Screen Design

### Design Concept

**Simplified Icon + Brand Name**

A centered, slightly larger version of the app icon with "Umuve" wordmark below.

### Layout Structure

```
┌─────────────────────────────┐
│                             │
│                             │
│         [App Icon]          │  ← 160x160pt centered icon
│           Umuve            │  ← Wordmark below
│                             │
│                             │
└─────────────────────────────┘
```

### Color Scheme

- **Background**: Indigo gradient (#7C7FF5 → #6366F1)
  - Same as app icon background
  - Creates brand consistency

- **Icon**: Full app icon (trash bin + arrow)
  - Size: 160pt x 160pt
  - Centered vertically and horizontally

- **Wordmark**: "Umuve"
  - Font: SF Pro Display Bold (iOS system font)
  - Size: 32pt
  - Color: White (#FFFFFF)
  - Letter-spacing: Slightly increased (2-3%)
  - Position: 24pt below icon

---

## Implementation Options

### Option 1: Storyboard (Recommended for simplicity)

Create `LaunchScreen.storyboard` with:

1. **View Controller** with gradient background
2. **Image View** (160x160pt) - app icon
3. **Label** - "Umuve" text

**Constraints**:
- Image View: Center X, Center Y - 40pt
- Label: Center X, Top = Image.bottom + 24pt

---

### Option 2: SwiftUI Launch Screen (iOS 14+)

Create `LaunchScreen.swift`:

```swift
import SwiftUI

struct LaunchScreenView: View {
    var body: some View {
        ZStack {
            // Gradient background
            LinearGradient(
                gradient: Gradient(colors: [
                    Color(red: 0.486, green: 0.498, blue: 0.961), // #7C7FF5
                    Color(red: 0.388, green: 0.400, blue: 0.945)  // #6366F1
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 24) {
                // App icon
                Image("LaunchIcon")
                    .resizable()
                    .frame(width: 160, height: 160)
                    .cornerRadius(35.6) // iOS app icon radius at 160pt
                
                // App name
                Text("Umuve")
                    .font(.system(size: 32, weight: .bold, design: .default))
                    .foregroundColor(.white)
                    .kerning(1.0)
            }
        }
    }
}
```

Configure in Info.plist:
```xml
<key>UILaunchScreen</key>
<dict>
    <key>UIImageName</key>
    <string>LaunchIcon</string>
    <key>UIColorName</key>
    <string>LaunchBackgroundColor</string>
</dict>
```

---

### Option 3: Asset Catalog Launch Image (Legacy)

For iOS 13+, use `LaunchImage.imageset` in Assets.xcassets:

**Sizes needed**:
- iPhone 15 Pro Max: 1290 x 2796 @3x
- iPhone 15/15 Pro: 1179 x 2556 @3x
- iPhone SE: 750 x 1334 @2x
- iPad Pro 12.9": 2048 x 2732 @2x

**Not recommended**: Requires many image variations, hard to maintain.

---

## Xcode Configuration

### Step 1: Create Launch Screen Storyboard

1. **File → New → File**
2. Select **Launch Screen** (under iOS → User Interface)
3. Name: `LaunchScreen.storyboard`
4. Add to target: ✓ Umuve

### Step 2: Design Launch Screen

1. **Add View Controller**:
   - Automatically created with storyboard

2. **Set Background**:
   - Select View
   - Background → Custom
   - Color: Indigo #6366F1
   - (For gradient, see Layer method below)

3. **Add App Icon Image**:
   - Drag **Image View** onto view
   - Image: Use `launch-icon.png` (export 160x160@3x = 480px)
   - Content Mode: Aspect Fit
   - Width: 160pt, Height: 160pt

4. **Add Constraints** (Image View):
   - Center Horizontally in Container
   - Center Vertically in Container
   - Constant: -40 (shift up 40pt)

5. **Add App Name Label**:
   - Drag **Label** onto view
   - Text: "Umuve"
   - Font: System Bold, 32pt
   - Color: White
   - Alignment: Center

6. **Add Constraints** (Label):
   - Center Horizontally in Container
   - Top Space to Image View: 24pt

### Step 3: Add Gradient Background (Optional)

For gradient background in Storyboard:

**Method A: CAGradientLayer in Code**

Create `LaunchScreenViewController.swift`:

```swift
import UIKit

class LaunchScreenViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        
        let gradientLayer = CAGradientLayer()
        gradientLayer.frame = view.bounds
        gradientLayer.colors = [
            UIColor(red: 0.486, green: 0.498, blue: 0.961, alpha: 1).cgColor,
            UIColor(red: 0.388, green: 0.400, blue: 0.945, alpha: 1).cgColor
        ]
        gradientLayer.startPoint = CGPoint(x: 0, y: 0)
        gradientLayer.endPoint = CGPoint(x: 1, y: 1)
        
        view.layer.insertSublayer(gradientLayer, at: 0)
    }
}
```

**Method B: Background Image**

Create 1px × 1024px gradient image in design tool, export as `launch-bg.png`, set as background image.

### Step 4: Configure Project Settings

1. **Select project** in navigator
2. **Select target** (Umuve)
3. **General tab**
4. **App Icons and Launch Images**:
   - Launch Screen File: `LaunchScreen`

5. **Info.plist**:
   Verify `UILaunchStoryboardName` key:
   ```xml
   <key>UILaunchStoryboardName</key>
   <string>LaunchScreen</string>
   ```

---

## Assets Required

### 1. Launch Icon Image

**File**: `launch-icon.png`
**Size**: 480x480px (160pt @3x)
**Format**: PNG with transparency OR solid background
**Location**: Assets.xcassets → New Image Set → "LaunchIcon"

**Export from SVG**:
```bash
magick icon-template.svg -resize 480x480 launch-icon.png
```

Or use same icon-160.png if already generated (scale to 480px for @3x).

### 2. Optional: Background Image

**File**: `launch-bg.png`
**Size**: 1px width × 2000px height (gradient strip)
**Format**: PNG
**Content**: Vertical gradient (#7C7FF5 → #6366F1)

---

## Testing Launch Screen

### In Simulator

1. **Run app**: Cmd + R
2. **Close app**: Cmd + Shift + H (Home)
3. **Relaunch** from home screen
4. Observe launch screen briefly appears

### Force Refresh (if changes don't appear)

```bash
# Delete app from simulator
# Clean build folder
Product → Clean Build Folder (Cmd + Shift + K)

# Reset simulator
Simulator → Device → Erase All Content and Settings

# Rebuild and run
Product → Run (Cmd + R)
```

### On Physical Device

1. **Archive and install** via Xcode
2. **TestFlight** for external testing
3. Launch app multiple times
4. Test on different device sizes:
   - iPhone SE (small)
   - iPhone 15 Pro (standard)
   - iPhone 15 Pro Max (large)
   - iPad Mini
   - iPad Pro 12.9"

---

## Alternative Design Variations

### Variation 1: Minimal (Icon Only)

- Just the app icon (180pt)
- Gradient background
- No text
- Ultra-clean, fast perception

### Variation 2: Animated (Requires Loading State)

⚠️ **Not a true launch screen** (can't animate launch screen).

Implement in first view controller:

```swift
// FirstViewController.swift
override func viewDidLoad() {
    super.viewDidLoad()
    
    // Animate icon entrance
    iconImageView.alpha = 0
    iconImageView.transform = CGAffineTransform(scaleX: 0.6, y: 0.6)
    
    UIView.animate(withDuration: 0.6, delay: 0.1, options: .curveEaseOut) {
        self.iconImageView.alpha = 1
        self.iconImageView.transform = .identity
    }
}
```

### Variation 3: Branded Tagline

Add subtle tagline below app name:
- "Clean Up. Speed Up."
- Font: SF Pro Text Regular, 14pt
- Color: White with 70% opacity

---

## Accessibility Considerations

### Dynamic Type Support

If including text, support Dynamic Type:

```swift
label.font = UIFont.preferredFont(forTextStyle: .title1)
label.adjustsFontForContentSizeCategory = true
```

### VoiceOver

Launch screens are typically ignored by VoiceOver (non-interactive).

### Dark Mode

#### Option A: Same Design (Recommended)
- Keep gradient background
- Works well in both light/dark modes

#### Option B: Adaptive
- Light mode: Lighter gradient
- Dark mode: Current gradient

Implement in Storyboard:
- Set color in Assets.xcassets with light/dark variants

---

## Performance Optimization

### Load Time
- Keep image assets small (<50KB)
- Use compressed PNGs
- Avoid multiple large images

### Smooth Transition

Match launch screen to first app screen:

**Example**: If first screen shows:
- Same gradient background
- List of items

**Launch screen should**:
- Show same gradient
- Icon placeholder (no list yet)

Users won't notice transition.

---

## App Store Screenshots

Include launch screen in App Store preview:

1. Capture launch screen on device
2. Use in first screenshot (optional)
3. Shows branding consistency

---

## Troubleshooting

### Issue: Launch screen not updating

**Solution**:
```bash
# Delete app from device/simulator
# Clean build folder
# Reset simulator/device
# Rebuild
```

### Issue: Wrong aspect ratio on some devices

**Solution**:
- Use Auto Layout constraints (not fixed frames)
- Test on all device sizes
- Use Safe Area guides

### Issue: Icon looks different than app icon

**Solution**:
- Export launch icon from same source (SVG)
- Ensure color consistency
- Match corner radius (35.6pt at 160pt size)

### Issue: Text cut off on smaller devices

**Solution**:
- Use constraint priorities
- Test on iPhone SE (smallest screen)
- Reduce font size if necessary (min 24pt)

---

## Checklist

Before submitting to App Store:

- [ ] Launch screen displays correctly on all device sizes
- [ ] Colors match app icon (#6366F1, #10B981)
- [ ] Smooth transition from launch screen to first screen
- [ ] No localized text (or properly localized if included)
- [ ] Tested on physical devices (not just simulator)
- [ ] Gradient displays correctly (not pixelated)
- [ ] Icon corners match iOS standard (35.6pt at 160pt)
- [ ] No animations or interactive elements
- [ ] Launch screen file included in Xcode target
- [ ] Build succeeds without warnings

---

## Files to Create

### Minimal Setup (Recommended):
1. ✅ `LaunchScreen.storyboard` - Interface Builder file
2. ✅ `launch-icon.png` (480x480) - App icon for launch screen
3. ✅ Assets.xcassets → LaunchIcon.imageset

### Advanced Setup:
1. `LaunchScreen.storyboard`
2. `LaunchScreenViewController.swift` - For gradient background
3. `launch-icon.png` (480x480)
4. `launch-bg.png` (optional gradient image)
5. Color assets in Assets.xcassets

---

## Summary

**Recommended implementation:**

1. ✅ Use Storyboard method (easiest)
2. ✅ Gradient background (brand color)
3. ✅ Centered app icon (160pt)
4. ✅ "Umuve" wordmark below
5. ✅ Auto Layout for all devices

**Time to implement**: 20-40 minutes

---

## Resources

### Official Documentation
- [Apple - Launch Screen Docs](https://developer.apple.com/design/human-interface-guidelines/launching)
- [UILaunchScreen Info.plist](https://developer.apple.com/documentation/bundleresources/information_property_list/uilaunchscreen)

### Design Inspiration
- [LaunchScreen Examples](https://www.mobile-patterns.com/ios/launch-screens)
- [iOS Launch Screen Best Practices](https://sarunw.com/posts/launch-screen-best-practices/)

---

**Next Steps**: Create LaunchScreen.storyboard following the design above, test on devices, and integrate into Xcode project.

For questions about icon design, see `DESIGN_SPECIFICATION.md`.
For icon generation instructions, see `icon-generation-guide.md`.
