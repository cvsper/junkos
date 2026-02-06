# Junk Removal SaaS - Database Schema Design Guide

## Overview

This schema supports a multi-tenant SaaS platform for junk removal businesses with complete booking, dispatch, payment, and white-label branding capabilities.

## Key Design Patterns

### 1. Multi-Tenancy Strategy

**Pattern:** Shared database with tenant_id column (discriminator pattern)

**Rationale:**
- Cost-effective for SaaS with many small-medium tenants
- Easier to maintain than separate databases per tenant
- Better resource utilization
- Simpler backups and migrations

**Implementation:**
```sql
-- Every tenant-scoped table includes:
tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE

-- With composite indexes:
CREATE INDEX idx_jobs_tenant_id ON jobs(tenant_id) WHERE deleted_at IS NULL;

-- Row Level Security (RLS) enforces isolation:
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON jobs
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

**Application Layer:**
```javascript
// Set tenant context at connection/request level
await db.query("SET app.current_tenant_id = $1", [tenantId]);
```

---

### 2. Soft Deletes

**Pattern:** `deleted_at TIMESTAMP WITH TIME ZONE`

**Benefits:**
- Audit trail preservation
- Accidental deletion recovery
- Regulatory compliance (data retention)
- Customer history intact even after deletion

**Usage:**
```sql
-- Delete
UPDATE customers SET deleted_at = CURRENT_TIMESTAMP WHERE id = $1;

-- Query (always filter deleted records)
SELECT * FROM customers WHERE tenant_id = $1 AND deleted_at IS NULL;
```

---

### 3. Flexible Pricing Models

The `services` table supports multiple pricing strategies:

| Pricing Type | Use Case | Example |
|--------------|----------|---------|
| `fixed` | Flat rate services | $299 for standard pickup |
| `volume_based` | Per cubic yard | $50 per cubic yard |
| `hourly` | Time-based pricing | $100 per hour |
| `custom` | Quote required | Large commercial jobs |

**Example:**
```sql
INSERT INTO services (tenant_id, name, pricing_type, base_price, price_per_unit, unit_type)
VALUES 
  ($1, 'Standard Pickup', 'fixed', 299.00, NULL, NULL),
  ($1, 'Volume Removal', 'volume_based', 50.00, 50.00, 'cubic_yard'),
  ($1, 'Hourly Service', 'hourly', 100.00, 100.00, 'hour');
```

---

### 4. Job Workflow States

```
pending → confirmed → assigned → in_progress → completed
                                              → cancelled
```

**State Transitions:**
- `pending`: Customer booked, awaiting confirmation
- `confirmed`: Business accepted the booking
- `assigned`: Driver(s) assigned via `job_assignments`
- `in_progress`: Driver started the job (tracked in `actual_start_time`)
- `completed`: Job finished, ready for invoicing
- `cancelled`: Job cancelled by customer or business

---

### 5. Multi-Driver Support

**Pattern:** Many-to-many relationship via `job_assignments`

Jobs can have multiple crew members:
```sql
-- Assign a lead driver and helper
INSERT INTO job_assignments (tenant_id, job_id, user_id, role_in_job)
VALUES 
  ($1, $2, $3, 'lead'),    -- Lead driver
  ($1, $2, $4, 'helper');  -- Helper
```

---

### 6. Route Optimization

The `routes` table stores daily optimized schedules:

```sql
INSERT INTO routes (tenant_id, user_id, route_date, optimized_order)
VALUES ($1, $2, '2024-01-15', 
  '["uuid-job1", "uuid-job2", "uuid-job3"]'::jsonb
);
```

**Integration Points:**
- Use `latitude`/`longitude` from jobs table
- Integrate with Google Maps Directions API or similar
- Algorithm considerations: distance, time windows, job priority

---

### 7. White-Label Branding

**Storage:** JSONB column in `tenants` table

```json
{
  "logo_url": "https://cdn.example.com/logos/acme-junk.png",
  "primary_color": "#FF6B35",
  "secondary_color": "#004E89",
  "company_name": "Acme Junk Removal",
  "custom_domain": "www.acmejunk.com",
  "email_from_name": "Acme Support",
  "email_from_address": "support@acmejunk.com"
}
```

**Benefits:**
- Flexible schema (add new branding options without migrations)
- Easy to query specific properties: `branding_config->>'logo_url'`
- Supports varying tenant requirements

---

### 8. Payment Flow

```
Job Completed → Invoice Created → Payment(s) Received → Invoice Marked Paid
```

**Example Transaction:**
```sql
-- 1. Create invoice
INSERT INTO invoices (tenant_id, customer_id, job_id, invoice_number, 
                      subtotal, tax_amount, total_amount, amount_due, 
                      invoice_date, due_date, status)
