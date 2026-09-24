import os
import json
import requests
from typing import List, Dict, Optional
from pydantic import BaseModel
from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, NodeType, RelationType

class SemanticEdgeResponse(BaseModel):
    source_name: str
    target_name: str
    relation_type: RelationType
    chunk_id: str

class SemanticExtractionResponse(BaseModel):
    edges: List[SemanticEdgeResponse]

class SemanticGraphExtractor:
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY")

    def extract_semantic_edges(self, subject_id: str, material_id: str, chunks: List[Dict]) -> List[GraphEdgeDTO]:
        if not self.api_key:
            print("[SemanticGraphExtractor] No GROQ_API_KEY, falling back to structural only.")
            return []
            
        prompt = "Extract semantic relationships from the following text chunks. Return valid JSON matching the schema.\\n"
        prompt += "Valid relation types: PREREQUISITE_OF, EXPLAINS, EXAMPLE_OF, APPLIES_TO, RELATED_TO, CONTAINS, MENTIONS, PRACTICED_IN, DERIVED_FROM.\\n"
        for c in chunks[:10]: # Limit for token size
            prompt += f"Chunk {c['id']}: {c['text']}\\n"
            
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You extract knowledge graph edges. Return JSON like {'edges': [{'source_name': '...', 'target_name': '...', 'relation_type': 'EXPLAINS', 'chunk_id': '...'}]}"},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        
        try:
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload, timeout=10)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = SemanticExtractionResponse.model_validate_json(content)
                
                valid_edges = []
                valid_chunk_ids = {c["id"] for c in chunks}
                
                for e in parsed.edges:
                    if e.chunk_id not in valid_chunk_ids:
                        continue # Never accept edge without valid evidence
                    
                    evidence = GraphEvidenceDTO(
                        id="sem_ev_" + e.chunk_id,
                        material_id=material_id,
                        chunk_id=e.chunk_id,
                        snippet="Semantic relationship extracted from text."
                    )
                    
                    edge_dto = GraphEdgeDTO(
                        id=f"sem_edge_{e.source_name}_{e.target_name}",
                        subject_id=subject_id,
                        source_node_id=e.source_name,
                        target_node_id=e.target_name,
                        relation_type=e.relation_type,
                        extraction_mode="ONLINE_STRUCTURED",
                        evidence=[evidence],
                        evidence_counts=1
                    )
                    valid_edges.append(edge_dto)
                return valid_edges
        except Exception as e:
            print(f"[SemanticGraphExtractor] Failed semantic extraction: {e}")
            
        return []
