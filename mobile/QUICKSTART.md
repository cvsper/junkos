# Quick Start Guide

Get the JunkOS Booking app running in under 5 minutes.

## Prerequisites Check

```bash
# Check Node.js (need 18+)
node --version

# Check npm
npm --version
```

Don't have Node? Install from https://nodejs.org/

## Installation

```bash
# Navigate to project
cd ~/Documents/programs/webapps/junkos/mobile

# Install dependencies (takes 2-3 minutes)
npm install

# Start Expo dev server
npm start
```

## Run on Device/Simulator

### iOS Simulator (Mac only)

1. Install Xcode from App Store (if not already installed)
2. In terminal where `npm start` is running, press **`i`**
3. App will launch in iOS Simulator

### Physical iOS Device

1. Install **Expo Go** from App Store on your iPhone
2. Scan QR code shown in terminal
3. App will open in Expo Go

### Android

```bash
# Press 'a' in terminal
npm run android
```

Or install **Expo Go** from Google Play and scan QR code.

## Test Login

Use these test credentials (configure in your Flask backend):

```
Email: test@junkos.com
Password: password123
```

## Backend Setup

The app expects a Flask backend at `http://localhost:5000`.

If your backend is on a different URL, edit `utils/api.ts`:

```typescript
const API_URL = 'http://YOUR_BACKEND_URL';
```

**For testing on physical device:**
1. Find your computer's IP: `ifconfig` (look for 192.168.x.x)
2. Update API_URL to `http://192.168.1.100:5000` (your IP)
3. Ensure Flask backend allows connections from your network

## Common First-Run Issues

### "Metro bundler failed to start"
```bash
npx expo start -c
```

### "Cannot find module"
```bash
rm -rf node_modules
npm install
```

### "Command not found: expo"
```bash
npm install -g expo-cli
```

### Camera not working in simulator
- Normal! Simulator uses mock images
- Test on physical device for real camera

### Backend connection failed
- Check Flask backend is running: `curl http://localhost:5000`
- For physical device, use your computer's IP instead of localhost
- Check firewall settings

## Development Commands

```bash
# Start dev server
npm start

# Start with cache cleared
npx expo start -c

# Open iOS simulator
npm run ios

# Open Android emulator
npm run android

# Open in web browser
npm run web

# Check for issues
npx expo doctor
```

## Keyboard Shortcuts (in terminal)

- **i** - Open iOS simulator
- **a** - Open Android emulator
- **w** - Open web browser
- **r** - Reload app
- **m** - Toggle menu
- **j** - Open debugger
- **c** - Clear Metro bundler cache

## Testing the Full Flow

1. **Login:** Enter test credentials
2. **Address:** Fill in any valid US address
3. **Photos:** Take/select at least 1 photo
4. **Service:** Select a service type (e.g., Furniture)
5. **Date/Time:** Choose available date & time
6. **Confirm:** Review and submit

Data is saved between screens, so you can close and reopen the app.

## Where to Go Next

- **Having issues?** Check README.md
- **Ready to deploy?** See APP_STORE_CHECKLIST.md
- **Understanding the code?** See PROJECT_STRUCTURE.md
- **Customizing?** Edit screens in `app/screens/`

## Project Structure (Quick Reference)

```
app/
├── _layout.tsx          # Navigation setup
├── index.tsx            # Login screen
└── screens/
    ├── address.tsx      # Address input
    ├── photos.tsx       # Photo upload
    ├── service.tsx      # Service selection
    ├── datetime.tsx     # Scheduling
    └── confirmation.tsx # Review & submit

utils/
├── api.ts              # Backend API calls
└── storage.ts          # Local data storage

components/
├── Button.tsx          # Reusable button
└── Input.tsx           # Reusable input
```

## Get Help

1. Check terminal for error messages
2. Open React Native Debugger (press **j**)
3. Shake device to open developer menu
4. Look at Metro bundler output

## Success!

If you see the login screen with "JunkOS" title, you're all set! 🎉

Now try:
1. Logging in with test credentials
2. Completing a booking flow
3. Checking that data persists between screens

---

**Quick tip:** Keep the terminal open where you ran `npm start` - that's your development server. Don't close it while developing!
