"""Row locks must not drag Job's eager joins under FOR UPDATE: Postgres refuses
'FOR UPDATE cannot be applied to the nullable side of an outer join', and
SQLite never notices — which is how 2.2.97 shipped a 500 on checkout photos."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import lazyload

from models import Job


def _pg(q):
    return str(q.statement.compile(dialect=postgresql.dialect())).replace("\n", " ")


def test_job_lock_query_has_no_outer_join(app):
    with app.app_context():
        naive = _pg(Job.query.filter(Job.id == "x").with_for_update().limit(1))
        assert "OUTER JOIN" in naive and naive.rstrip().endswith("FOR UPDATE")   # the trap
        fixed = _pg(Job.query.options(lazyload("*")).filter(Job.id == "x").with_for_update().limit(1))
        assert "OUTER JOIN" not in fixed and fixed.rstrip().endswith("FOR UPDATE")


def test_every_job_lock_site_disables_eager_loads():
    import inspect
    import routes.upload, routes.payments, assignment
    for mod, fn in ((routes.upload, "upload_checkout_photos"), (routes.payments, "_lock_job"), (assignment, "_lock_job")):
        src = inspect.getsource(getattr(mod, fn))
        assert "with_for_update" in src and 'lazyload("*")' in src, fn


def test_recent_errors_route_is_admin_only(client):
    assert client.get("/api/admin/recent-errors").status_code == 401
