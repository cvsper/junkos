# Umuve Icon Generation Guide

Complete guide for creating, exporting, and integrating iOS app icons from the provided SVG template.

## Quick Start

1. Open `icon-template.svg` in your preferred design tool
2. Make any adjustments needed
3. Export all required sizes (see below)
4. Add to Xcode project
5. Test on devices

---

## Method 1: Using Design Tools (Figma, Sketch, Illustrator)

### Figma (Recommended)

#### Setup
1. **Import SVG**:
   ```
   File → Import → Select icon-template.svg
   ```

2. **Set up export frame**:
   - Select all elements
   - Frame selection: Cmd/Ctrl + Alt + G
   - Name frame: "Umuve-Icon"
   - Ensure frame is exactly 1024x1024px

3. **Configure exports**:
   - Select frame
   - Export settings (right panel)
   - Add all required sizes:

#### Export Settings
Add these export configurations:

```
iOS App Icon Sizes:
1x  → 1024x1024 (App Store)
1x  → 180x180  (iPhone @3x)
1x  → 167x167  (iPad Pro)
1x  → 152x152  (iPad @2x)
1x  → 120x120  (iPhone @2x)
1x  → 87x87    (iPhone @3x settings)
1x  → 80x80    (iPad @2x settings)
1x  → 76x76    (iPad)
1x  → 60x60    (iPhone)
1x  → 58x58    (iPhone settings)
1x  → 40x40    (Spotlight)
1x  → 29x29    (Settings)
1x  → 20x20    (Notification)
```

4. **Export**:
   - Format: PNG
   - Color profile: sRGB
   - Click "Export Umuve-Icon"

5. **Naming**:
   - Rename files to: `icon-{size}.png`
   - Example: `icon-1024.png`, `icon-180.png`

---

### Adobe Illustrator

#### Setup
1. **Open SVG**:
   ```
   File → Open → icon-template.svg
   ```

2. **Verify artboard**:
   - Should be 1024x1024pt
   - If not: File → Document Setup → Edit Artboards

#### Export Each Size
1. **Use Export for Screens**:
   ```
   File → Export → Export for Screens
   ```

2. **Configure formats**:
   - Format: PNG
   - Scale: Custom
   - Add each required size manually

3. **Scale calculations** (from 1024px base):
   ```
   1024px = 100%   (1024 ÷ 1024)
   180px  = 17.6%  (180 ÷ 1024)
   167px  = 16.3%  (167 ÷ 1024)
   152px  = 14.8%  (152 ÷ 1024)
   ... etc
   ```

4. **Export all**:
   - Click "Export Artboard"
   - Save to icons folder

---

### Sketch

#### Setup
1. **Import SVG**:
   ```
   File → Open → icon-template.svg
   ```

2. **Create artboard**:
   - Insert → Artboard
   - Size: 1024x1024
   - Place SVG inside artboard

#### Export
1. **Make artboard exportable**:
   - Select artboard
   - Click "Make Exportable" (bottom right)

2. **Add sizes**:
   - Click "+" for each size
   - Enter size (1024, 180, 167, etc.)
   - Format: PNG

3. **Export**:
   - File → Export
   - Or click "Export" in inspector

---

## Method 2: Using Online Tools (Fastest)

### appicon.co (Recommended)

1. **Export 1024x1024 PNG** from SVG:
   - Use any tool above to create icon-1024.png
   - Or use ImageMagick (see Method 3)

2. **Upload to appicon.co**:
   ```
   https://www.appicon.co/
   ```
   - Upload icon-1024.png
   - Select "iOS"
   - Download zip file

3. **Extract**:
   - Unzip downloaded file
   - Contains all required sizes
   - Copy to your project

### makeappicon.com

Similar process:
```
https://makeappicon.com/
```
- Upload 1024x1024 PNG
- Download iOS package
- Extract and use

---

## Method 3: Command Line (ImageMagick)

### Prerequisites
```bash
# Install ImageMagick
brew install imagemagick  # macOS
sudo apt install imagemagick  # Linux
```

### Batch Export Script

Create `generate-icons.sh`:

```bash
#!/bin/bash

# Input SVG file
INPUT="icon-template.svg"
OUTPUT_DIR="./exported"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# iOS icon sizes
sizes=(1024 180 167 152 120 87 80 76 60 58 40 29 20)

# Convert SVG to each size
for size in "${sizes[@]}"; do
  echo "Generating ${size}x${size}..."
  magick "$INPUT" \
    -resize "${size}x${size}" \
    -background none \
    -gravity center \
    -extent "${size}x${size}" \
    "$OUTPUT_DIR/icon-${size}.png"
done

echo "✓ All icons generated in $OUTPUT_DIR"
```

