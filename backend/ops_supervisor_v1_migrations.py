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
]

NEW_INDEXES_SQLITE = [
    "CREATE INDEX IF NOT EXISTS ix_langgraph_checkpoints_thread ON langgraph_checkpoints(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_langgraph_writes_thread ON langgraph_writes(thread_id)",
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
]

NEW_INDEXES_PG = [
    "CREATE INDEX IF NOT EXISTS ix_langgraph_checkpoints_thread ON langgraph_checkpoints(thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_langgraph_writes_thread ON langgraph_writes(thread_id)",
]


__all__ = [
    "NEW_TABLE_NAMES",
    "NEW_TABLES_SQLITE",
    "NEW_TABLES_PG",
    "NEW_INDEXES_SQLITE",
    "NEW_INDEXES_PG",
]
