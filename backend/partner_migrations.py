"""
Partner (Driver) Acquisition Agent — migration DDL (spec 07 §4).

The orchestrator will merge the dicts / lists exposed here into `migrate.py`
after the build. Ordering inside NEW_TABLE_NAMES matches NEW_TABLES_SQLITE
and NEW_TABLES_PG (zip-paired) — do not re-order without mirroring.

Isolation rule: we do NOT edit `migrate.py` directly because multiple build
agents are running in parallel.

Only `driver_leads` carries an org_id-style tenant column; the spec-07 MVP
is single-tenant (Umuve itself), so RLS_ORG_TABLES stays empty.
"""

from textwrap import dedent


# ---------------------------------------------------------------------------
# SQLite DDL
# ---------------------------------------------------------------------------
NEW_TABLES_SQLITE = [
    # lead_sources — created first, driver_leads FKs into it.
    dedent("""\
    CREATE TABLE IF NOT EXISTS lead_sources (
        id VARCHAR(36) PRIMARY KEY,
        platform VARCHAR(24) NOT NULL,
        search_url TEXT NOT NULL,
        metro VARCHAR(16),
        last_scraped_at DATETIME,
        health_status VARCHAR(24) NOT NULL DEFAULT 'healthy',
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_lead_source_platform CHECK (platform IN ('fb_marketplace','craigslist','thumbtack','nextdoor','indeed')),
        CONSTRAINT ck_lead_source_health CHECK (health_status IN ('healthy','rate_limited','banned'))
    )"""),
    # driver_leads
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_leads (
        id VARCHAR(36) PRIMARY KEY,
        source_id VARCHAR(36) REFERENCES lead_sources(id) ON DELETE SET NULL,
        external_ref VARCHAR(255),
        raw_listing_json TEXT,
        name_guess VARCHAR(255),
        phone_e164 VARCHAR(20),
        email VARCHAR(255),
        metro VARCHAR(16),
        state VARCHAR(24) NOT NULL DEFAULT 'NEW',
        qualification_score INTEGER,
        assigned_agent_run_id VARCHAR(36),
        dedupe_hash VARCHAR(64) NOT NULL,
        opted_out BOOLEAN NOT NULL DEFAULT 0,
        platform VARCHAR(24),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT uq_driver_leads_dedupe_hash UNIQUE (dedupe_hash),
        CONSTRAINT ck_driver_lead_state CHECK (state IN ('NEW','OUTREACHED','RESPONDED','QUALIFIED','ONBOARDING','ACTIVE','REJECTED','HUMAN_REVIEW'))
    )"""),
    # outreach_attempts
    dedent("""\
    CREATE TABLE IF NOT EXISTS outreach_attempts (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        channel VARCHAR(16) NOT NULL,
        direction VARCHAR(4) NOT NULL,
        body TEXT,
        claude_prompt_hash VARCHAR(64),
        response_latency_sec INTEGER,
        sentiment VARCHAR(16),
        twilio_sid VARCHAR(64),
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_outreach_channel CHECK (channel IN ('sms','email','fb_msg')),
        CONSTRAINT ck_outreach_direction CHECK (direction IN ('out','in')),
        CONSTRAINT ck_outreach_sentiment CHECK (sentiment IS NULL OR sentiment IN ('positive','neutral','negative','red_flag'))
    )"""),
    # driver_qualifications
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_qualifications (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        has_truck BOOLEAN,
        truck_type VARCHAR(24),
        has_insurance BOOLEAN,
        has_license BOOLEAN,
        past_hauling_years INTEGER,
        self_reported_availability_hours INTEGER,
        consent_checkr BOOLEAN NOT NULL DEFAULT 0,
        consent_sms BOOLEAN NOT NULL DEFAULT 0,
        ssn_last_4 VARCHAR(8),
        completed_at DATETIME,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_qualification_truck_type CHECK (truck_type IS NULL OR truck_type IN ('pickup','box','flatbed','van','other'))
    )"""),
    # background_checks
    dedent("""\
    CREATE TABLE IF NOT EXISTS background_checks (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        checkr_candidate_id VARCHAR(128),
        checkr_report_id VARCHAR(128),
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        mvr_status VARCHAR(32),
        criminal_status VARCHAR(32),
        adverse_action_sent_at DATETIME,
        adverse_action_due_at DATETIME,
        raw_webhook_json TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_bg_check_status CHECK (status IN ('pending','clear','consider','suspended'))
    )"""),
    # driver_onboarding_steps
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_onboarding_steps (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        step VARCHAR(32) NOT NULL,
        completed_at DATETIME,
        payload_json TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_onboarding_step CHECK (step IN ('stripe_link_sent','stripe_kyc_done','app_installed','sim_dispatch_done'))
    )"""),
    # driver_onboarding_audits
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_onboarding_audits (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        actor VARCHAR(64) NOT NULL,
        action VARCHAR(64) NOT NULL,
        before_state VARCHAR(24),
        after_state VARCHAR(24),
        payload_json TEXT,
        created_at DATETIME NOT NULL
    )"""),
]


