# Umuve Mobile - React Native Booking App

A production-ready React Native booking app for Umuve junk removal service, built with Expo.

## Features

✅ **6-Screen Booking Flow**
- Welcome/Login screen with JWT authentication
- Address input with validation
- Photo upload (camera + gallery)
- Service type selection
- Date/time picker
- Booking confirmation

✅ **Native Features**
- Camera access (expo-image-picker)
- Photo library access
- Persistent storage (AsyncStorage)
- iOS Human Interface Guidelines styling

✅ **Backend Integration**
- Flask backend (http://localhost:5000)
- JWT authentication
- Photo upload
- Booking creation

## Tech Stack

- **Framework:** React Native + Expo
- **Navigation:** Expo Router
- **Styling:** NativeWind (Tailwind CSS)
- **Language:** TypeScript
- **Storage:** AsyncStorage
- **Camera:** expo-image-picker

## Prerequisites

- Node.js 18+
- npm or yarn
- iOS Simulator (Xcode) or physical iOS device
- Flask backend running on http://localhost:5000

## Installation

1. **Install dependencies:**
   ```bash
   cd ~/Documents/programs/webapps/junkos/mobile
   npm install
   ```

2. **Start the Expo development server:**
   ```bash
   npm start
   ```

3. **Run on iOS:**
   ```bash
   npm run ios
   ```

4. **Run on Android:**
   ```bash
   npm run android
   ```

## Project Structure

```
mobile/
├── app/
│   ├── _layout.tsx          # Root layout with navigation
│   ├── index.tsx            # Welcome/Login screen
│   └── screens/
│       ├── address.tsx      # Address input
│       ├── photos.tsx       # Photo upload
│       ├── service.tsx      # Service details
│       ├── datetime.tsx     # Date/time picker
│       └── confirmation.tsx # Booking review
├── utils/
│   ├── api.ts              # API client & JWT auth
│   └── storage.ts          # AsyncStorage helpers
├── app.json                # Expo configuration
├── package.json            # Dependencies
└── tailwind.config.js      # NativeWind styling
```

## Backend API Requirements

The app expects the following Flask endpoints:

### Authentication
```
POST /auth/login
Body: { email: string, password: string }
Response: { token: string, user: object }
```

### Photo Upload
```
POST /upload
Headers: { Authorization: "Bearer <token>" }
Body: FormData with 'photo' field
Response: { url: string }
```

### Create Booking
```
POST /bookings
Headers: { Authorization: "Bearer <token>" }
Body: {
  address: string,
  serviceType: string,
  serviceDetails: string,
  scheduledDate: string,
  scheduledTime: string,
  photos: string[]
}
Response: { id: string, ... }
```

## Configuration

### Bundle Identifier
Set in `app.json`:
```json
{
  "expo": {
    "ios": {
      "bundleIdentifier": "com.goumuve.app"
    }
  }
}
```

### API URL
Edit `utils/api.ts` to change backend URL:
```typescript
const API_URL = 'http://localhost:5000';
```

For physical device testing, replace with your computer's local IP:
```typescript
const API_URL = 'http://192.168.1.100:5000';
```

## Development

### Testing Authentication
Use test credentials (configure in your Flask backend):
```
Email: test@goumuve.com
Password: password123
```

### Debugging
- Press `j` in terminal to open debugger
- Shake device to open developer menu
- View logs in terminal

### Clear Booking Draft
Booking data is saved to AsyncStorage. To reset:
```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
await AsyncStorage.removeItem('booking_draft');
```

## Building for TestFlight

See `APP_STORE_CHECKLIST.md` for complete deployment instructions.

Quick build:
```bash
# Install EAS CLI
npm install -g eas-cli

# Configure project
eas build:configure

# Build for iOS
eas build --platform ios
```

## Troubleshooting

### Camera Not Working
- Check permissions in `app.json`
- Restart Expo after adding permissions
- On simulator, camera returns mock images

### Backend Connection Failed
- Ensure Flask backend is running
- Check API_URL matches your backend
- For physical devices, use local IP instead of localhost

### Navigation Issues
- Clear Metro bundler cache: `npx expo start -c`
- Delete `node_modules` and reinstall

## Environment Variables

For production, use Expo's environment variables:

```bash
# .env.production
API_URL=https://api.goumuve.com
```

Access in code:
```typescript
import Constants from 'expo-constants';
const API_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:5000';
```

## License

Proprietary - Umuve

## Support

For issues or questions, contact the development team.
