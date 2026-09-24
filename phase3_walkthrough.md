# Phase 3 Walkthrough: Evidence-Backed Interactive Knowledge Graph

Phase 3 is complete. The Kestrel Knowledge Graph is now fully integrated into the Subject Workspace as an evidence-backed learning map.

## 1. Safe SQLite Migration via Batch Operations
To implement the new `ConceptNode`, `ConceptEdge`, and `GraphEvidence` models, we encountered SQLite's strict limitations on `ALTER TABLE`. We resolved this by enabling `render_as_batch=True` in `alembic/env.py`.
The migration `6f9fbf64e222_update_graph_models_for_phase_3_batch_.py` now cleanly performs a table copy-and-swap (batch operation) to adjust constraints and columns without touching the legacy FTS index tables that were triggering errors. The database was successfully upgraded.

## 2. Shared Graph Contracts
We introduced clean Data Transfer Objects (DTOs) in `shared/contracts/graph_contracts.py`:
- `GraphNodeDTO`
- `GraphEdgeDTO`
- `GraphEvidenceDTO`
- `GraphSnapshot`

These ensure that the UI renders pure data without maintaining active SQLAlchemy sessions, avoiding threading and locking issues.

## 3. Offline Structural Extraction Service
We created `app/services/knowledge/graph_extraction_service.py`.
This service runs entirely offline and deterministically parses the hierarchical structure created during Phase 1 ingestion:
- **Subjects** form the central hub.
- **Resources** (PDFs/Images) link to the Subject (`PART_OF`).
- **Modules** (Chapters) link to the Resource.
- **Concepts** (Sections) link to the Chapter or Resource.
- **Notebooks** link to the Subject.

Every node and edge retains `GraphEvidenceDTO` linking back to the precise page, chunk, and snippet that sourced it. The service executes synchronously and commits the unified snapshot back to the database tables (`GraphEvidence`, `ConceptNode`, `ConceptEdge`).

## 4. Ingestion Worker Integration
The graph extraction is invoked seamlessly at the end of the `SubjectIngestionService.ingest_material()` pipeline. Once vector embeddings and chunks are saved, the graph extraction service rebuilds the knowledge graph for the subject.

## 5. Reusable GraphCanvas Widget
The monolithic `ObsidianGraphPanel` was refactored. We extracted the core Force-Directed Layout and drawing logic into a pure UI component: `app/ui/components/graph_canvas.py`.
- `GraphCanvas` knows nothing about SQLAlchemy.
- It simply takes a `GraphSnapshot` via `set_snapshot()` and renders it.
- Progressive disclosure (drill-down) is supported. 

## 6. SubjectDetailView Integration
The `SubjectDetailView` now utilizes the new `GraphCanvas` for its "Knowledge Map" tab. When `load_subject` is called, it iterates through the ORM models (`subject.concept_nodes` and `subject.concept_edges`), maps them to DTOs, wraps them in a `GraphSnapshot`, and instantly renders the evidence-backed graph for the active subject. 

The global view (`ObsidianGraphPanel`) is maintained independently for top-level exploration, respecting the explicit directive to keep two levels of the graph.

Phase 3 is complete and ready for validation.
