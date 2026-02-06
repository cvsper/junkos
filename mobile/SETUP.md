# Quick Setup Guide

Get JunkOS mobile app running in 10 minutes.

## ⚡ Prerequisites

Install these first:

```bash
# Node.js 18+ (check version)
node --version  # Should be v18.0.0 or higher

# Install Expo CLI globally
npm install -g expo-cli

# Verify Expo
expo --version
```

## 📲 iOS Requirements

**For iOS Simulator:**
- macOS required
- Xcode 14+ from Mac App Store
- Command Line Tools: `xcode-select --install`

**For Physical iPhone:**
- iPhone with iOS 13+
- Expo Go app from App Store

## 🚀 Installation

### 1. Navigate to Project

```bash
cd ~/Documents/programs/webapps/junkos/mobile
```

### 2. Install Dependencies

```bash
npm install
```

This installs ~150MB of packages. Takes 2-3 minutes.

### 3. Download Fonts

**Option A: Manual (Recommended)**

1. Download [Poppins](https://fonts.google.com/specimen/Poppins)
2. Download [Open Sans](https://fonts.google.com/specimen/Open+Sans)
3. Extract and copy these files to `assets/fonts/`:
   - `Poppins-Regular.ttf`
   - `Poppins-Medium.ttf`
   - `Poppins-SemiBold.ttf`
   - `Poppins-Bold.ttf`
   - `OpenSans-Regular.ttf`
   - `OpenSans-SemiBold.ttf`

**Option B: Command Line**

```bash
cd assets/fonts
curl -L "https://fonts.google.com/download?family=Poppins" -o poppins.zip
curl -L "https://fonts.google.com/download?family=Open%20Sans" -o opensans.zip
unzip poppins.zip && unzip opensans.zip
rm *.zip
cd ../..
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
API_BASE_URL=http://localhost:5000
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
```

**Get test Stripe key:**
1. Sign up at [stripe.com](https://stripe.com)
2. Go to Developers → API Keys
3. Copy "Publishable key" (starts with `pk_test_`)

### 5. Start Backend (Optional)

If you have the backend running:

```bash
# In another terminal
cd ~/Documents/programs/webapps/junkos/backend
python app.py
```

Backend should be at http://localhost:5000

### 6. Start App

```bash
npm start
```

You'll see:

```
› Metro waiting on exp://192.168.1.X:8081
› Scan the QR code above with Expo Go (iOS)
```

### 7. Open on Device

**iOS Simulator:**
- Press `i` in the terminal
- Simulator opens automatically

**Physical iPhone:**
1. Install Expo Go from App Store
2. Open Camera app
3. Scan QR code from terminal
4. App opens in Expo Go

## 🎨 Create App Icons (Optional)

For development, Expo uses default icons. For production:

```bash
# Create basic placeholder icon
cd assets
# Use any image editor to create 1024x1024 PNG
# Background: #6366F1, add text "J" or truck emoji
# Save as icon.png
```

Or use [AppIcon.co](https://appicon.co) to generate all sizes.

## ✅ Verify Setup

Test these features:

1. **App Launches** - Welcome screen appears
2. **Navigation** - Tap "Get Started"
3. **Login Screen** - Form fields appear
4. **Create Account** - Try registering (requires backend)

## 🐛 Troubleshooting

### "Unable to resolve module"

```bash
# Clear cache and reinstall
rm -rf node_modules
npm install
expo start --clear
```

### "No matching font found"

- Verify fonts are in `assets/fonts/`
- Check filenames match exactly (case-sensitive)
- Restart Expo: `expo start --clear`

### "Network request failed"

- Ensure backend is running at `API_BASE_URL`
- Check `.env` file exists and is configured
- Try `http://localhost:5000` or your machine's IP

### iOS Simulator not opening

```bash
# Install iOS Simulator
xcode-select --install

# Open Simulator manually
open -a Simulator

# Then press 'i' in Expo terminal
```

### "Unable to connect to Metro"

```bash
# Reset Metro bundler
expo start --clear

# Or kill process and restart
pkill -f "expo" && expo start
```

### Camera/Location not working

- Simulator: Limited functionality (use physical device)
- Device: Tap "Allow" when permission prompts appear
- Settings: Enable permissions in iOS Settings if denied

## 📱 Development Workflow

### Hot Reload

Changes auto-reload. No need to restart unless:
- Adding new dependencies
- Changing `app.json`
- Adding new fonts

### Test User Account

Create in backend:

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Password123!",
    "firstName": "Test",
    "lastName": "User"
  }'
```

### Test Stripe Payment

Use test card:
- **Card**: 4242 4242 4242 4242
- **Expiry**: Any future date
- **CVC**: Any 3 digits

## 🔄 Daily Development

```bash
# Start backend (terminal 1)
cd ~/Documents/programs/webapps/junkos/backend
python app.py

# Start mobile app (terminal 2)
cd ~/Documents/programs/webapps/junkos/mobile
npm start
```

Press `i` to open iOS simulator or scan QR with phone.

## 📚 Next Steps

- [ ] Read [README.md](./README.md) for full documentation
- [ ] Review [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md) for styling
- [ ] Check [CONTRIBUTING.md](./CONTRIBUTING.md) for code guidelines
- [ ] Explore code in `src/screens/` and `src/api/`

## 🆘 Still Having Issues?

1. Verify Node.js version: `node --version` (must be 18+)
2. Update Expo: `npm install -g expo-cli@latest`
3. Check [Expo troubleshooting](https://docs.expo.dev/troubleshooting/overview/)
4. Ask in Expo forum: [forums.expo.dev](https://forums.expo.dev)

---

**Setup time**: ~10 minutes (excluding font downloads)

**Happy coding! 🚀**
