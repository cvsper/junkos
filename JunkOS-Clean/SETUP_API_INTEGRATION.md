# JunkOS iOS API Integration Setup

## ✅ Completed Tasks

### 1. API Client Infrastructure
- ✅ Created `Config.swift` - Environment configuration (dev/prod)
- ✅ Created `APIModels.swift` - Request/Response models with Codable support
- ✅ Created `APIClient.swift` - Full API service with async/await

### 2. API Endpoints Implemented
- ✅ `GET /api/services` - Load available services
- ✅ `POST /api/quote` - Get price quote
- ✅ `POST /api/bookings` - Create booking
- ✅ `GET /api/bookings/:id` - Get booking details
- ✅ `GET /api/health` - Health check

### 3. ViewModels Updated
- ✅ **ServiceSelectionViewModel** - Loads services from API with fallback
- ✅ **DateTimePickerViewModel** - Fetches quotes from API
- ✅ **ConfirmationViewModel** - Submits bookings to API
- ✅ **PhotoUploadViewModel** - Handles photo selection (upload in booking)

### 4. Network State Handling
- ✅ Loading indicators (`isLoading`, `isLoadingQuote`, `isSubmitting`)
- ✅ Error messages (`errorMessage`, `quoteError`)
- ✅ Success states (`showSuccess`, `bookingResponse`)
- ✅ Haptic feedback for errors and success

## 🔧 Setup Instructions

### Step 1: Add Files to Xcode Project

The files have been created but need to be added to the Xcode project:

1. **Open Xcode:**
   ```bash
   open ~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj
   ```

2. **Add Services folder:**
   - Right-click on `JunkOS` folder in project navigator
   - Select "Add Files to JunkOS..."
   - Navigate to `JunkOS/Services`
   - Select both files:
     - `APIClient.swift`
     - `Config.swift`
   - Check "Copy items if needed" (if not already in project)
   - Click "Add"

3. **Add API Models:**
   - Right-click on `JunkOS/Models` folder
   - Select "Add Files to JunkOS..."
   - Navigate to `JunkOS/Models`
   - Select `APIModels.swift`
   - Click "Add"

**OR** Use the auto-add script:
```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
./add_files_to_xcode.sh
```

### Step 2: Start the Backend

```bash
cd ~/Documents/programs/webapps/junkos/backend
./run.sh
```

The API will start on `http://localhost:8080`

Verify it's running:
```bash
curl http://localhost:8080/api/health
```

### Step 3: Configure API Settings

The iOS app is configured to use `localhost:8080` in development mode.

**For device testing** (not simulator), update `Config.swift`:
```swift
case .development:
    return "http://YOUR_MAC_IP:8080"  // e.g., "http://192.168.1.100:8080"
```

Find your Mac's IP:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### Step 4: Build and Test

1. **Build the project in Xcode:**
   - Select target: `JunkOS`
   - Select simulator: iPhone 15 Pro (or any device)
   - Press `Cmd+B` to build

2. **Run the app:**
   - Press `Cmd+R` or click the Play button

3. **Test the booking flow:**
   - Welcome screen → Continue
   - Enter address
   - Upload photos (optional)
   - Select services (should load from API)
   - Pick date/time (should fetch quote from API)
   - Confirm booking (should submit to API)

## 🧪 Testing Checklist

### API Health Check
```bash
curl -H "X-API-Key: junkos-api-key-12345" http://localhost:8080/api/health
```
Expected: `{"status": "healthy", "service": "JunkOS API"}`

### Services Endpoint
```bash
curl -H "X-API-Key: junkos-api-key-12345" http://localhost:8080/api/services
```
Expected: JSON array of services

### Quote Endpoint
```bash
curl -X POST \
  -H "X-API-Key: junkos-api-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"services": ["furniture", "appliances"], "zip_code": "33139"}' \
  http://localhost:8080/api/quote
```
Expected: Quote with estimated price

### Create Booking
```bash
curl -X POST \
  -H "X-API-Key: junkos-api-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, Miami, FL 33139",
    "zip_code": "33139",
    "services": ["furniture"],
    "photos": [],
    "scheduled_datetime": "2024-02-15 10:00",
    "customer": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890"
    },
    "notes": "Test booking"
  }' \
  http://localhost:8080/api/bookings
```
Expected: Booking confirmation with ID

## 🐛 Troubleshooting

### Issue: "Invalid or missing API key"
**Solution:** Check that the API key in `Config.swift` matches the backend's `.env` file:
- iOS: `junkos-api-key-12345`
- Backend: Check `backend/.env` → `API_KEY=junkos-api-key-12345`

### Issue: Services not loading
**Solution:**
1. Check backend is running: `curl http://localhost:8080/api/health`
2. Check Xcode console for error messages
3. Services will fallback to local hardcoded services if API fails

### Issue: "Connection refused"
**Solution:**
- Make sure backend is running on port 8080
- If testing on device (not simulator), use Mac's IP address instead of localhost
- Check firewall settings if needed

### Issue: App crashes on build
**Solution:**
- Make sure all files are added to Xcode project target
- Clean build folder: `Product → Clean Build Folder` (Cmd+Shift+K)
- Rebuild: `Product → Build` (Cmd+B)

## 📁 File Structure

```
JunkOS-Clean/
├── JunkOS/
│   ├── Services/          # NEW
│   │   ├── APIClient.swift      # Main API client
│   │   └── Config.swift         # Environment configuration
│   ├── Models/
│   │   ├── APIModels.swift      # NEW - API request/response models
│   │   └── BookingModels.swift  # Existing local models
│   └── ViewModels/
│       ├── ServiceSelectionViewModel.swift  # UPDATED
│       ├── DateTimePickerViewModel.swift    # UPDATED
│       └── ConfirmationViewModel.swift      # UPDATED
```

## 🔄 API Flow

1. **App Launch** → ServiceSelectionViewModel loads services from API
2. **Service Selection** → User selects services
3. **Date/Time Selection** → DateTimePickerViewModel fetches quote from API
4. **Confirmation** → ConfirmationViewModel submits booking to API
5. **Success** → Display booking confirmation

## 🚀 Next Steps

### Improvements to consider:
- [ ] Add proper loading spinners in UI
- [ ] Add retry logic for failed requests
- [ ] Implement proper keychain storage for API keys
- [ ] Add offline mode detection
- [ ] Cache services data
- [ ] Add booking history view
- [ ] Implement push notifications for booking updates
- [ ] Add photo compression before upload
- [ ] Implement multipart/form-data for photo uploads

## 📝 Notes

- **Environment:** Development mode uses `localhost:8080`
- **API Key:** Hardcoded for dev, should use secure storage in production
- **Error Handling:** All API errors fall back to local data where possible
- **Async/Await:** All API calls use modern Swift concurrency
- **Thread Safety:** All UI updates happen on MainActor

## 🆘 Need Help?

Check the Xcode console for detailed error messages during API calls. The APIClient logs all decoding errors with response data.
