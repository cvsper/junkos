# Fonts Setup

## Required Fonts

### Poppins (Headings)
Download from: https://fonts.google.com/specimen/Poppins

**Required weights:**
- Regular (400)
- Medium (500)
- SemiBold (600)
- Bold (700)

**Files needed:**
- `Poppins-Regular.ttf`
- `Poppins-Medium.ttf`
- `Poppins-SemiBold.ttf`
- `Poppins-Bold.ttf`

### Open Sans (Body Text)
Download from: https://fonts.google.com/specimen/Open+Sans

**Required weights:**
- Regular (400)
- SemiBold (600)

**Files needed:**
- `OpenSans-Regular.ttf`
- `OpenSans-SemiBold.ttf`

## Installation

1. Visit the Google Fonts links above
2. Click "Download family"
3. Extract the zip files
4. Copy the `.ttf` files listed above to this directory
5. Restart the Expo development server

## Quick Download

```bash
# From mobile/ directory
cd assets/fonts

# Download Poppins
curl -L "https://fonts.google.com/download?family=Poppins" -o poppins.zip
unzip poppins.zip
mv Poppins-Regular.ttf Poppins-Medium.ttf Poppins-SemiBold.ttf Poppins-Bold.ttf .
rm poppins.zip

# Download Open Sans
curl -L "https://fonts.google.com/download?family=Open%20Sans" -o opensans.zip
unzip opensans.zip
mv OpenSans-Regular.ttf OpenSans-SemiBold.ttf .
rm opensans.zip
```

## Verification

After adding fonts, verify they load:

```bash
# Start Expo
npm start

# If fonts don't load, clear cache
expo start --clear
```

Font loading happens in `App.tsx` using `useFonts()` hook.