# ---------------------------------------------------------------------------
# PostgreSQL DDL — mirrors SQLite with PG-native types (JSONB, TIMESTAMP).
# ---------------------------------------------------------------------------
NEW_TABLES_PG = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS lead_sources (
        id VARCHAR(36) PRIMARY KEY,
        platform VARCHAR(24) NOT NULL,
        search_url TEXT NOT NULL,
        metro VARCHAR(16),
        last_scraped_at TIMESTAMP,
        health_status VARCHAR(24) NOT NULL DEFAULT 'healthy',
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_lead_source_platform CHECK (platform IN ('fb_marketplace','craigslist','thumbtack','nextdoor','indeed')),
        CONSTRAINT ck_lead_source_health CHECK (health_status IN ('healthy','rate_limited','banned'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_leads (
        id VARCHAR(36) PRIMARY KEY,
        source_id VARCHAR(36) REFERENCES lead_sources(id) ON DELETE SET NULL,
        external_ref VARCHAR(255),
        raw_listing_json JSONB,
        name_guess VARCHAR(255),
        phone_e164 VARCHAR(20),
        email VARCHAR(255),
        metro VARCHAR(16),
        state VARCHAR(24) NOT NULL DEFAULT 'NEW',
        qualification_score INTEGER,
        assigned_agent_run_id VARCHAR(36),
        dedupe_hash VARCHAR(64) NOT NULL,
        opted_out BOOLEAN NOT NULL DEFAULT FALSE,
        platform VARCHAR(24),
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT uq_driver_leads_dedupe_hash UNIQUE (dedupe_hash),
        CONSTRAINT ck_driver_lead_state CHECK (state IN ('NEW','OUTREACHED','RESPONDED','QUALIFIED','ONBOARDING','ACTIVE','REJECTED','HUMAN_REVIEW'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS outreach_attempts (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        channel VARCHAR(16) NOT NULL,
        direction VARCHAR(4) NOT NULL,
        body TEXT,
        claude_prompt_hash VARCHAR(64),
        response_latency_sec INTEGER,
        sentiment VARCHAR(16),
        twilio_sid VARCHAR(64),
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_outreach_channel CHECK (channel IN ('sms','email','fb_msg')),
        CONSTRAINT ck_outreach_direction CHECK (direction IN ('out','in')),
        CONSTRAINT ck_outreach_sentiment CHECK (sentiment IS NULL OR sentiment IN ('positive','neutral','negative','red_flag'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_qualifications (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        has_truck BOOLEAN,
        truck_type VARCHAR(24),
        has_insurance BOOLEAN,
        has_license BOOLEAN,
        past_hauling_years INTEGER,
        self_reported_availability_hours INTEGER,
        consent_checkr BOOLEAN NOT NULL DEFAULT FALSE,
        consent_sms BOOLEAN NOT NULL DEFAULT FALSE,
        ssn_last_4 VARCHAR(8),
        completed_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_qualification_truck_type CHECK (truck_type IS NULL OR truck_type IN ('pickup','box','flatbed','van','other'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS background_checks (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        checkr_candidate_id VARCHAR(128),
        checkr_report_id VARCHAR(128),
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        mvr_status VARCHAR(32),
        criminal_status VARCHAR(32),
        adverse_action_sent_at TIMESTAMP,
        adverse_action_due_at TIMESTAMP,
        raw_webhook_json JSONB,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_bg_check_status CHECK (status IN ('pending','clear','consider','suspended'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_onboarding_steps (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        step VARCHAR(32) NOT NULL,
        completed_at TIMESTAMP,
        payload_json JSONB,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_onboarding_step CHECK (step IN ('stripe_link_sent','stripe_kyc_done','app_installed','sim_dispatch_done'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS driver_onboarding_audits (
        id VARCHAR(36) PRIMARY KEY,
        lead_id VARCHAR(36) NOT NULL REFERENCES driver_leads(id) ON DELETE CASCADE,
        actor VARCHAR(64) NOT NULL,
        action VARCHAR(64) NOT NULL,
        before_state VARCHAR(24),
        after_state VARCHAR(24),
        payload_json JSONB,
        created_at TIMESTAMP NOT NULL
    )"""),
]


# Zip-paired with both lists above.
NEW_TABLE_NAMES = [
    "lead_sources",
    "driver_leads",
    "outreach_attempts",
    "driver_qualifications",
    "background_checks",
    "driver_onboarding_steps",
    "driver_onboarding_audits",
]

# Partner acquisition is single-tenant (Umuve itself); no RLS needed in MVP.
RLS_ORG_TABLES = []
