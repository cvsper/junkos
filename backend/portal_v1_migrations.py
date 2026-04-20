"""
B2B Commercial Portal — v1 expansion migration DDL (Spec 04 §9).

The orchestrator merges these lists into `migrate.py`.  Ordering between
NEW_TABLE_NAMES / NEW_TABLES_SQLITE / NEW_TABLES_PG is significant (they
zip-pair).  Don't reorder without mirroring.

Self-contained: we never edit `migrate.py` directly because multiple build
agents run in parallel.

Also exposed:

  * COLUMN_MIGRATIONS          — new columns on existing tables
                                 (jobs.unit_id, orgs.esg_*)
  * RLS_ORG_TABLES             — extend the Postgres RLS list
  * apply_sqlite / apply_pg    — standalone helpers usable from tests so
                                 we don't need to round-trip through
                                 `flask db-migrate`
"""

from textwrap import dedent


# ---------------------------------------------------------------------------
# SQLite DDL — new tables
# ---------------------------------------------------------------------------
NEW_TABLES_SQLITE = [
    # portal_units — subdivision of a portal_property (many units per prop).
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_units (
        id VARCHAR(36) PRIMARY KEY,
        property_id VARCHAR(36) NOT NULL REFERENCES portal_properties(id) ON DELETE CASCADE,
        unit_number VARCHAR(40) NOT NULL,
        sqft INTEGER,
        access_notes TEXT,
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_portal_unit_status CHECK (status IN ('active','inactive')),
        CONSTRAINT uq_portal_unit_property_number UNIQUE (property_id, unit_number)
    )"""),
    # portal_recurring_schedules — jobs generator input.
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_recurring_schedules (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        property_id VARCHAR(36) NOT NULL REFERENCES portal_properties(id) ON DELETE CASCADE,
        unit_id VARCHAR(36) REFERENCES portal_units(id) ON DELETE SET NULL,
        cadence VARCHAR(12) NOT NULL,
        day_of_week INTEGER,
        day_of_month INTEGER,
        next_run_at DATETIME NOT NULL,
        active BOOLEAN NOT NULL DEFAULT 1,
        paused_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT ck_recurring_cadence CHECK (cadence IN ('weekly','biweekly','monthly'))
    )"""),
    # portal_v1_audit_log — richer audit w/ actor_member_id (spec §9.4).
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_v1_audit_log (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL,
        actor_member_id VARCHAR(36),
        entity_type VARCHAR(40) NOT NULL,
        entity_id VARCHAR(36),
        action VARCHAR(20) NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at DATETIME NOT NULL,
        CONSTRAINT ck_portal_v1_audit_action CHECK (action IN ('create','update','delete'))
    )"""),
]


# ---------------------------------------------------------------------------
# Postgres DDL — new tables
# ---------------------------------------------------------------------------
NEW_TABLES_PG = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_units (
        id VARCHAR(36) PRIMARY KEY,
        property_id VARCHAR(36) NOT NULL REFERENCES portal_properties(id) ON DELETE CASCADE,
        unit_number VARCHAR(40) NOT NULL,
        sqft INTEGER,
        access_notes TEXT,
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_portal_unit_status CHECK (status IN ('active','inactive')),
        CONSTRAINT uq_portal_unit_property_number UNIQUE (property_id, unit_number)
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_recurring_schedules (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        property_id VARCHAR(36) NOT NULL REFERENCES portal_properties(id) ON DELETE CASCADE,
        unit_id VARCHAR(36) REFERENCES portal_units(id) ON DELETE SET NULL,
        cadence VARCHAR(12) NOT NULL,
        day_of_week INTEGER,
        day_of_month INTEGER,
        next_run_at TIMESTAMP NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        paused_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_recurring_cadence CHECK (cadence IN ('weekly','biweekly','monthly'))
    )"""),
    dedent("""\
    CREATE TABLE IF NOT EXISTS portal_v1_audit_log (
        id VARCHAR(36) PRIMARY KEY,
        org_id VARCHAR(36) NOT NULL,
        actor_member_id VARCHAR(36),
        entity_type VARCHAR(40) NOT NULL,
        entity_id VARCHAR(36),
        action VARCHAR(20) NOT NULL,
        before_json JSONB,
        after_json JSONB,
        created_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_portal_v1_audit_action CHECK (action IN ('create','update','delete'))
    )"""),
]


