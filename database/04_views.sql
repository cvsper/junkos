-- ============================================================================
-- JunkOS Database Views
-- ============================================================================
-- Purpose: Create useful views for common queries and reporting
-- Usage: psql -U postgres -d junkos -f 04_views.sql
-- ============================================================================

\c junkos

BEGIN;

-- ============================================================================
-- OPERATIONAL VIEWS
-- ============================================================================

-- View: Active jobs with full details
CREATE OR REPLACE VIEW v_active_jobs AS
SELECT 
    j.id,
    j.tenant_id,
    j.job_number,
    j.status,
    j.priority,
    j.scheduled_date,
    j.scheduled_time_start,
    j.scheduled_time_end,
    
    -- Customer info
    c.id AS customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.phone AS customer_phone,
    c.email AS customer_email,
    
    -- Service info
    s.id AS service_id,
    s.name AS service_name,
    s.pricing_type,
    
    -- Location
    j.service_address_line1,
    j.service_address_line2,
    j.service_city,
    j.service_state,
    j.service_postal_code,
    j.latitude,
    j.longitude,
    
    -- Job details
    j.items_description,
    j.special_instructions,
    j.estimated_volume,
    
    -- Assigned drivers (aggregated)
    STRING_AGG(
        DISTINCT u.first_name || ' ' || u.last_name, 
        ', ' 
        ORDER BY u.first_name || ' ' || u.last_name
    ) AS assigned_drivers,
    COUNT(DISTINCT ja.user_id) AS driver_count,
    
    -- Timestamps
    j.created_at,
    j.updated_at
    
FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
LEFT JOIN services s ON j.service_id = s.id
LEFT JOIN job_assignments ja ON j.id = ja.job_id AND ja.status IN ('assigned', 'accepted')
LEFT JOIN users u ON ja.user_id = u.id AND u.role = 'driver'

WHERE j.deleted_at IS NULL
    AND j.status NOT IN ('completed', 'cancelled')
    
GROUP BY 
    j.id, c.id, c.first_name, c.last_name, c.phone, c.email,
    s.id, s.name, s.pricing_type;

COMMENT ON VIEW v_active_jobs IS 'Active jobs (not completed/cancelled) with customer, service, and driver info';

-- ============================================================================

-- View: Driver schedule - shows what each driver has on their plate
CREATE OR REPLACE VIEW v_driver_schedule AS
SELECT 
    u.id AS driver_id,
    u.tenant_id,
    u.first_name || ' ' || u.last_name AS driver_name,
    u.phone AS driver_phone,
    u.status AS driver_status,
    
    j.id AS job_id,
    j.job_number,
    j.status AS job_status,
    j.scheduled_date,
    j.scheduled_time_start,
    j.scheduled_time_end,
    
    c.first_name || ' ' || c.last_name AS customer_name,
    c.phone AS customer_phone,
    
    j.service_address_line1,
    j.service_city,
    j.service_state,
    j.latitude,
    j.longitude,
    
    ja.status AS assignment_status,
    ja.assigned_at,
    ja.accepted_at,
    
    s.name AS service_name,
    j.estimated_duration_minutes

FROM users u
LEFT JOIN job_assignments ja ON u.id = ja.user_id AND ja.status IN ('assigned', 'accepted')
LEFT JOIN jobs j ON ja.job_id = j.id AND j.deleted_at IS NULL
LEFT JOIN customers c ON j.customer_id = c.id
LEFT JOIN services s ON j.service_id = s.id

WHERE u.role = 'driver'
    AND u.deleted_at IS NULL
    AND (j.status IS NULL OR j.status NOT IN ('completed', 'cancelled'))
    
ORDER BY u.last_name, u.first_name, j.scheduled_date, j.scheduled_time_start;

COMMENT ON VIEW v_driver_schedule IS 'Shows all drivers and their assigned jobs';

-- ============================================================================

-- View: Outstanding invoices with urgency flags
CREATE OR REPLACE VIEW v_outstanding_invoices AS
SELECT 
    i.id,
    i.tenant_id,
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    i.status,
    
    -- Amounts
    i.total_amount,
    i.amount_paid,
    i.amount_due,
    
    -- Days overdue
    CASE 
        WHEN i.due_date < CURRENT_DATE 
        THEN CURRENT_DATE - i.due_date 
        ELSE 0 
    END AS days_overdue,
    
    -- Urgency classification
    CASE 
        WHEN i.due_date < CURRENT_DATE THEN 'overdue'
        WHEN i.due_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'due_soon'
        WHEN i.due_date <= CURRENT_DATE + INTERVAL '14 days' THEN 'upcoming'
        ELSE 'pending'
    END AS urgency,
    
    -- Customer info
    c.id AS customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.email AS customer_email,
    c.phone AS customer_phone,
    
    -- Job reference
    j.id AS job_id,
    j.job_number,
    
    i.notes,
    i.created_at

