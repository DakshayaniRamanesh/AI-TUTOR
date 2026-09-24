import argparse
import sys
import os
from sqlalchemy.orm import Session
from app.storage.database import SessionLocal, Subject, Material, SubjectChunk
from app.storage.database_ops import update_material_status
from backend.workspace.subject_ingestion_service import SubjectIngestionService

def run_diagnostic(subject_id: str):
    print(f"--- Kestrel Subject Brain Diagnostic ---")
    print(f"Subject ID: {subject_id}")
    
    with SessionLocal() as db:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            print(f"Error: Subject {subject_id} not found in SQLite.")
            return

        print(f"Subject Name: {subject.name}")
        materials = db.query(Material).filter(Material.subject_id == subject_id).all()
        print(f"\n[SQLite] Material count: {len(materials)}")
        
        status_counts = {}
        failed_mats = []
        partial_mats = []
        for m in materials:
            status_counts[m.ingestion_status] = status_counts.get(m.ingestion_status, 0) + 1
            if m.ingestion_status == "FAILED":
                failed_mats.append(m)
            elif m.ingestion_status == "PARTIAL":
                partial_mats.append(m)
                
        print(f"Status breakdown: {status_counts}")
        
        if failed_mats:
            print("\nFailed materials:")
            for m in failed_mats:
                print(f"  - {m.filename} (ID: {m.id}): {m.error_message}")
                
        if partial_mats:
            print("\nPartial materials:")
            for m in partial_mats:
                print(f"  - {m.filename} (ID: {m.id}): {m.error_message or 'Analysis deferred'}")

        chunks = db.query(SubjectChunk).filter(SubjectChunk.subject_id == subject_id).all()
        print(f"\n[SQLite] Chunk count: {len(chunks)}")
        
        # FTS Count
        # We can do a dummy search or just count via direct query.
        try:
            from sqlalchemy import text
            fts_count = db.execute(
                text("SELECT count(*) FROM subject_chunks_fts WHERE subject_id = :subject_id"),
                {"subject_id": subject_id}
            ).scalar()
            print(f"[SQLite FTS] FTS count: {fts_count}")
        except Exception as e:
            print(f"[SQLite FTS] FTS count failed: {e}")

    print("\n--- Qdrant Status ---")
    try:
        from backend.workspace.subject_ingestion_service import SubjectIngestionService
        from backend.workspace.subject_vector_store import COLLECTION
        service = SubjectIngestionService()
        client = service.vector_store.client
        collection = COLLECTION
        
        # Determine mode
        # The Qdrant client usually has _client.location or similar
        mode = "persistent local"
        if ":memory:" in str(client._client):
            mode = "memory"
        elif hasattr(client._client, 'rest_uri') and client._client.rest_uri:
            mode = f"remote ({client._client.rest_uri})"
            
        print(f"Qdrant mode: {mode}")
        
        # Check point count
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            count_result = client.count(
                collection_name=collection,
                count_filter=Filter(
                    must=[
                        FieldCondition(key="subject_id", match=MatchValue(value=subject_id))
                    ]
                )
            )
            print(f"Qdrant point count: {count_result.count}")
        except Exception as e:
            print(f"Qdrant point count failed (Collection might not exist yet): {e}")
            
    except Exception as e:
        print(f"Qdrant check failed. Qdrant might be unavailable: {e}")
        
    print("\n--- Embedding Status ---")
    try:
        from backend.workspace.subject_ingestion_service import SubjectIngestionService
        svc = SubjectIngestionService()
        if hasattr(svc.vector_store, 'embedder'):
            print(f"Real embedding availability: Yes, using {svc.vector_store.embedder.__class__.__name__}")
        else:
            print("Real embedding availability: Unknown")
    except Exception as e:
        print(f"Embedding check failed: {e}")
        
    print("\nDiagnostic complete. No data was inserted or generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read-only Subject Brain diagnostic tool.")
    parser.add_argument("--subject", required=True, help="The subject_id to inspect.")
    args = parser.parse_args()
    
    # Ensure correct working directory for SQLite relative paths
    # (assuming we run from repository root)
    run_diagnostic(args.subject)
