# JunkOS Dashboard Architecture

## Overview

The JunkOS Dashboard is a modern React-based admin panel for managing junk removal operations. It provides real-time job tracking, driver dispatch, scheduling, and analytics capabilities.

## Technology Stack

### Core
- **React 18.3** - UI framework
- **Vite 5** - Build tool and dev server
- **React Router 6** - Client-side routing
- **TanStack Query** - Server state management
- **Axios** - HTTP client

### UI & Styling
- **Tailwind CSS 3.4** - Utility-first CSS framework
- **shadcn/ui** - Component library (custom implementation)
- **Lucide React** - Icon library
- **Sonner** - Toast notifications

### Features
- **React Big Calendar** - Calendar and scheduling
- **React Beautiful DnD** - Drag-and-drop dispatch
- **Recharts** - Charts and analytics
- **React Map GL** - Map integration (Mapbox)
- **date-fns** - Date manipulation

## Architecture Patterns

### Component Structure

```
┌─────────────────────────────────────┐
│           App (Router)              │
├─────────────────────────────────────┤
│        AuthProvider Context         │
├─────────────────────────────────────┤
│      QueryClientProvider            │
└─────────────────────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼────┐      ┌──────▼────────┐
│ Login  │      │  Dashboard    │
│ Page   │      │   Layout      │
└────────┘      └───────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    ┌───▼────┐    ┌────▼────┐    ┌────▼─────┐
    │ Jobs   │    │ Dispatch│    │ Analytics│
    │ Page   │    │  Page   │    │   Page   │
    └────────┘    └─────────┘    └──────────┘
```

### State Management

**Server State** (TanStack Query)
- Job data
- Driver information
- Analytics data
- Caching with 5-minute stale time
- Automatic refetching on window focus

**Client State** (React Context + useState)
- Authentication state
- User session
- UI state (modals, filters)

**Global State** (Not implemented, ready for Zustand)
- WebSocket messages
- Real-time notifications
- App-wide settings

### Data Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Component│────▶│  Query   │────▶│   API    │
│          │     │  Hook    │     │  Client  │
└──────────┘     └──────────┘     └────┬─────┘
                                        │
                                        ▼
                                 ┌─────────────┐
                                 │    Flask    │
                                 │   Backend   │
                                 └─────────────┘
