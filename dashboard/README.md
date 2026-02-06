# JunkOS Dashboard

A modern, responsive operator dashboard for JunkOS junk removal operations. Built with React, Tailwind CSS, and shadcn/ui components.

## Features

- 📊 **Analytics Dashboard** - Revenue tracking, job metrics, and performance insights
- 📋 **Job Management** - View, filter, and manage jobs by status
- 🚚 **Dispatch Interface** - Drag-and-drop job assignment to drivers
- 📅 **Calendar View** - Schedule and visualize jobs on an interactive calendar
- 👥 **Driver Management** - Manage driver availability and assignments
- 🔐 **Authentication** - Role-based access control (admin, dispatcher, driver)
- 📱 **Mobile Responsive** - Works seamlessly on tablets and mobile devices
- 🔄 **Real-time Updates** - WebSocket support for live data synchronization
- 🎨 **Modern UI** - Clean, professional interface with Tailwind CSS and shadcn/ui

## Tech Stack

- **Frontend Framework**: React 18 with Vite
- **Styling**: Tailwind CSS + shadcn/ui components
- **State Management**: Zustand + TanStack Query (React Query)
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **Charts**: Recharts
- **Calendar**: React Big Calendar
- **Drag & Drop**: React Beautiful DnD
- **Maps**: React Map GL (Mapbox)
- **Notifications**: Sonner (toast notifications)

## Prerequisites

- Node.js 18+ (recommended: 20+)
- npm or yarn
- Flask backend API running (see backend setup)

## Installation

1. **Clone and navigate to the dashboard directory:**
   ```bash
   cd ~/Documents/programs/webapps/junkos/dashboard
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set your configuration:
   ```env
   VITE_API_URL=http://localhost:5000
   VITE_WS_URL=ws://localhost:5000
   VITE_MAPBOX_TOKEN=your_mapbox_token_here
   VITE_ENABLE_WEBSOCKET=true
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```

   The dashboard will be available at `http://localhost:3000`

## Build for Production

```bash
npm run build
```

The production-ready files will be in the `dist/` directory.

Preview the production build:
```bash
npm run preview
```

## Project Structure

```
dashboard/
├── public/                 # Static assets
├── src/
│   ├── components/        # React components
│   │   ├── ui/           # shadcn/ui base components
│   │   ├── auth/         # Authentication components
│   │   ├── jobs/         # Job-related components
│   │   └── layout/       # Layout components
│   ├── contexts/         # React contexts (Auth, etc.)
│   ├── lib/              # Utilities and helpers
│   │   ├── api.js       # API client and endpoints
│   │   ├── utils.js     # Utility functions
│   │   └── websocket.js # WebSocket service
│   ├── pages/           # Page components
│   │   ├── Dashboard.jsx
│   │   ├── JobsPage.jsx
│   │   ├── DispatchPage.jsx
│   │   ├── DriversPage.jsx
│   │   ├── CalendarPage.jsx
│   │   └── AnalyticsPage.jsx
│   ├── App.jsx          # Main app component
│   ├── main.jsx         # App entry point
│   └── index.css        # Global styles
├── .env.example         # Environment variables template
├── package.json         # Dependencies
├── vite.config.js       # Vite configuration
├── tailwind.config.js   # Tailwind CSS configuration
└── README.md           # This file
```

## API Integration

The dashboard expects the following Flask backend endpoints:

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user

### Jobs
- `GET /api/jobs` - List all jobs (with query params for filtering)
- `GET /api/jobs/:id` - Get job details
- `POST /api/jobs` - Create new job
- `PATCH /api/jobs/:id` - Update job
- `PATCH /api/jobs/:id/status` - Update job status
- `PATCH /api/jobs/:id/assign` - Assign job to driver
- `DELETE /api/jobs/:id` - Delete job

### Drivers
- `GET /api/drivers` - List all drivers
- `GET /api/drivers/:id` - Get driver details
- `POST /api/drivers` - Create new driver
- `PATCH /api/drivers/:id` - Update driver
- `PATCH /api/drivers/:id/availability` - Update driver availability
- `DELETE /api/drivers/:id` - Delete driver

### Analytics
- `GET /api/analytics/dashboard` - Dashboard statistics
- `GET /api/analytics/revenue` - Revenue trends
- `GET /api/analytics/jobs` - Job statistics

## WebSocket Events

The dashboard listens for these WebSocket events:

- `job:created` - New job created
- `job:updated` - Job updated
- `job:status_changed` - Job status changed
- `job:assigned` - Job assigned to driver
- `driver:location_updated` - Driver location updated
- `driver:availability_changed` - Driver availability changed

## Default Credentials

For testing/demo purposes:
- **Admin**: admin@junkos.com / admin123
- **Dispatcher**: dispatcher@junkos.com / dispatch123

## Role-Based Access

- **Admin**: Full access to all features including analytics
- **Dispatcher**: Access to jobs, dispatch, drivers, and calendar
- **Driver**: Limited access (mobile app only)

## Customization

### Theme Colors

Edit `src/index.css` to customize the color scheme:

```css
:root {
  --primary: 221.2 83.2% 53.3%;  /* Blue */
  --secondary: 210 40% 96.1%;    /* Light gray */
  /* ... other colors */
}
```

### Adding New Pages

1. Create page component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add navigation item in `src/components/layout/DashboardLayout.jsx`

### Adding New UI Components

The dashboard uses shadcn/ui. To add more components:

1. Create component in `src/components/ui/`
2. Follow shadcn/ui patterns for consistency
3. Use `cn()` utility for className merging

## Troubleshooting

### Development server won't start
- Check if port 3000 is available
- Verify Node.js version: `node -v` (should be 18+)
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`

### API requests failing
- Verify backend is running at the URL specified in `.env`
- Check CORS configuration on Flask backend
- Open browser DevTools Network tab to see detailed errors

### WebSocket not connecting
- Ensure `VITE_WS_URL` is correct in `.env`
- Check if Flask WebSocket endpoint is working
- Verify authentication token is being sent

### Build errors
- Run `npm run lint` to check for code issues
- Clear Vite cache: `rm -rf node_modules/.vite`
- Update dependencies: `npm update`

## Performance Tips

1. **Lazy Loading**: Add code splitting for routes using `React.lazy()`
2. **Image Optimization**: Use WebP format for job photos
3. **API Caching**: Adjust TanStack Query `staleTime` as needed
4. **Bundle Size**: Run `npm run build` and check bundle analyzer

## Development Workflow

1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes and test locally
3. Run linter: `npm run lint`
4. Build for production: `npm run build`
5. Test production build: `npm run preview`
6. Commit and push changes

## Deployment

### Deploy to Vercel/Netlify

1. Connect your Git repository
2. Set build command: `npm run build`
3. Set output directory: `dist`
4. Add environment variables

### Deploy with Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
RUN npm install -g serve
CMD ["serve", "-s", "dist", "-l", "3000"]
EXPOSE 3000
```

## Support & Contributing

For issues, feature requests, or contributions:
1. Check existing issues
2. Create detailed bug reports
3. Follow code style guidelines
4. Write tests for new features

## License

Private - JunkOS Internal Use Only

---

Built with ❤️ for JunkOS operations teams