VALUES ($1, $2, $3, 'INV-2024-0001', 500.00, 40.00, 540.00, 540.00,
        CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'sent');

-- 2. Add line items
INSERT INTO invoice_line_items (tenant_id, invoice_id, description, 
                                quantity, unit_price, total_price)
VALUES 
  ($1, $invoice_id, 'Junk Removal - 10 cubic yards', 10, 50.00, 500.00);

-- 3. Record payment
INSERT INTO payments (tenant_id, invoice_id, customer_id, 
                     payment_method, amount, transaction_id, processor)
VALUES ($1, $invoice_id, $2, 'credit_card', 540.00, 
        'ch_stripe123', 'stripe');

-- 4. Update invoice
UPDATE invoices 
SET amount_paid = 540.00, 
    amount_due = 0, 
    status = 'paid',
    paid_at = CURRENT_TIMESTAMP
WHERE id = $invoice_id;
```

---

### 9. Photo Management

**Design Decisions:**
- Store file metadata in database
- Actual files in S3/cloud storage
- Support multiple photo types per job
- Include geolocation for verification

**Implementation:**
```sql
-- Upload before photo
INSERT INTO photos (tenant_id, job_id, uploaded_by, photo_type,
                   file_path, file_url, latitude, longitude, taken_at)
VALUES ($1, $2, $driver_id, 'before',
        's3://bucket/photos/job123-before-1.jpg',
        'https://cdn.example.com/photos/job123-before-1.jpg',
        40.7128, -74.0060, CURRENT_TIMESTAMP);
