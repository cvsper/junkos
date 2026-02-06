# Database Entity Relationship Diagram

## Core Entity Relationships

```
┌─────────────────┐
│    TENANTS      │ (Root entity - multi-tenant isolation)
│─────────────────│
│ id (PK)         │
│ name            │
│ slug            │
│ branding_config │ ← White-label branding (JSONB)
│ subscription... │
└────────┬────────┘
         │
         │ (All entities reference tenant_id for isolation)
         │
    ┌────┴────────────────────────────────────────┐
    │                                             │
    ▼                                             ▼
┌─────────────────┐                    ┌─────────────────┐
│     USERS       │                    │   CUSTOMERS     │
│─────────────────│                    │─────────────────│
│ id (PK)         │                    │ id (PK)         │
│ tenant_id (FK)  │                    │ tenant_id (FK)  │
│ email           │                    │ first_name      │
│ role            │ ← admin/dispatch/  │ last_name       │
│ password_hash   │   driver           │ phone           │
│ driver_license  │                    │ address         │
│ vehicle_info    │                    │ lat/long        │ ← For routing
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │                                      │
         │                   ┌──────────────────┘
         │                   │
         │                   │
         │              ┌────▼────────┐
         │              │    JOBS     │ ← Core booking entity
         │              │─────────────│
         │              │ id (PK)     │
         │              │ tenant_id   │
         │         ┌────│ customer_id │ (FK to customers)
         │         │    │ service_id  │ (FK to services)
         │         │    │ job_number  │
         │         │    │ status      │ ← pending/confirmed/assigned/in_progress/completed
         │         │    │ scheduled_  │
         │         │    │   date/time │
         │         │    │ service_    │
         │         │    │   address   │
         │         │    │ lat/long    │ ← For routing
         │         │    │ items_desc  │
         │         │    └─────┬───────┘
         │         │          │
         │         │          │
         │    ┌────┴──────────┴─────┬─────────────┬────────────┐
         │    │                     │             │            │
         │    ▼                     ▼             ▼            ▼
         │ ┌─────────────┐   ┌─────────────┐ ┌────────┐  ┌──────────┐
         │ │ JOB_        │   │  INVOICES   │ │ PHOTOS │  │ ACTIVITY │
         │ │ ASSIGNMENTS │   │─────────────│ │────────│  │ LOG      │
         │ │─────────────│   │ id (PK)     │ │ id     │  │──────────│
         └─│ user_id (FK)│   │ tenant_id   │ │ job_id │  │ entity_  │
           │ job_id (FK) │   │ customer_id │ │ type   │  │   type   │
           │ role_in_job │   │ job_id      │ │ file_  │  │ entity_id│
           │ status      │   │ invoice_#   │ │   path │  │ action   │
           └──────┬──────┘   │ total_amt   │ │ url    │  │ changes  │
                  │          │ amount_due  │ └────────┘  └──────────┘
                  │          └──────┬──────┘
                  │                 │
                  │            ┌────┴────────┐
                  │            │             │
                  │            ▼             ▼
                  │     ┌─────────────┐ ┌─────────┐
                  │     │ INVOICE_    │ │ PAYMENTS│
                  │     │ LINE_ITEMS  │ │─────────│
                  │     │─────────────│ │ id (PK) │
                  │     │ invoice_id  │ │ invoice │
                  │     │ description │ │   _id   │
                  │     │ quantity    │ │ amount  │
                  │     │ unit_price  │ │ method  │
                  │     └─────────────┘ │ trans_id│
                  │                     │ status  │
                  │                     └─────────┘
                  │
                  ▼
           ┌─────────────┐
           │   ROUTES    │ ← Daily driver schedules
           │─────────────│
           │ id (PK)     │
           │ tenant_id   │
           │ user_id (FK)│ ← Driver
           │ route_date  │
           │ optimized_  │ ← Job IDs in order (JSONB array)
           │   order     │
           │ total_miles │
           └─────────────┘


┌─────────────────┐
│    SERVICES     │ ← Service catalog
│─────────────────│
│ id (PK)         │
│ tenant_id (FK)  │
│ name            │
│ description     │
│ pricing_type    │ ← fixed/volume_based/hourly/custom
│ base_price      │
│ price_per_unit  │
└─────────────────┘


┌──────────────────┐
│ TENANT_SETTINGS  │ ← Operational config per tenant
│──────────────────│
│ id (PK)          │
│ tenant_id (FK)   │
│ business_hours   │ (JSONB)
│ service_area_... │
│ tax_rate         │
│ integrations     │ (JSONB) ← API keys for Stripe, Twilio, etc.
└──────────────────┘


┌──────────────────┐
│ NOTIFICATIONS    │ ← In-app notifications
│──────────────────│
│ id (PK)          │
│ tenant_id (FK)   │
│ user_id (FK)     │
│ type             │
│ title/message    │
│ read_at          │
└──────────────────┘
```

