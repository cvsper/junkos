# Umuve Database

Complete database initialization and migration framework for the Umuve multi-tenant junk removal SaaS platform.

## 📁 Structure

```
database/
├── 01_create_database.sql    # Database creation with extensions
├── 02_schema.sql              # Complete table schema
├── 03_seed_data.sql           # Sample data for testing
├── 04_views.sql               # Useful database views
├── migrate.py                 # Migration runner
├── rollback.py                # Rollback tool
├── migrations/                # Migration files directory
├── .env.example               # Environment configuration template
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Initial Setup

**Prerequisites:**
- PostgreSQL 12+ installed
- Python 3.8+ installed
- `psycopg2` Python package

Install Python dependencies:
```bash
pip install psycopg2-binary
```

**Configure Environment:**
```bash
# Copy environment template
cp .env.example .env

# Edit with your database credentials
nano .env
```

### 2. Initialize Database

Run the initialization scripts in order:

```bash
# 1. Create database and extensions
psql -U postgres -f 01_create_database.sql

# 2. Create all tables and indexes
psql -U postgres -d umuve -f 02_schema.sql

# 3. Load sample data (optional - for testing)
psql -U postgres -d umuve -f 03_seed_data.sql

# 4. Create useful views
psql -U postgres -d umuve -f 04_views.sql
```

**Or run all at once:**
```bash
psql -U postgres -f 01_create_database.sql && \
psql -U postgres -d umuve -f 02_schema.sql && \
psql -U postgres -d umuve -f 03_seed_data.sql && \
psql -U postgres -d umuve -f 04_views.sql
```

### 3. Verify Setup

```bash
# Connect to database
psql -U postgres -d umuve

# List tables
\dt

# Check sample data
SELECT COUNT(*) FROM tenants;
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM jobs;

# Test views
SELECT * FROM v_active_jobs LIMIT 5;
```

## 🔄 Migration Workflow

### Check Migration Status

```bash
python migrate.py --status
```

### Create a New Migration

```bash
python migrate.py --create "add customer loyalty points"
```

This creates a timestamped file: `migrations/20240206120000_add_customer_loyalty_points.sql`

**Edit the migration file:**
```sql
BEGIN;

-- Add loyalty points column
ALTER TABLE customers ADD COLUMN loyalty_points INTEGER DEFAULT 0;
CREATE INDEX idx_customers_loyalty ON customers(loyalty_points);

-- ROLLBACK: DROP INDEX idx_customers_loyalty;
-- ROLLBACK: ALTER TABLE customers DROP COLUMN loyalty_points;

COMMIT;
```

### Apply Migrations

```bash
# Run all pending migrations
python migrate.py

# Migrate to specific version
python migrate.py --to 20240206120000
```

### Rollback Migrations

```bash
# Rollback last migration
python rollback.py

# Rollback to specific version
python rollback.py --to 20240206120000

# View rollback history
python rollback.py --list
```

## 💾 Backup & Restore

### Create Backup

**Full database backup:**
```bash
# Plain SQL format (human-readable)
pg_dump -U postgres -d umuve -F p -f umuve_backup_$(date +%Y%m%d_%H%M%S).sql

# Custom format (compressed, supports parallel restore)
pg_dump -U postgres -d umuve -F c -f umuve_backup_$(date +%Y%m%d_%H%M%S).dump
```

**Schema only (no data):**
```bash
pg_dump -U postgres -d umuve --schema-only -f umuve_schema.sql
```

**Data only:**
```bash
pg_dump -U postgres -d umuve --data-only -f umuve_data.sql
```

**Specific tables:**
```bash
pg_dump -U postgres -d umuve -t jobs -t customers -f umuve_jobs_customers.sql
```

### Restore Backup

**From SQL file:**
```bash
psql -U postgres -d umuve -f umuve_backup_20240206_120000.sql
```

**From custom format:**
```bash
pg_restore -U postgres -d umuve umuve_backup_20240206_120000.dump
```

**Create new database from backup:**
```bash
createdb -U postgres umuve_restored
psql -U postgres -d umuve_restored -f umuve_backup.sql
```

### Automated Backup Script

Create `backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/umuve"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -U postgres -d umuve -F c -f $BACKUP_DIR/umuve_$DATE.dump

# Keep only last 30 days
find $BACKUP_DIR -name "umuve_*.dump" -mtime +30 -delete

echo "Backup completed: umuve_$DATE.dump"
```

**Schedule with cron:**
```bash
# Run daily at 2 AM
0 2 * * * /path/to/backup.sh >> /var/log/umuve_backup.log 2>&1
```

## 🗃️ Database Views

The following views are available for common queries:

### Operational Views
- **`v_active_jobs`** - Active jobs with customer and driver details
- **`v_driver_schedule`** - Driver assignments and schedules
- **`v_upcoming_schedule`** - Jobs scheduled in next 7 days

### Financial Views
- **`v_outstanding_invoices`** - Unpaid invoices with urgency flags
- **`v_daily_revenue`** - Daily revenue breakdown
- **`v_payment_history`** - Complete payment transaction history

### Analytics Views
- **`v_customer_summary`** - Customer lifetime value and statistics
- **`v_job_metrics`** - Job completion metrics and KPIs
- **`v_driver_performance`** - Driver performance statistics
- **`v_tenant_dashboard`** - Tenant health metrics

**Example usage:**
```sql
-- Show today's schedule
SELECT * FROM v_upcoming_schedule 
WHERE scheduled_date = CURRENT_DATE
ORDER BY scheduled_time_start;

