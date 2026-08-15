import os
import uuid
from typing import List, Optional
from sqlalchemy.orm import joinedload

# Assuming you rename databse.py to database.py
from .database import SessionLocal, User, Subject, Notebook, Material, Video, ConceptNode, ConceptEdge

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
        return db.query(Subject).options(
            joinedload(Subject.notebooks),
            joinedload(Subject.materials),
            joinedload(Subject.videos)
        ).filter(Subject.user_id == user_id).all()

def get_subject_details(subject_id: str) -> Optional[Subject]:
    """Fetches a subject and ALL its related items (notebooks, materials, videos) in one go."""
    with SessionLocal() as db:
        # joinedload ensures we pull the related lists in a single efficient query
        return db.query(Subject).options(
            joinedload(Subject.notebooks),
            joinedload(Subject.materials),
            joinedload(Subject.videos),
            joinedload(Subject.concept_nodes),
            joinedload(Subject.concept_edges)
        ).filter(Subject.id == subject_id).first()

def create_notebook(name: str, subject_id: Optional[str] = None, override_id: str = None) -> Notebook:
    """Creates a notebook record in the database.
    
    If override_id is provided (e.g. from NotebookStorage), uses that ID
    and skips creating a JSON file (NotebookStorage already did it).
    """
    with SessionLocal() as db:
        nb_id = override_id or uuid.uuid4().hex
        notebook = Notebook(id=nb_id, name=name, subject_id=subject_id)
        db.add(notebook)
        db.commit()
        db.refresh(notebook)
        
        # Only create a JSON file if we're NOT using an override_id
        # (meaning NotebookStorage hasn't already created one)
        if not override_id:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            nb_dir = os.path.join(base_dir, "storage_data", "boards")
            os.makedirs(nb_dir, exist_ok=True)
            file_path = os.path.join(nb_dir, f"{nb_id}.json")
            if not os.path.exists(file_path):
                import json
                with open(file_path, "w") as f:
                    json.dump({"board_id": nb_id, "title": name, "items": []}, f)
            
        return notebook

def delete_subject(subject_id: str):
    """Deletes a subject and all its related cascades (notebooks, etc) from the DB."""
    with SessionLocal() as db:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject:
            db.delete(subject)
            db.commit()

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

def delete_notebook_record(notebook_id: str):
    """Deletes a notebook record from the DB. Does NOT delete the JSON board file."""
    with SessionLocal() as db:
        nb = db.query(Notebook).filter(Notebook.id == notebook_id).first()
        if nb:
            db.delete(nb)
            db.commit()

def delete_material(material_id: str) -> Optional[str]:
    """Deletes a material record from the DB. Returns the file_path so the caller can remove the physical file."""
    with SessionLocal() as db:
        mat = db.query(Material).filter(Material.id == material_id).first()
        if mat:
            path = mat.file_path
            db.delete(mat)
            db.commit()
            return path
    return None

def delete_video(video_id: str) -> Optional[str]:
    """Deletes a video record from the DB. Returns the video_url so the caller can remove the physical file."""
    with SessionLocal() as db:
        vid = db.query(Video).filter(Video.id == video_id).first()
        if vid:
            path = vid.video_url
            db.delete(vid)
            db.commit()
            return path
    return None

def update_subject_knowledge_graph(subject_id: str, nodes: List[dict], edges: List[dict], clear_existing: bool = False):
    """Merges new nodes and edges, or replaces them entirely if clear_existing is True."""
    with SessionLocal() as db:
        if clear_existing:
            db.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).delete()
            # Cascade will automatically delete the related edges
            
        # 1. Load existing nodes to check for duplicates
        existing_nodes = {
            n.name: n for n in db.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
        }
        
        # 2. Add new nodes if they don't already exist
        for node_data in nodes:
            name = node_data.get("term", node_data.get("name", "Unknown"))

            if name not in existing_nodes:
                node = ConceptNode(
                    id=uuid.uuid4().hex,
                    subject_id=subject_id,
                    name=name,
                    category=node_data.get("category", "concept"),
                    description=node_data.get("description", "")
                )
                db.add(node)
                existing_nodes[name] = node  # Add to our tracker
                
        # 3. Load existing edges to check for duplicates
        existing_edges = {
            (e.source_name, e.target_name) for e in db.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()
        }
            
        # 4. Add new edges if they don't exist, AND if both nodes exist
        for edge_data in edges:
            src = edge_data["source"]
            tgt = edge_data["target"]
            if (src, tgt) not in existing_edges and src in existing_nodes and tgt in existing_nodes:
                edge = ConceptEdge(
                    id=uuid.uuid4().hex,
                    subject_id=subject_id,
                    source_name=src,
                    target_name=tgt,
                    relationship_desc=edge_data.get("relationship", "related_to")
                )
                db.add(edge)
                existing_edges.add((src, tgt))
            
        db.commit()

