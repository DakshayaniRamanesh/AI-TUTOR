import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# 1. Setup SQLite Engine and Session
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Allow tests or environment to override the database URL
_ENV_DB_URL = os.getenv("KESTREL_DATABASE_URL")
if _ENV_DB_URL:
    _resolved_db_url = _ENV_DB_URL
else:
    DB_PATH = os.path.join(_BASE_DIR, "storage_data", "kestrel.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _resolved_db_url = f"sqlite:///{DB_PATH}"

engine = create_engine(_resolved_db_url, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_engine():
    return engine

def get_session_factory():
    return SessionLocal

# 2. Define Models
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subjects")
    notebooks = relationship("Notebook", back_populates="subject", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="subject", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="subject", cascade="all, delete-orphan")
    concept_nodes = relationship("ConceptNode", cascade="all, delete-orphan")
    concept_edges = relationship("ConceptEdge", cascade="all, delete-orphan")


class Notebook(Base):
    __tablename__ = "notebooks"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True) # Nullable for "Blank Notebook"
    name = Column(String, default="Untitled Notebook")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = relationship("Subject", back_populates="notebooks")


class Material(Base):
    __tablename__ = "materials"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    
    resource_type = Column(String, default="PDF")
    mime_type = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    ingestion_status = Column(String, default="REGISTERED")
    chunk_count = Column(Integer, default=0)
    ingestion_error = Column(String, nullable=True)
    last_indexed_at = Column(DateTime, nullable=True)
    metadata_json = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="materials")
    chunks = relationship("SubjectChunk", back_populates="material", cascade="all, delete-orphan")


class SubjectChunk(Base):
    __tablename__ = "subject_chunks"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    material_id = Column(String, ForeignKey("materials.id"), nullable=False)
    
    chunk_index = Column(Integer, nullable=False)
    document_title = Column(String)
    chapter = Column(String)
    section = Column(String)
    page_number = Column(Integer)
    content_type = Column(String)
    text = Column(String)
    token_count = Column(Integer)
    content_hash = Column(String)
    parent_path = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = relationship("Subject")
    material = relationship("Material", back_populates="chunks")


class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    title = Column(String, nullable=False)
    video_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="videos")

class ConceptNode(Base):
    __tablename__ = "concept_nodes"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, default="concept")
    description = Column(String)

class ConceptEdge(Base):
    __tablename__ = "concept_edges"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    source_name = Column(String, nullable=False)
    target_name = Column(String, nullable=False)
    relationship_desc = Column(String)

from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

# 3. Tables are now created/migrated via Alembic.
# Base.metadata.create_all(bind=engine) is REMOVED to prevent import-time side effects.