FROM invoices i
INNER JOIN customers c ON i.customer_id = c.id
LEFT JOIN jobs j ON i.job_id = j.id

WHERE i.deleted_at IS NULL
    AND i.status IN ('sent', 'overdue')
    AND i.amount_due > 0
    
ORDER BY 
    CASE 
        WHEN i.due_date < CURRENT_DATE THEN 0
        WHEN i.due_date <= CURRENT_DATE + INTERVAL '7 days' THEN 1
        ELSE 2
    END,
    i.due_date;

COMMENT ON VIEW v_outstanding_invoices IS 'Unpaid invoices with urgency flags and days overdue';

-- ============================================================================

-- View: Customer summary - lifetime value, job count, etc.
CREATE OR REPLACE VIEW v_customer_summary AS
SELECT 
    c.id,
    c.tenant_id,
    c.first_name,
    c.last_name,
    c.first_name || ' ' || c.last_name AS full_name,
    c.email,
    c.phone,
    c.city,
    c.state,
    
    -- Job statistics
    COUNT(DISTINCT j.id) AS total_jobs,
    COUNT(DISTINCT CASE WHEN j.status = 'completed' THEN j.id END) AS completed_jobs,
    COUNT(DISTINCT CASE WHEN j.status IN ('pending', 'confirmed', 'assigned', 'in_progress') THEN j.id END) AS active_jobs,
    
    -- Financial statistics
    COALESCE(SUM(CASE WHEN i.status = 'paid' THEN i.total_amount ELSE 0 END), 0) AS lifetime_value,
    COALESCE(SUM(CASE WHEN i.status IN ('sent', 'overdue') THEN i.amount_due ELSE 0 END), 0) AS outstanding_balance,
    
    -- Rating
    c.rating AS average_rating,
    
    -- Activity
    MAX(j.scheduled_date) AS last_job_date,
    c.created_at AS customer_since,
    
    -- Flags
    c.marketing_opt_in,
    CASE 
        WHEN MAX(j.scheduled_date) < CURRENT_DATE - INTERVAL '6 months' THEN true 
        ELSE false 
    END AS inactive_customer

FROM customers c
LEFT JOIN jobs j ON c.id = j.customer_id AND j.deleted_at IS NULL
LEFT JOIN invoices i ON c.id = i.customer_id AND i.deleted_at IS NULL

WHERE c.deleted_at IS NULL

GROUP BY c.id

ORDER BY lifetime_value DESC;

COMMENT ON VIEW v_customer_summary IS 'Customer lifetime value, job counts, and activity summary';

-- ============================================================================

-- View: Daily revenue summary
CREATE OR REPLACE VIEW v_daily_revenue AS
SELECT 
    i.tenant_id,
    i.invoice_date AS date,
    
    -- Invoice counts
    COUNT(DISTINCT i.id) AS invoices_issued,
    COUNT(DISTINCT CASE WHEN i.status = 'paid' THEN i.id END) AS invoices_paid,
    
    -- Revenue
    COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
    COALESCE(SUM(CASE WHEN i.status = 'paid' THEN i.total_amount ELSE 0 END), 0) AS total_collected,
    COALESCE(SUM(CASE WHEN i.status IN ('sent', 'overdue') THEN i.amount_due ELSE 0 END), 0) AS total_outstanding,
    
    -- Breakdown
    COALESCE(SUM(i.subtotal), 0) AS subtotal,
    COALESCE(SUM(i.tax_amount), 0) AS tax_collected,
    COALESCE(SUM(i.dump_fee), 0) AS dump_fees,
    COALESCE(SUM(i.discount_amount), 0) AS discounts_given

FROM invoices i

WHERE i.deleted_at IS NULL

GROUP BY i.tenant_id, i.invoice_date

ORDER BY i.invoice_date DESC;

COMMENT ON VIEW v_daily_revenue IS 'Daily revenue breakdown by tenant';

-- ============================================================================

-- View: Job completion metrics
CREATE OR REPLACE VIEW v_job_metrics AS
SELECT 
    j.tenant_id,
    DATE(j.scheduled_date) AS job_date,
    
    -- Job counts by status
    COUNT(*) AS total_jobs,
    COUNT(CASE WHEN j.status = 'completed' THEN 1 END) AS completed_jobs,
    COUNT(CASE WHEN j.status = 'cancelled' THEN 1 END) AS cancelled_jobs,
    COUNT(CASE WHEN j.status IN ('pending', 'confirmed') THEN 1 END) AS pending_jobs,
    COUNT(CASE WHEN j.status IN ('assigned', 'in_progress') THEN 1 END) AS in_progress_jobs,
    
    -- Completion rate
    ROUND(
        100.0 * COUNT(CASE WHEN j.status = 'completed' THEN 1 END)::DECIMAL / 
        NULLIF(COUNT(CASE WHEN j.status IN ('completed', 'cancelled') THEN 1 END), 0),
        2
    ) AS completion_rate_pct,
    
    -- Volume metrics
    COALESCE(AVG(j.actual_volume), 0) AS avg_volume_completed,
    COALESCE(SUM(j.actual_volume), 0) AS total_volume_completed,
    
    -- Customer satisfaction
    COALESCE(AVG(j.customer_rating), 0) AS avg_rating,
    COUNT(CASE WHEN j.customer_rating >= 4 THEN 1 END) AS high_rated_jobs,
    
    -- Timing
    AVG(
        EXTRACT(EPOCH FROM (j.actual_end_time - j.actual_start_time)) / 60
    ) AS avg_duration_minutes

FROM jobs j

WHERE j.deleted_at IS NULL

GROUP BY j.tenant_id, DATE(j.scheduled_date)

ORDER BY job_date DESC;

COMMENT ON VIEW v_job_metrics IS 'Daily job completion metrics and KPIs';

-- ============================================================================

-- View: Driver performance
CREATE OR REPLACE VIEW v_driver_performance AS
SELECT 
    u.id AS driver_id,
    u.tenant_id,
    u.first_name || ' ' || u.last_name AS driver_name,
    u.email,
    u.phone,
    u.status,
    
    -- Job statistics
    COUNT(DISTINCT ja.job_id) AS total_jobs_assigned,
    COUNT(DISTINCT CASE WHEN j.status = 'completed' THEN ja.job_id END) AS jobs_completed,
    COUNT(DISTINCT CASE WHEN ja.status = 'rejected' THEN ja.job_id END) AS jobs_rejected,
    
    -- Completion rate
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN j.status = 'completed' THEN ja.job_id END)::DECIMAL /
        NULLIF(COUNT(DISTINCT ja.job_id), 0),
        2
    ) AS completion_rate_pct,
    
    -- Customer satisfaction
    COALESCE(AVG(j.customer_rating), 0) AS avg_customer_rating,
    COUNT(CASE WHEN j.customer_rating = 5 THEN 1 END) AS five_star_jobs,
    
    -- Volume handled
    COALESCE(SUM(j.actual_volume), 0) AS total_volume_hauled,
    
    -- Activity
    MIN(ja.assigned_at) AS first_job_date,
    MAX(ja.assigned_at) AS last_job_date,
    MAX(u.last_login_at) AS last_login

FROM users u
LEFT JOIN job_assignments ja ON u.id = ja.user_id
LEFT JOIN jobs j ON ja.job_id = j.id AND j.deleted_at IS NULL

WHERE u.role = 'driver'
    AND u.deleted_at IS NULL

GROUP BY u.id

ORDER BY jobs_completed DESC, avg_customer_rating DESC;

COMMENT ON VIEW v_driver_performance IS 'Driver performance metrics - completion rates, ratings, volume';

-- ============================================================================

-- View: Upcoming schedule (next 7 days)
CREATE OR REPLACE VIEW v_upcoming_schedule AS
SELECT 
    j.tenant_id,
    j.scheduled_date,
    j.scheduled_time_start,
    j.job_number,
    j.status,
    j.priority,
    
    c.first_name || ' ' || c.last_name AS customer_name,
    c.phone AS customer_phone,
    
    j.service_address_line1 || ', ' || j.service_city AS service_address,
    j.items_description,
    
    s.name AS service_name,
    s.estimated_duration_minutes,
    
    STRING_AGG(
        u.first_name || ' ' || u.last_name, 
        ', '
    ) AS assigned_drivers,
    
    j.special_instructions,
    j.access_instructions

FROM jobs j
INNER JOIN customers c ON j.customer_id = c.id
LEFT JOIN services s ON j.service_id = s.id
LEFT JOIN job_assignments ja ON j.id = ja.job_id AND ja.status IN ('assigned', 'accepted')
LEFT JOIN users u ON ja.user_id = u.id

WHERE j.deleted_at IS NULL
    AND j.scheduled_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
    AND j.status NOT IN ('completed', 'cancelled')

GROUP BY 
    j.id, j.tenant_id, j.scheduled_date, j.scheduled_time_start, j.job_number,
    j.status, j.priority, c.first_name, c.last_name, c.phone,
    j.service_address_line1, j.service_city, j.items_description,
    s.name, s.estimated_duration_minutes, j.special_instructions, j.access_instructions

