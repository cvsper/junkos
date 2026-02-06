# JunkOS Backend API

Flask-based REST API for the JunkOS multi-tenant junk removal SaaS platform.

## Features

- 🏢 **Multi-tenant architecture** with tenant isolation
- 🔐 **JWT authentication** with role-based access control
- 📦 **SQLAlchemy ORM** with PostgreSQL
- 🚀 **Flask factory pattern** for clean app structure
- ✅ **CORS enabled** for frontend integration

## Tech Stack

- **Flask 3.0** - Web framework
- **SQLAlchemy** - ORM
- **PostgreSQL** - Database
- **PyJWT** - JWT tokens
- **bcrypt** - Password hashing
- **Gunicorn** - Production server

## Quick Start

### 1. Prerequisites

- Python 3.9+
- PostgreSQL 14+
- pip

### 2. Installation

```bash
# Clone and navigate to backend directory
cd ~/Documents/programs/webapps/junkos/backend/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
# - Set DATABASE_URL to your PostgreSQL connection string
# - Change SECRET_KEY and JWT_SECRET_KEY to random strings
# - Adjust CORS_ORIGINS for your frontend URLs
```

### 4. Database Setup

```bash
# Make sure PostgreSQL is running

# Create database
createdb junkos_dev

# Run schema (from parent directory)
psql junkos_dev < ../junk_removal_schema.sql

# Or using psql prompt:
# psql
# CREATE DATABASE junkos_dev;
# \c junkos_dev
# \i ../junk_removal_schema.sql
```

### 5. Run Development Server

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run the app
python run.py

# Or with Flask CLI
export FLASK_APP=run.py
flask run
```

The API will be available at `http://localhost:5000`

### 6. Test the API

```bash
# Health check
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy", "service": "junkos-backend"}
```

## API Endpoints

### Authentication

#### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
  "tenant_id": "uuid",
  "email": "admin@example.com",
  "password": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "role": "admin",
  "phone": "555-1234"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "securepass123",
  "tenant_id": "uuid"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": { ... }
}
```

### Bookings

All booking endpoints require authentication. Include JWT token in header:
```
Authorization: Bearer <token>
```

#### List Bookings
```http
GET /api/bookings?page=1&per_page=20&status=pending
```

#### Create Booking
```http
POST /api/bookings
Content-Type: application/json

{
  "customer_id": "uuid",
  "service_id": "uuid",
  "scheduled_date": "2024-01-15",
  "scheduled_time_start": "09:00",
  "service_address_line1": "123 Main St",
  "service_city": "Boston",
  "service_state": "MA",
  "service_postal_code": "02101",
  "items_description": "Old furniture and appliances",
  "special_instructions": "Call before arriving",
  "estimated_volume": 3.5
}
```

#### Get Booking
```http
GET /api/bookings/:id
```

### Jobs

#### List Jobs
```http
GET /api/jobs?page=1&status=in_progress
```

**Note:** Drivers only see jobs assigned to them. Admins/dispatchers see all jobs.

#### Update Job Status
```http
PATCH /api/jobs/:id
Content-Type: application/json

{
  "status": "in_progress",
  "actual_start_time": "2024-01-15T09:00:00Z",
  "actual_volume": 4.5
}
```

#### Assign Job to Driver (Admin/Dispatcher only)
```http
POST /api/jobs/:id/assign
Content-Type: application/json

{
  "driver_ids": ["driver-uuid-1", "driver-uuid-2"],
  "role_in_job": "driver"
}
```

### Payments

#### List Invoices
```http
GET /api/payments/invoices?page=1&status=sent
```

#### Get Invoice
```http
GET /api/payments/invoices/:id
```

#### List Payments
```http
GET /api/payments?payment_status=completed
```

#### Record Payment (Admin/Dispatcher only)
```http
POST /api/payments
Content-Type: application/json

