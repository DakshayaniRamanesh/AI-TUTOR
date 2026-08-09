import uuid
from typing import List, Optional
from sqlalchemy.orm import joinedload

# Assuming you rename databse.py to database.py
from .database import SessionLocal, User, Subject, Notebook, Material, Video

def get_or_create_user(username: str) -> User:
    """Gets an existing user by username, or creates them if they don't exist."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(id=uuid.uuid4().hex, username=username)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

def create_subject(user_id: str, name: str) -> Subject:
    """Creates a new subject under a specific user."""
    with SessionLocal() as db:
        subject = Subject(id=uuid.uuid4().hex, user_id=user_id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return subject

def get_user_subjects(user_id: str) -> List[Subject]:
    """Lists all subjects belonging to a user."""
    with SessionLocal() as db:
        return db.query(Subject).filter(Subject.user_id == user_id).all()

def get_subject_details(subject_id: str) -> Optional[Subject]:
    """Fetches a subject and ALL its related items (notebooks, materials, videos) in one go."""
    with SessionLocal() as db:
        # joinedload ensures we pull the related lists in a single efficient query
        return db.query(Subject).options(
            joinedload(Subject.notebooks),
            joinedload(Subject.materials),
            joinedload(Subject.videos)
        ).filter(Subject.id == subject_id).first()

def create_notebook(name: str, subject_id: Optional[str] = None) -> Notebook:
    """Creates a notebook. subject_id is None for the 'Blank Notebook' path."""
    with SessionLocal() as db:
        notebook = Notebook(id=uuid.uuid4().hex, name=name, subject_id=subject_id)
        db.add(notebook)
        db.commit()
        db.refresh(notebook)
        return notebook

def add_material(subject_id: str, filename: str, file_path: str) -> Material:
    """Logs an uploaded PDF/document under a subject."""
    with SessionLocal() as db:
        material = Material(id=uuid.uuid4().hex, subject_id=subject_id, filename=filename, file_path=file_path)
        db.add(material)
        db.commit()
        db.refresh(material)
        return material

def add_video(subject_id: str, title: str, video_url: str) -> Video:
    """Logs a generated AI video under a subject."""
    with SessionLocal() as db:
        video = Video(id=uuid.uuid4().hex, subject_id=subject_id, title=title, video_url=video_url)
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