ORDER BY j.scheduled_date, j.scheduled_time_start NULLS LAST;

COMMENT ON VIEW v_upcoming_schedule IS 'Jobs scheduled for the next 7 days';

-- ============================================================================

-- View: Payment history with invoice details
CREATE OR REPLACE VIEW v_payment_history AS
SELECT 
    p.id AS payment_id,
    p.tenant_id,
    p.payment_date,
    p.amount,
    p.payment_method,
    p.payment_status,
    p.reference_number,
    
    i.id AS invoice_id,
    i.invoice_number,
    i.total_amount AS invoice_total,
    
    c.id AS customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.email AS customer_email,
    c.phone AS customer_phone,
    
    j.job_number,
    
    p.processor,
    p.transaction_id,
    
    CASE 
        WHEN p.refunded_at IS NOT NULL THEN 'refunded'
        ELSE p.payment_status
    END AS effective_status,
    
    p.refund_amount,
    p.refund_reason,
    p.notes

FROM payments p
INNER JOIN invoices i ON p.invoice_id = i.id
INNER JOIN customers c ON p.customer_id = c.id
LEFT JOIN jobs j ON i.job_id = j.id

ORDER BY p.payment_date DESC, p.created_at DESC;

COMMENT ON VIEW v_payment_history IS 'Complete payment history with invoice and customer details';

-- ============================================================================

-- View: Tenant health dashboard
CREATE OR REPLACE VIEW v_tenant_dashboard AS
SELECT 
    t.id AS tenant_id,
    t.name AS tenant_name,
    t.slug,
    t.status AS tenant_status,
    t.subscription_tier,
    
    -- User counts
    (SELECT COUNT(*) FROM users u WHERE u.tenant_id = t.id AND u.deleted_at IS NULL) AS total_users,
    (SELECT COUNT(*) FROM users u WHERE u.tenant_id = t.id AND u.role = 'driver' AND u.deleted_at IS NULL) AS total_drivers,
    
    -- Customer count
    (SELECT COUNT(*) FROM customers c WHERE c.tenant_id = t.id AND c.deleted_at IS NULL) AS total_customers,
    
    -- Job statistics (all time)
    (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.deleted_at IS NULL) AS total_jobs,
    (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status = 'completed' AND j.deleted_at IS NULL) AS completed_jobs,
    
    -- Jobs this month
    (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.scheduled_date >= DATE_TRUNC('month', CURRENT_DATE) AND j.deleted_at IS NULL) AS jobs_this_month,
    
    -- Revenue this month
    (SELECT COALESCE(SUM(i.total_amount), 0) FROM invoices i WHERE i.tenant_id = t.id AND i.invoice_date >= DATE_TRUNC('month', CURRENT_DATE) AND i.deleted_at IS NULL) AS revenue_this_month,
    
    -- Outstanding balance
    (SELECT COALESCE(SUM(i.amount_due), 0) FROM invoices i WHERE i.tenant_id = t.id AND i.status IN ('sent', 'overdue') AND i.deleted_at IS NULL) AS outstanding_balance,
    
    -- Activity
    t.created_at AS tenant_since,
    t.subscription_started_at,
    t.trial_ends_at

FROM tenants t

WHERE t.deleted_at IS NULL

ORDER BY t.name;

COMMENT ON VIEW v_tenant_dashboard IS 'High-level tenant health metrics and key statistics';

COMMIT;

-- Display success message
DO $$
DECLARE
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public'
        AND table_name LIKE 'v_%';
    
    RAISE NOTICE '✓ Database views created successfully';
    RAISE NOTICE '  → % views available', view_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Available views:';
    RAISE NOTICE '  • v_active_jobs - Active jobs with customer and driver info';
    RAISE NOTICE '  • v_driver_schedule - Driver assignments and schedules';
    RAISE NOTICE '  • v_outstanding_invoices - Unpaid invoices with urgency';
    RAISE NOTICE '  • v_customer_summary - Customer lifetime value and stats';
    RAISE NOTICE '  • v_daily_revenue - Daily revenue breakdown';
    RAISE NOTICE '  • v_job_metrics - Job completion metrics and KPIs';
    RAISE NOTICE '  • v_driver_performance - Driver performance statistics';
    RAISE NOTICE '  • v_upcoming_schedule - Jobs in next 7 days';
    RAISE NOTICE '  • v_payment_history - Payment transaction history';
    RAISE NOTICE '  • v_tenant_dashboard - Tenant health dashboard';
    RAISE NOTICE '';
    RAISE NOTICE '→ Database initialization complete!';
END $$;
