# Database Migrations

This directory contains timestamped database migration files.

## File Naming Convention

Migrations follow the format: `YYYYMMDDHHMMSS_description.sql`

Example: `20240206143000_add_customer_loyalty_program.sql`

## Creating Migrations

**Use the migration tool:**
```bash
python ../migrate.py --create "add customer loyalty program"
```

This automatically creates a properly named and formatted migration file.

## Migration File Format

Each migration should be wrapped in a transaction and include rollback instructions:

```sql
-- Migration: Add customer loyalty program
-- Created: 2024-02-06 14:30:00
-- ============================================================================

BEGIN;

-- ============================================================================
-- UP MIGRATION
-- ============================================================================

-- Add loyalty points column
ALTER TABLE customers ADD COLUMN loyalty_points INTEGER DEFAULT 0 NOT NULL;
CREATE INDEX idx_customers_loyalty_points ON customers(loyalty_points);

-- Add loyalty tier enum
CREATE TYPE loyalty_tier AS ENUM ('bronze', 'silver', 'gold', 'platinum');
ALTER TABLE customers ADD COLUMN loyalty_tier loyalty_tier DEFAULT 'bronze';

-- Add comment
COMMENT ON COLUMN customers.loyalty_points IS 'Points earned from completed jobs';

-- ============================================================================
-- ROLLBACK SQL (for rollback.py)
-- ============================================================================
-- ROLLBACK: ALTER TABLE customers DROP COLUMN loyalty_tier;
-- ROLLBACK: DROP TYPE loyalty_tier;
-- ROLLBACK: DROP INDEX idx_customers_loyalty_points;
-- ROLLBACK: ALTER TABLE customers DROP COLUMN loyalty_points;

COMMIT;
```

## Best Practices

### 1. Always Use Transactions
Wrap all migrations in `BEGIN;` and `COMMIT;` blocks for atomicity.

### 2. Include Rollback SQL
Add rollback instructions as comments with `-- ROLLBACK:` prefix. The rollback tool will extract and execute these automatically.

### 3. Test Before Applying
```bash
# Test on a copy of the database
psql -d junkos_test -f migrations/20240206143000_add_loyalty.sql

# If successful, apply to main database
python ../migrate.py
```

### 4. Keep Migrations Small
One logical change per migration makes troubleshooting easier.

### 5. Data Migrations
When migrating data, be cautious with large tables:

```sql
-- Good: Batched update
UPDATE customers 
SET loyalty_tier = 'gold' 
WHERE total_spent > 10000 
  AND id IN (
    SELECT id FROM customers 
    WHERE total_spent > 10000 
    LIMIT 1000
  );

-- Bad: Single large update (locks table)
UPDATE customers SET loyalty_tier = 'gold' WHERE total_spent > 10000;
```

### 6. Backwards Compatibility
When possible, make changes backwards compatible:

```sql
-- Phase 1: Add new column (nullable)
ALTER TABLE users ADD COLUMN new_field VARCHAR(100);

-- Phase 2 (later migration): Make it required
-- ALTER TABLE users ALTER COLUMN new_field SET NOT NULL;
```

### 7. Index Creation
For large tables, create indexes concurrently to avoid locks:

```sql
CREATE INDEX CONCURRENTLY idx_customers_email ON customers(email);
```

## Common Migration Patterns

### Adding a Column
```sql
BEGIN;

ALTER TABLE customers ADD COLUMN referral_code VARCHAR(20) UNIQUE;
CREATE INDEX idx_customers_referral_code ON customers(referral_code);

-- ROLLBACK: DROP INDEX idx_customers_referral_code;
-- ROLLBACK: ALTER TABLE customers DROP COLUMN referral_code;

COMMIT;
```

### Adding a Table
```sql
BEGIN;

CREATE TABLE customer_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_notes_customer_id ON customer_notes(customer_id);

-- ROLLBACK: DROP TABLE customer_notes;

COMMIT;
```

### Adding a Foreign Key
```sql
BEGIN;

-- Add column first
ALTER TABLE jobs ADD COLUMN assigned_team_id UUID;

-- Add foreign key
ALTER TABLE jobs 
ADD CONSTRAINT fk_jobs_team 
FOREIGN KEY (assigned_team_id) 
REFERENCES teams(id) ON DELETE SET NULL;

CREATE INDEX idx_jobs_team_id ON jobs(assigned_team_id);

-- ROLLBACK: DROP INDEX idx_jobs_team_id;
-- ROLLBACK: ALTER TABLE jobs DROP CONSTRAINT fk_jobs_team;
-- ROLLBACK: ALTER TABLE jobs DROP COLUMN assigned_team_id;

COMMIT;
```

### Renaming a Column
```sql
BEGIN;

ALTER TABLE customers RENAME COLUMN phone TO phone_number;

-- ROLLBACK: ALTER TABLE customers RENAME COLUMN phone_number TO phone;

COMMIT;
```

### Adding an Enum Type
```sql
BEGIN;

CREATE TYPE job_complexity AS ENUM ('simple', 'moderate', 'complex');
ALTER TABLE jobs ADD COLUMN complexity job_complexity DEFAULT 'moderate';

-- ROLLBACK: ALTER TABLE jobs DROP COLUMN complexity;
-- ROLLBACK: DROP TYPE job_complexity;

COMMIT;
```

## Migration Checklist

Before applying a migration to production:

- [ ] Migration tested on development database
- [ ] Rollback SQL included and tested
- [ ] Large table changes use batching or CONCURRENTLY
- [ ] Backwards compatibility considered
- [ ] Database backup created
- [ ] Migration reviewed by another developer
- [ ] Downtime window scheduled (if required)

## Troubleshooting

### Migration Fails
1. Check PostgreSQL logs: `tail -f /var/log/postgresql/postgresql-*.log`
2. Verify syntax: `psql -d junkos -f migrations/failed_migration.sql`
3. Transaction is automatically rolled back on error

### Rollback Fails
1. Check if rollback SQL exists in migration file
2. Manually execute rollback SQL if needed
3. Remove migration from `schema_migrations` table manually if necessary

### Migration Stuck
```sql
-- Check for locks
SELECT * FROM pg_locks WHERE NOT granted;

-- Kill blocking queries (use with caution)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';
```

## Examples

See the main schema files for examples:
- `01_create_database.sql` - Database setup
- `02_schema.sql` - Initial schema
- `03_seed_data.sql` - Data insertion
- `04_views.sql` - View creation

---

**Ready to migrate?**
```bash
cd ..
python migrate.py --status   # Check what needs to run
python migrate.py            # Apply all pending migrations
```
