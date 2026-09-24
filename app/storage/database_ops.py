import os
import uuid
import datetime
from typing import List, Optional
from sqlalchemy.orm import joinedload

# Assuming you rename databse.py to database.py
from .database import SessionLocal, User, Subject, Notebook, Material, Video, ConceptNode, ConceptEdge, SubjectChunk
from app.services.knowledge.graph_reconciliation_service import GraphReconciliationService

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

def add_material(subject_id: str, filename: str, file_path: str, resource_type: str = "PDF") -> Material:
    """Logs an uploaded PDF/document under a subject."""
    with SessionLocal() as db:
        material = Material(id=uuid.uuid4().hex, subject_id=subject_id, filename=filename, file_path=file_path, resource_type=resource_type)
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
    """Deletes a material record from the DB and its vector points. Returns the file_path."""
    from backend.workspace.subject_vector_store import SubjectVectorStore
    
    with SessionLocal() as db:
        mat = db.query(Material).filter(Material.id == material_id).first()
        if not mat:
            return None
            
        subject_id = mat.subject_id
        path = mat.file_path
        
        try:
            SubjectVectorStore().delete_by_material(subject_id, material_id)
        except Exception as e:
            print(f"[DB] Failed to delete vector points for material {material_id}: {e}")
            
        try:
            GraphReconciliationService().reconcile_material_graph(subject_id, material_id, [], [])
        except Exception as e:
            print(f"[DB] Failed to cleanup graph for material {material_id}: {e}")
            
        db.delete(mat)
        db.commit()
        return path

def update_material_status(
    material_id: str, 
    status: str, 
    error: Optional[str] = None, 
    chunk_count: Optional[int] = None,
    content_hash: Optional[str] = None,
    file_size: Optional[int] = None,
    last_indexed_at: Optional[datetime.datetime] = None
) -> Optional[Material]:
    with SessionLocal() as db:
        mat = db.query(Material).filter(Material.id == material_id).first()
        if mat:
            mat.ingestion_status = status
            if error is not None:
                mat.ingestion_error = error
            if chunk_count is not None:
                mat.chunk_count = chunk_count
            if content_hash is not None:
                mat.content_hash = content_hash
            if file_size is not None:
                mat.file_size = file_size
            if last_indexed_at is not None:
                mat.last_indexed_at = last_indexed_at
            db.commit()
            db.refresh(mat)
            return mat
    return None

def replace_subject_chunks(material_id: str, subject_id: str, chunks: List[dict]):
    """Transactionally deletes old chunks for a material and inserts new ones."""
    with SessionLocal() as db:
        # Delete old chunks
        db.query(SubjectChunk).filter(SubjectChunk.material_id == material_id).delete()
        
        # Insert new chunks
        for chunk in chunks:
            c = SubjectChunk(
                id=chunk.get("id"),
                subject_id=subject_id,
                material_id=material_id,
                chunk_index=chunk.get("chunk_index"),
                document_title=chunk.get("document_title"),
                chapter=chunk.get("chapter"),
                section=chunk.get("section"),
                page_number=chunk.get("page_number"),
                content_type=chunk.get("content_type"),
                text=chunk.get("text"),
                token_count=chunk.get("token_count"),
                content_hash=chunk.get("content_hash"),
                parent_path=chunk.get("parent_path")
            )
            db.add(c)
        db.commit()

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



def bootstrap_db():
    """Run Alembic migrations programmatically to ensure schema is up-to-date."""
    from alembic.config import Config
    from alembic import command
    import os
    
    # Locate alembic.ini from the project root
    _BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    alembic_cfg = Config(os.path.join(_BASE_DIR, 'alembic.ini'))
    
    try:
        command.upgrade(alembic_cfg, 'head')
        print("[DB] Alembic upgrade head successful.", flush=True)
    except Exception as e:
        print(f"[DB] Alembic migration failed: {e}", flush=True)
        raise e