{
  "invoice_id": "uuid",
  "customer_id": "uuid",
  "amount": 150.00,
  "payment_method": "credit_card",
  "payment_status": "completed",
  "transaction_id": "txn_123456",
  "processor": "stripe",
  "notes": "Payment via Stripe"
}
```

## User Roles

- **admin**: Full access to all resources
- **dispatcher**: Manage jobs, assign drivers, view reports
- **driver**: View assigned jobs, update job status

## Project Structure

```
backend/
├── app/
│   ├── __init__.py          # Flask factory and app initialization
│   ├── models.py            # SQLAlchemy models
│   ├── utils.py             # Helper functions and decorators
│   └── routes/
│       ├── __init__.py
│       ├── auth.py          # Authentication endpoints
│       ├── bookings.py      # Booking management
│       ├── jobs.py          # Job management
│       └── payments.py      # Payment and invoice endpoints
├── config.py                # Configuration classes
├── requirements.txt         # Python dependencies
├── .env.example             # Example environment variables
├── run.py                   # Application entry point
└── README.md               # This file
```

## Security Features

- **JWT tokens** with configurable expiration
- **bcrypt password hashing** with salt
- **Tenant isolation** enforced at database and API level
- **Role-based access control** with decorators
- **CORS configuration** for cross-origin requests

## Production Deployment

### Using Gunicorn

```bash
# Install gunicorn (already in requirements.txt)
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app

# With environment variables
gunicorn -w 4 -b 0.0.0.0:5000 \
  --env FLASK_ENV=production \
  --access-logfile - \
  --error-logfile - \
  run:app
```

### Environment Variables for Production

```bash
FLASK_ENV=production
DEBUG=False
SECRET_KEY=<strong-random-key>
JWT_SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:pass@host:5432/dbname
CORS_ORIGINS=https://your-frontend.com,https://admin.your-frontend.com
```

### Systemd Service (Optional)

Create `/etc/systemd/system/junkos-backend.service`:

```ini
[Unit]
Description=JunkOS Backend API
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/path/to/backend
EnvironmentFile=/path/to/backend/.env
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable junkos-backend
sudo systemctl start junkos-backend
```

## Development Tips

### Create First Tenant (Manual)

```sql
-- Connect to database
psql junkos_dev

-- Create tenant
INSERT INTO tenants (id, name, slug, contact_email, status)
VALUES (
  uuid_generate_v4(),
  'Demo Company',
  'demo',
  'demo@example.com',
  'active'
);

-- Get tenant ID
SELECT id, name, slug FROM tenants;
```

### Test Authentication Flow

```bash
# 1. Register user (use tenant_id from above)
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "YOUR-TENANT-ID",
    "email": "admin@demo.com",
    "password": "admin123",
    "first_name": "Admin",
    "last_name": "User",
    "role": "admin"
  }'

# 2. Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@demo.com",
    "password": "admin123"
  }'

# 3. Use token for authenticated requests
curl http://localhost:5000/api/bookings \
  -H "Authorization: Bearer YOUR-JWT-TOKEN"
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
pg_isready

# Test connection
psql -U your_user -d junkos_dev -c "SELECT 1"

# Check DATABASE_URL format
echo $DATABASE_URL
# Should be: postgresql://username:password@host:port/database
```

### Import Errors

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.9+
```

### CORS Issues

If frontend can't connect, check:
1. `.env` has correct `CORS_ORIGINS`
2. Frontend is using the correct API URL
3. JWT token is being sent in `Authorization` header

## Next Steps

### Recommended Enhancements

1. **Add more endpoints**: Update/delete for bookings, customers, etc.
2. **Geocoding**: Integrate Google Maps API to populate latitude/longitude
3. **Email notifications**: Add email service for booking confirmations
4. **Payment integration**: Connect Stripe or Square APIs
5. **File uploads**: Add photo upload endpoints
6. **Webhooks**: Implement webhook handlers for payment processors
7. **Rate limiting**: Add rate limiting with Flask-Limiter
8. **Logging**: Implement structured logging
9. **Testing**: Add pytest test suite
10. **API documentation**: Generate OpenAPI/Swagger docs

### Migration to Production

- Set up proper database backups
- Configure SSL/TLS certificates
- Set up monitoring (Sentry, DataDog, etc.)
- Implement proper logging and error tracking
- Add health checks and metrics endpoints
- Set up CI/CD pipeline

## Support

For issues or questions:
- Check the database schema: `../junk_removal_schema.sql`
- Review Flask documentation: https://flask.palletsprojects.com/
- SQLAlchemy docs: https://docs.sqlalchemy.org/

## License

MIT License - see LICENSE file for details