-- Find overdue invoices
SELECT * FROM v_outstanding_invoices 
WHERE urgency = 'overdue';

-- Top customers by revenue
SELECT * FROM v_customer_summary 
ORDER BY lifetime_value DESC 
LIMIT 10;
```

## 🔧 Advanced Configuration

### Connection Pooling

For production applications, use connection pooling:

**Python (psycopg2):**
```python
from psycopg2 import pool

db_pool = pool.SimpleConnectionPool(
    minconn=2,
    maxconn=10,
    dsn=os.getenv('DATABASE_URL')
)
```

**Node.js (pg):**
```javascript
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  min: 2,
  max: 10
});
```

### Performance Tuning

**Analyze query performance:**
```sql
-- Enable timing
\timing

-- Explain query plan
EXPLAIN ANALYZE SELECT * FROM v_active_jobs;

-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Vacuum and analyze:**
```bash
# Manual vacuum
vacuumdb -U postgres -d umuve --analyze

# Enable autovacuum (postgresql.conf)
autovacuum = on
autovacuum_max_workers = 3
```

### Row-Level Security (RLS)

RLS is enabled on all tenant-scoped tables. To use it:

**Set tenant context in application:**
```sql
-- Set current tenant for session
SET app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440001';

-- Now queries are automatically filtered
SELECT * FROM jobs; -- Only shows jobs for this tenant
```

**Example policy (already applied):**
```sql
CREATE POLICY tenant_isolation_policy ON users
FOR ALL
USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### Monitoring

**Check database size:**
```sql
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'umuve';
```

**Monitor table sizes:**
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Active connections:**
```sql
SELECT 
    count(*) as connections,
    state
FROM pg_stat_activity
WHERE datname = 'umuve'
GROUP BY state;
```

## 🧪 Testing

### Reset Database (Development Only)

```bash
# WARNING: This deletes all data!
psql -U postgres << EOF
DROP DATABASE IF EXISTS umuve;
EOF

# Then re-run initialization
psql -U postgres -f 01_create_database.sql
psql -U postgres -d umuve -f 02_schema.sql
psql -U postgres -d umuve -f 03_seed_data.sql
psql -U postgres -d umuve -f 04_views.sql
```

### Sample Queries for Testing

```sql
-- List all tenants with job counts
SELECT 
    t.name,
    COUNT(j.id) as total_jobs
FROM tenants t
LEFT JOIN jobs j ON t.id = j.tenant_id
GROUP BY t.id, t.name;

-- Today's schedule
SELECT * FROM v_upcoming_schedule
WHERE scheduled_date = CURRENT_DATE;

-- Driver workload
SELECT 
    driver_name,
    COUNT(*) as assigned_jobs
FROM v_driver_schedule
WHERE job_status IN ('assigned', 'confirmed')
GROUP BY driver_id, driver_name;
```

## 🐛 Troubleshooting

### Common Issues

**Connection refused:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql
```

**Permission denied:**
```bash
# Grant permissions to user
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE umuve TO your_user;"
```

**Migration table doesn't exist:**
```bash
# Initialize migration tracking
python migrate.py --status
```

**Rollback fails:**
- Check migration file for `-- ROLLBACK:` comments
- Manual rollback may be required if no rollback SQL is provided

### Database Logs

**Find log location:**
```sql
SHOW log_directory;
SHOW log_filename;
```

**View recent errors:**
```bash
tail -f /var/log/postgresql/postgresql-*.log
```

## 📚 Resources

### PostgreSQL Documentation
- [PostgreSQL Official Docs](https://www.postgresql.org/docs/)
- [psql Commands](https://www.postgresql.org/docs/current/app-psql.html)
- [Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)

### Multi-Tenancy Best Practices
- [Multi-Tenant Data Architecture](https://docs.microsoft.com/en-us/azure/sql-database/saas-tenancy-app-design-patterns)
- [Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

### Migration Patterns
- [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html)
- [Zero-Downtime Migrations](https://blog.codeship.com/zero-downtime-database-migrations/)

## 🤝 Contributing

When adding new migrations:

1. Always include rollback SQL as comments
2. Test migrations on a development database first
3. Use transactions (BEGIN/COMMIT) for safety
4. Document complex migrations in comments
5. Keep migrations small and focused

## 📝 License

Part of the Umuve project.

---

**Need help?** Check the troubleshooting section or review the PostgreSQL logs.
