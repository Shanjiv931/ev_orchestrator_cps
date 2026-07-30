from app.database import engine
from app.migrate import run_lightweight_migrations


def test_lightweight_migrations_are_idempotent():
    run_lightweight_migrations(engine)
    run_lightweight_migrations(engine)  # must not raise on a second run
