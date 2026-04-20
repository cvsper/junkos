"""
B2B Commercial Portal — SSO identity mapping table (spec 04 §9.6 v1
follow-up).

The v1 skeleton at `routes/portal_sso.py` linked SSO logins to orgs by
email-domain match against `orgs.sso_domain`. That works for the happy
path — "bob@acme.com" → org with sso_domain='acme.com' — but has three
gaps:

  1. Two separate Google accounts with the same email (shared mailbox
     rebinding) would both land the same org.  The provider's `sub`
     claim is the stable, cryptographic identifier — it's what we
     should key off.
  2. If someone changes their work email (Entra re-issues the email
     claim when a user renames), the domain still matches but the
     identity is a different one.
  3. There's no audit trail of which `sub` first linked to which
     user_id — security review can't retroactively answer "is this
     token holder the same human who logged in yesterday?".

Design:
  * `sso_identities` is a thin mapping table: (provider, subject) is
    UNIQUE, pointing at a user_id.
  * The SSO callback first tries identity lookup by (provider, sub).
  * On miss, it falls back to the existing email-domain path.
  * On success of *either* path, we upsert the identity so the next
    login short-circuits to step 1.

The table is NOT org-scoped — users can belong to one identity that
grants them membership in multiple orgs via OrgMember rows.  No RLS.
"""

from textwrap import dedent


NEW_TABLES_SQLITE = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS sso_identities (
        id VARCHAR(36) PRIMARY KEY,
        provider VARCHAR(16) NOT NULL,
        subject VARCHAR(200) NOT NULL,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        email VARCHAR(160),
        created_at DATETIME NOT NULL,
        last_seen_at DATETIME NOT NULL,
        CONSTRAINT ck_sso_provider CHECK (provider IN ('google','entra')),
        CONSTRAINT uq_sso_provider_subject UNIQUE (provider, subject)
    )"""),
]


NEW_TABLES_PG = [
    dedent("""\
    CREATE TABLE IF NOT EXISTS sso_identities (
        id VARCHAR(36) PRIMARY KEY,
        provider VARCHAR(16) NOT NULL,
        subject VARCHAR(200) NOT NULL,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        email VARCHAR(160),
        created_at TIMESTAMP NOT NULL,
        last_seen_at TIMESTAMP NOT NULL,
        CONSTRAINT ck_sso_provider CHECK (provider IN ('google','entra')),
        CONSTRAINT uq_sso_provider_subject UNIQUE (provider, subject)
    )"""),
]


NEW_TABLE_NAMES = ["sso_identities"]


# No RLS — identities are cross-org by design.
RLS_ORG_TABLES = []


def apply_sqlalchemy(engine):
    """Apply the sso_identities DDL using a SQLAlchemy engine. Idempotent.

    Tests and one-off scripts use this so they don't have to round-trip
    through `flask db-migrate`.  Safe to call when the table already
    exists — every DDL is `IF NOT EXISTS`.
    """
    from sqlalchemy import text

    dialect = engine.dialect.name
    is_sqlite = dialect == "sqlite"
    tables = NEW_TABLES_SQLITE if is_sqlite else NEW_TABLES_PG
    with engine.begin() as conn:
        for ddl in tables:
            conn.execute(text(ddl))
