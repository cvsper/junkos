# JunkOS Mobile - Project Structure

Complete directory layout for the React Native booking app.

## Root Directory

```
junkos/mobile/
├── app/                      # Expo Router app directory
│   ├── _layout.tsx          # Root navigation layout
│   ├── index.tsx            # Welcome/Login screen (Screen 1)
│   └── screens/             # Feature screens
│       ├── address.tsx      # Address input (Screen 2)
│       ├── photos.tsx       # Photo upload (Screen 3)
│       ├── service.tsx      # Service details (Screen 4)
│       ├── datetime.tsx     # Date/time picker (Screen 5)
│       └── confirmation.tsx # Booking review (Screen 6)
│
├── components/              # Reusable UI components
│   ├── Button.tsx          # Custom button component
│   └── Input.tsx           # Custom input component
│
├── utils/                   # Utility functions
│   ├── api.ts              # API client & authentication
│   └── storage.ts          # AsyncStorage helpers & types
│
├── assets/                  # Static assets
│   ├── icon.png            # App icon (1024x1024)
│   ├── splash.png          # Splash screen (1284x2778)
│   ├── adaptive-icon.png   # Android icon
│   ├── favicon.png         # Web favicon
│   └── README.md           # Asset generation guide
│
├── app.json                 # Expo configuration
├── package.json             # Dependencies & scripts
├── tsconfig.json            # TypeScript configuration
├── tailwind.config.js       # NativeWind/Tailwind config
├── babel.config.js          # Babel configuration
├── global.css               # Global styles (NativeWind)
├── .gitignore              # Git ignore rules
│
├── README.md               # Setup & development guide
├── APP_STORE_CHECKLIST.md  # Deployment checklist
└── PROJECT_STRUCTURE.md    # This file
```

## Screen Flow

```
1. index.tsx (Welcome/Login)
   ↓ (after authentication)
2. screens/address.tsx (Address Input)
   ↓
3. screens/photos.tsx (Photo Upload)
   ↓
4. screens/service.tsx (Service Details)
   ↓
5. screens/datetime.tsx (Date/Time Selection)
   ↓
6. screens/confirmation.tsx (Review & Confirm)
   ↓
   [Submit to Backend] → Success → Return to index.tsx
```

## Key Files Explained

### Configuration Files

**app.json**
- Expo project configuration
- iOS bundle identifier: `com.junkos.booking`
- Camera & photo library permissions
- Splash screen & icon settings

**package.json**
- Dependencies: Expo Router, NativeWind, expo-image-picker, AsyncStorage
- Scripts: start, ios, android, web

**tsconfig.json**
- TypeScript configuration with path aliases
- Extends expo/tsconfig.base

**tailwind.config.js**
- iOS-native color palette (Human Interface Guidelines)
- Custom Tailwind classes for native components

**babel.config.js**
- NativeWind babel plugin
- React Native Reanimated plugin

### App Directory (Expo Router)

**app/_layout.tsx**
- Root navigation stack
- Header styling (iOS-native blue)
- Screen configurations

**app/index.tsx**
- Login/authentication screen
- JWT token storage
- Navigates to address screen on success

**app/screens/*.tsx**
- Each screen is self-contained
- Uses AsyncStorage for draft persistence
- iOS-native styling throughout

### Utilities

**utils/api.ts**
- REST API client wrapper
- JWT authentication handling
- Endpoints: login, createBooking, uploadPhoto
- Error handling & response typing

**utils/storage.ts**
- AsyncStorage wrapper
- BookingData interface
- Draft management functions
- Auth token helpers

### Components

**components/Button.tsx**
- Reusable button with variants
- Loading state support
- iOS-native styling

**components/Input.tsx**
- Reusable text input
- Error state support
- Label & validation display

## Data Flow

### Booking Draft (Persisted)

```typescript
interface BookingData {
  address?: string;           // "123 Main|SF|CA|94102"
  photos?: string[];          // ["file:///...", "file:///..."]
  serviceType?: string;       // "furniture"
  serviceDetails?: string;    // "2 sofas, 1 mattress"
  scheduledDate?: string;     // "2024-03-15"
  scheduledTime?: string;     // "10:00 AM - 12:00 PM"
}
```

Saved to AsyncStorage at key: `booking_draft`

### Authentication

JWT token stored at: `auth_token`
- Set on login success
- Included in all authenticated API requests
- Removed on logout

## Backend Integration

### Expected Endpoints

```
POST /auth/login
  Body: { email, password }
  Response: { token, user }

POST /upload
  Headers: { Authorization: "Bearer <token>" }
  Body: FormData with 'photo' field
  Response: { url }

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
  Response: { id, ... }
```

## Development Workflow

1. **Start dev server:** `npm start`
2. **Open iOS:** Press `i` or `npm run ios`
3. **Open Android:** Press `a` or `npm run android`
4. **Clear cache:** `npx expo start -c`
5. **Debug:** Shake device → Developer Menu

## Build & Deploy

1. **Configure EAS:** `eas build:configure`
2. **Build iOS:** `eas build --platform ios`
3. **Submit:** `eas submit --platform ios`

See APP_STORE_CHECKLIST.md for complete deployment guide.

## Environment-Specific Config

### Local Development
```typescript
const API_URL = 'http://localhost:5000';
```

### Physical Device Testing
```typescript
const API_URL = 'http://192.168.1.100:5000'; // Your computer's IP
```

### Production
```typescript
const API_URL = 'https://api.junkos.com';
```

Update in `utils/api.ts` or use environment variables.

## iOS Human Interface Guidelines Compliance

✅ Native navigation patterns
✅ SF Pro Text font (system default)
✅ iOS color palette (primary blue: #007AFF)
✅ Rounded corners (12px standard)
✅ Proper spacing (multiples of 4)
✅ Touch targets (44x44pt minimum)
✅ Native keyboard handling
✅ Safe area awareness

## Testing Checklist

- [ ] Login works with test credentials
- [ ] Address validation accepts valid addresses
- [ ] Camera permission requested properly
- [ ] Photos display after selection
- [ ] Gallery picker works
- [ ] Photo removal works
- [ ] Service type selection persists
- [ ] Date picker shows correct dates
- [ ] Time slots are selectable
- [ ] Confirmation shows all data correctly
- [ ] Booking submission succeeds
- [ ] Draft clears after submission
- [ ] Logout works
- [ ] App works offline (shows error)
- [ ] Back navigation preserves data

## Common Issues

### Metro Bundler Cache
```bash
npx expo start -c
```

### Node Modules
```bash
rm -rf node_modules
npm install
```

### iOS Pods (if using bare workflow)
```bash
cd ios && pod install
```

### Permissions Not Working
- Restart Expo after changing app.json
- Check infoPlist in app.json
- On simulator, accept all permissions

## Next Steps

1. Add app icon & splash screen to assets/
2. Configure backend API URL for your environment
3. Test complete booking flow
4. Add error boundaries
5. Implement analytics (Firebase/Sentry)
6. Add push notifications (expo-notifications)
7. Optimize images (expo-optimize)
8. Build for TestFlight

---

**Built with:** Expo SDK 51, React Native 0.74, TypeScript, NativeWind
**Bundle ID:** com.junkos.booking
**Target:** iOS 13+
