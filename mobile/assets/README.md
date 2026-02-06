# Assets Directory

Place your app assets here:

## Required Files

### Icon
- **File:** `icon.png`
- **Size:** 1024x1024px
- **Format:** PNG
- **Notes:** No transparency, no rounded corners

### Splash Screen
- **File:** `splash.png`
- **Size:** 1284x2778px (portrait)
- **Format:** PNG
- **Notes:** Will be resized to fit all screen sizes

### Adaptive Icon (Android)
- **File:** `adaptive-icon.png`
- **Size:** 1024x1024px
- **Format:** PNG
- **Notes:** For Android adaptive icons

### Favicon
- **File:** `favicon.png`
- **Size:** 48x48px
- **Format:** PNG
- **Notes:** For web version

## Generating Assets

You can generate all required assets from a single 1024x1024px icon using:

```bash
# Using online tools
# - https://appicon.co/
# - https://icon.kitchen/

# Or use Expo's asset generation
npx expo-optimize
```

## Testing Without Assets

The app will work without these files during development, but you'll see warnings. Add them before building for production or TestFlight.
