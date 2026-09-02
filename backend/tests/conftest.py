import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.domain.persona_loader import load_persona

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((BACKEND_ROOT / "db" / "migrations").glob("*.sql"))
CONTAINER_NAME = "yahya-platform-db-pytest"
TEST_PORT = 15433


@pytest.fixture(scope="session")
def persona() -> dict:
    return load_persona()


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Spins up a disposable Postgres+pgvector container for the test session and
    applies the schema migration. Mirrors what was done manually to validate
    0001_init.sql (see architecture-assessment.md) — same container image, same
    migration file, now automated as a fixture per the brief's testing strategy
    ("Postgres (testcontainers or a disposable schema)")."""
    if shutil.which("docker") is None:
        pytest.skip("docker not available — integration tests require a Postgres container")

    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    run = subprocess.run(
        ["docker", "run", "-d", "--name", CONTAINER_NAME, "-e", "POSTGRES_PASSWORD=test",
         "-p", f"{TEST_PORT}:5432", "pgvector/pgvector:pg16"],
        capture_output=True, text=True)
    if run.returncode != 0:
        pytest.skip(f"could not start postgres test container: {run.stderr}")

    for _ in range(30):
        ready = subprocess.run(["docker", "exec", CONTAINER_NAME, "pg_isready", "-U", "postgres"],
                               capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        pytest.skip("postgres test container did not become ready in time")

    for migration in MIGRATIONS:
        subprocess.run(["docker", "cp", str(migration), f"{CONTAINER_NAME}:/tmp/{migration.name}"],
                       check=True)
        apply = subprocess.run(
            ["docker", "exec", "-e", "PGPASSWORD=test", CONTAINER_NAME,
             "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-f", f"/tmp/{migration.name}"],
            capture_output=True, text=True)
        if apply.returncode != 0:
            subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
            pytest.fail(f"migration {migration.name} failed to apply:\n{apply.stdout}\n{apply.stderr}")

    yield f"postgresql+psycopg://postgres:test@localhost:{TEST_PORT}/postgres"

    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)


@pytest.fixture(scope="session")
def engine(postgres_url):
    from app.db.base import make_engine
    return make_engine(postgres_url)


@pytest.fixture()
def db_session(engine):
    """One real transaction per test, rolled back afterwards — isolation without
    resetting the whole database between tests."""
    from sqlalchemy.orm import Session

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def bg_session_factory(engine):
    """For testing code that calls `session.commit()` itself (background tasks,
    scripts) without permanently polluting the shared session-scoped test
    database. Standard SQLAlchemy testing recipe: the connection's OUTER
    transaction is never committed (only rolled back at teardown); an inner
    SAVEPOINT is what `session.commit()` actually releases, and a listener
    re-opens a fresh SAVEPOINT after each release so the code under test can
    call commit() any number of times.

    Yields a zero-arg factory (matching `session_factory: Callable[[], Session]`
    call sites) that always returns the SAME session — fine for code that
    only calls the factory once, which is the only pattern this project uses
    background sessions for.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    connection = engine.connect()
    outer_transaction = connection.begin()
    connection.begin_nested()
    session = Session(bind=connection)

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield lambda: session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
