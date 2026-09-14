"""A new model column reaches Postgres only through migrate.COLUMN_MIGRATIONS.

There is no Alembic here: `create_all` creates missing TABLES but never adds a
column to a table that already exists. On 14 Sep two columns were added to the
Payment model without the matching migration lines. Job eager-joins Payment, so
every query that loaded a job died on Postgres with UndefinedColumn and the
dispatch desk went down — while the tests stayed green, because SQLite builds
the table fresh from the model on every run.

These tests can't prove the rule for columns that predate the migration list,
so they pin the two that caused the outage and keep the list itself honest.
"""
from migrate import COLUMN_MIGRATIONS
import models


def _migrated():
    return {(t, c) for t, c, *_ in COLUMN_MIGRATIONS}


def _model_tables():
    out = {}
    for obj in vars(models).values():
        if getattr(obj, "__tablename__", None) and getattr(obj, "__table__", None) is not None:
            out[obj.__tablename__] = obj.__table__
    return out


def test_the_columns_that_took_the_desk_down_are_registered():
    migrated = _migrated()
    assert ("payments", "stripe_payment_method_id") in migrated
    assert ("payments", "stripe_customer_id") in migrated


def test_every_payment_column_added_since_the_list_began_is_in_it():
    """Payment is the table Job eager-joins, so a gap here breaks everything."""
    table = _model_tables()["payments"]
    migrated = _migrated()
    # columns that shipped with the original table, before migrations existed
    original = {"id", "job_id", "stripe_payment_intent_id", "amount", "service_fee",
                "created_at", "commission", "driver_payout_amount", "payment_status"}
    missing = [c.name for c in table.columns
               if c.name not in original and ("payments", c.name) not in migrated]
    assert not missing, (
        "payments: {} is on the model but not in migrate.COLUMN_MIGRATIONS — "
        "create_all will not add it to the existing Postgres table.".format(missing))