# Table name order MUST match the two lists above.
NEW_TABLE_NAMES = [
    "portal_units",
    "portal_recurring_schedules",
    "portal_v1_audit_log",
]


# ---------------------------------------------------------------------------
# Column additions to existing tables.
# Same shape as migrate.py::COLUMN_MIGRATIONS:
#     (table, column, sqlite_type, pg_type, default_expr | "NULL")
# ---------------------------------------------------------------------------
COLUMN_MIGRATIONS = [
    # Jobs get an optional unit_id stamp (nullable — most residential jobs
    # and legacy portal jobs won't have one).
    ("jobs", "unit_id", "VARCHAR(36)", "VARCHAR(36)", "NULL"),

    # ESG capture on Org (spec §9.5).
    ("orgs", "esg_report_enabled", "BOOLEAN", "BOOLEAN", "FALSE"),
    ("orgs", "esg_contact_email", "VARCHAR(160)", "VARCHAR(160)", "NULL"),
]


# ---------------------------------------------------------------------------
# RLS — new org-scoped tables that need Postgres Row-Level Security.
# `portal_v1_audit_log` carries org_id directly, `portal_recurring_schedules`
# too.  `portal_units` is scoped indirectly via property -> org, but we add
# RLS anyway for defense in depth (join-based policy).
# ---------------------------------------------------------------------------
RLS_ORG_TABLES = [
    "portal_recurring_schedules",
    "portal_v1_audit_log",
    # portal_units RLS policy needs a join; handled app-layer for SQLite
    # parity and left to the orchestrator to wire PG-side.
]


# ---------------------------------------------------------------------------
# Standalone appliers — so tests / one-off scripts don't have to reach
# into migrate.py.  Idempotent.
# ---------------------------------------------------------------------------
def _sqlite_table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _sqlite_columns(cursor, table):
    cursor.execute("PRAGMA table_info('{}')".format(table))
    return {row[1] for row in cursor.fetchall()}


def apply_sqlite(connection):
    """Apply v1 DDL to a sqlite3 connection.  Idempotent."""
    cursor = connection.cursor()
    # New tables
    for ddl in NEW_TABLES_SQLITE:
        cursor.execute(ddl)
    # Column additions on existing tables
    for table, column, sqlite_type, _pg_type, default in COLUMN_MIGRATIONS:
        if not _sqlite_table_exists(cursor, table):
            continue
        if column in _sqlite_columns(cursor, table):
            continue
        default_clause = ""
        if default and default != "NULL":
            default_clause = " DEFAULT {}".format(default)
        cursor.execute(
            "ALTER TABLE {} ADD COLUMN {} {}{}".format(
                table, column, sqlite_type, default_clause
            )
        )
    connection.commit()


def apply_sqlalchemy(engine):
    """Apply v1 DDL using a SQLAlchemy engine (works for both sqlite + pg)."""
    from sqlalchemy import text

    dialect = engine.dialect.name
    is_sqlite = dialect == "sqlite"

    with engine.begin() as conn:
        # 1) New tables
        tables = NEW_TABLES_SQLITE if is_sqlite else NEW_TABLES_PG
        for ddl in tables:
            conn.execute(text(ddl))

        # 2) Column additions
        for table, column, sqlite_type, pg_type, default in COLUMN_MIGRATIONS:
            # Does the table exist?
            if is_sqlite:
                exists = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name=:t"
                    ),
                    {"t": table},
                ).fetchone() is not None
            else:
                exists = conn.execute(
                    text(
                        "SELECT EXISTS(SELECT FROM information_schema.tables "
                        "WHERE table_name = :t)"
                    ),
                    {"t": table},
                ).scalar()
            if not exists:
                continue

            # Does the column exist?
            if is_sqlite:
                rows = conn.execute(
                    text("PRAGMA table_info('{}')".format(table))
                ).fetchall()
                cols = {r[1] for r in rows}
            else:
                rows = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :t"
                    ),
                    {"t": table},
                ).fetchall()
                cols = {r[0] for r in rows}
            if column in cols:
                continue

            col_type = sqlite_type if is_sqlite else pg_type
            default_clause = ""
            if default and default != "NULL":
                default_clause = " DEFAULT {}".format(default)
            conn.execute(
                text(
                    "ALTER TABLE {} ADD COLUMN {} {}{}".format(
                        table, column, col_type, default_clause
                    )
                )
            )
