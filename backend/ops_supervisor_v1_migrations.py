"""
Ops Supervisor v1 — additive migrations (spec 11 §9).

New table in v1:

    langgraph_checkpoints    — LangGraph SqliteSaver writes workflow state
                                here so a worker crash can resume. Columns
                                mirror what ``langgraph.checkpoint.sqlite``
                                creates on first use; we own the schema so
                                the standard ``migrate.py`` flow can apply
                                it alongside the ops_supervisor tables.

Shape mirrors ``migrate.py``'s ``NEW_TABLES_SQLITE`` / ``NEW_TABLES_PG`` +
``NEW_TABLE_NAMES``. Indexes live in their own arrays
(``NEW_INDEXES_SQLITE`` / ``NEW_INDEXES_PG``) so callers don't interleave
``CREATE INDEX`` with ``CREATE TABLE`` — previous phases caught a regression
where mixed arrays left indexes behind when a table already existed.
"""

from textwrap import dedent


NEW_TABLE_NAMES = [
    "langgraph_checkpoints",
    "langgraph_writes",
    "ops_workflow_dead_letters",
]


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------
NEW_TABLES_SQLITE = [
    # LangGraph's SqliteSaver expects this exact shape when we point it at a
    # shared DB (keys: thread_id, checkpoint_ns, checkpoint_id, parent_id,
    # type, checkpoint, metadata). We do NOT include indexes here — see
    # NEW_INDEXES_SQLITE below.
    dedent("""\
    CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        parent_checkpoint_id TEXT,
        type TEXT,
        checkpoint BLOB,
        metadata BLOB,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
    )"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS langgraph_writes (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        idx INTEGER NOT NULL,
        channel TEXT NOT NULL,
        type TEXT,
        value BLOB,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
    )"""),

    # Dead-letter queue for workflow runs that either exceeded the wall-clock
    # deadline or raised an exception the top-level driver couldn't recover
    # from. Operators replay these manually via `flask ops-replay-dlq <id>`.
    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_workflow_dead_letters (
        id VARCHAR(36) PRIMARY KEY,
        event_id VARCHAR(36) NOT NULL,
        thread_id VARCHAR(80),
        reason VARCHAR(32) NOT NULL,
        error_message TEXT,
        state_snapshot TEXT,
        created_at DATETIME NOT NULL,
        replayed_at DATETIME,
        CONSTRAINT ck_ops_dlq_reason
            CHECK (reason IN ('deadline_exceeded','exception','no_event'))
    )"""),
]

NEW_INDEXES_SQLITE = [
    "CREATE INDEX IF NOT EXISTS ix_langgraph_checkpoints_thread ON langgraph_checkpoints(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_langgraph_writes_thread ON langgraph_writes(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_dlq_event ON ops_workflow_dead_letters(event_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_dlq_replayed ON ops_workflow_dead_letters(replayed_at)",
]


# ---------------------------------------------------------------------------
# Postgres (BLOB -> BYTEA, TEXT unchanged)
# ---------------------------------------------------------------------------
NEW_TABLES_PG = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        parent_checkpoint_id TEXT,
        type TEXT,
        checkpoint BYTEA,
        metadata BYTEA,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
    )"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS langgraph_writes (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        idx INTEGER NOT NULL,
        channel TEXT NOT NULL,
        type TEXT,
        value BYTEA,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
    )"""),

    dedent("""\
    CREATE TABLE IF NOT EXISTS ops_workflow_dead_letters (
        id VARCHAR(36) PRIMARY KEY,
        event_id VARCHAR(36) NOT NULL,
        thread_id VARCHAR(80),
        reason VARCHAR(32) NOT NULL,
        error_message TEXT,
        state_snapshot JSONB,
        created_at TIMESTAMP NOT NULL,
        replayed_at TIMESTAMP,
        CONSTRAINT ck_ops_dlq_reason
            CHECK (reason IN ('deadline_exceeded','exception','no_event'))
    )"""),
]

NEW_INDEXES_PG = [
    "CREATE INDEX IF NOT EXISTS ix_langgraph_checkpoints_thread ON langgraph_checkpoints(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_langgraph_writes_thread ON langgraph_writes(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_dlq_event ON ops_workflow_dead_letters(event_id)",
    "CREATE INDEX IF NOT EXISTS ix_ops_dlq_replayed ON ops_workflow_dead_letters(replayed_at)",
]


__all__ = [
    "NEW_TABLE_NAMES",
    "NEW_TABLES_SQLITE",
    "NEW_TABLES_PG",
    "NEW_INDEXES_SQLITE",
    "NEW_INDEXES_PG",
]