### Run Script:
```bash
chmod +x generate-icons.sh
./generate-icons.sh
```

---

## Method 4: Node.js Script (Automated)

### Prerequisites
```bash
npm install sharp
```

### Create `generate-icons.js`:

```javascript
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const sizes = [1024, 180, 167, 152, 120, 87, 80, 76, 60, 58, 40, 29, 20];
const inputSvg = 'icon-template.svg';
const outputDir = './exported';

// Create output directory
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Generate each size
Promise.all(
  sizes.map(size => {
    const outputPath = path.join(outputDir, `icon-${size}.png`);
    console.log(`Generating ${size}x${size}...`);
    
    return sharp(inputSvg)
      .resize(size, size)
      .png()
      .toFile(outputPath);
  })
).then(() => {
  console.log('✓ All icons generated successfully!');
}).catch(err => {
  console.error('Error generating icons:', err);
});
```

### Run Script:
```bash
node generate-icons.js
```

---

## Adding to Xcode Project

### Step 1: Create Asset Catalog

1. **Open Xcode project**
2. **Create/locate Assets.xcassets**:
   ```
   Right-click project navigator → Add Files
   → New File → Asset Catalog
   ```

### Step 2: Create AppIcon Asset

1. **In Assets.xcassets**:
   - Click "+" → App Icons & Launch Images → New iOS App Icon
   - Name it "AppIcon"

2. **Drag and drop icons**:
   - Open exported icons folder
   - Drag each PNG to corresponding slot in Xcode
   - Match sizes:
     - iPhone Notification (20pt): icon-20.png, icon-40.png (2x), icon-60.png (3x)
     - iPhone Settings (29pt): icon-29.png, icon-58.png (2x), icon-87.png (3x)
     - iPhone Spotlight (40pt): icon-40.png, icon-80.png (2x), icon-120.png (3x)
     - iPhone App (60pt): icon-120.png (2x), icon-180.png (3x)
     - iPad Notifications (20pt): icon-20.png, icon-40.png (2x)
     - iPad Settings (29pt): icon-29.png, icon-58.png (2x)
     - iPad Spotlight (40pt): icon-40.png, icon-80.png (2x)
     - iPad App (76pt): icon-76.png, icon-152.png (2x)
     - iPad Pro App (83.5pt): icon-167.png (2x)
     - App Store: icon-1024.png

### Step 3: Configure Project Settings

1. **Select project** in navigator
2. **Select target** (your app)
3. **General tab**
4. **App Icons and Launch Images**:
   - App Icons Source: "AppIcon"

### Step 4: Verify

Run this in Xcode:
```
Product → Clean Build Folder (Cmd + Shift + K)
Product → Build (Cmd + B)
```

Check for warnings about missing icon sizes.

---

## Alternative: Contents.json Method

If you prefer manual setup, create `AppIcon.appiconset/Contents.json`:

```json
{
  "images" : [
    {
      "filename" : "icon-40.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "20x20"
    },
    {
      "filename" : "icon-60.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "20x20"
    },
    {
      "filename" : "icon-58.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "29x29"
    },
    {
      "filename" : "icon-87.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "29x29"
    },
    {
      "filename" : "icon-80.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "40x40"
    },
    {
      "filename" : "icon-120.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "40x40"
    },
    {
      "filename" : "icon-120.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "60x60"
    },
    {
      "filename" : "icon-180.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "60x60"
    },
    {
      "filename" : "icon-20.png",
      "idiom" : "ipad",
      "scale" : "1x",
      "size" : "20x20"
    },
    {
      "filename" : "icon-40.png",
      "idiom" : "ipad",
      "scale" : "2x",
      "size" : "20x20"
    },
    {
      "filename" : "icon-29.png",
      "idiom" : "ipad",
      "scale" : "1x",
      "size" : "29x29"
    },
    {
      "filename" : "icon-58.png",
      "idiom" : "ipad",
      "scale" : "2x",
      "size" : "29x29"
    },
    {
      "filename" : "icon-40.png",
      "idiom" : "ipad",
      "scale" : "1x",
      "size" : "40x40"
    },
    {
      "filename" : "icon-80.png",
      "idiom" : "ipad",
      "scale" : "2x",
      "size" : "40x40"
    },
    {
      "filename" : "icon-76.png",
      "idiom" : "ipad",
      "scale" : "1x",
      "size" : "76x76"
    },
    {
      "filename" : "icon-152.png",
      "idiom" : "ipad",
      "scale" : "2x",
      "size" : "76x76"
    },
    {
      "filename" : "icon-167.png",
      "idiom" : "ipad",
      "scale" : "2x",
      "size" : "83.5x83.5"
    },
    {
      "filename" : "icon-1024.png",
      "idiom" : "ios-marketing",
      "scale" : "1x",
      "size" : "1024x1024"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
```

