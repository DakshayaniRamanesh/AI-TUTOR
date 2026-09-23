import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Override the DB URL BEFORE importing the app models!
# We use a temporary file instead of :memory: so that multiple threads/processes
# (if any) can share the database file during a single test run without it disappearing.
_temp_db_fd, _temp_db_path = tempfile.mkstemp(suffix=".db", prefix="kestrel_test_")
os.environ["KESTREL_DATABASE_URL"] = f"sqlite:///{_temp_db_path}"

from app.storage.database import Base, get_engine, get_session_factory

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create the test database schema once for the entire test session."""
    engine = get_engine()
    
    # Verify we are definitely not pointing at the production DB!
    assert "kestrel.db" not in str(engine.url), "FATAL: Test engine points to production DB!"
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Teardown
    engine.dispose()
    os.close(_temp_db_fd)
    try:
        os.unlink(_temp_db_path)
    except OSError:
        pass

@pytest.fixture
def db_session_factory():
    """Provides a session factory for tests to inject into repositories."""
    return get_session_factory()
