# JunkOS Frontend - Quick Setup Guide

## 🚀 Quick Start (5 minutes)

### Step 1: Install Dependencies
```bash
cd ~/Documents/programs/webapps/junkos/frontend
npm install
```

### Step 2: Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your keys
nano .env
```

**Required API Keys:**

1. **Google Maps API Key** (for address autocomplete)
   - Go to: https://console.cloud.google.com/
   - Enable "Places API" and "Maps JavaScript API"
   - Create credentials → API key
   - Add to `.env`: `VITE_GOOGLE_MAPS_API_KEY=your_key_here`

2. **Stripe Public Key** (for payments)
   - Go to: https://dashboard.stripe.com/test/apikeys
   - Copy "Publishable key" (starts with `pk_test_`)
   - Add to `.env`: `VITE_STRIPE_PUBLIC_KEY=pk_test_your_key_here`

3. **Backend API URL**
   - Default: `http://localhost:5000/api`
   - Change if your backend runs elsewhere
   - Add to `.env`: `VITE_API_URL=http://localhost:5000/api`

### Step 3: Update Google Maps in index.html

Edit `index.html` and replace the Google Maps script line with your actual API key:

```html
<!-- Find this line around line 11 -->
<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY&libraries=places" async defer></script>

<!-- Replace YOUR_API_KEY with your actual key -->
<script src="https://maps.googleapis.com/maps/api/js?key=AIza...your-key...&libraries=places" async defer></script>
```

### Step 4: Start Development Server
```bash
npm run dev
```

The app will open at: **http://localhost:3000**

## ✅ Verify Setup

1. **Address Autocomplete**: Type an address in Step 1. Should show dropdown suggestions.
2. **Photo Upload**: Drag & drop or click to upload images in Step 2.
3. **Backend Connection**: Check browser console for API errors.
4. **Stripe**: Test card should work in Step 6: `4242 4242 4242 4242`

## 🔧 Troubleshooting

### "Google is not defined"
- Check Google Maps script is loaded in `index.html`
- Verify API key is valid and has Places API enabled
- Check browser console for specific errors

### Photos won't upload
- Ensure backend is running and `/api/bookings/upload-photos` endpoint exists
- Check file size (max 10MB) and type (JPG, PNG, WebP)
- Look at Network tab in browser DevTools

### Stripe errors
- Verify public key starts with `pk_test_` (for test mode)
- Check Stripe dashboard for API logs
- Ensure backend has matching secret key

### API connection failed
- Make sure Flask backend is running: `python app.py`
- Check `VITE_API_URL` in `.env` matches backend URL
- Verify CORS is enabled on backend
- Test backend directly: `curl http://localhost:5000/api/health`

## 📦 Build for Production

```bash
# Create optimized build
npm run build

# Preview production build locally
npm run preview

# Deploy the dist/ folder to your hosting
```

## 🎨 Customization

### Change Colors
Edit `tailwind.config.js`:
```js
theme: {
  extend: {
    colors: {
      primary: {
        500: '#your-color',
        600: '#your-darker-color',
      }
    }
  }
}
```

### Add Your Logo
1. Replace `public/vite.svg` with your logo
2. Update `index.html` title and favicon
3. Update `Layout.jsx` header section

### Modify Booking Flow
- Add/remove steps in `src/App.jsx`
- Create new step components in `src/components/BookingFlow/`
- Update `totalSteps` in `useBookingForm.js`

## 📱 Testing on Mobile

### Using Your Phone:
1. Find your computer's local IP: `ifconfig | grep inet` (Mac/Linux) or `ipconfig` (Windows)
2. Start dev server: `npm run dev`
3. On your phone, visit: `http://YOUR_IP:3000`
4. Test photo upload with camera

### Using Browser DevTools:
1. Open Chrome DevTools (F12)
2. Click device toggle icon (Ctrl+Shift+M)
3. Select phone model (iPhone, Pixel, etc.)
4. Test responsive layout

## 🚢 Deployment Options

### Vercel (Recommended)
```bash
npm install -g vercel
vercel login
vercel --prod
```

### Netlify
```bash
npm install -g netlify-cli
netlify login
netlify deploy --prod --dir=dist
```

### Traditional Hosting
```bash
npm run build
# Upload dist/ folder to your web host
```

## 📚 Next Steps

1. ✅ Set up backend API (Flask)
2. ✅ Configure Stripe webhook for production
3. ✅ Add real Google Maps API billing
4. ✅ Set up domain and SSL certificate
5. ✅ Configure production environment variables
6. ✅ Test complete booking flow end-to-end

## 🆘 Need Help?

- Check `README.md` for detailed documentation
- Review `src/services/api.js` for API endpoints
- Inspect browser console for errors
- Check backend logs for API issues

---

**Happy coding! 🎉**
