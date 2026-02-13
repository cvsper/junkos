# Quick Setup Guide

## First-Time Setup

Follow these steps to get the Umuve Dashboard running:

### 1. Install Dependencies

```bash
cd ~/Documents/programs/webapps/junkos/dashboard
npm install
```

This will install all required packages (may take 2-3 minutes).

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and update these values:

```env
# Point to your Flask backend
VITE_API_URL=http://localhost:5000

# WebSocket URL (for real-time updates)
VITE_WS_URL=ws://localhost:5000

# Optional: Mapbox token for maps
# Get free token at https://mapbox.com
VITE_MAPBOX_TOKEN=your_token_here
```

### 3. Start Backend First

Make sure your Flask backend is running:

```bash
cd ~/Documents/programs/webapps/junkos/backend
python app.py
```

Backend should be available at `http://localhost:5000`

### 4. Start Dashboard

In a new terminal:

```bash
cd ~/Documents/programs/webapps/junkos/dashboard
npm run dev
```

Dashboard will open at: **http://localhost:3000**

### 5. Login

Use demo credentials:
- Email: `admin@goumuve.com`
- Password: `admin123`

## Verifying Installation

✅ **You should see:**
- Login page at localhost:3000
- No console errors in browser DevTools
- Backend API responding (check Network tab)

❌ **Common Issues:**

**"Cannot find module" errors:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**Port 3000 already in use:**
```bash
# Edit vite.config.js and change port:
server: {
  port: 3001,
}
```

**API requests fail (CORS errors):**
- Verify backend is running
- Check backend has CORS enabled
- Confirm `VITE_API_URL` matches backend URL

## Next Steps

1. **Test all pages**: Dashboard, Jobs, Dispatch, Drivers, Calendar, Analytics
2. **Create test data**: Add sample jobs and drivers through the UI
3. **Test WebSocket**: Make changes and verify real-time updates
4. **Mobile test**: Open on tablet/phone to verify responsive design

## Development Commands

```bash
# Start dev server
npm run dev

# Run linter
npm run lint

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
dashboard/
├── src/
│   ├── components/     # UI components
│   │   ├── ui/        # Base UI components (buttons, cards, etc)
│   │   ├── auth/      # Login, ProtectedRoute
│   │   ├── jobs/      # Job cards, modals
│   │   └── layout/    # DashboardLayout, Sidebar
│   ├── pages/         # Main pages
│   ├── contexts/      # Auth context
│   ├── lib/           # API, utils, websocket
│   └── App.jsx        # Routes and main app
├── public/            # Static files
└── package.json       # Dependencies
```

## Making Changes

### Add a new page:

1. Create `src/pages/NewPage.jsx`
2. Add route in `src/App.jsx`
3. Add nav link in `src/components/layout/DashboardLayout.jsx`

### Add a new API endpoint:

1. Add function in `src/lib/api.js`
2. Use in component with React Query:

```javascript
const { data } = useQuery({
  queryKey: ['myData'],
  queryFn: async () => {
    const response = await myAPI.getData()
    return response.data
  },
})
```

### Style changes:

- Edit Tailwind classes directly in components
- Customize theme colors in `src/index.css`
- Add global styles in `src/index.css`

## Production Deployment

### Build:
```bash
npm run build
```

Output is in `dist/` directory.

### Deploy to Vercel:
```bash
vercel deploy
```

### Deploy to Netlify:
```bash
netlify deploy --prod
```

Need help? Check the main README.md for detailed documentation.
