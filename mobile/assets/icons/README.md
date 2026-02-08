# JunkOS iOS App Icon Assets

Complete icon package for JunkOS iOS app with design specs, generation tools, and implementation guides.

## 📦 Package Contents

```
icons/
├── README.md                      ← You are here
├── icon-template.svg              ← Editable SVG source file
├── DESIGN_SPECIFICATION.md        ← Complete design documentation
├── icon-generation-guide.md       ← How to generate all sizes
├── splash-screen-spec.md          ← Launch screen requirements
├── generate-icons.sh              ← Bash script for icon generation
└── generate-icons.js              ← Node.js script for icon generation
```

## 🚀 Quick Start

### Option 1: Use Online Tool (Fastest - 5 minutes)

1. Generate 1024x1024 PNG from SVG:
   ```bash
   # Install ImageMagick if needed
   brew install imagemagick
   
   # Generate base icon
   magick icon-template.svg -resize 1024x1024 icon-1024.png
   ```

2. Upload to [appicon.co](https://www.appicon.co/)
3. Download and extract iOS icons
4. Add to Xcode Assets.xcassets

### Option 2: Generate Locally with Script (10 minutes)

```bash
# Make script executable
chmod +x generate-icons.sh

# Run generation (requires ImageMagick)
./generate-icons.sh

# Icons will be in ./exported/ folder
```

### Option 3: Use Node.js Script (10 minutes)

```bash
# Install dependencies
npm install sharp

# Generate all sizes
node generate-icons.js

# Icons will be in ./exported/ folder
```

## 📋 What You Get

### All Required iOS Sizes
- ✅ 1024x1024 (App Store)
- ✅ 180x180 (iPhone @3x)
- ✅ 167x167 (iPad Pro)
- ✅ 152x152 (iPad @2x)
- ✅ 120x120 (iPhone @2x)
- ✅ 87x87 (iPhone @3x settings)
- ✅ 80x80 (iPad @2x settings)
- ✅ 76x76 (iPad)
- ✅ 60x60 (iPhone)
- ✅ 58x58 (iPhone settings)
- ✅ 40x40 (Spotlight)
- ✅ 29x29 (Settings)
- ✅ 20x20 (Notification)

## 🎨 Design Details

**Icon Concept**: Modern trash bin with upward arrow (removal/cleanup)

**Colors**:
- Primary: Indigo `#6366F1`
- Accent: Emerald `#10B981`
- Background: White elements on gradient

**Style**: Clean, iOS HIG compliant, recognizable at all sizes

👉 See `DESIGN_SPECIFICATION.md` for complete details

## 📝 Documentation

| File | Purpose |
|------|---------|
| `DESIGN_SPECIFICATION.md` | Complete design concept, colors, rationale |
| `icon-generation-guide.md` | Step-by-step generation in Figma/Sketch/CLI |
| `splash-screen-spec.md` | Launch screen design and implementation |
| `icon-template.svg` | Source vector file (editable) |

## 🛠️ Editing the Icon

The SVG template can be edited in:
- **Figma** (recommended, free)
- **Adobe Illustrator** (paid)
- **Sketch** (macOS, paid)
- **Inkscape** (free, open-source)

Make changes to `icon-template.svg`, then regenerate all sizes.

## ✅ Adding to Xcode

1. **Open Xcode project**
2. **Navigate to Assets.xcassets**
3. **Create AppIcon** (if not exists):
   - Click "+" → App Icons & Launch Images → New iOS App Icon
4. **Drag and drop** generated PNGs to appropriate slots
5. **Build and test**

Detailed instructions in `icon-generation-guide.md` (search for "Adding to Xcode").

## 🎯 Launch Screen

To create launch screen:
1. Read `splash-screen-spec.md`
2. Create `LaunchScreen.storyboard` in Xcode
3. Add app icon image (160pt) + "JunkOS" text
4. Use same gradient background

Time estimate: 20-40 minutes

## 🔍 Quality Checklist

Before submitting to App Store:

- [ ] All 13 icon sizes generated
- [ ] Icons look sharp on devices (not blurry)
- [ ] Colors match spec (#6366F1, #10B981)
- [ ] Icon recognizable at 20x20px
- [ ] No Xcode warnings about missing icons
- [ ] Tested on iPhone and iPad
- [ ] Launch screen matches icon design
- [ ] App Store icon (1024x1024) is opaque

## 📊 File Sizes

Expected PNG file sizes:
- 1024x1024: ~40-60KB
- 180x180: ~8-12KB
- Smaller sizes: 2-8KB each

Total package: ~100-150KB

## 🐛 Troubleshooting

**Icons look blurry?**
→ Ensure exporting at exact pixel sizes (not scaled)

**Xcode shows warnings?**
→ Check all 13 sizes are present and named correctly

**Wrong colors?**
→ Use sRGB color profile, verify hex values

**App Store rejection?**
→ Ensure 1024x1024 has no transparency (alpha channel)

See `icon-generation-guide.md` "Troubleshooting" section for more.

## 🔗 Resources

- [Apple Human Interface Guidelines - App Icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- [appicon.co](https://www.appicon.co/) - Online icon generator
- [makeappicon.com](https://makeappicon.com/) - Alternative generator

## 📞 Need Help?

1. Check documentation files in this folder
2. Verify SVG renders correctly in design tool
3. Test icon generation with one of the scripts
4. Review Xcode console for specific errors

## 📈 Version

**v1.0** (2026-02-06)
- Initial icon design
- Complete documentation
- Generation scripts
- Launch screen specs

---

**Ready to generate icons?** Run `./generate-icons.sh` or follow Quick Start guide above. 🚀
