#!/usr/bin/env python3
"""
Umuve Database Migration Script

Handles column additions to existing tables and creation of new tables
that db.create_all() won't add to already-existing tables.

Usage:
    python migrate.py          # standalone
    flask db-migrate           # via Flask CLI (registered in server.py)

Safe to run multiple times (idempotent).
Supports both SQLite and PostgreSQL.
"""

import os
import sys
from textwrap import dedent

# ---------------------------------------------------------------------------
# Resolve database URL
# ---------------------------------------------------------------------------

def _resolve_database_url():
    """Return the SQLAlchemy-compatible database URL."""
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # Fix Heroku/Render-style postgres:// -> postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return "sqlite:///umuve.db"


def _is_sqlite(url):
    return url.startswith("sqlite")


# ---------------------------------------------------------------------------
# Column migration definitions
# ---------------------------------------------------------------------------
# Each entry: (table, column, sql_type_sqlite, sql_type_pg, default_expr | None)
# default_expr is a SQL literal (e.g. "''" or "0.0" or "FALSE" or "NULL")

COLUMN_MIGRATIONS = [
    # User table
    ("users", "referral_code", "VARCHAR(8)", "VARCHAR(8)", "NULL"),

    # Job table
    ("jobs", "before_photos", "TEXT", "JSON", "NULL"),       # JSON stored as TEXT in SQLite
    ("jobs", "after_photos", "TEXT", "JSON", "NULL"),
    ("jobs", "proof_submitted_at", "DATETIME", "TIMESTAMP", "NULL"),
    ("jobs", "operator_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("jobs", "delegated_at", "DATETIME", "TIMESTAMP", "NULL"),

    # Contractor table
    ("contractors", "is_operator", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("contractors", "operator_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("contractors", "operator_commission_rate", "FLOAT", "FLOAT", "0.15"),

    # Contractor onboarding fields
    ("contractors", "onboarding_status", "VARCHAR(20)", "VARCHAR(20)", "'pending'"),
    ("contractors", "background_check_status", "VARCHAR(20)", "VARCHAR(20)", "'not_started'"),
    ("contractors", "insurance_document_url", "VARCHAR(500)", "VARCHAR(500)", "NULL"),
    ("contractors", "drivers_license_url", "VARCHAR(500)", "VARCHAR(500)", "NULL"),
    ("contractors", "vehicle_registration_url", "VARCHAR(500)", "VARCHAR(500)", "NULL"),
    ("contractors", "insurance_expiry", "DATETIME", "TIMESTAMP", "NULL"),
    ("contractors", "license_expiry", "DATETIME", "TIMESTAMP", "NULL"),
    ("contractors", "onboarding_completed_at", "DATETIME", "TIMESTAMP", "NULL"),
    ("contractors", "rejection_reason", "TEXT", "TEXT", "NULL"),

    # Payment table
    ("payments", "operator_payout_amount", "FLOAT", "FLOAT", "0.0"),

    # Job promo code fields
    ("jobs", "promo_code_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("jobs", "discount_amount", "FLOAT", "FLOAT", "0.0"),
    ("jobs", "cancelled_at", "DATETIME", "TIMESTAMP", "NULL"),
    ("jobs", "cancellation_fee", "FLOAT", "FLOAT", "0.0"),
    ("jobs", "rescheduled_count", "INTEGER", "INTEGER", "0"),

    # Job confirmation & volume adjustment (added 2026-02-17)
    ("jobs", "confirmation_code", "VARCHAR(8)", "VARCHAR(8)", "NULL"),
    ("jobs", "volume_adjustment_proposed", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("jobs", "adjusted_volume", "FLOAT", "FLOAT", "NULL"),
    ("jobs", "adjusted_price", "FLOAT", "FLOAT", "NULL"),
    ("jobs", "volume_estimate", "FLOAT", "FLOAT", "NULL"),
    ("jobs", "volume_price", "FLOAT", "FLOAT", "0.0"),
    ("jobs", "item_total", "FLOAT", "FLOAT", "0.0"),

    # Payment fields (added 2026-02-17)
    ("payments", "driver_payout_amount", "FLOAT", "FLOAT", "0.0"),
    ("payments", "payout_status", "VARCHAR(30)", "VARCHAR(30)", "'pending'"),
    ("payments", "payment_status", "VARCHAR(30)", "VARCHAR(30)", "'pending'"),
    ("payments", "tip_amount", "FLOAT", "FLOAT", "0.0"),
    ("payments", "commission", "FLOAT", "FLOAT", "0.0"),

    # Contractors availability
    ("contractors", "availability_schedule", "TEXT", "JSON", "NULL"),

    # Payments updated_at
    ("payments", "updated_at", "DATETIME", "TIMESTAMP", "NULL"),

    # Job lead source (added 2026-03-24)
    ("jobs", "lead_source", "VARCHAR(100)", "VARCHAR(100)", "NULL"),

    # Job reminder + review fields (added 2026-03-24)
    ("jobs", "reminder_sent", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("jobs", "reminder_call_id", "VARCHAR(255)", "VARCHAR(255)", "NULL"),
    ("jobs", "review_requested", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("jobs", "review_call_id", "VARCHAR(255)", "VARCHAR(255)", "NULL"),

    # No-show watchdog flags (added 2026-05-27)
    ("jobs", "noshow_t30_alerted", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("jobs", "noshow_late_alerted", "BOOLEAN", "BOOLEAN", "FALSE"),

    # User win-back fields (added 2026-03-24)
    ("users", "winback_called", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("users", "last_winback_at", "DATETIME", "TIMESTAMP", "NULL"),

    # Call log scoring + follow-up fields (added 2026-03-24)
    ("call_logs", "lead_score", "VARCHAR(10)", "VARCHAR(10)", "NULL"),
    ("call_logs", "followup_sent", "BOOLEAN", "BOOLEAN", "FALSE"),

    # Call log lead assignment fields (added 2026-03-24)
    ("call_logs", "assigned_operator_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("call_logs", "assigned_driver_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("call_logs", "assignment_status", "VARCHAR(20)", "VARCHAR(20)", "'unassigned'"),
    ("call_logs", "assigned_at", "DATETIME", "TIMESTAMP", "NULL"),

    # Scheduled callback lead assignment fields (added 2026-03-24)
    ("scheduled_callbacks", "assigned_operator_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("scheduled_callbacks", "assigned_driver_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
    ("scheduled_callbacks", "assignment_status", "VARCHAR(20)", "VARCHAR(20)", "'unassigned'"),
    ("scheduled_callbacks", "assigned_at", "DATETIME", "TIMESTAMP", "NULL"),

    # Job drip stage for abandoned booking emails (added 2026-03-30)
    ("jobs", "drip_stage", "INTEGER", "INTEGER", "0"),

    # B2B Commercial Portal (spec 04) — stamp jobs with originating org.
    # NULL = one-off residential; set = booked via portal.goumuve.com.
    ("jobs", "org_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),
]


# ---------------------------------------------------------------------------
# New table definitions (for tables that may not exist at all)
# ---------------------------------------------------------------------------
# These are the CREATE TABLE IF NOT EXISTS statements for tables added after
# the initial schema.  db.create_all() handles this too, but we include them
# here for standalone usage without importing the full Flask app.

NEW_TABLES_SQLITE = [
    # referrals
    dedent("""\
    CREATE TABLE IF NOT EXISTS referrals (
        id VARCHAR(36) PRIMARY KEY,
        referrer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        referee_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        referral_code VARCHAR(8) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        reward_amount FLOAT DEFAULT 10.00,
        created_at DATETIME,
        completed_at DATETIME,
        CONSTRAINT ck_referral_status CHECK (status IN ('pending', 'signed_up', 'completed', 'rewarded'))
    )"""),
    # recurring_bookings
    dedent("""\
    CREATE TABLE IF NOT EXISTS recurring_bookings (
        id VARCHAR(36) PRIMARY KEY,
        customer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        frequency VARCHAR(20) NOT NULL,
        day_of_week INTEGER,
        day_of_month INTEGER,
        preferred_time VARCHAR(5) NOT NULL DEFAULT '09:00',
        address TEXT NOT NULL,
        lat FLOAT,
        lng FLOAT,
        items TEXT,
        notes TEXT,
        is_active BOOLEAN DEFAULT 1,
        next_scheduled_at DATETIME,
        total_bookings_created INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME,
        CONSTRAINT ck_recurring_frequency CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
        CONSTRAINT ck_recurring_day_of_week CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)),
        CONSTRAINT ck_recurring_day_of_month CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 28))
    )"""),
    # device_tokens
    dedent("""\
    CREATE TABLE IF NOT EXISTS device_tokens (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token VARCHAR(512) UNIQUE NOT NULL,
        platform VARCHAR(10) NOT NULL DEFAULT 'ios',
        created_at DATETIME,
        CONSTRAINT ck_device_token_platform CHECK (platform IN ('ios', 'android'))
    )"""),
    # pricing_config
    dedent("""\
    CREATE TABLE IF NOT EXISTS pricing_config (
        key VARCHAR(100) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME
    )"""),
    # operator_invites
    dedent("""\
    CREATE TABLE IF NOT EXISTS operator_invites (
        id VARCHAR(36) PRIMARY KEY,
        operator_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        invite_code VARCHAR(20) UNIQUE NOT NULL,
        email VARCHAR(255),
        max_uses INTEGER DEFAULT 1,
        use_count INTEGER DEFAULT 0,
        expires_at DATETIME,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME
    )"""),
    # promo_codes
    dedent("""\
    CREATE TABLE IF NOT EXISTS promo_codes (
        id VARCHAR(36) PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        discount_type VARCHAR(20) NOT NULL,
        discount_value FLOAT NOT NULL,
        min_order_amount FLOAT DEFAULT 0.0,
        max_discount FLOAT,
        max_uses INTEGER,
        use_count INTEGER DEFAULT 0,
        expires_at DATETIME,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME,
        created_by VARCHAR(36),
        CONSTRAINT ck_promo_discount_type CHECK (discount_type IN ('percentage', 'fixed'))
    )"""),
    # chat_messages
    dedent("""\
    CREATE TABLE IF NOT EXISTS chat_messages (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        sender_id VARCHAR(36) NOT NULL,
        sender_role VARCHAR(20) NOT NULL,
        message TEXT NOT NULL,
        read_at DATETIME,
        created_at DATETIME,
        CONSTRAINT ck_chat_sender_role CHECK (sender_role IN ('customer', 'driver'))
    )"""),
    # reviews
    dedent("""\
    CREATE TABLE IF NOT EXISTS reviews (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
        customer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        contractor_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at DATETIME,
        CONSTRAINT ck_review_rating CHECK (rating >= 1 AND rating <= 5)
    )"""),
    # refunds
    dedent("""\
    CREATE TABLE IF NOT EXISTS refunds (
        id VARCHAR(36) PRIMARY KEY,
        payment_id VARCHAR(36) NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
        amount FLOAT NOT NULL,
        reason TEXT,
        stripe_refund_id VARCHAR(255) UNIQUE,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        created_at DATETIME,
        CONSTRAINT ck_refund_status CHECK (status IN ('pending', 'succeeded', 'failed', 'cancelled'))
    )"""),
    # webhook_events
    dedent("""\
    CREATE TABLE IF NOT EXISTS webhook_events (
        id VARCHAR(36) PRIMARY KEY,
        stripe_event_id VARCHAR(255) UNIQUE,
        event_type VARCHAR(100) NOT NULL,
        payload TEXT,
        status VARCHAR(20) NOT NULL DEFAULT 'processed',
        error_message TEXT,
        created_at DATETIME
    )"""),
    # Vision Quote Engine -- spec 01-vision-quote-engine.md
    # quotes (created first; raw_inference_id FK back-filled via vision_inference_logs)
    dedent("""\
    CREATE TABLE IF NOT EXISTS quotes (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) REFERENCES users(id),
        guest_phone VARCHAR(20),
        guest_email VARCHAR(255),
        zip_code VARCHAR(10) NOT NULL,
        zone VARCHAR(32) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        price_cents INTEGER NOT NULL,
        price_floor_cents INTEGER,
        price_ceiling_cents INTEGER,
        estimated_volume_cubic_yards FLOAT NOT NULL,
        confidence_score FLOAT NOT NULL,
        hazmat_flag BOOLEAN NOT NULL DEFAULT 0,
        binding BOOLEAN NOT NULL DEFAULT 0,
        model_version VARCHAR(64) NOT NULL,
        calibration_version VARCHAR(32) NOT NULL,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        accepted_at DATETIME,
        booked_at DATETIME,
        booking_id VARCHAR(36) REFERENCES jobs(id),
        photo_urls TEXT NOT NULL,
        raw_inference_id VARCHAR(36),
        CONSTRAINT ck_quote_status CHECK (status IN ('draft','pending_review','binding','buffered','accepted','booked','expired','voided'))
    )"""),
    # quote_items
    dedent("""\
    CREATE TABLE IF NOT EXISTS quote_items (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        label VARCHAR(64) NOT NULL,
        display_name VARCHAR(128) NOT NULL,
        count INTEGER NOT NULL DEFAULT 1,
        volume_cubic_yards FLOAT NOT NULL,
        unit_price_cents INTEGER NOT NULL,
        hazmat BOOLEAN NOT NULL DEFAULT 0,
        photo_index INTEGER,
        bbox TEXT
    )"""),
    # vision_inference_logs
    dedent("""\
    CREATE TABLE IF NOT EXISTS vision_inference_logs (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) REFERENCES quotes(id),
        model VARCHAR(64) NOT NULL,
        prompt_hash VARCHAR(64) NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_cents FLOAT NOT NULL,
        latency_ms INTEGER NOT NULL,
        raw_response TEXT NOT NULL,
        error VARCHAR(1024),
        created_at DATETIME NOT NULL
    )"""),
    # quote_feedback
    dedent("""\
    CREATE TABLE IF NOT EXISTS quote_feedback (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL UNIQUE REFERENCES quotes(id) ON DELETE CASCADE,
        driver_id VARCHAR(36) NOT NULL REFERENCES users(id),
        actual_price_cents INTEGER NOT NULL,
        actual_volume_cubic_yards FLOAT NOT NULL,
        actual_labor_minutes INTEGER NOT NULL,
        delta_cents INTEGER NOT NULL,
        delta_pct FLOAT NOT NULL,
        miss_category VARCHAR(20) NOT NULL,
        driver_notes VARCHAR(2048),
        post_job_photo_urls TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_quote_feedback_miss_category CHECK (miss_category IN ('accurate','under','over','hazmat_missed','volume_missed','item_missed'))
    )"""),
    # calibration_samples
    dedent("""\
    CREATE TABLE IF NOT EXISTS calibration_samples (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        photo_urls TEXT NOT NULL,
        predicted_items TEXT NOT NULL,
        actual_items TEXT NOT NULL,
        predicted_price_cents INTEGER NOT NULL,
        actual_price_cents INTEGER NOT NULL,
        used_for_training BOOLEAN NOT NULL DEFAULT 0,
        training_run_id VARCHAR(64),
        created_at DATETIME NOT NULL
    )"""),
    # Post-Haul Attach Engine -- spec 09-post-haul-attach-engine.md
    # offer_catalog -- 12 canonical upsell templates seeded at migrate time
    dedent("""\
    CREATE TABLE IF NOT EXISTS offer_catalog (
        code VARCHAR(60) PRIMARY KEY,
        display_name VARCHAR(128) NOT NULL,
        description TEXT,
        fulfillment VARCHAR(20) NOT NULL,
        partner_id VARCHAR(64),
        base_price_cents INTEGER NOT NULL,
        umuve_margin_cents INTEGER NOT NULL,
        copy_template TEXT NOT NULL,
        active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_offer_catalog_fulfillment CHECK (fulfillment IN ('inhouse','partner','hybrid'))
    )"""),
    # attach_offers
    dedent("""\
    CREATE TABLE IF NOT EXISTS attach_offers (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        customer_id VARCHAR(36) REFERENCES users(id),
        catalog_code VARCHAR(60) NOT NULL REFERENCES offer_catalog(code),
        offer_price_cents INTEGER NOT NULL,
        expected_margin_cents INTEGER NOT NULL,
        copy_rendered TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        channel VARCHAR(20) NOT NULL DEFAULT 'sms',
        origin VARCHAR(20) NOT NULL DEFAULT 'operator',
        created_by VARCHAR(36) REFERENCES users(id),
        accept_token VARCHAR(32) UNIQUE NOT NULL,
        attributes TEXT,
        scheduled_for DATETIME,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        sent_at DATETIME,
        opened_at DATETIME,
        clicked_at DATETIME,
        accepted_at DATETIME,
        declined_at DATETIME,
        CONSTRAINT ck_attach_offer_status CHECK (status IN ('pending','sent','opened','clicked','accepted','declined','expired','converted','failed')),
        CONSTRAINT ck_attach_offer_channel CHECK (channel IN ('sms','push','email','in_app')),
        CONSTRAINT ck_attach_offer_origin CHECK (origin IN ('operator','vision','rules','crew_note'))
    )"""),
    # attach_conversions
    dedent("""\
    CREATE TABLE IF NOT EXISTS attach_conversions (
        id VARCHAR(36) PRIMARY KEY,
        offer_id VARCHAR(36) NOT NULL UNIQUE REFERENCES attach_offers(id) ON DELETE CASCADE,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id),
        customer_id VARCHAR(36) REFERENCES users(id),
        stripe_payment_intent_id VARCHAR(255),
        amount_cents INTEGER NOT NULL,
        margin_cents INTEGER NOT NULL,
        scheduled_for DATETIME,
        payment_method_id VARCHAR(255),
        fulfilled_at DATETIME,
        fulfillment_notes TEXT,
        follow_on_job_id VARCHAR(36) REFERENCES jobs(id),
        created_at DATETIME NOT NULL
    )"""),
    # Donation / Resale Rescue Engine -- spec 05-donation-resale-engine.md
    # item_valuations
    dedent("""\
    CREATE TABLE IF NOT EXISTS item_valuations (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        item_label VARCHAR(64) NOT NULL,
        display_name VARCHAR(128) NOT NULL,
        condition_grade VARCHAR(1),
        est_fmv_low_cents INTEGER NOT NULL DEFAULT 0,
        est_fmv_high_cents INTEGER NOT NULL DEFAULT 0,
        resale_probability FLOAT NOT NULL DEFAULT 0.0,
        donation_eligible BOOLEAN NOT NULL DEFAULT 0,
        hazmat_flag BOOLEAN NOT NULL DEFAULT 0,
        high_value BOOLEAN NOT NULL DEFAULT 0,
        reasoning VARCHAR(512),
        model VARCHAR(64) NOT NULL,
        prompt_hash VARCHAR(64) NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        cost_cents FLOAT NOT NULL DEFAULT 0.0,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_item_valuation_condition CHECK (condition_grade IS NULL OR condition_grade IN ('A','B','C','D'))
    )"""),
    # resale_listings
    dedent("""\
    CREATE TABLE IF NOT EXISTS resale_listings (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        valuation_id VARCHAR(36) REFERENCES item_valuations(id) ON DELETE SET NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'candidate',
        channel VARCHAR(20) NOT NULL DEFAULT 'none',
        channel_listing_id VARCHAR(128),
        channel_listing_url VARCHAR(512),
        title VARCHAR(200),
        description TEXT,
        list_price_cents INTEGER,
        sold_price_cents INTEGER,
        photo_urls TEXT,
        est_fmv_low_cents INTEGER NOT NULL DEFAULT 0,
        est_fmv_high_cents INTEGER NOT NULL DEFAULT 0,
        customer_approval_at DATETIME,
        listed_at DATETIME,
        sold_at DATETIME,
        expires_at DATETIME,
        declined_reason VARCHAR(128),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_resale_listing_status CHECK (status IN ('candidate','approved','declined','listed','sold','expired','donated')),
        CONSTRAINT ck_resale_listing_channel CHECK (channel IN ('none','fb_marketplace','offerup','ebay','habitat','goodwill'))
    )"""),
    # resale_splits
    dedent("""\
    CREATE TABLE IF NOT EXISTS resale_splits (
        id VARCHAR(36) PRIMARY KEY,
        listing_id VARCHAR(36) NOT NULL UNIQUE REFERENCES resale_listings(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        gross_cents INTEGER NOT NULL,
        customer_cut_cents INTEGER NOT NULL,
        umuve_cut_cents INTEGER NOT NULL,
        customer_share FLOAT NOT NULL DEFAULT 0.40,
        umuve_share FLOAT NOT NULL DEFAULT 0.60,
        stripe_payment_intent_id VARCHAR(128),
        stripe_transfer_id VARCHAR(128),
        customer_payout_status VARCHAR(20) NOT NULL DEFAULT 'pending',
        settled_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_resale_split_payout_status CHECK (customer_payout_status IN ('pending','paid','failed')),
        CONSTRAINT ck_resale_split_nonneg CHECK (gross_cents >= 0 AND customer_cut_cents >= 0 AND umuve_cut_cents >= 0)
    )"""),
    # donation_receipts
    dedent("""\
    CREATE TABLE IF NOT EXISTS donation_receipts (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        listing_id VARCHAR(36) REFERENCES resale_listings(id) ON DELETE SET NULL,
        charity_partner_name VARCHAR(128) NOT NULL,
        charity_partner_ein VARCHAR(32),
        charity_address VARCHAR(512),
        item_description TEXT NOT NULL,
        condition_grade VARCHAR(1),
        fair_market_value_cents INTEGER NOT NULL DEFAULT 0,
        drop_off_at DATETIME,
        drop_off_photo_url VARCHAR(512),
        form_8283_pdf_url VARCHAR(512),
        docusign_envelope_id VARCHAR(128),
        customer_signed_at DATETIME,
        customer_email VARCHAR(255),
        receipt_number VARCHAR(32) UNIQUE,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_donation_receipt_condition CHECK (condition_grade IS NULL OR condition_grade IN ('A','B','C','D'))
    )"""),
    # ------------------------------------------------------------------
    # Life-Event Demand Trigger Engine (spec 03-life-event-triggers.md)
    # ------------------------------------------------------------------
    # life_events
    dedent("""\
    CREATE TABLE IF NOT EXISTS life_events (
        id VARCHAR(36) PRIMARY KEY,
        source VARCHAR(32) NOT NULL,
        source_record_id VARCHAR(128) NOT NULL,
        event_type VARCHAR(32) NOT NULL,
        event_date DATETIME,
        county VARCHAR(32) NOT NULL,
        zip_code VARCHAR(10),
        address_line1 VARCHAR(255),
        apn VARCHAR(64),
        prospect_name VARCHAR(255),
        prospect_phone_e164 VARCHAR(20),
        prospect_email VARCHAR(255),
        raw_payload TEXT,
        pii_hydrated BOOLEAN NOT NULL DEFAULT 0,
        sensitive BOOLEAN NOT NULL DEFAULT 0,
        pipeline_status VARCHAR(24) NOT NULL DEFAULT 'new',
        suppressed_reason VARCHAR(64),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_life_events_event_type CHECK (event_type IN (
            'deed_transfer','moving_permit','estate','probate_filing','mls_closing',
            'building_permit','divorce_filing','eviction','bankruptcy','obituary'
        )),
        CONSTRAINT ck_life_events_county CHECK (county IN ('miami-dade','broward','palm-beach')),
        CONSTRAINT ck_life_events_pipeline_status CHECK (pipeline_status IN (
            'new','matched','queued','contacted','converted','suppressed','stale'
        )),
        CONSTRAINT uq_life_events_source_record UNIQUE (source, source_record_id)
    )"""),
    # lead_pipelines
    dedent("""\
    CREATE TABLE IF NOT EXISTS lead_pipelines (
        id VARCHAR(36) PRIMARY KEY,
        life_event_id VARCHAR(36) NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
        assigned_operator_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        stage VARCHAR(24) NOT NULL DEFAULT 'inbox',
        priority VARCHAR(10) NOT NULL DEFAULT 'normal',
        projected_quote_low_cents INTEGER,
        projected_quote_high_cents INTEGER,
        last_stage_change_at DATETIME NOT NULL,
        claimed_at DATETIME,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_lead_pipelines_stage CHECK (stage IN (
            'inbox','qualified','outreach_drafted','outreach_sent','replied',
            'booked','closed_won','closed_lost','blocked'
        )),
        CONSTRAINT ck_lead_pipelines_priority CHECK (priority IN ('low','normal','high','urgent'))
    )"""),
    # tcpa_consents
    dedent("""\
    CREATE TABLE IF NOT EXISTS tcpa_consents (
        id VARCHAR(36) PRIMARY KEY,
        phone_e164 VARCHAR(20),
        email VARCHAR(255),
        channel VARCHAR(16) NOT NULL,
        consent_method VARCHAR(32) NOT NULL,
        consent_source_url VARCHAR(512),
        consent_ip VARCHAR(45),
        consent_user_agent VARCHAR(512),
        consent_text_hash VARCHAR(64),
        granted_at DATETIME NOT NULL,
        revoked_at DATETIME,
        revoked_reason VARCHAR(64),
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_tcpa_consents_channel CHECK (channel IN ('sms','call','email','direct_mail')),
        CONSTRAINT ck_tcpa_consents_method CHECK (consent_method IN (
            'express_written','web_form','sms_double_opt_in','existing_business',
            'inbound_call','manual_admin'
        )),
        CONSTRAINT ck_tcpa_consents_identifier_present CHECK (phone_e164 IS NOT NULL OR email IS NOT NULL)
    )"""),
    # outreach_logs
    dedent("""\
    CREATE TABLE IF NOT EXISTS outreach_logs (
        id VARCHAR(36) PRIMARY KEY,
        life_event_id VARCHAR(36) NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
        pipeline_id VARCHAR(36) REFERENCES lead_pipelines(id) ON DELETE SET NULL,
        channel VARCHAR(16) NOT NULL,
        to_phone_e164 VARCHAR(20),
        to_email VARCHAR(255),
        to_address_line1 VARCHAR(255),
        subject VARCHAR(255),
        body_rendered TEXT,
        regulatory_disclaimer TEXT NOT NULL,
        tcpa_consent_id VARCHAR(36) REFERENCES tcpa_consents(id) ON DELETE SET NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'drafted',
        block_reason VARCHAR(64),
        provider VARCHAR(24),
        provider_msg_id VARCHAR(128),
        cost_cents INTEGER,
        created_at DATETIME NOT NULL,
        sent_at DATETIME,
        CONSTRAINT ck_outreach_logs_channel CHECK (channel IN ('sms','call','email','direct_mail')),
        CONSTRAINT ck_outreach_logs_status CHECK (status IN (
            'drafted','queued','sent','delivered','bounced','opted_out','blocked','failed'
        ))
    )"""),
    # ------------------------------------------------------------------
    # Landfill Routing Optimizer (spec 06)
    # ------------------------------------------------------------------
    # landfill_facilities
    dedent("""\
    CREATE TABLE IF NOT EXISTS landfill_facilities (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(128) NOT NULL UNIQUE,
        type VARCHAR(24) NOT NULL,
        operator VARCHAR(128),
        permit_no VARCHAR(64),
        address VARCHAR(512) NOT NULL,
        lat FLOAT NOT NULL,
        lon FLOAT NOT NULL,
        county VARCHAR(32) NOT NULL,
        accepts_categories TEXT NOT NULL DEFAULT '[]',
        hours_json TEXT,
        phone VARCHAR(32),
        scale_method VARCHAR(16) NOT NULL DEFAULT 'per_ton',
        avg_turnaround_min INTEGER NOT NULL DEFAULT 25,
        notes TEXT,
        fee_accuracy_validated BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_landfill_facility_type CHECK (type IN (
            'transfer_station','landfill','mrf','c_and_d','wte'
        )),
        CONSTRAINT ck_landfill_facility_scale_method CHECK (scale_method IN (
            'per_ton','per_cu_yd','flat'
        ))
    )"""),
    # tip_fees
    dedent("""\
    CREATE TABLE IF NOT EXISTS tip_fees (
        id VARCHAR(36) PRIMARY KEY,
        facility_id VARCHAR(36) NOT NULL REFERENCES landfill_facilities(id) ON DELETE CASCADE,
        category VARCHAR(24) NOT NULL,
        fee_amount FLOAT NOT NULL,
        fee_unit VARCHAR(16) NOT NULL DEFAULT 'per_ton',
        effective_from DATETIME NOT NULL,
        effective_to DATETIME,
        source VARCHAR(12) NOT NULL DEFAULT 'seed',
        confidence FLOAT NOT NULL DEFAULT 0.70,
        captured_at DATETIME NOT NULL,
        CONSTRAINT ck_tip_fee_category CHECK (category IN (
            'msw','c_and_d','yard','bulky','metal','appliance_w_freon',
            'mattress','tires','concrete','drywall','mixed'
        )),
        CONSTRAINT ck_tip_fee_unit CHECK (fee_unit IN (
            'per_ton','per_cu_yd','per_item','flat'
        )),
        CONSTRAINT ck_tip_fee_source CHECK (source IN (
            'scrape','phone','manual','api','seed'
        ))
    )"""),
    # route_optimizations
    dedent("""\
    CREATE TABLE IF NOT EXISTS route_optimizations (
        id VARCHAR(36) PRIMARY KEY,
        vehicle_id VARCHAR(36),
        vehicle_label VARCHAR(64),
        capacity_tons FLOAT NOT NULL DEFAULT 4.0,
        run_date DATETIME NOT NULL,
        candidates_json TEXT NOT NULL DEFAULT '[]',
        chosen_facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        predicted_total_cost_cents INTEGER NOT NULL DEFAULT 0,
        predicted_tipping_cents INTEGER NOT NULL DEFAULT 0,
        predicted_fuel_cents INTEGER NOT NULL DEFAULT 0,
        predicted_labor_cents INTEGER NOT NULL DEFAULT 0,
        predicted_drive_minutes INTEGER NOT NULL DEFAULT 0,
        baseline_total_cost_cents INTEGER NOT NULL DEFAULT 0,
        baseline_facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        savings_cents INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(16) NOT NULL DEFAULT 'planned',
        solver_version VARCHAR(32) NOT NULL DEFAULT 'v1',
        solver_mode VARCHAR(32) NOT NULL DEFAULT 'branch_and_bound_fallback',
        notes TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_route_optimization_status CHECK (status IN (
            'planned','dispatched','completed','voided'
        )),
        CONSTRAINT ck_route_optimization_solver_mode CHECK (solver_mode IN (
            'ortools_vrp','branch_and_bound_fallback','nearest'
        ))
    )"""),
    # route_stops
    dedent("""\
    CREATE TABLE IF NOT EXISTS route_stops (
        id VARCHAR(36) PRIMARY KEY,
        route_id VARCHAR(36) NOT NULL REFERENCES route_optimizations(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL,
        stop_type VARCHAR(16) NOT NULL,
        job_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        lat FLOAT NOT NULL,
        lon FLOAT NOT NULL,
        distance_meters INTEGER,
        drive_seconds INTEGER,
        service_seconds INTEGER,
        estimated_load_tons FLOAT,
        earliest_arrival DATETIME,
        latest_arrival DATETIME,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_route_stop_type CHECK (stop_type IN (
            'pickup','facility','depot_start','depot_end'
        ))
    )"""),
    # Voice AI (spec 02) — voice_calls, turns, transcript, outcomes, sms
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_calls (
        id VARCHAR(36) PRIMARY KEY,
        vapi_call_id VARCHAR(64) UNIQUE NOT NULL,
        twilio_call_sid VARCHAR(64),
        caller_number VARCHAR(20) NOT NULL,
        called_number VARCHAR(20) NOT NULL,
        started_at DATETIME NOT NULL,
        answered_at DATETIME,
        ended_at DATETIME,
        duration_s INTEGER,
        cost_usd FLOAT,
        status VARCHAR(24),
        outcome_id VARCHAR(36),
        recording_url VARCHAR(512),
        consent_given BOOLEAN DEFAULT 0,
        created_at DATETIME,
        CONSTRAINT ck_voice_calls_status CHECK (
            status IS NULL OR status IN ('in_progress','completed','failed','spam')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_turns (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
        turn_index INTEGER NOT NULL,
        role VARCHAR(12) NOT NULL,
        text TEXT NOT NULL,
        tool_name VARCHAR(64),
        tool_input TEXT,
        tool_output TEXT,
        latency_ms INTEGER,
        created_at DATETIME,
        CONSTRAINT ck_voice_call_turns_role CHECK (role IN ('caller','agent','tool'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_transcripts (
        call_id VARCHAR(36) PRIMARY KEY REFERENCES voice_calls(id) ON DELETE CASCADE,
        full_text TEXT NOT NULL,
        summary TEXT,
        sentiment VARCHAR(16),
        tags TEXT,
        CONSTRAINT ck_voice_call_transcripts_sentiment CHECK (
            sentiment IS NULL OR sentiment IN ('positive','neutral','negative','grief')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_outcomes (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL UNIQUE REFERENCES voice_calls(id) ON DELETE CASCADE,
        booked BOOLEAN DEFAULT 0,
        booking_id VARCHAR(36) REFERENCES jobs(id),
        quote_id VARCHAR(36) REFERENCES quotes(id),
        quoted_amount FLOAT,
        paid BOOLEAN DEFAULT 0,
        payment_link_url VARCHAR(512),
        stripe_session_id VARCHAR(128),
        escalated BOOLEAN DEFAULT 0,
        escalation_reason VARCHAR(32),
        abandon_stage VARCHAR(32),
        discount_pct FLOAT,
        CONSTRAINT ck_voice_call_outcomes_escalation_reason CHECK (
            escalation_reason IS NULL OR escalation_reason IN
            ('commercial','estate','complex','complaint','consent_refused','out_of_area')
        ),
        CONSTRAINT ck_voice_call_outcomes_abandon_stage CHECK (
            abandon_stage IS NULL OR abandon_stage IN
            ('qualify','photo','quote','book','pay')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_sms_exchanges (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
        direction VARCHAR(4) NOT NULL,
        purpose VARCHAR(24) NOT NULL,
        body TEXT NOT NULL,
        media_url VARCHAR(512),
        twilio_sid VARCHAR(64) UNIQUE,
        delivered BOOLEAN DEFAULT 0,
        created_at DATETIME,
        CONSTRAINT ck_voice_sms_exchanges_direction CHECK (direction IN ('in','out')),
        CONSTRAINT ck_voice_sms_exchanges_purpose CHECK (
            purpose IN ('photo_request','quote_link','payment_link','confirmation')
        )
    )"""),

    # ---------------------------------------------------------------
    # B2B Commercial Portal (spec 04)
    # ---------------------------------------------------------------
    dedent("""\
    CREATE TABLE IF NOT EXISTS orgs (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        slug VARCHAR(60) NOT NULL UNIQUE,
        tax_id VARCHAR(32),
        billing_email VARCHAR(120) NOT NULL,
        billing_address TEXT,
        stripe_customer_id VARCHAR(64) UNIQUE,
        stripe_subscription_id VARCHAR(64),
        tier VARCHAR(20) NOT NULL DEFAULT 'starter',
        status VARCHAR(20) NOT NULL DEFAULT 'trial',
        sso_provider VARCHAR(32),
        sso_domain VARCHAR(120),
        auto_pay BOOLEAN DEFAULT 1,
        net_terms_days INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME,
        CONSTRAINT ck_org_tier CHECK (tier IN ('starter','pro','enterprise')),
        CONSTRAINT ck_org_status CHECK (
            status IN ('trial','active','past_due','paused','churned')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS org_members (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL,
        scopes TEXT,
        invited_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        invite_token VARCHAR(80) UNIQUE,
        invited_at DATETIME,
        joined_at DATETIME,
        CONSTRAINT ck_orgmember_role CHECK (
            role IN ('owner','admin','operator','viewer')
        ),
        CONSTRAINT ix_orgmember_org_user UNIQUE (org_id, user_id)
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_properties (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        name VARCHAR(120) NOT NULL,
        address_line1 VARCHAR(160),
        address_line2 VARCHAR(160),
        city VARCHAR(60),
        state VARCHAR(2),
        zip VARCHAR(10),
        lat FLOAT,
        lng FLOAT,
        external_ref VARCHAR(64),
        source VARCHAR(16) DEFAULT 'manual',
        unit_count INTEGER DEFAULT 1,
        active BOOLEAN DEFAULT 1,
        created_at DATETIME
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS contracts (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        tier VARCHAR(20) NOT NULL,
        monthly_base_cents INTEGER NOT NULL,
        metered_per_pickup_cents INTEGER DEFAULT 0,
        metered_per_ton_cents INTEGER DEFAULT 0,
        included_pickups INTEGER DEFAULT 0,
        pricing_overrides TEXT,
        effective_from DATETIME NOT NULL,
        effective_to DATETIME,
        signed_pdf_s3_key VARCHAR(240),
        created_at DATETIME,
        CONSTRAINT ck_contract_tier CHECK (
            tier IN ('starter','pro','enterprise')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_invoices (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        number VARCHAR(24) NOT NULL UNIQUE,
        period_start DATETIME NOT NULL,
        period_end DATETIME NOT NULL,
        subtotal_cents INTEGER NOT NULL DEFAULT 0,
        tax_cents INTEGER DEFAULT 0,
        total_cents INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        stripe_invoice_id VARCHAR(64),
        due_at DATETIME,
        paid_at DATETIME,
        sent_at DATETIME,
        created_at DATETIME,
        CONSTRAINT ck_portal_invoice_status CHECK (
            status IN ('draft','open','paid','past_due','void')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_invoice_line_items (
        id VARCHAR(36) PRIMARY KEY,
        invoice_id VARCHAR(36) NOT NULL
            REFERENCES portal_invoices(id) ON DELETE CASCADE,
        job_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        property_id VARCHAR(36)
            REFERENCES portal_properties(id) ON DELETE SET NULL,
        description VARCHAR(240),
        quantity FLOAT DEFAULT 1.0,
        unit_cents INTEGER NOT NULL DEFAULT 0,
        amount_cents INTEGER NOT NULL DEFAULT 0
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_payment_methods (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        kind VARCHAR(16) NOT NULL,
        stripe_payment_method_id VARCHAR(64),
        last4 VARCHAR(4),
        bank_name VARCHAR(60),
        is_default BOOLEAN DEFAULT 0,
        created_at DATETIME,
        CONSTRAINT ck_portal_pm_kind CHECK (kind IN ('ach','card','check'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_audit_logs (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36),
        user_id VARCHAR(36),
        action VARCHAR(60) NOT NULL,
        object_type VARCHAR(40),
        object_id VARCHAR(36),
        before TEXT,
        after TEXT,
        ip VARCHAR(45),
        user_agent VARCHAR(240),
        created_at DATETIME
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_api_keys (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        name VARCHAR(80),
        prefix VARCHAR(16),
        hashed_key VARCHAR(128) NOT NULL UNIQUE,
        scopes TEXT,
        last_used_at DATETIME,
        revoked_at DATETIME,
        created_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        created_at DATETIME
    )"""),
]

# Partner Acquisition Agent (spec 07) + Ops Supervisor (spec 11) migrations
# are imported as separate modules and appended here to keep this file
# merge-friendly for parallel subagent builds.
from partner_migrations import (
    NEW_TABLES_SQLITE as _PARTNER_SQLITE,
    NEW_TABLES_PG as _PARTNER_PG,
    NEW_TABLE_NAMES as _PARTNER_NAMES,
)
from ops_supervisor_migrations import (
    NEW_TABLES_SQLITE as _OPS_SQLITE_ALL,
    NEW_TABLES_PG as _OPS_PG_ALL,
    NEW_TABLE_NAMES as _OPS_NAMES,
)
from portal_v1_migrations import (
    NEW_TABLES_SQLITE as _PORTAL_V1_SQLITE,
    NEW_TABLES_PG as _PORTAL_V1_PG,
    NEW_TABLE_NAMES as _PORTAL_V1_NAMES,
    COLUMN_MIGRATIONS as _PORTAL_V1_COLUMNS,
    RLS_ORG_TABLES as _PORTAL_V1_RLS,
)
from ops_supervisor_v1_migrations import (
    NEW_TABLES_SQLITE as _OPS_V1_SQLITE,
    NEW_TABLES_PG as _OPS_V1_PG,
    NEW_TABLE_NAMES as _OPS_V1_NAMES,
    NEW_INDEXES_SQLITE as _OPS_V1_INDEXES_SQLITE,
    NEW_INDEXES_PG as _OPS_V1_INDEXES_PG,
)
from portal_sso_migrations import (
    NEW_TABLES_SQLITE as _PORTAL_SSO_SQLITE,
    NEW_TABLES_PG as _PORTAL_SSO_PG,
    NEW_TABLE_NAMES as _PORTAL_SSO_NAMES,
)
COLUMN_MIGRATIONS.extend(_PORTAL_V1_COLUMNS)
# ops_supervisor_migrations interleaves CREATE INDEX statements; separate
# them so the zip(NAMES, TABLES) alignment stays 1:1.
def _split_tables_and_indexes(stmts):
    tables, indexes = [], []
    for s in stmts:
        if s.lstrip().upper().startswith("CREATE TABLE"):
            tables.append(s)
        else:
            indexes.append(s)
    return tables, indexes

_OPS_SQLITE, _OPS_INDEXES_SQLITE = _split_tables_and_indexes(_OPS_SQLITE_ALL)
_OPS_PG, _OPS_INDEXES_PG = _split_tables_and_indexes(_OPS_PG_ALL)

NEW_TABLES_SQLITE.extend(_PARTNER_SQLITE)
NEW_TABLES_SQLITE.extend(_OPS_SQLITE)
NEW_TABLES_SQLITE.extend(_PORTAL_V1_SQLITE)
NEW_TABLES_SQLITE.extend(_OPS_V1_SQLITE)
NEW_TABLES_SQLITE.extend(_PORTAL_SSO_SQLITE)

NEW_TABLES_PG = [
    # referrals
    dedent("""\
    CREATE TABLE IF NOT EXISTS referrals (
        id VARCHAR(36) PRIMARY KEY,
        referrer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        referee_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        referral_code VARCHAR(8) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        reward_amount FLOAT DEFAULT 10.00,
        created_at TIMESTAMP,
        completed_at TIMESTAMP,
        CONSTRAINT ck_referral_status CHECK (status IN ('pending', 'signed_up', 'completed', 'rewarded'))
    )"""),
    # recurring_bookings
    dedent("""\
    CREATE TABLE IF NOT EXISTS recurring_bookings (
        id VARCHAR(36) PRIMARY KEY,
        customer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        frequency VARCHAR(20) NOT NULL,
        day_of_week INTEGER,
        day_of_month INTEGER,
        preferred_time VARCHAR(5) NOT NULL DEFAULT '09:00',
        address TEXT NOT NULL,
        lat FLOAT,
        lng FLOAT,
        items JSON,
        notes TEXT,
        is_active BOOLEAN DEFAULT FALSE,
        next_scheduled_at TIMESTAMP,
        total_bookings_created INTEGER DEFAULT 0,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        CONSTRAINT ck_recurring_frequency CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
        CONSTRAINT ck_recurring_day_of_week CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)),
        CONSTRAINT ck_recurring_day_of_month CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 28))
    )"""),
    # device_tokens
    dedent("""\
    CREATE TABLE IF NOT EXISTS device_tokens (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token VARCHAR(512) UNIQUE NOT NULL,
        platform VARCHAR(10) NOT NULL DEFAULT 'ios',
        created_at TIMESTAMP,
        CONSTRAINT ck_device_token_platform CHECK (platform IN ('ios', 'android'))
    )"""),
    # pricing_config
    dedent("""\
    CREATE TABLE IF NOT EXISTS pricing_config (
        key VARCHAR(100) PRIMARY KEY,
        value JSON NOT NULL,
        updated_at TIMESTAMP
    )"""),
    # operator_invites
    dedent("""\
    CREATE TABLE IF NOT EXISTS operator_invites (
        id VARCHAR(36) PRIMARY KEY,
        operator_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        invite_code VARCHAR(20) UNIQUE NOT NULL,
        email VARCHAR(255),
        max_uses INTEGER DEFAULT 1,
        use_count INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP
    )"""),
    # promo_codes
    dedent("""\
    CREATE TABLE IF NOT EXISTS promo_codes (
        id VARCHAR(36) PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        discount_type VARCHAR(20) NOT NULL,
        discount_value FLOAT NOT NULL,
        min_order_amount FLOAT DEFAULT 0.0,
        max_discount FLOAT,
        max_uses INTEGER,
        use_count INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP,
        created_by VARCHAR(36),
        CONSTRAINT ck_promo_discount_type CHECK (discount_type IN ('percentage', 'fixed'))
    )"""),
    # chat_messages
    dedent("""\
    CREATE TABLE IF NOT EXISTS chat_messages (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        sender_id VARCHAR(36) NOT NULL,
        sender_role VARCHAR(20) NOT NULL CHECK (sender_role IN ('customer', 'driver')),
        message TEXT NOT NULL,
        read_at TIMESTAMP,
        created_at TIMESTAMP
    )"""),
    # reviews
    dedent("""\
    CREATE TABLE IF NOT EXISTS reviews (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
        customer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        contractor_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP,
        CONSTRAINT ck_review_rating CHECK (rating >= 1 AND rating <= 5)
    )"""),
    # refunds
    dedent("""\
    CREATE TABLE IF NOT EXISTS refunds (
        id VARCHAR(36) PRIMARY KEY,
        payment_id VARCHAR(36) NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
        amount FLOAT NOT NULL,
        reason TEXT,
        stripe_refund_id VARCHAR(255) UNIQUE,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP,
        CONSTRAINT ck_refund_status CHECK (status IN ('pending', 'succeeded', 'failed', 'cancelled'))
    )"""),
    # webhook_events
    dedent("""\
    CREATE TABLE IF NOT EXISTS webhook_events (
        id VARCHAR(36) PRIMARY KEY,
        stripe_event_id VARCHAR(255) UNIQUE,
        event_type VARCHAR(100) NOT NULL,
        payload JSON,
        status VARCHAR(20) NOT NULL DEFAULT 'processed',
        error_message TEXT,
        created_at TIMESTAMP
    )"""),
    # Vision Quote Engine -- spec 01-vision-quote-engine.md
    # quotes
    dedent("""\
    CREATE TABLE IF NOT EXISTS quotes (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) REFERENCES users(id),
        guest_phone VARCHAR(20),
        guest_email VARCHAR(255),
        zip_code VARCHAR(10) NOT NULL,
        zone VARCHAR(32) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        price_cents INTEGER NOT NULL,
        price_floor_cents INTEGER,
        price_ceiling_cents INTEGER,
        estimated_volume_cubic_yards FLOAT NOT NULL,
        confidence_score FLOAT NOT NULL,
        hazmat_flag BOOLEAN NOT NULL DEFAULT FALSE,
        binding BOOLEAN NOT NULL DEFAULT FALSE,
        model_version VARCHAR(64) NOT NULL,
        calibration_version VARCHAR(32) NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP NOT NULL,
        accepted_at TIMESTAMP,
        booked_at TIMESTAMP,
        booking_id VARCHAR(36) REFERENCES jobs(id),
        photo_urls JSON NOT NULL,
        raw_inference_id VARCHAR(36),
        CONSTRAINT ck_quote_status CHECK (status IN ('draft','pending_review','binding','buffered','accepted','booked','expired','voided'))
    )"""),
    # quote_items
    dedent("""\
    CREATE TABLE IF NOT EXISTS quote_items (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        label VARCHAR(64) NOT NULL,
        display_name VARCHAR(128) NOT NULL,
        count INTEGER NOT NULL DEFAULT 1,
        volume_cubic_yards FLOAT NOT NULL,
        unit_price_cents INTEGER NOT NULL,
        hazmat BOOLEAN NOT NULL DEFAULT FALSE,
        photo_index INTEGER,
        bbox JSON
    )"""),
    # vision_inference_logs
    dedent("""\
    CREATE TABLE IF NOT EXISTS vision_inference_logs (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) REFERENCES quotes(id),
        model VARCHAR(64) NOT NULL,
        prompt_hash VARCHAR(64) NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_cents FLOAT NOT NULL,
        latency_ms INTEGER NOT NULL,
        raw_response JSON NOT NULL,
        error VARCHAR(1024),
        created_at TIMESTAMP NOT NULL
    )"""),
    # quote_feedback
    dedent("""\
    CREATE TABLE IF NOT EXISTS quote_feedback (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL UNIQUE REFERENCES quotes(id) ON DELETE CASCADE,
        driver_id VARCHAR(36) NOT NULL REFERENCES users(id),
        actual_price_cents INTEGER NOT NULL,
        actual_volume_cubic_yards FLOAT NOT NULL,
        actual_labor_minutes INTEGER NOT NULL,
        delta_cents INTEGER NOT NULL,
        delta_pct FLOAT NOT NULL,
        miss_category VARCHAR(20) NOT NULL,
        driver_notes VARCHAR(2048),
        post_job_photo_urls JSON,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_quote_feedback_miss_category CHECK (miss_category IN ('accurate','under','over','hazmat_missed','volume_missed','item_missed'))
    )"""),
    # calibration_samples
    dedent("""\
    CREATE TABLE IF NOT EXISTS calibration_samples (
        id VARCHAR(36) PRIMARY KEY,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        photo_urls JSON NOT NULL,
        predicted_items JSON NOT NULL,
        actual_items JSON NOT NULL,
        predicted_price_cents INTEGER NOT NULL,
        actual_price_cents INTEGER NOT NULL,
        used_for_training BOOLEAN NOT NULL DEFAULT FALSE,
        training_run_id VARCHAR(64),
        created_at TIMESTAMP NOT NULL
    )"""),
    # Post-Haul Attach Engine -- spec 09-post-haul-attach-engine.md
    # offer_catalog
    dedent("""\
    CREATE TABLE IF NOT EXISTS offer_catalog (
        code VARCHAR(60) PRIMARY KEY,
        display_name VARCHAR(128) NOT NULL,
        description TEXT,
        fulfillment VARCHAR(20) NOT NULL,
        partner_id VARCHAR(64),
        base_price_cents INTEGER NOT NULL,
        umuve_margin_cents INTEGER NOT NULL,
        copy_template TEXT NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_offer_catalog_fulfillment CHECK (fulfillment IN ('inhouse','partner','hybrid'))
    )"""),
    # attach_offers
    dedent("""\
    CREATE TABLE IF NOT EXISTS attach_offers (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        customer_id VARCHAR(36) REFERENCES users(id),
        catalog_code VARCHAR(60) NOT NULL REFERENCES offer_catalog(code),
        offer_price_cents INTEGER NOT NULL,
        expected_margin_cents INTEGER NOT NULL,
        copy_rendered TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        channel VARCHAR(20) NOT NULL DEFAULT 'sms',
        origin VARCHAR(20) NOT NULL DEFAULT 'operator',
        created_by VARCHAR(36) REFERENCES users(id),
        accept_token VARCHAR(32) UNIQUE NOT NULL,
        attributes JSON,
        scheduled_for TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP NOT NULL,
        sent_at TIMESTAMP,
        opened_at TIMESTAMP,
        clicked_at TIMESTAMP,
        accepted_at TIMESTAMP,
        declined_at TIMESTAMP,
        CONSTRAINT ck_attach_offer_status CHECK (status IN ('pending','sent','opened','clicked','accepted','declined','expired','converted','failed')),
        CONSTRAINT ck_attach_offer_channel CHECK (channel IN ('sms','push','email','in_app')),
        CONSTRAINT ck_attach_offer_origin CHECK (origin IN ('operator','vision','rules','crew_note'))
    )"""),
    # attach_conversions
    dedent("""\
    CREATE TABLE IF NOT EXISTS attach_conversions (
        id VARCHAR(36) PRIMARY KEY,
        offer_id VARCHAR(36) NOT NULL UNIQUE REFERENCES attach_offers(id) ON DELETE CASCADE,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id),
        customer_id VARCHAR(36) REFERENCES users(id),
        stripe_payment_intent_id VARCHAR(255),
        amount_cents INTEGER NOT NULL,
        margin_cents INTEGER NOT NULL,
        scheduled_for TIMESTAMP,
        payment_method_id VARCHAR(255),
        fulfilled_at TIMESTAMP,
        fulfillment_notes TEXT,
        follow_on_job_id VARCHAR(36) REFERENCES jobs(id),
        created_at TIMESTAMP NOT NULL
    )"""),
    # Donation / Resale Rescue Engine -- spec 05-donation-resale-engine.md
    # item_valuations
    dedent("""\
    CREATE TABLE IF NOT EXISTS item_valuations (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        item_label VARCHAR(64) NOT NULL,
        display_name VARCHAR(128) NOT NULL,
        condition_grade VARCHAR(1),
        est_fmv_low_cents INTEGER NOT NULL DEFAULT 0,
        est_fmv_high_cents INTEGER NOT NULL DEFAULT 0,
        resale_probability FLOAT NOT NULL DEFAULT 0.0,
        donation_eligible BOOLEAN NOT NULL DEFAULT FALSE,
        hazmat_flag BOOLEAN NOT NULL DEFAULT FALSE,
        high_value BOOLEAN NOT NULL DEFAULT FALSE,
        reasoning VARCHAR(512),
        model VARCHAR(64) NOT NULL,
        prompt_hash VARCHAR(64) NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        cost_cents FLOAT NOT NULL DEFAULT 0.0,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_item_valuation_condition CHECK (condition_grade IS NULL OR condition_grade IN ('A','B','C','D'))
    )"""),
    # resale_listings
    dedent("""\
    CREATE TABLE IF NOT EXISTS resale_listings (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        valuation_id VARCHAR(36) REFERENCES item_valuations(id) ON DELETE SET NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'candidate',
        channel VARCHAR(20) NOT NULL DEFAULT 'none',
        channel_listing_id VARCHAR(128),
        channel_listing_url VARCHAR(512),
        title VARCHAR(200),
        description TEXT,
        list_price_cents INTEGER,
        sold_price_cents INTEGER,
        photo_urls JSON,
        est_fmv_low_cents INTEGER NOT NULL DEFAULT 0,
        est_fmv_high_cents INTEGER NOT NULL DEFAULT 0,
        customer_approval_at TIMESTAMP,
        listed_at TIMESTAMP,
        sold_at TIMESTAMP,
        expires_at TIMESTAMP,
        declined_reason VARCHAR(128),
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_resale_listing_status CHECK (status IN ('candidate','approved','declined','listed','sold','expired','donated')),
        CONSTRAINT ck_resale_listing_channel CHECK (channel IN ('none','fb_marketplace','offerup','ebay','habitat','goodwill'))
    )"""),
    # resale_splits
    dedent("""\
    CREATE TABLE IF NOT EXISTS resale_splits (
        id VARCHAR(36) PRIMARY KEY,
        listing_id VARCHAR(36) NOT NULL UNIQUE REFERENCES resale_listings(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        gross_cents INTEGER NOT NULL,
        customer_cut_cents INTEGER NOT NULL,
        umuve_cut_cents INTEGER NOT NULL,
        customer_share FLOAT NOT NULL DEFAULT 0.40,
        umuve_share FLOAT NOT NULL DEFAULT 0.60,
        stripe_payment_intent_id VARCHAR(128),
        stripe_transfer_id VARCHAR(128),
        customer_payout_status VARCHAR(20) NOT NULL DEFAULT 'pending',
        settled_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_resale_split_payout_status CHECK (customer_payout_status IN ('pending','paid','failed')),
        CONSTRAINT ck_resale_split_nonneg CHECK (gross_cents >= 0 AND customer_cut_cents >= 0 AND umuve_cut_cents >= 0)
    )"""),
    # donation_receipts
    dedent("""\
    CREATE TABLE IF NOT EXISTS donation_receipts (
        id VARCHAR(36) PRIMARY KEY,
        quote_item_id VARCHAR(36) NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
        quote_id VARCHAR(36) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
        listing_id VARCHAR(36) REFERENCES resale_listings(id) ON DELETE SET NULL,
        charity_partner_name VARCHAR(128) NOT NULL,
        charity_partner_ein VARCHAR(32),
        charity_address VARCHAR(512),
        item_description TEXT NOT NULL,
        condition_grade VARCHAR(1),
        fair_market_value_cents INTEGER NOT NULL DEFAULT 0,
        drop_off_at TIMESTAMP,
        drop_off_photo_url VARCHAR(512),
        form_8283_pdf_url VARCHAR(512),
        docusign_envelope_id VARCHAR(128),
        customer_signed_at TIMESTAMP,
        customer_email VARCHAR(255),
        receipt_number VARCHAR(32) UNIQUE,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_donation_receipt_condition CHECK (condition_grade IS NULL OR condition_grade IN ('A','B','C','D'))
    )"""),
    # ------------------------------------------------------------------
    # Life-Event Demand Trigger Engine (spec 03-life-event-triggers.md)
    # ------------------------------------------------------------------
    # life_events
    dedent("""\
    CREATE TABLE IF NOT EXISTS life_events (
        id VARCHAR(36) PRIMARY KEY,
        source VARCHAR(32) NOT NULL,
        source_record_id VARCHAR(128) NOT NULL,
        event_type VARCHAR(32) NOT NULL,
        event_date TIMESTAMP,
        county VARCHAR(32) NOT NULL,
        zip_code VARCHAR(10),
        address_line1 VARCHAR(255),
        apn VARCHAR(64),
        prospect_name VARCHAR(255),
        prospect_phone_e164 VARCHAR(20),
        prospect_email VARCHAR(255),
        raw_payload JSON,
        pii_hydrated BOOLEAN NOT NULL DEFAULT FALSE,
        sensitive BOOLEAN NOT NULL DEFAULT FALSE,
        pipeline_status VARCHAR(24) NOT NULL DEFAULT 'new',
        suppressed_reason VARCHAR(64),
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_life_events_event_type CHECK (event_type IN (
            'deed_transfer','moving_permit','estate','probate_filing','mls_closing',
            'building_permit','divorce_filing','eviction','bankruptcy','obituary'
        )),
        CONSTRAINT ck_life_events_county CHECK (county IN ('miami-dade','broward','palm-beach')),
        CONSTRAINT ck_life_events_pipeline_status CHECK (pipeline_status IN (
            'new','matched','queued','contacted','converted','suppressed','stale'
        )),
        CONSTRAINT uq_life_events_source_record UNIQUE (source, source_record_id)
    )"""),
    # lead_pipelines
    dedent("""\
    CREATE TABLE IF NOT EXISTS lead_pipelines (
        id VARCHAR(36) PRIMARY KEY,
        life_event_id VARCHAR(36) NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
        assigned_operator_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        stage VARCHAR(24) NOT NULL DEFAULT 'inbox',
        priority VARCHAR(10) NOT NULL DEFAULT 'normal',
        projected_quote_low_cents INTEGER,
        projected_quote_high_cents INTEGER,
        last_stage_change_at TIMESTAMP NOT NULL,
        claimed_at TIMESTAMP,
        notes TEXT,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_lead_pipelines_stage CHECK (stage IN (
            'inbox','qualified','outreach_drafted','outreach_sent','replied',
            'booked','closed_won','closed_lost','blocked'
        )),
        CONSTRAINT ck_lead_pipelines_priority CHECK (priority IN ('low','normal','high','urgent'))
    )"""),
    # tcpa_consents
    dedent("""\
    CREATE TABLE IF NOT EXISTS tcpa_consents (
        id VARCHAR(36) PRIMARY KEY,
        phone_e164 VARCHAR(20),
        email VARCHAR(255),
        channel VARCHAR(16) NOT NULL,
        consent_method VARCHAR(32) NOT NULL,
        consent_source_url VARCHAR(512),
        consent_ip VARCHAR(45),
        consent_user_agent VARCHAR(512),
        consent_text_hash VARCHAR(64),
        granted_at TIMESTAMP NOT NULL,
        revoked_at TIMESTAMP,
        revoked_reason VARCHAR(64),
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_tcpa_consents_channel CHECK (channel IN ('sms','call','email','direct_mail')),
        CONSTRAINT ck_tcpa_consents_method CHECK (consent_method IN (
            'express_written','web_form','sms_double_opt_in','existing_business',
            'inbound_call','manual_admin'
        )),
        CONSTRAINT ck_tcpa_consents_identifier_present CHECK (phone_e164 IS NOT NULL OR email IS NOT NULL)
    )"""),
    # outreach_logs
    dedent("""\
    CREATE TABLE IF NOT EXISTS outreach_logs (
        id VARCHAR(36) PRIMARY KEY,
        life_event_id VARCHAR(36) NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
        pipeline_id VARCHAR(36) REFERENCES lead_pipelines(id) ON DELETE SET NULL,
        channel VARCHAR(16) NOT NULL,
        to_phone_e164 VARCHAR(20),
        to_email VARCHAR(255),
        to_address_line1 VARCHAR(255),
        subject VARCHAR(255),
        body_rendered TEXT,
        regulatory_disclaimer TEXT NOT NULL,
        tcpa_consent_id VARCHAR(36) REFERENCES tcpa_consents(id) ON DELETE SET NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'drafted',
        block_reason VARCHAR(64),
        provider VARCHAR(24),
        provider_msg_id VARCHAR(128),
        cost_cents INTEGER,
        created_at TIMESTAMP NOT NULL,
        sent_at TIMESTAMP,
        CONSTRAINT ck_outreach_logs_channel CHECK (channel IN ('sms','call','email','direct_mail')),
        CONSTRAINT ck_outreach_logs_status CHECK (status IN (
            'drafted','queued','sent','delivered','bounced','opted_out','blocked','failed'
        ))
    )"""),
    # ------------------------------------------------------------------
    # Landfill Routing Optimizer (spec 06)
    # ------------------------------------------------------------------
    # landfill_facilities
    dedent("""\
    CREATE TABLE IF NOT EXISTS landfill_facilities (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(128) NOT NULL UNIQUE,
        type VARCHAR(24) NOT NULL,
        operator VARCHAR(128),
        permit_no VARCHAR(64),
        address VARCHAR(512) NOT NULL,
        lat DOUBLE PRECISION NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        county VARCHAR(32) NOT NULL,
        accepts_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
        hours_json JSONB,
        phone VARCHAR(32),
        scale_method VARCHAR(16) NOT NULL DEFAULT 'per_ton',
        avg_turnaround_min INTEGER NOT NULL DEFAULT 25,
        notes TEXT,
        fee_accuracy_validated BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_landfill_facility_type CHECK (type IN (
            'transfer_station','landfill','mrf','c_and_d','wte'
        )),
        CONSTRAINT ck_landfill_facility_scale_method CHECK (scale_method IN (
            'per_ton','per_cu_yd','flat'
        ))
    )"""),
    # tip_fees
    dedent("""\
    CREATE TABLE IF NOT EXISTS tip_fees (
        id VARCHAR(36) PRIMARY KEY,
        facility_id VARCHAR(36) NOT NULL REFERENCES landfill_facilities(id) ON DELETE CASCADE,
        category VARCHAR(24) NOT NULL,
        fee_amount DOUBLE PRECISION NOT NULL,
        fee_unit VARCHAR(16) NOT NULL DEFAULT 'per_ton',
        effective_from TIMESTAMP NOT NULL,
        effective_to TIMESTAMP,
        source VARCHAR(12) NOT NULL DEFAULT 'seed',
        confidence DOUBLE PRECISION NOT NULL DEFAULT 0.70,
        captured_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_tip_fee_category CHECK (category IN (
            'msw','c_and_d','yard','bulky','metal','appliance_w_freon',
            'mattress','tires','concrete','drywall','mixed'
        )),
        CONSTRAINT ck_tip_fee_unit CHECK (fee_unit IN (
            'per_ton','per_cu_yd','per_item','flat'
        )),
        CONSTRAINT ck_tip_fee_source CHECK (source IN (
            'scrape','phone','manual','api','seed'
        ))
    )"""),
    # route_optimizations
    dedent("""\
    CREATE TABLE IF NOT EXISTS route_optimizations (
        id VARCHAR(36) PRIMARY KEY,
        vehicle_id VARCHAR(36),
        vehicle_label VARCHAR(64),
        capacity_tons DOUBLE PRECISION NOT NULL DEFAULT 4.0,
        run_date TIMESTAMP NOT NULL,
        candidates_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        chosen_facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        predicted_total_cost_cents INTEGER NOT NULL DEFAULT 0,
        predicted_tipping_cents INTEGER NOT NULL DEFAULT 0,
        predicted_fuel_cents INTEGER NOT NULL DEFAULT 0,
        predicted_labor_cents INTEGER NOT NULL DEFAULT 0,
        predicted_drive_minutes INTEGER NOT NULL DEFAULT 0,
        baseline_total_cost_cents INTEGER NOT NULL DEFAULT 0,
        baseline_facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        savings_cents INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(16) NOT NULL DEFAULT 'planned',
        solver_version VARCHAR(32) NOT NULL DEFAULT 'v1',
        solver_mode VARCHAR(32) NOT NULL DEFAULT 'branch_and_bound_fallback',
        notes TEXT,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_route_optimization_status CHECK (status IN (
            'planned','dispatched','completed','voided'
        )),
        CONSTRAINT ck_route_optimization_solver_mode CHECK (solver_mode IN (
            'ortools_vrp','branch_and_bound_fallback','nearest'
        ))
    )"""),
    # route_stops
    dedent("""\
    CREATE TABLE IF NOT EXISTS route_stops (
        id VARCHAR(36) PRIMARY KEY,
        route_id VARCHAR(36) NOT NULL REFERENCES route_optimizations(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL,
        stop_type VARCHAR(16) NOT NULL,
        job_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        facility_id VARCHAR(36) REFERENCES landfill_facilities(id) ON DELETE SET NULL,
        lat DOUBLE PRECISION NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        distance_meters INTEGER,
        drive_seconds INTEGER,
        service_seconds INTEGER,
        estimated_load_tons DOUBLE PRECISION,
        earliest_arrival TIMESTAMP,
        latest_arrival TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_route_stop_type CHECK (stop_type IN (
            'pickup','facility','depot_start','depot_end'
        ))
    )"""),
    # Voice AI (spec 02) — PostgreSQL variants
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_calls (
        id VARCHAR(36) PRIMARY KEY,
        vapi_call_id VARCHAR(64) UNIQUE NOT NULL,
        twilio_call_sid VARCHAR(64),
        caller_number VARCHAR(20) NOT NULL,
        called_number VARCHAR(20) NOT NULL,
        started_at TIMESTAMP NOT NULL,
        answered_at TIMESTAMP,
        ended_at TIMESTAMP,
        duration_s INTEGER,
        cost_usd FLOAT,
        status VARCHAR(24),
        outcome_id VARCHAR(36),
        recording_url VARCHAR(512),
        consent_given BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP,
        CONSTRAINT ck_voice_calls_status CHECK (
            status IS NULL OR status IN ('in_progress','completed','failed','spam')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_turns (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
        turn_index INTEGER NOT NULL,
        role VARCHAR(12) NOT NULL,
        text TEXT NOT NULL,
        tool_name VARCHAR(64),
        tool_input JSON,
        tool_output JSON,
        latency_ms INTEGER,
        created_at TIMESTAMP,
        CONSTRAINT ck_voice_call_turns_role CHECK (role IN ('caller','agent','tool'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_transcripts (
        call_id VARCHAR(36) PRIMARY KEY REFERENCES voice_calls(id) ON DELETE CASCADE,
        full_text TEXT NOT NULL,
        summary TEXT,
        sentiment VARCHAR(16),
        tags JSON,
        CONSTRAINT ck_voice_call_transcripts_sentiment CHECK (
            sentiment IS NULL OR sentiment IN ('positive','neutral','negative','grief')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_call_outcomes (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL UNIQUE REFERENCES voice_calls(id) ON DELETE CASCADE,
        booked BOOLEAN DEFAULT FALSE,
        booking_id VARCHAR(36) REFERENCES jobs(id),
        quote_id VARCHAR(36) REFERENCES quotes(id),
        quoted_amount FLOAT,
        paid BOOLEAN DEFAULT FALSE,
        payment_link_url VARCHAR(512),
        stripe_session_id VARCHAR(128),
        escalated BOOLEAN DEFAULT FALSE,
        escalation_reason VARCHAR(32),
        abandon_stage VARCHAR(32),
        discount_pct FLOAT,
        CONSTRAINT ck_voice_call_outcomes_escalation_reason CHECK (
            escalation_reason IS NULL OR escalation_reason IN
            ('commercial','estate','complex','complaint','consent_refused','out_of_area')
        ),
        CONSTRAINT ck_voice_call_outcomes_abandon_stage CHECK (
            abandon_stage IS NULL OR abandon_stage IN
            ('qualify','photo','quote','book','pay')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS voice_sms_exchanges (
        id VARCHAR(36) PRIMARY KEY,
        call_id VARCHAR(36) NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
        direction VARCHAR(4) NOT NULL,
        purpose VARCHAR(24) NOT NULL,
        body TEXT NOT NULL,
        media_url VARCHAR(512),
        twilio_sid VARCHAR(64) UNIQUE,
        delivered BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP,
        CONSTRAINT ck_voice_sms_exchanges_direction CHECK (direction IN ('in','out')),
        CONSTRAINT ck_voice_sms_exchanges_purpose CHECK (
            purpose IN ('photo_request','quote_link','payment_link','confirmation')
        )
    )"""),

    # ---------------------------------------------------------------
    # B2B Commercial Portal (spec 04)
    # ---------------------------------------------------------------
    dedent("""\
    CREATE TABLE IF NOT EXISTS orgs (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        slug VARCHAR(60) NOT NULL UNIQUE,
        tax_id VARCHAR(32),
        billing_email VARCHAR(120) NOT NULL,
        billing_address JSON,
        stripe_customer_id VARCHAR(64) UNIQUE,
        stripe_subscription_id VARCHAR(64),
        tier VARCHAR(20) NOT NULL DEFAULT 'starter',
        status VARCHAR(20) NOT NULL DEFAULT 'trial',
        sso_provider VARCHAR(32),
        sso_domain VARCHAR(120),
        auto_pay BOOLEAN DEFAULT TRUE,
        net_terms_days INTEGER DEFAULT 0,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        CONSTRAINT ck_org_tier CHECK (tier IN ('starter','pro','enterprise')),
        CONSTRAINT ck_org_status CHECK (
            status IN ('trial','active','past_due','paused','churned')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS org_members (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL,
        scopes JSON,
        invited_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        invite_token VARCHAR(80) UNIQUE,
        invited_at TIMESTAMP,
        joined_at TIMESTAMP,
        CONSTRAINT ck_orgmember_role CHECK (
            role IN ('owner','admin','operator','viewer')
        ),
        CONSTRAINT ix_orgmember_org_user UNIQUE (org_id, user_id)
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_properties (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        name VARCHAR(120) NOT NULL,
        address_line1 VARCHAR(160),
        address_line2 VARCHAR(160),
        city VARCHAR(60),
        state VARCHAR(2),
        zip VARCHAR(10),
        lat DOUBLE PRECISION,
        lng DOUBLE PRECISION,
        external_ref VARCHAR(64),
        source VARCHAR(16) DEFAULT 'manual',
        unit_count INTEGER DEFAULT 1,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS contracts (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        tier VARCHAR(20) NOT NULL,
        monthly_base_cents INTEGER NOT NULL,
        metered_per_pickup_cents INTEGER DEFAULT 0,
        metered_per_ton_cents INTEGER DEFAULT 0,
        included_pickups INTEGER DEFAULT 0,
        pricing_overrides JSON,
        effective_from TIMESTAMP NOT NULL,
        effective_to TIMESTAMP,
        signed_pdf_s3_key VARCHAR(240),
        created_at TIMESTAMP,
        CONSTRAINT ck_contract_tier CHECK (
            tier IN ('starter','pro','enterprise')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_invoices (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        number VARCHAR(24) NOT NULL UNIQUE,
        period_start TIMESTAMP NOT NULL,
        period_end TIMESTAMP NOT NULL,
        subtotal_cents INTEGER NOT NULL DEFAULT 0,
        tax_cents INTEGER DEFAULT 0,
        total_cents INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        stripe_invoice_id VARCHAR(64),
        due_at TIMESTAMP,
        paid_at TIMESTAMP,
        sent_at TIMESTAMP,
        created_at TIMESTAMP,
        CONSTRAINT ck_portal_invoice_status CHECK (
            status IN ('draft','open','paid','past_due','void')
        )
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_invoice_line_items (
        id VARCHAR(36) PRIMARY KEY,
        invoice_id VARCHAR(36) NOT NULL
            REFERENCES portal_invoices(id) ON DELETE CASCADE,
        job_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        property_id VARCHAR(36)
            REFERENCES portal_properties(id) ON DELETE SET NULL,
        description VARCHAR(240),
        quantity DOUBLE PRECISION DEFAULT 1.0,
        unit_cents INTEGER NOT NULL DEFAULT 0,
        amount_cents INTEGER NOT NULL DEFAULT 0
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_payment_methods (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        kind VARCHAR(16) NOT NULL,
        stripe_payment_method_id VARCHAR(64),
        last4 VARCHAR(4),
        bank_name VARCHAR(60),
        is_default BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP,
        CONSTRAINT ck_portal_pm_kind CHECK (kind IN ('ach','card','check'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_audit_logs (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36),
        user_id VARCHAR(36),
        action VARCHAR(60) NOT NULL,
        object_type VARCHAR(40),
        object_id VARCHAR(36),
        before JSON,
        after JSON,
        ip VARCHAR(45),
        user_agent VARCHAR(240),
        created_at TIMESTAMP
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_api_keys (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        name VARCHAR(80),
        prefix VARCHAR(16),
        hashed_key VARCHAR(128) NOT NULL UNIQUE,
        scopes JSON,
        last_used_at TIMESTAMP,
        revoked_at TIMESTAMP,
        created_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP
    )"""),
]
NEW_TABLES_PG.extend(_PARTNER_PG)
NEW_TABLES_PG.extend(_OPS_PG)
NEW_TABLES_PG.extend(_PORTAL_V1_PG)
NEW_TABLES_PG.extend(_OPS_V1_PG)
NEW_TABLES_PG.extend(_PORTAL_SSO_PG)

# Table names for the new tables (used for reporting)
NEW_TABLE_NAMES = [
    "referrals",
    "recurring_bookings",
    "device_tokens",
    "pricing_config",
    "operator_invites",
    "promo_codes",
    "chat_messages",
    "reviews",
    "refunds",
    "webhook_events",
    # Vision Quote Engine (spec 01)
    "quotes",
    "quote_items",
    "vision_inference_logs",
    "quote_feedback",
    "calibration_samples",
    # Post-Haul Attach Engine (spec 09)
    "offer_catalog",
    "attach_offers",
    "attach_conversions",
    # Donation / Resale Rescue Engine (spec 05)
    "item_valuations",
    "resale_listings",
    "resale_splits",
    "donation_receipts",
    # Life-Event Demand Trigger Engine (spec 03)
    "life_events",
    "lead_pipelines",
    "tcpa_consents",
    "outreach_logs",
    # Landfill Routing Optimizer (spec 06)
    "landfill_facilities",
    "tip_fees",
    "route_optimizations",
    "route_stops",
    # Voice AI Inbound (spec 02)
    "voice_calls",
    "voice_call_turns",
    "voice_call_transcripts",
    "voice_call_outcomes",
    "voice_sms_exchanges",
    # B2B Commercial Portal (spec 04)
    "orgs",
    "org_members",
    "portal_properties",
    "contracts",
    "portal_invoices",
    "portal_invoice_line_items",
    "portal_payment_methods",
    "portal_audit_logs",
    "portal_api_keys",
]
NEW_TABLE_NAMES.extend(_PARTNER_NAMES)
NEW_TABLE_NAMES.extend(_OPS_NAMES)
NEW_TABLE_NAMES.extend(_PORTAL_V1_NAMES)
NEW_TABLE_NAMES.extend(_OPS_V1_NAMES)
NEW_TABLE_NAMES.extend(_PORTAL_SSO_NAMES)

# ---------------------------------------------------------------------------
# job_offers — marketplace broadcast / first-to-accept (Growth-1)
# ---------------------------------------------------------------------------
_JOB_OFFERS_SQLITE = dedent("""\
    CREATE TABLE IF NOT EXISTS job_offers (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        contractor_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        status VARCHAR(20) NOT NULL DEFAULT 'sent',
        accept_token VARCHAR(36) UNIQUE NOT NULL,
        distance_miles FLOAT,
        payout_amount FLOAT,
        sent_at DATETIME,
        responded_at DATETIME,
        expires_at DATETIME,
        created_at DATETIME,
        CONSTRAINT ck_job_offer_status CHECK (status IN ('sent','accepted','declined','expired','superseded'))
    )""")
_JOB_OFFERS_PG = dedent("""\
    CREATE TABLE IF NOT EXISTS job_offers (
        id VARCHAR(36) PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        contractor_id VARCHAR(36) NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
        status VARCHAR(20) NOT NULL DEFAULT 'sent',
        accept_token VARCHAR(36) UNIQUE NOT NULL,
        distance_miles DOUBLE PRECISION,
        payout_amount DOUBLE PRECISION,
        sent_at TIMESTAMP,
        responded_at TIMESTAMP,
        expires_at TIMESTAMP,
        created_at TIMESTAMP,
        CONSTRAINT ck_job_offer_status CHECK (status IN ('sent','accepted','declined','expired','superseded'))
    )""")
NEW_TABLES_SQLITE.append(_JOB_OFFERS_SQLITE)
NEW_TABLES_PG.append(_JOB_OFFERS_PG)
NEW_TABLE_NAMES.append("job_offers")

# Tables that require Postgres Row-Level Security. On SQLite the app-layer
# tenant_guard middleware is the sole enforcer. Spec 04 §3.
RLS_ORG_TABLES = [
    "orgs",
    "org_members",
    "portal_properties",
    "contracts",
    "portal_invoices",
    "portal_payment_methods",
    "portal_audit_logs",
    "portal_api_keys",
]
RLS_ORG_TABLES.extend(_PORTAL_V1_RLS)


# ---------------------------------------------------------------------------
# Migration engine
# ---------------------------------------------------------------------------

def _get_existing_columns_sqlite(cursor, table):
    """Return set of column names for a table in SQLite."""
    cursor.execute("PRAGMA table_info('{}')".format(table))
    return {row[1] for row in cursor.fetchall()}


def _get_existing_columns_pg(cursor, table):
    """Return set of column names for a table in PostgreSQL."""
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s",
        (table,),
    )
    return {row[0] for row in cursor.fetchall()}


def _table_exists_sqlite(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _table_exists_pg(cursor, table):
    cursor.execute(
        "SELECT EXISTS ("
        "  SELECT FROM information_schema.tables "
        "  WHERE table_name = %s"
        ")",
        (table,),
    )
    return cursor.fetchone()[0]


def run_migrations(database_url=None):
    """
    Run all pending migrations.

    Returns a list of action strings describing what was done.
    """
    if database_url is None:
        database_url = _resolve_database_url()

    is_sqlite = _is_sqlite(database_url)
    actions = []

    if is_sqlite:
        import sqlite3
        # Extract the file path from the URL
        # "sqlite:///umuve.db" -> "umuve.db"
        # "sqlite:////absolute/path/db" -> "/absolute/path/db"
        db_path = database_url.replace("sqlite:///", "", 1)
        if not db_path:
            db_path = "umuve.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ---- Add missing columns to existing tables ----
        for table, column, sql_type, _pg_type, default in COLUMN_MIGRATIONS:
            if not _table_exists_sqlite(cursor, table):
                # Table doesn't exist yet -- it will be created below or by create_all
                continue
            existing = _get_existing_columns_sqlite(cursor, table)
            if column not in existing:
                default_clause = " DEFAULT {}".format(default) if default and default != "NULL" else ""
                stmt = "ALTER TABLE {} ADD COLUMN {} {}{}".format(
                    table, column, sql_type, default_clause
                )
                cursor.execute(stmt)
                actions.append("Added column {}.{}  ({}{})".format(
                    table, column, sql_type, default_clause
                ))

        # ---- Create new tables ----
        for name, ddl in zip(NEW_TABLE_NAMES, NEW_TABLES_SQLITE):
            if not _table_exists_sqlite(cursor, name):
                cursor.execute(ddl)
                actions.append("Created table {}".format(name))
            else:
                actions.append("Table {} already exists -- skipped".format(name))

        # ---- Ops Supervisor indexes (idempotent CREATE INDEX IF NOT EXISTS) ----
        for ddl in _OPS_INDEXES_SQLITE:
            cursor.execute(ddl)
        for ddl in _OPS_V1_INDEXES_SQLITE:
            cursor.execute(ddl)

        conn.commit()
        conn.close()

    else:
        # PostgreSQL
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()

        # ---- Add missing columns to existing tables ----
        for table, column, _sqlite_type, sql_type, default in COLUMN_MIGRATIONS:
            if not _table_exists_pg(cursor, table):
                continue
            existing = _get_existing_columns_pg(cursor, table)
            if column not in existing:
                default_clause = " DEFAULT {}".format(default) if default and default != "NULL" else ""
                stmt = "ALTER TABLE {} ADD COLUMN {} {}{}".format(
                    table, column, sql_type, default_clause
                )
                cursor.execute(stmt)
                actions.append("Added column {}.{}  ({}{})".format(
                    table, column, sql_type, default_clause
                ))

        # ---- Create new tables ----
        for name, ddl in zip(NEW_TABLE_NAMES, NEW_TABLES_PG):
            if not _table_exists_pg(cursor, name):
                cursor.execute(ddl)
                actions.append("Created table {}".format(name))
            else:
                actions.append("Table {} already exists -- skipped".format(name))

        # ---- Ops Supervisor indexes (idempotent) ----
        for ddl in _OPS_INDEXES_PG:
            cursor.execute(ddl)
        for ddl in _OPS_V1_INDEXES_PG:
            cursor.execute(ddl)

        # ---- Apply Row-Level Security to org-scoped tables (spec 04 §3) ----
        # Idempotent: ENABLE RLS is a no-op if already enabled; we DROP the
        # policy before CREATE so re-runs don't error on duplicate names.
        for table in RLS_ORG_TABLES:
            if not _table_exists_pg(cursor, table):
                continue
            pkey = "id" if table == "orgs" else "org_id"
            policy = "rls_{}_org".format(table)
            try:
                cursor.execute(
                    "ALTER TABLE {} ENABLE ROW LEVEL SECURITY".format(table)
                )
                cursor.execute(
                    "DROP POLICY IF EXISTS {} ON {}".format(policy, table)
                )
                cursor.execute(
                    "CREATE POLICY {} ON {} USING ("
                    "{} = current_setting('app.current_org_id', true)"
                    ")".format(policy, table, pkey)
                )
                actions.append("Applied RLS policy to {}".format(table))
            except Exception as exc:
                # RLS is Postgres >= 9.5; degrade gracefully if ALTER fails.
                actions.append(
                    "RLS skipped for {} ({})".format(table, exc)
                )

        cursor.close()
        conn.close()

    if not any("Added" in a or "Created table" in a for a in actions):
        actions.append("Database is up to date -- nothing to do.")

    return actions


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Umuve Database Migration")
    print("=" * 60)

    url = _resolve_database_url()
    db_type = "SQLite" if _is_sqlite(url) else "PostgreSQL"
    safe_url = url if _is_sqlite(url) else url.split("@")[-1] if "@" in url else url
    print("Database: {} ({})".format(safe_url, db_type))
    print("-" * 60)

    actions = run_migrations(url)
    for action in actions:
        print("  -> {}".format(action))

    print("-" * 60)
    print("Migration complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