```

---

### 10. User Roles & Permissions

| Role | Capabilities |
|------|--------------|
| **Admin** | Full access: settings, billing, users, all data |
| **Dispatcher** | Create jobs, assign drivers, view schedules, manage customers |
| **Driver** | View assigned jobs, update status, upload photos, record volumes |

**Application-level enforcement:**
```javascript
// Middleware example
function requireRole(allowedRoles) {
  return (req, res, next) => {
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
}

app.post('/api/jobs', requireRole(['admin', 'dispatcher']), createJob);
app.patch('/api/jobs/:id/status', requireRole(['driver', 'admin']), updateJobStatus);
```

---

## Common Query Patterns

### 1. Get Today's Jobs for a Driver

```sql
SELECT 
  j.id,
  j.job_number,
  j.scheduled_time_start,
  j.service_address_line1,
  j.service_city,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.phone AS customer_phone,
  j.items_description
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
INNER JOIN job_assignments ja ON j.id = ja.job_id
WHERE j.tenant_id = $1
  AND ja.user_id = $2
  AND j.scheduled_date = CURRENT_DATE
  AND j.status IN ('assigned', 'in_progress')
  AND j.deleted_at IS NULL
ORDER BY j.scheduled_time_start;
```

### 2. Find Nearby Available Drivers

```sql
-- Requires PostGIS or earthdistance extension
SELECT 
  u.id,
  u.first_name || ' ' || u.last_name AS driver_name,
  COUNT(ja.id) AS jobs_today
FROM users u
LEFT JOIN job_assignments ja ON u.id = ja.user_id 
  AND ja.assigned_at::date = CURRENT_DATE
WHERE u.tenant_id = $1
  AND u.role = 'driver'
  AND u.status = 'active'
  AND u.deleted_at IS NULL
GROUP BY u.id, u.first_name, u.last_name
HAVING COUNT(ja.id) < 5  -- Not overloaded
ORDER BY COUNT(ja.id);
```

### 3. Monthly Revenue Report

```sql
SELECT 
  DATE_TRUNC('month', i.invoice_date) AS month,
  COUNT(DISTINCT i.id) AS total_invoices,
  SUM(i.total_amount) AS total_billed,
  SUM(i.amount_paid) AS total_collected,
  SUM(i.amount_due) AS outstanding
FROM invoices i
WHERE i.tenant_id = $1
  AND i.invoice_date >= DATE_TRUNC('year', CURRENT_DATE)
  AND i.deleted_at IS NULL
GROUP BY DATE_TRUNC('month', i.invoice_date)
ORDER BY month DESC;
```

### 4. Customer Lifetime Value

```sql
SELECT 
  c.id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.total_jobs_completed,
  c.total_spent,
  AVG(j.customer_rating) AS avg_rating,
  MAX(j.scheduled_date) AS last_service_date
FROM customers c
LEFT JOIN jobs j ON c.id = j.customer_id AND j.status = 'completed'
WHERE c.tenant_id = $1
  AND c.deleted_at IS NULL
GROUP BY c.id, c.first_name, c.last_name, c.total_jobs_completed, c.total_spent
ORDER BY c.total_spent DESC
LIMIT 50;
```

### 5. Driver Performance Dashboard

```sql
SELECT 
  u.id,
  u.first_name || ' ' || u.last_name AS driver_name,
  COUNT(DISTINCT j.id) AS total_jobs,
  AVG(j.customer_rating) AS avg_rating,
  SUM(EXTRACT(EPOCH FROM (j.actual_end_time - j.actual_start_time))/3600) AS total_hours,
  COUNT(CASE WHEN j.status = 'completed' THEN 1 END) AS completed_jobs,
  COUNT(CASE WHEN j.actual_end_time <= (scheduled_date + scheduled_time_end) THEN 1 END) AS on_time_jobs
FROM users u
INNER JOIN job_assignments ja ON u.id = ja.user_id
INNER JOIN jobs j ON ja.job_id = j.id
WHERE u.tenant_id = $1
  AND u.role = 'driver'
  AND j.scheduled_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.id, u.first_name, u.last_name
ORDER BY avg_rating DESC;
```

---

## Indexing Strategy

### High-Priority Indexes (Already Included)

1. **Tenant isolation**: `(tenant_id)` on all tenant-scoped tables
2. **Foreign keys**: All FK columns for join performance
3. **Status filters**: `(tenant_id, status)` for workflow queries
4. **Date ranges**: `(tenant_id, scheduled_date)` for calendar views
5. **Geospatial**: GiST indexes on lat/long for routing

### When to Add More Indexes

Monitor slow queries with:
```sql
-- Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries > 1s

-- Analyze query plans
EXPLAIN ANALYZE SELECT ...;
```

Add indexes when you see sequential scans on large tables.

---

## Migration Strategy

### Initial Deployment

```bash
# 1. Run schema creation
psql -U postgres -d junk_removal -f junk_removal_schema.sql

# 2. Verify tables
psql -U postgres -d junk_removal -c "\dt"

# 3. Check indexes
psql -U postgres -d junk_removal -c "\di"
```

### Adding New Tenants

```sql
-- 1. Create tenant
INSERT INTO tenants (name, slug, contact_email)
VALUES ('Acme Junk Removal', 'acme-junk', 'admin@acmejunk.com')
RETURNING id;

-- 2. Create admin user
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role)
VALUES ($tenant_id, 'admin@acmejunk.com', $hashed_password, 'John', 'Doe', 'admin');

-- 3. Create default settings
INSERT INTO tenant_settings (tenant_id, business_hours)
VALUES ($tenant_id, '{
  "monday": {"open": "08:00", "close": "18:00"},
  "tuesday": {"open": "08:00", "close": "18:00"},
  "wednesday": {"open": "08:00", "close": "18:00"},
  "thursday": {"open": "08:00", "close": "18:00"},
  "friday": {"open": "08:00", "close": "18:00"},
  "saturday": {"open": "09:00", "close": "15:00"},
  "sunday": {"closed": true}
}'::jsonb);
```

---

## Performance Optimization Tips

### 1. Connection Pooling

Use connection pooling (PgBouncer, pg-pool) for multi-tenant SaaS to handle concurrent requests efficiently.

### 2. Partitioning (Future Scaling)

If a tenant grows very large, consider table partitioning:
```sql
-- Partition jobs by date range
CREATE TABLE jobs_2024_q1 PARTITION OF jobs
FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
```

### 3. Read Replicas

For reporting/analytics, use PostgreSQL read replicas to avoid impacting transactional performance.

### 4. Caching

Cache frequently-accessed data:
- Tenant branding config
- User permissions
- Active jobs count

### 5. Archive Old Data

Move completed jobs older than 2 years to archive tables:
```sql
CREATE TABLE jobs_archive (LIKE jobs INCLUDING ALL);

