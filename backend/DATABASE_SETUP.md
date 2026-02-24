# Database Setup Guide

## Quick Reference

```bash
# Initialize all tables (idempotent)
python3 init_db.py

# Or make executable and run directly
chmod +x init_db.py
./init_db.py
```

## Overview

The Umuve backend uses **SQLAlchemy** ORM with support for both PostgreSQL (production) and SQLite (development).

## Tables

The following tables are defined in `models.py`:

1. **users** - Customer and contractor user accounts
2. **contractors** - Contractor profiles with onboarding, licensing, and operator features
3. **promo_codes** - Promotional discount codes
4. **jobs** - Junk removal jobs/bookings
5. **ratings** - Job ratings (1-5 stars)
6. **payments** - Payment records and payout tracking
7. **pricing_rules** - Item-based pricing configuration
8. **surge_zones** - Geographic surge pricing zones
9. **notifications** - In-app notifications
10. **operator_invites** - Operator invite codes for fleet management
11. **device_tokens** - Push notification device tokens (iOS/Android)
12. **pricing_config** - Key-value config for admin-overridable pricing
13. **recurring_bookings** - Recurring job schedules
14. **referrals** - User referral tracking
15. **support_messages** - Customer support tickets
16. **refunds** - Payment refunds
17. **webhook_events** - Stripe webhook event audit log
18. **chat_messages** - Real-time job chat between customers and drivers
19. **reviews** - Customer reviews of completed jobs
20. **operator_applications** - Landing page operator signup forms

## Quick Start

### 1. Initialize Database

Run the initialization script to create all tables:

```bash
# From the backend directory
cd backend
python init_db.py
```

This script is **idempotent** - safe to run multiple times. It will only create tables that don't already exist.

### 2. Environment Variables

The script respects the following environment variables:

```bash
# PostgreSQL (Production - Render)
DATABASE_URL=postgresql://user:password@host:port/dbname

# SQLite (Development - Local)
# If DATABASE_URL is not set, defaults to sqlite:///umuve.db
```

### 3. Verify Tables

The script will output all created tables:

```
✓ Total tables: 20
Tables created:
  - chat_messages
  - contractors
  - device_tokens
  - jobs
  - notifications
  - operator_applications
  - operator_invites
  - payments
  - pricing_config
  - pricing_rules
  - promo_codes
  - ratings
  - recurring_bookings
  - referrals
  - refunds
  - reviews
  - support_messages
  - surge_zones
  - users
  - webhook_events
```

## Production Deployment (Render)

When deploying to Render:

1. **PostgreSQL database is auto-created** by Render when you add a PostgreSQL service
2. **DATABASE_URL is auto-set** by Render and injected into your app
3. **Run init_db.py** after first deployment:
   ```bash
   # SSH into Render shell or use build command
   python init_db.py
   ```

## Manual Table Creation (Alternative)

If you prefer SQL, you can also initialize tables via Flask shell:

```python
from server import app
from models import db

with app.app_context():
    db.create_all()
```

## Schema Changes

When you modify `models.py`:

1. For simple changes (new tables), just run `init_db.py` again
2. For complex migrations (column changes, renames), use **Alembic** or manual SQL

## Troubleshooting

### "No module named 'flask'"
```bash
pip install -r requirements.txt
```

### "Permission denied"
```bash
chmod +x init_db.py
```

### "Table already exists"
This is normal - the script is idempotent. Tables that already exist are skipped.

### PostgreSQL connection issues
Check that:
- `DATABASE_URL` is set correctly
- Database server is accessible
- Credentials are correct
- For Render: database service is running

## Migration Scripts Comparison

The backend has three database scripts with different purposes:

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **init_db.py** | Create all tables from scratch using SQLAlchemy models | First-time setup, fresh database, or production deployment |
| **migrate.py** | Add missing columns and tables to existing database | When adding new fields to existing schema |
| **migrate_to_postgres.py** | Copy data from SQLite to PostgreSQL | One-time migration from local dev to production |

**Recommendation**: For production setup on Render, use `init_db.py` first, then run `migrate.py` if needed for schema updates.

## Related Files

- `models.py` - SQLAlchemy model definitions (source of truth)
- `server.py` - Flask app with database configuration
- `app_config.py` - Configuration class
- `init_db.py` - **NEW**: Fresh table creation script
- `migrate.py` - Schema update script (adds columns/tables)
- `migrate_to_postgres.py` - Data migration from SQLite to PostgreSQL