---

## Key Relationships Explained

### 1. Tenant → Everything
Every table (except `tenants` itself) has `tenant_id` for multi-tenant isolation.

### 2. Customer → Jobs (One-to-Many)
A customer can have multiple bookings over time.

### 3. Jobs → Job Assignments (One-to-Many)
A single job can be assigned to multiple drivers (crew support).

### 4. User (Driver) → Job Assignments (One-to-Many)
A driver can have multiple jobs assigned.

### 5. Jobs → Invoices (One-to-Many*)
Typically one invoice per job, but supports multiple (e.g., deposits, final bill).

### 6. Invoices → Payments (One-to-Many)
Invoices can have partial payments from multiple transactions.

### 7. Jobs → Photos (One-to-Many)
Multiple before/after photos per job.

### 8. User (Driver) → Routes (One-to-Many)
Each driver has a route per day with optimized job sequence.

---

## Cardinality Summary

| Relationship | Type | Cardinality |
|--------------|------|-------------|
| Tenant → Users | 1:N | One tenant has many users |
| Tenant → Customers | 1:N | One tenant has many customers |
| Customer → Jobs | 1:N | One customer books many jobs |
| Job → Job Assignments | 1:N | One job can have multiple drivers |
| User (Driver) → Job Assignments | 1:N | One driver handles many jobs |
| Job → Photos | 1:N | One job has many photos |
| Job → Invoices | 1:N | One job can have multiple invoices |
| Invoice → Payments | 1:N | One invoice can have multiple payments |
| Invoice → Line Items | 1:N | One invoice has multiple line items |
| User (Driver) → Routes | 1:N | One driver has many routes (one per day) |
| Tenant → Services | 1:N | One tenant offers many service types |
| Tenant → Settings | 1:1 | One tenant has one settings record |

---

## Workflow Data Flow

### Booking to Completion Flow

```
1. CUSTOMER books a job
   └─> INSERT INTO jobs (customer_id, status='pending', ...)

2. ADMIN/DISPATCHER confirms
   └─> UPDATE jobs SET status='confirmed'

3. DISPATCHER assigns DRIVER(s)
   └─> INSERT INTO job_assignments (job_id, user_id, ...)
   └─> UPDATE jobs SET status='assigned'

4. DRIVER accepts and starts job
   └─> UPDATE job_assignments SET status='accepted'
   └─> UPDATE jobs SET status='in_progress', actual_start_time=NOW()

5. DRIVER uploads photos during job
   └─> INSERT INTO photos (job_id, photo_type='before', ...)
   └─> INSERT INTO photos (job_id, photo_type='after', ...)

6. DRIVER completes job
   └─> UPDATE jobs SET status='completed', actual_end_time=NOW(), actual_volume=X

7. SYSTEM generates invoice
   └─> INSERT INTO invoices (job_id, customer_id, total_amount=X, status='sent')
   └─> INSERT INTO invoice_line_items (invoice_id, description, ...)

8. CUSTOMER makes payment
   └─> INSERT INTO payments (invoice_id, amount=X, payment_method='credit_card')
   └─> UPDATE invoices SET amount_paid=X, status='paid'

9. SYSTEM logs all changes
   └─> INSERT INTO activity_log (entity_type='jobs', action='status_changed', ...)
```

---

## Index Strategy Visualization

### High-Traffic Query Patterns

