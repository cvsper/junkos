# JunkOS Frontend - Quick Reference

## 🚀 Get Started (Copy & Paste)

```bash
# 1. Navigate to project
cd ~/Documents/programs/webapps/junkos/frontend

# 2. Install dependencies
npm install

# 3. Create environment file
cp .env.example .env

# 4. Edit environment variables (add your keys)
nano .env

# 5. Start development server
npm run dev

# Now open http://localhost:3000 in your browser
```

## 🔑 Required API Keys

1. **Google Maps API Key**
   - Get from: https://console.cloud.google.com/
   - Enable: Places API + Maps JavaScript API
   - Add to `.env`: `VITE_GOOGLE_MAPS_API_KEY=your_key`
   - Also update in `index.html` line 11

2. **Stripe Public Key**
   - Get from: https://dashboard.stripe.com/test/apikeys
   - Copy "Publishable key" (starts with `pk_test_`)
   - Add to `.env`: `VITE_STRIPE_PUBLIC_KEY=pk_test_your_key`

3. **Backend API URL**
   - Default: `http://localhost:5000/api`
   - Add to `.env`: `VITE_API_URL=http://localhost:5000/api`

## 📱 Test on Phone

```bash
# Find your IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Start server
npm run dev

# On phone, visit:
# http://YOUR_IP:3000
```

## 🧪 Test Stripe Payment

Use test card: **4242 4242 4242 4242**
- Any future expiry date
- Any 3-digit CVC
- Any ZIP code

## 🏗️ Project Structure

```
src/
├── App.jsx              # Main app, renders current step
├── main.jsx             # Entry point
├── index.css            # Global styles
├── components/
│   ├── Layout.jsx       # Header + Footer wrapper
│   ├── ProgressBar.jsx  # Step indicator
│   └── BookingFlow/     # 6 step components
├── hooks/
│   └── useBookingForm.js  # Form state management
├── services/
│   └── api.js           # API client (Axios)
└── utils/
    └── validation.js    # Form validators
```

## 🎨 Key Components

| Component | Purpose | Props |
|-----------|---------|-------|
| App.jsx | Main orchestrator | - |
| ProgressBar | Shows booking progress | currentStep, onStepClick |
| Step1Address | Address input | formData, updateFormData, nextStep, ... |
| Step2Photos | Photo upload | formData, updateFormData, nextStep, prevStep, ... |
| Step3Items | Item details | formData, updateFormData, nextStep, prevStep, ... |
| Step4DateTime | Schedule picker | formData, updateFormData, nextStep, prevStep, ... |
| Step5Estimate | Price review | formData, updateFormData, nextStep, prevStep, ... |
| Step6Payment | Payment + Success | formData, updateCustomerInfo, prevStep, resetForm, ... |

## 🔧 Common Tasks

### Change Colors
Edit `tailwind.config.js`:
```js
colors: {
  primary: { 500: '#0ea5e9', 600: '#0284c7' },  // Blue
  accent: { 500: '#f59e0b', 600: '#d97706' },   // Amber
}
```

### Add Form Field
1. Add to `formData` in `useBookingForm.js`
2. Add input in step component
3. Add validation in `utils/validation.js`
4. Update API call in `services/api.js`

### Debug API Calls
Open browser console and check:
- Network tab for requests/responses
- Console tab for errors
- Look for red error messages

### Fix Linting Errors
```bash
npm run lint
```

## 📊 File Sizes

| File | Lines | Purpose |
|------|-------|---------|
| Step1Address.jsx | 201 | Address input with Google Maps |
| Step2Photos.jsx | 268 | Drag & drop photo upload |
| Step3Items.jsx | 329 | Item description form |
| Step4DateTime.jsx | 327 | Calendar + time slots |
| Step5Estimate.jsx | 392 | Price breakdown display |
| Step6Payment.jsx | 455 | Stripe payment + success |
| App.jsx | 218 | Main app component |
| api.js | 125 | Backend API integration |
| validation.js | 125 | Form validation utils |

**Total: ~2,500 lines** (excluding node_modules)

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Google Maps not loading | Check API key in both `.env` AND `index.html` |
| Photos won't upload | Backend must be running. Check CORS enabled. |
| Stripe payment fails | Verify `pk_test_` key. Use test card 4242... |
| "Cannot connect to API" | Start backend: `python app.py` (in backend folder) |
| Styles not loading | Run `npm install` again. Clear cache. |
| Build fails | Delete `node_modules/`, run `npm install` |

## 🌐 API Endpoints

```
POST   /api/bookings/validate-address      # Verify address
POST   /api/bookings/upload-photos         # Upload images
POST   /api/bookings/estimate              # Calculate price
GET    /api/bookings/available-slots       # Check availability
POST   /api/bookings                       # Create booking
POST   /api/payments/create-intent         # Init payment
POST   /api/payments/confirm               # Confirm payment
```

See `src/services/api.js` for full details.

## 🚢 Deploy

### Vercel (Easiest)
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

### Manual
```bash
npm run build
# Upload dist/ folder to your hosting
```

## 📚 Documentation Files

- **README.md** - Full technical documentation
- **SETUP.md** - Step-by-step setup guide
- **PROJECT_SUMMARY.md** - Comprehensive project overview
- **QUICK_REF.md** - This cheat sheet

## ⚡ Useful Commands

```bash
npm run dev              # Start dev server
npm run build            # Build for production
npm run preview          # Preview production build
npm run lint             # Check code quality

# Clear cache if things break
rm -rf node_modules dist .vite
npm install
npm run dev
```

## 🎯 Testing Checklist

- [ ] Address autocomplete works
- [ ] Photos upload (try drag & drop)
- [ ] All 6 steps complete successfully
- [ ] Stripe test payment works
- [ ] Success page displays booking ID
- [ ] Looks good on mobile (test on phone)
- [ ] Error messages show properly
- [ ] Back button navigation works

## 💡 Pro Tips

1. **Use browser DevTools**: F12 → Console & Network tabs
2. **Test mobile-first**: Ctrl+Shift+M in Chrome
3. **Check backend logs**: If frontend fails, backend might have errors
4. **Use React DevTools**: Install Chrome extension for debugging
5. **Read error messages**: They usually tell you exactly what's wrong

## 🎓 Learn More

- React: https://react.dev
- Vite: https://vitejs.dev
- Tailwind: https://tailwindcss.com
- Stripe: https://stripe.com/docs/stripe-js/react
- Google Maps: https://developers.google.com/maps/documentation/javascript

---

**Need help?** Check the detailed README.md or SETUP.md files.
