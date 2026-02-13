# Umuve Web MVP Testing Guide

## 🎯 Goal
Verify the complete web stack works end-to-end before mobile deployment.

---

## 📋 Pre-Testing Checklist

Before running `make up`, verify these files exist:

```bash
cd ~/Documents/programs/webapps/junkos

# Backend
ls backend/app/
ls backend/requirements.txt
ls backend/run.py

# Frontend
ls frontend/src/
ls frontend/package.json

# Dashboard
ls dashboard/src/
ls dashboard/package.json

# Docker
ls docker-compose.yml
ls Makefile

# Database
ls database/junk_removal_schema.sql
```

**All files should exist.** If any are missing, let me know.

---

## 🚀 Step 1: Start the Stack

```bash
cd ~/Documents/programs/webapps/junkos

# Build Docker images (first time only - takes 5-10 min)
make build

# Start all services
make up
```

**What starts:**
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Flask backend (port 5000)
- Customer portal (port 3000)
- Operator dashboard (port 3001)
- Nginx reverse proxy (port 80)

**Wait for:** "All services started successfully" message

---

## ✅ Step 2: Verify Services Are Running

Open new terminal and check:

```bash
# Check Docker containers
docker ps

# Should see 6 containers running:
# - junkos-postgres
# - junkos-redis
# - umuve-backend
# - junkos-frontend
# - junkos-dashboard
# - junkos-nginx
```

**If any container is missing or "Exited":**
```bash
make logs        # Check all logs
make logs-backend  # Check specific service
```

---

## 🧪 Step 3: Test Backend API

```bash
# Health check
curl http://localhost:5000/health

# Expected: {"status": "healthy"}
```

**If you get connection refused:**
```bash
make logs-backend  # Check backend logs
```

---

## 👤 Step 4: Test Customer Portal

1. **Open browser:** http://localhost:3000
2. **Expected:** Umuve customer booking page loads
3. **Try the booking flow:**
   - Click "Start Booking" or "Get Started"
   - Enter address
   - Upload a test photo (any image from your computer)
   - Select service type
   - Choose date/time
   - See price estimate

**If page doesn't load:**
```bash
make logs-frontend
```

---

## 🎛️ Step 5: Test Operator Dashboard

1. **Open browser:** http://localhost:3001
2. **Expected:** Umuve dashboard login page
3. **Create test account:**
   - Register new operator account
   - Email: admin@test.com
   - Password: test1234

4. **After login, check:**
   - Job queue view
   - Driver management
   - Calendar view
   - Analytics dashboard

**If dashboard doesn't load:**
```bash
make logs-dashboard
```

---

## 🔗 Step 6: Test End-to-End Flow

### Create a Test Booking

**On Customer Portal (http://localhost:3000):**
1. Start new booking
2. Address: 123 Test St, Miami, FL 33101
3. Upload photo: Any JPG/PNG from your computer
4. Service: Full house cleanout
5. Date: Tomorrow
6. Time: 10:00 AM
7. Submit booking

**On Operator Dashboard (http://localhost:3001):**
1. Login as operator
2. Go to "Jobs" or "Queue"
3. **Expected:** See the test booking you just created
4. Click on the job
5. **Expected:** See customer details, photos, address, time
6. Try changing status: Pending → Scheduled → Completed

**Success Criteria:**
✅ Booking appears in dashboard within 5 seconds
✅ All booking details are correct
✅ Photo uploaded successfully
✅ Can change job status

---

## 💳 Step 7: Test Payment Flow (Optional for Now)

**Note:** Payments use Stripe test mode by default.

1. Complete a booking on customer portal
2. At payment step, use Stripe test card:
   - Card: 4242 4242 4242 4242
   - Expiry: Any future date (e.g., 12/25)
   - CVC: Any 3 digits (e.g., 123)
   - ZIP: Any 5 digits (e.g., 12345)

3. Submit payment
4. **Expected:** Payment success message
5. Check dashboard → Invoices → Should see payment recorded

---

## 🐛 Common Issues & Fixes

### "Port already in use"
```bash
# Find what's using port 5000/3000/3001
lsof -i :5000
lsof -i :3000
lsof -i :3001

# Kill the process or stop the service
kill -9 <PID>
```

### "Database connection error"
```bash
# Check if postgres is running
docker ps | grep postgres

# If not, restart:
make down
make up
```

### "Cannot connect to backend"
```bash
# Check backend logs
make logs-backend

# Common fix: Rebuild backend
make rebuild-backend
```

### Frontend shows blank page
```bash
# Check browser console (F12) for errors
# Common fix: Clear browser cache (Cmd+Shift+R)
```

### Docker build fails
```bash
# Clean everything and rebuild
make clean
make build
```

---

## 📊 Success Checklist

Before proceeding to mobile testing:

- [ ] All 6 Docker containers running
- [ ] Backend API responds at http://localhost:5000/health
- [ ] Customer portal loads at http://localhost:3000
- [ ] Operator dashboard loads at http://localhost:3001
- [ ] Can create a test booking
- [ ] Booking appears in operator dashboard
- [ ] Can upload photos successfully
- [ ] Can change job status in dashboard
- [ ] Payment flow works (Stripe test mode)

**If all checked → Web MVP is working! ✅**

---

## 🛑 Stop Services

When done testing:

```bash
# Stop all services
make down

# Keep data, just stop containers
```

**To reset everything:**
```bash
make clean  # Removes containers, volumes, networks
```

---

## 📞 Troubleshooting Commands

```bash
# View all logs
make logs

# View specific service logs
make logs-backend
make logs-frontend
make logs-dashboard
make logs-postgres

# Restart a specific service
docker-compose restart backend

# Check service health
docker-compose ps

# Access database directly
make db-shell
```

---

## 🎯 What To Look For

### Good Signs ✅
- All containers show "Up" status
- No error messages in logs
- Pages load within 2-3 seconds
- Bookings save successfully
- Photos upload and display correctly

### Red Flags 🚨
- Container keeps restarting
- "Connection refused" errors
- 500 Internal Server Error
- Database connection errors
- Photos fail to upload

**If you see red flags, check logs and share them with me!**

---

**Last Updated:** 2026-02-06  
**Next Step:** Once web testing passes, proceed to mobile app testing