```

### Authentication Flow

```
1. User enters credentials
2. POST /api/auth/login
3. Receive JWT token + user data
4. Store token in localStorage
5. Add token to all API requests (interceptor)
6. Load user data into AuthContext
7. Render protected routes
```

Token refresh happens via:
- 401 response → logout and redirect to login
- Manual refresh (future enhancement)

## File Organization

### Atomic Design Principles

**Atoms** (`src/components/ui/`)
- Button, Input, Badge, Card, etc.
- Reusable, single-responsibility components
- No business logic

**Molecules** (`src/components/jobs/`, `src/components/drivers/`)
- JobCard, DriverCard, JobDetailModal
- Composed of atoms + specific logic
- Domain-specific

**Organisms** (`src/components/layout/`)
- DashboardLayout, Sidebar, Header
- Complex compositions
- Page structure

**Pages** (`src/pages/`)
- Full page views
- Route targets
- Orchestrate multiple organisms

### Folder Structure

```
src/
├── components/
│   ├── ui/              # Atomic UI components
│   ├── auth/            # Auth-specific components
│   ├── jobs/            # Job-related components
│   ├── drivers/         # Driver components
│   └── layout/          # Layout components
├── contexts/            # React contexts
├── hooks/               # Custom hooks (future)
├── lib/                 # Utilities
│   ├── api.js          # API client & endpoints
│   ├── utils.js        # Helper functions
│   └── websocket.js    # WebSocket service
├── pages/              # Page components
├── App.jsx             # Root component
└── main.jsx            # Entry point
```

## API Integration

### REST Endpoints

**Jobs:**
- `GET /api/jobs` - List with filters
- `GET /api/jobs/:id` - Single job
- `POST /api/jobs` - Create
- `PATCH /api/jobs/:id` - Update
- `PATCH /api/jobs/:id/status` - Update status
- `PATCH /api/jobs/:id/assign` - Assign driver
- `DELETE /api/jobs/:id` - Delete

**Drivers:**
- `GET /api/drivers` - List
- `GET /api/drivers/:id` - Single driver
- `POST /api/drivers` - Create
- `PATCH /api/drivers/:id` - Update
- `PATCH /api/drivers/:id/availability` - Toggle availability
- `DELETE /api/drivers/:id` - Delete

**Analytics:**
- `GET /api/analytics/dashboard` - Summary stats
- `GET /api/analytics/revenue` - Revenue trends
- `GET /api/analytics/jobs` - Job statistics

### WebSocket Events

**Subscribed:**
- `job:created` → Refetch jobs list
- `job:updated` → Update job in cache
- `job:status_changed` → Refresh status
- `driver:location_updated` → Update map
- `driver:availability_changed` → Refresh driver list

**Published:**
- `subscribe` → Subscribe to updates
- `unsubscribe` → Unsubscribe

## Performance Optimizations

### Current
1. **Code Splitting** - Route-based (ready for React.lazy)
2. **Query Caching** - 5-minute stale time
3. **Optimistic Updates** - Instant UI updates
4. **Debounced Search** - Reduce API calls
5. **Memoization** - useMemo for expensive calculations

### Future Enhancements
1. **Lazy Loading** - Images and components
2. **Virtual Scrolling** - Large job lists
3. **Service Worker** - Offline support
4. **Bundle Analysis** - Tree shaking optimization
5. **CDN Assets** - Static file delivery

## Security

### Implemented
- JWT token authentication
- Protected routes
- Role-based access control
- Axios interceptors for auth
- Auto-logout on 401
- XSS protection (React default)

### Best Practices
- No sensitive data in localStorage (only token)
- HTTPS required in production
- CORS configured on backend
- Input validation
- Sanitized outputs

## Deployment Strategy

### Development
```bash
npm run dev  # Vite dev server on :3000
```

### Production Build
```bash
npm run build  # Output to dist/
npm run preview  # Test production build
```

### Deployment Targets
1. **Vercel** (recommended)
   - Auto HTTPS
   - Global CDN
   - Instant rollbacks

2. **Netlify**
   - Similar to Vercel
   - Built-in forms

3. **Docker**
   - Self-hosted
   - Full control
   - nginx or serve

4. **Static Hosting**
   - S3 + CloudFront
   - Firebase Hosting
   - GitHub Pages

## Testing Strategy (Future)

### Unit Tests
- Component rendering
- Utility functions
- API client

### Integration Tests
- User flows
- API integration
- State management

### E2E Tests
- Full workflows
- Login → create job → assign → complete

## Monitoring & Analytics

### Recommended Tools
- **Sentry** - Error tracking
- **LogRocket** - Session replay
- **Google Analytics** - Usage metrics
- **Hotjar** - User behavior

### Custom Logging
```javascript
// Error boundary
// API error logging
// Performance monitoring
```

## Future Enhancements

### Short-term (1-2 months)
- [ ] Export reports (PDF, Excel)
- [ ] Email notifications
- [ ] SMS integration
- [ ] Photo uploads with compression
- [ ] GPS tracking on map
- [ ] Dark mode toggle

### Medium-term (3-6 months)
- [ ] Mobile app (React Native)
- [ ] Offline mode
- [ ] Customer portal
- [ ] Automated routing
- [ ] Invoice generation
- [ ] Payment processing

### Long-term (6+ months)
- [ ] AI route optimization
- [ ] Predictive scheduling
- [ ] Customer review system
- [ ] Multi-language support
- [ ] Franchise management
- [ ] Advanced analytics ML

## Contributing Guidelines

1. Follow existing code patterns
2. Use TypeScript for new files (migration planned)
3. Write meaningful commit messages
4. Add tests for new features
5. Update documentation
6. Run linter before committing

## Changelog

### v1.0.0 (Initial Release)
- Dashboard with analytics
- Job management system
- Drag-and-drop dispatch
- Driver management
- Calendar view
- Role-based auth
- WebSocket support
- Mobile responsive design

---

**Last Updated:** February 6, 2026
**Maintained by:** OpenClaw AI