Place this file and all icon PNGs in `Assets.xcassets/AppIcon.appiconset/`.

---

## Quality Check

Before submitting to App Store:

### Visual Testing
- [ ] Icons look sharp at all sizes
- [ ] No pixelation or blur
- [ ] Colors match specification (#6366F1, #10B981)
- [ ] Design is recognizable at 20x20

### Technical Testing
- [ ] All sizes present in Xcode
- [ ] No Xcode warnings about missing icons
- [ ] Build succeeds without icon-related errors
- [ ] Test on real devices (not just simulator)

### Device Testing
Test on actual devices:
```
iPhone 15 Pro Max (6.7")
iPhone SE (4.7")
iPad Pro 12.9"
iPad Mini
```

View icon:
- On home screen
- In Settings
- In App Library
- In Spotlight search

### App Store Validation
Before upload:
```bash
# Validate icon sizes
xcrun appiconutil --list-sizes AppIcon.appiconset

# Check for validation issues
Product → Archive → Validate App
```

---

## Troubleshooting

### Issue: Icons look blurry

**Solution**:
- Export at exact pixel dimensions (not scaled)
- Use PNG, not JPG
- Ensure "Export at 1x" not using @2x/@3x multipliers

### Issue: Xcode shows warnings

**Solution**:
- Check all required sizes are present
- Verify filenames match Contents.json
- Ensure PNGs are 24-bit RGB (not indexed color)

### Issue: Wrong colors after export

**Solution**:
- Embed sRGB color profile
- Check color mode is RGB (not CMYK)
- Use hex values exactly: #6366F1, #10B981

### Issue: Icon rejected by App Store

**Common reasons**:
- 1024x1024 has transparency (must be opaque)
- Wrong color space
- Contains Apple UI elements
- Too similar to existing Apple icons

**Solution**:
- Remove alpha channel from 1024x1024
- Use solid background
- Ensure unique design

---

## Alternative Formats

### For React Native

If using React Native:
```
ios/
  AppName/
    Images.xcassets/
      AppIcon.appiconset/
        [all PNG files]
        Contents.json
```

### For Flutter

```
flutter pub add flutter_launcher_icons
```

Configure in `pubspec.yaml`:
```yaml
flutter_launcher_icons:
  ios: true
  image_path: "assets/icons/icon-1024.png"
```

Run:
```bash
flutter pub run flutter_launcher_icons
```

---

## Automation Tips

### Git Hook for Auto-Generation

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
if [ -f icon-template.svg ]; then
  npm run generate-icons
  git add exported/*.png
fi
```

### CI/CD Integration

Add to GitHub Actions / GitLab CI:
```yaml
- name: Generate Icons
  run: |
    npm install sharp
    node generate-icons.js
    
- name: Upload Icons
  uses: actions/upload-artifact@v2
  with:
    name: app-icons
    path: exported/
```

---

## Resources

### Official Guidelines
- [Apple Human Interface Guidelines - App Icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- [Xcode Asset Catalog Format Reference](https://developer.apple.com/library/archive/documentation/Xcode/Reference/xcode_ref-Asset_Catalog_Format/)

### Design Tools
- [Figma](https://figma.com) - Free for personal use
- [Sketch](https://sketch.com) - macOS only, paid
- [Adobe Illustrator](https://adobe.com/illustrator) - Paid
- [Inkscape](https://inkscape.org) - Free, open source

### Icon Generators
- [appicon.co](https://www.appicon.co/)
- [makeappicon.com](https://makeappicon.com/)
- [appicon.build](https://www.appicon.build/)

### Testing Tools
- [IconKit](https://apps.apple.com/us/app/iconkit-the-icon-resizer/id507135296) - macOS app
- [Icon Preview](https://apps.apple.com/us/app/icon-preview/id1545766962) - View icons on device mockups

---

## Summary

**Recommended workflow:**

1. ✅ Use provided `icon-template.svg`
2. ✅ Method 1 (Figma) or Method 2 (appicon.co) for generation
3. ✅ Add to Xcode via Assets.xcassets
4. ✅ Test on real devices
5. ✅ Validate before App Store submission

**Time estimate**: 15-30 minutes from SVG to Xcode integration.

---

Need help? Check design specification in `DESIGN_SPECIFICATION.md`.