```
Query: Get today's jobs for a driver
├─ INDEX: job_assignments(tenant_id, user_id, assigned_at)
└─ INDEX: jobs(tenant_id, scheduled_date, status)

Query: Find customer by phone
└─ INDEX: customers(tenant_id, phone)

Query: Outstanding invoices
├─ INDEX: invoices(tenant_id, status, due_date)
└─ INDEX: invoices(tenant_id, customer_id)

Query: Search jobs by address/description
└─ INDEX: jobs GIN full-text search

Query: Route optimization (nearby jobs)
└─ INDEX: jobs GiST spatial (lat/long)
```

---

## Multi-Tenancy Isolation Layers

```
┌─────────────────────────────────────────┐
│   Application Layer                     │
│   - Set tenant context on each request  │ ← req.user.tenantId
│   - Middleware validates tenant access  │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│   ORM/Query Layer                       │
│   - Auto-inject tenant_id in queries    │ ← WHERE tenant_id = $1
│   - Validate all FK references          │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│   Database Layer (Row Level Security)   │
│   - RLS policies enforce isolation      │ ← CREATE POLICY ...
│   - Block cross-tenant queries at DB    │
└─────────────────────────────────────────┘
```

### Defense in Depth

1. **Application**: Tenant context validation
2. **ORM**: Automatic tenant_id filtering
3. **Database**: RLS as last line of defense

---

## Scalability Considerations

### Horizontal Scaling Options

```
Current: Single database with tenant_id
         ├─ Works for: 100-1000 tenants
         └─ Limit: Shared resources

Option 1: Schema-per-tenant
         ├─ CREATE SCHEMA tenant_abc;
         ├─ Better isolation
         └─ Harder to maintain

Option 2: Database-per-tenant
         ├─ Complete isolation
         ├─ Best for enterprise clients
         └─ Higher infrastructure cost

Option 3: Hybrid (tenant tiers)
         ├─ Enterprise → Dedicated DB
         ├─ Pro → Dedicated schema
         └─ Basic → Shared DB (current design)
```

### Table Partitioning (Future)

For high-volume tables, consider partitioning:

```sql
-- Partition jobs by date
CREATE TABLE jobs (
  ...
) PARTITION BY RANGE (scheduled_date);

CREATE TABLE jobs_2024_q1 PARTITION OF jobs
  FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');

CREATE TABLE jobs_2024_q2 PARTITION OF jobs
  FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');

-- OR partition by tenant_id for very large multi-tenant systems
CREATE TABLE jobs (
  ...
) PARTITION BY LIST (tenant_id);
```

---

## Summary Statistics

### Schema Metrics

- **Total Tables**: 18
- **Core Entities**: 6 (tenants, users, customers, jobs, invoices, payments)
- **Supporting Tables**: 12
- **Views**: 2 (active_jobs, outstanding_invoices)
- **Indexes**: 50+ (covering tenant isolation, FKs, spatial, full-text)
- **Triggers**: 10 (automatic updated_at timestamps)

### Storage Estimates (per 1,000 jobs/month)

| Table | Rows/Month | Est. Size |
|-------|------------|-----------|
| jobs | 1,000 | ~500 KB |
| job_assignments | 1,500 | ~200 KB |
| photos | 4,000 | ~100 KB* |
| invoices | 1,000 | ~300 KB |
| payments | 1,200 | ~200 KB |
| activity_log | 10,000 | ~2 MB |

*Metadata only; actual photo files stored in S3

**Yearly estimate**: ~50 MB per 1,000 jobs/month (metadata only)

---

## Quick Reference: Status Fields

### Job Status Values
- `pending` - Customer booked, awaiting confirmation
- `confirmed` - Business accepted booking
- `assigned` - Driver(s) assigned
- `in_progress` - Job actively being worked on
- `completed` - Finished successfully
- `cancelled` - Cancelled by customer or business

### Invoice Status Values
- `draft` - Being prepared, not sent yet
- `sent` - Sent to customer
- `paid` - Fully paid
- `overdue` - Past due date, not paid
- `cancelled` - Voided invoice

### Payment Status Values
- `pending` - Payment initiated, not confirmed
- `completed` - Successfully processed
- `failed` - Payment failed
- `refunded` - Payment was refunded

### User Status Values
- `active` - Can log in and work
- `inactive` - Temporarily disabled
- `suspended` - Blocked due to policy violation

---

This ERD provides a complete overview of the database structure. Use it alongside the SQL schema file for implementation!
