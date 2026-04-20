"""
Ops Supervisor Agent — migration SQL (spec 11, 72h MVP).

Exposes the same shape as ``migrate.py``'s ``NEW_TABLES_SQLITE`` /
``NEW_TABLES_PG`` so a future merge is a copy-paste. ``NEW_TABLE_NAMES`` is
provided for the migrate script's drop/idempotency scan.

These SQL strings and the ORM definitions in ``ops_supervisor_models.py``
MUST stay in sync. If you change one, change the other.
"""

from textwrap import dedent


NEW_TABLE_NAMES = [
    "ops_events",
    "ops_situations",
    "ops_agent_decisions",
    "ops_agent_actions",
    "ops_escalation_tickets",
]


NEW_TABLES_SQLITE = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_events (
        id VARCHAR(36) PRIMARY KEY,
        type VARCHAR(80) NOT NULL,
        booking_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        payload_json TEXT,
        source VARCHAR(40),
        received_at DATETIME NOT NULL,
        classifier_tag VARCHAR(60),
        classifier_confidence FLOAT
    )"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_events_booking_id
        ON ops_events(booking_id)"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_events_received_at
        ON ops_events(received_at)"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_events_type
        ON ops_events(type)"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_situations (
        id VARCHAR(36) PRIMARY KEY,
        booking_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        primary_event_id VARCHAR(36) REFERENCES ops_events(id) ON DELETE SET NULL,
        tag VARCHAR(60),
        context_snapshot_json TEXT,
        severity VARCHAR(10) NOT NULL DEFAULT 'low',
        opened_at DATETIME NOT NULL,
        closed_at DATETIME,
        outcome VARCHAR(60),
        CONSTRAINT ck_ops_situation_severity
            CHECK (severity IN ('info','low','medium','high','critical'))
    )"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_situations_booking_id
        ON ops_situations(booking_id)"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_situations_opened_at
        ON ops_situations(opened_at)"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_agent_decisions (
        id VARCHAR(36) PRIMARY KEY,
        situation_id VARCHAR(36) NOT NULL REFERENCES ops_situations(id) ON DELETE CASCADE,
        model VARCHAR(60) NOT NULL DEFAULT 'rules-mvp-v1',
        prompt_hash VARCHAR(64),
        decision_json TEXT,
        rationale TEXT,
        confidence FLOAT,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        latency_ms INTEGER,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_ops_decision_status
            CHECK (status IN ('pending','executed','blocked_by_guardrail','failed'))
    )"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_agent_decisions_situation_id
        ON ops_agent_decisions(situation_id)"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_agent_actions (
        id VARCHAR(36) PRIMARY KEY,
        decision_id VARCHAR(36) NOT NULL REFERENCES ops_agent_decisions(id) ON DELETE CASCADE,
        tool VARCHAR(40) NOT NULL,
        args_json TEXT,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        external_ref VARCHAR(255),
        error_message TEXT,
        executed_at DATETIME,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_ops_action_status
            CHECK (status IN ('pending','executed','blocked_by_guardrail','failed'))
    )"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_agent_actions_decision_id
        ON ops_agent_actions(decision_id)"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_escalation_tickets (
        id VARCHAR(36) PRIMARY KEY,
        situation_id VARCHAR(36) NOT NULL REFERENCES ops_situations(id) ON DELETE CASCADE,
        assignee VARCHAR(60),
        priority VARCHAR(4) NOT NULL DEFAULT 'p2',
        pagerduty_incident VARCHAR(120),
        summary_md TEXT,
        resolved_at DATETIME,
        resolution_note TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_ops_escalation_priority
            CHECK (priority IN ('p0','p1','p2'))
    )"""),
    dedent("""\
    CREATE INDEX IF NOT EXISTS ix_ops_escalation_tickets_situation_id
        ON ops_escalation_tickets(situation_id)"""),
]


# Postgres: mostly identical, TEXT -> JSONB, DATETIME -> TIMESTAMP.
NEW_TABLES_PG = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_events (
        id VARCHAR(36) PRIMARY KEY,
        type VARCHAR(80) NOT NULL,
        booking_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        payload_json JSONB,
        source VARCHAR(40),
        received_at TIMESTAMP NOT NULL,
        classifier_tag VARCHAR(60),
        classifier_confidence DOUBLE PRECISION
    )"""),
    "CREATE INDEX IF NOT EXISTS ix_ops_events_booking_id ON ops_events(booking_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_events_received_at ON ops_events(received_at)",
    "CREATE INDEX IF NOT EXISTS ix_ops_events_type ON ops_events(type)",

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_situations (
        id VARCHAR(36) PRIMARY KEY,
        booking_id VARCHAR(36) REFERENCES jobs(id) ON DELETE SET NULL,
        primary_event_id VARCHAR(36) REFERENCES ops_events(id) ON DELETE SET NULL,
        tag VARCHAR(60),
        context_snapshot_json JSONB,
        severity VARCHAR(10) NOT NULL DEFAULT 'low',
        opened_at TIMESTAMP NOT NULL,
        closed_at TIMESTAMP,
        outcome VARCHAR(60),
        CONSTRAINT ck_ops_situation_severity
            CHECK (severity IN ('info','low','medium','high','critical'))
    )"""),
    "CREATE INDEX IF NOT EXISTS ix_ops_situations_booking_id ON ops_situations(booking_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_situations_opened_at ON ops_situations(opened_at)",

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_agent_decisions (
        id VARCHAR(36) PRIMARY KEY,
        situation_id VARCHAR(36) NOT NULL REFERENCES ops_situations(id) ON DELETE CASCADE,
        model VARCHAR(60) NOT NULL DEFAULT 'rules-mvp-v1',
        prompt_hash VARCHAR(64),
        decision_json JSONB,
        rationale TEXT,
        confidence DOUBLE PRECISION,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        latency_ms INTEGER,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_ops_decision_status
            CHECK (status IN ('pending','executed','blocked_by_guardrail','failed'))
    )"""),
    "CREATE INDEX IF NOT EXISTS ix_ops_agent_decisions_situation_id ON ops_agent_decisions(situation_id)",

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_agent_actions (
        id VARCHAR(36) PRIMARY KEY,
        decision_id VARCHAR(36) NOT NULL REFERENCES ops_agent_decisions(id) ON DELETE CASCADE,
        tool VARCHAR(40) NOT NULL,
        args_json JSONB,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        external_ref VARCHAR(255),
        error_message TEXT,
        executed_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_ops_action_status
            CHECK (status IN ('pending','executed','blocked_by_guardrail','failed'))
    )"""),
    "CREATE INDEX IF NOT EXISTS ix_ops_agent_actions_decision_id ON ops_agent_actions(decision_id)",

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_escalation_tickets (
        id VARCHAR(36) PRIMARY KEY,
        situation_id VARCHAR(36) NOT NULL REFERENCES ops_situations(id) ON DELETE CASCADE,
        assignee VARCHAR(60),
        priority VARCHAR(4) NOT NULL DEFAULT 'p2',
        pagerduty_incident VARCHAR(120),
        summary_md TEXT,
        resolved_at TIMESTAMP,
        resolution_note TEXT,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_ops_escalation_priority
            CHECK (priority IN ('p0','p1','p2'))
    )"""),
    "CREATE INDEX IF NOT EXISTS ix_ops_escalation_tickets_situation_id ON ops_escalation_tickets(situation_id)",
]


__all__ = ["NEW_TABLES_SQLITE", "NEW_TABLES_PG", "NEW_TABLE_NAMES"]