-- Move old records
INSERT INTO jobs_archive SELECT * FROM jobs 
WHERE status = 'completed' 
  AND scheduled_date < CURRENT_DATE - INTERVAL '2 years';

DELETE FROM jobs 
WHERE status = 'completed' 
  AND scheduled_date < CURRENT_DATE - INTERVAL '2 years';
```

---

## Security Considerations

### 1. Row Level Security (RLS)

Enforce tenant isolation at the database level:
```sql
-- Application sets tenant context
SET app.current_tenant_id = 'uuid-of-tenant';

-- RLS policy blocks cross-tenant access automatically
```

### 2. Password Hashing

Never store plain passwords. Use bcrypt:
```javascript
const bcrypt = require('bcrypt');
const hashedPassword = await bcrypt.hash(plainPassword, 10);
```

### 3. API Key Storage

Store integration API keys encrypted:
```sql
-- Use pgcrypto extension
CREATE EXTENSION pgcrypto;

-- Encrypt before storing
UPDATE tenant_settings 
SET integrations = integrations || jsonb_build_object(
  'stripe_api_key', 
  pgp_sym_encrypt('sk_live_...', current_setting('app.encryption_key'))
);
```

### 4. SQL Injection Prevention

Always use parameterized queries:
```javascript
// ✅ Good
db.query('SELECT * FROM jobs WHERE id = $1', [jobId]);

// ❌ Bad
db.query(`SELECT * FROM jobs WHERE id = '${jobId}'`);
```

---

## Testing Recommendations

### 1. Unit Tests

Test critical business logic:
- Invoice calculation
- Payment allocation
- Job status transitions

### 2. Integration Tests

Test multi-step workflows:
- Book job → assign driver → complete → invoice → payment
- Multi-driver assignments
- Route optimization

### 3. Load Testing

Simulate concurrent tenants:
```bash
# Using Apache Bench
ab -n 10000 -c 100 https://api.example.com/jobs
```

### 4. Tenant Isolation Testing

Verify RLS policies prevent cross-tenant data leakage:
```sql
-- Set tenant A context
SET app.current_tenant_id = 'tenant-a-uuid';
SELECT * FROM jobs; -- Should only see tenant A jobs

-- Attempt to access tenant B job directly
SELECT * FROM jobs WHERE id = 'tenant-b-job-uuid'; -- Should return 0 rows
```

---

## Monitoring & Maintenance

### Key Metrics to Track

1. **Query Performance**
   - Slow query log (> 1s)
   - Most frequent queries
   - Index usage

2. **Database Size**
   - Per-tenant storage usage
   - Growth rate
   - Table bloat

3. **Connection Pool**
   - Active connections
   - Wait times
   - Connection errors

### Regular Maintenance

```sql
-- Weekly vacuum analyze
VACUUM ANALYZE;

-- Check table bloat
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Rebuild indexes if needed
REINDEX TABLE jobs;
```

---

## Next Steps

1. **Application Layer**
   - Implement authentication (JWT, session-based)
   - Build API endpoints (REST or GraphQL)
   - Set up tenant context middleware

2. **Integrations**
   - Payment processors (Stripe, Square)
   - SMS notifications (Twilio)
   - Email service (SendGrid, AWS SES)
   - Geocoding API (Google Maps, Mapbox)

3. **Frontend**
   - Admin dashboard (job management, scheduling)
   - Driver mobile app (job tracking, photos)
   - Customer booking portal

4. **DevOps**
   - Set up CI/CD pipeline
   - Database backups (automated daily)
   - Monitoring (Datadog, New Relic)
   - Error tracking (Sentry)

---

## Questions & Support

This schema is production-ready but should be adapted to your specific business requirements. Consider:

- Do you need recurring service bookings?
- Should customers have accounts or book as guests?
- Do you need equipment tracking (trucks, tools)?
- Should you support subcontractors?
- Do you need multi-location support per tenant?

Feel free to extend the schema as your business grows!
