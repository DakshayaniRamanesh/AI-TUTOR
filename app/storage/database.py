import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# 1. Setup SQLite Engine and Session
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(_BASE_DIR, "storage_data", "kestrel.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

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
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="materials")


class Video(Base):
    __tablename__ = "videos"
    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    title = Column(String, nullable=False)
    video_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="videos")

# 3. Create tables if they don't exist
Base.metadata.create_all(bind=engine)
