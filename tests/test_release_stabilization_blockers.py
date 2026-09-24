import os
import tempfile
import pytest
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command

# Ensure QT offscreen mode for headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

from shared.contracts.context import ContextRequest, ContextScope
from shared.contracts.tutoring import TutorMode
from app.ui.main_window import MainWindow
from app.services.memory.repositories import MemoryRepository
from app.storage.database import Base, User, Subject, Notebook, SessionLocal
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    from app.storage.database import engine, Base
    Base.metadata.create_all(bind=engine)
    yield app


@pytest.fixture
def temp_db():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    yield Session, db_path

    try:
        os.remove(db_path)
    except OSError:
        pass


# -----------------------------------------------------------------------------
# 1. Subject Ingestion Imports
# -----------------------------------------------------------------------------

def test_subject_ingestion_imports():
    from app.services.knowledge.graph_extraction_service import KnowledgeGraphExtractionService
    from backend.workspace.subject_ingestion_service import SubjectIngestionService
    from app.ui.workers.ingestion_worker import IngestionWorker

    assert KnowledgeGraphExtractionService is not None
    assert SubjectIngestionService is not None
    assert IngestionWorker is not None


# -----------------------------------------------------------------------------
# 2-9. Request Lifecycle, Coexistence, & Staleness
# -----------------------------------------------------------------------------

def test_request_registration_and_accept(qapp):
    win = MainWindow()
    req = ContextRequest(
        request_id="req-1",
        subject_id="s1",
        notebook_id="nb1",
        attempt_id="att1",
        canvas_revision=1,
        tutor_mode="CHECK_STEP"
    )
    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req)
    assert win._is_request_stale("check_step", req) is False


def test_unknown_request_id_rejected(qapp):
    win = MainWindow()
    req_registered = ContextRequest(
        request_id="req-known",
        subject_id="s1",
        notebook_id="nb1",
        attempt_id="att1"
    )
    req_unknown = ContextRequest(
        request_id="req-unknown",
        subject_id="s1",
        notebook_id="nb1",
        attempt_id="att1"
    )
    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req_registered)
    assert win._is_request_stale("check_step", req_unknown) is True


def test_previous_request_rejected_after_replacement(qapp):
    win = MainWindow()
    req1 = ContextRequest(request_id="req-1", subject_id="s1", notebook_id="nb1", attempt_id="att1")
    req2 = ContextRequest(request_id="req-2", subject_id="s1", notebook_id="nb1", attempt_id="att1")

    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req1)
    win._register_active_request("check_step", req2)

    assert win._is_request_stale("check_step", req1) is True
    assert win._is_request_stale("check_step", req2) is False


def test_ask_ai_and_check_step_coexist(qapp):
    win = MainWindow()
    req_check = ContextRequest(request_id="req-check", subject_id="s1", notebook_id="nb1", attempt_id="att1", tutor_mode="CHECK_STEP")
    req_ask = ContextRequest(request_id="req-ask", subject_id="s1", notebook_id="nb1", attempt_id="att1", tutor_mode="EXPLAIN")

    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req_check)
    win._register_active_request("ask", req_ask)

    assert win._is_request_stale("check_step", req_check) is False
    assert win._is_request_stale("ask", req_ask) is False


def test_switching_notebooks_rejects_old_result(qapp):
    win = MainWindow()
    req = ContextRequest(request_id="req-1", subject_id="s1", notebook_id="nb1", attempt_id="att1")
    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req)
    win._clear_active_requests("notebook_switch")
    win._current_notebook_id = "nb2"

    assert win._is_request_stale("check_step", req) is True


def test_switching_subjects_rejects_old_result(qapp):
    win = MainWindow()
    req = ContextRequest(request_id="req-1", subject_id="s1", notebook_id="nb1", attempt_id="att1")
    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"

    win._register_active_request("check_step", req)
    win._clear_active_requests("subject_switch")
    win.current_subject_id = "s2"

    assert win._is_request_stale("check_step", req) is True


def test_canvas_revision_mismatch_rejects_result(qapp):
    win = MainWindow()
    req = ContextRequest(request_id="req-1", subject_id="s1", notebook_id="nb1", attempt_id="att1", canvas_revision=1)
    win._current_notebook_id = "nb1"
    win.current_subject_id = "s1"
    win.current_attempt_id = "att1"

    win._register_active_request("check_step", req)
    class FakeScene:
        def get_revision(self):
            return 2
    win.scene = FakeScene()

    assert win._is_request_stale("check_step", req) is True


# -----------------------------------------------------------------------------
# 10-12. Session Lifecycle & Scoped Attempts
# -----------------------------------------------------------------------------

def test_startup_does_not_create_unscoped_session(qapp):
    win = MainWindow()
    assert win.current_learning_session_id is None
    assert win.current_attempt_id is None


def test_loading_notebook_creates_or_resumes_scoped_session(temp_db):
    Session, db_path = temp_db
    with Session() as db:
        user = User(id="u1", username="u1")
        subj = Subject(id="s1", user_id="u1", name="Math")
        nb1 = Notebook(id="nb1", subject_id="s1")
        db.add_all([user, subj, nb1])
        db.commit()

    repo = MemoryRepository(session_factory=Session)

    sess1 = repo.get_or_create_active_session(notebook_id="nb1", user_id="u1", subject_id="s1")
    att1 = repo.get_or_create_active_attempt(sess1)

    sess1_again = repo.get_or_create_active_session(notebook_id="nb1", user_id="u1", subject_id="s1")
    att1_again = repo.get_or_create_active_attempt(sess1)

    assert sess1 == sess1_again
    assert att1 == att1_again
    assert sess1 is not None


def test_switching_notebooks_produces_correct_attempt_isolation(temp_db):
    Session, db_path = temp_db
    with Session() as db:
        user = User(id="u1", username="u1")
        subj = Subject(id="s1", user_id="u1", name="Math")
        nb1 = Notebook(id="nb1", subject_id="s1")
        nb2 = Notebook(id="nb2", subject_id="s1")
        db.add_all([user, subj, nb1, nb2])
        db.commit()

    repo = MemoryRepository(session_factory=Session)

    sess1 = repo.get_or_create_active_session(notebook_id="nb1", user_id="u1", subject_id="s1")
    att1 = repo.get_or_create_active_attempt(sess1)

    sess2 = repo.get_or_create_active_session(notebook_id="nb2", user_id="u1", subject_id="s1")
    att2 = repo.get_or_create_active_attempt(sess2)

    assert sess1 != sess2
    assert att1 != att2

    repo.append_reasoning_step(attempt_id=att1, recognized_text="2x = 4")
    steps1 = repo.get_recent_steps(att1)
    steps2 = repo.get_recent_steps(att2)

    assert len(steps1) == 1
    assert len(steps2) == 0


# -----------------------------------------------------------------------------
# 13-15. Alembic Migrations
# -----------------------------------------------------------------------------

def test_fresh_database_upgrades_to_alembic_head():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    try:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "reasoning_steps" in tables
        assert "learning_sessions" in tables
        assert "problem_attempts" in tables
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_upgrade_downgrade_one_revision_upgrade_succeeds():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    try:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        cols = [c["name"] for c in inspector.get_columns("reasoning_steps")]

        assert "previous_step_id" in cols
        assert "replaces_step_id" in cols
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_reasoning_steps_table_contains_one_copy_of_each_ancestry_column():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    try:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        cols = [c["name"] for c in inspector.get_columns("reasoning_steps")]

        assert cols.count("previous_step_id") == 1
        assert cols.count("replaces_step_id") == 1
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass
