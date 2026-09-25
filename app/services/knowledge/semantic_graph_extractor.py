import os
import re
import json
import uuid
from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, Field

from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, NodeType, RelationType
from shared.ai_client import ai_client

class SemanticConceptResponse(BaseModel):
    name: str
    concept_type: str = "CONCEPT"  # CONCEPT, FORMULA, THEORM, TECHNIQUE
    description: str
    key_formula: Optional[str] = None
    chunk_id: Optional[str] = None

class SemanticEdgeResponse(BaseModel):
    source_name: str
    target_name: str
    relation_type: str = "RELATED_TO"
    chunk_id: Optional[str] = None

class SemanticExtractionResponse(BaseModel):
    concepts: List[SemanticConceptResponse] = Field(default_factory=list)
    edges: List[SemanticEdgeResponse] = Field(default_factory=list)


class SemanticGraphExtractor:
    """
    Extracts meaningful pedagogical concepts and directional relationships
    from learning materials using AI with deterministic heuristics fallback.
    """
    def __init__(self):
        pass

    def extract_semantic_graph(self, subject_id: str, material_id: str, chunks: List[Dict]) -> Tuple[List[GraphNodeDTO], List[GraphEdgeDTO]]:
        """
        Extracts both ConceptNode DTOs and ConceptEdge DTOs from document chunks.
        """
        if not chunks:
            return [], []

        # 1. Try AI extraction first
        ai_nodes, ai_edges = self._extract_with_ai(subject_id, material_id, chunks)
        if ai_nodes or ai_edges:
            return ai_nodes, ai_edges

        # 2. Rule-based heuristic extraction fallback
        return self._extract_heuristically(subject_id, material_id, chunks)

    def extract_semantic_edges(self, subject_id: str, material_id: str, chunks: List[Dict]) -> List[GraphEdgeDTO]:
        """Backward-compatible method returning only edges."""
        _, edges = self.extract_semantic_graph(subject_id, material_id, chunks)
        return edges

    def _extract_with_ai(self, subject_id: str, material_id: str, chunks: List[Dict]) -> Tuple[List[GraphNodeDTO], List[GraphEdgeDTO]]:
        valid_chunk_map = {c["id"]: c for c in chunks}
        chunk_snippets = []
        for c in chunks[:12]:
            text_preview = (c.get("text") or "").strip()[:400].replace("\n", " ")
            chunk_snippets.append(f"[Chunk {c['id']} (p.{c.get('page_number', 1)})]: {text_preview}")

        combined_text = "\n".join(chunk_snippets)
        prompt = f"""You are an expert STEM curriculum knowledge graph builder.
Analyze the following educational material excerpts and extract key concepts and relationships that help a student learn.

EXCERPTS:
{combined_text}

OUTPUT INSTRUCTIONS:
Return a JSON object with two arrays: "concepts" and "edges".
1. "concepts":
   - "name": Concise concept title (e.g. "Distributive Property", "Quadratic Formula", "Completing the Square").
   - "concept_type": One of: "CONCEPT", "FORMULA", "THEORM", "TECHNIQUE".
   - "description": 1-2 sentence student-friendly explanation of what it is, key insight, or formula.
   - "key_formula": Mathematical formula if applicable (LaTeX format without surrounding $).
   - "chunk_id": The chunk ID where this concept is introduced.

2. "edges":
   - "source_name": Exact concept name from the concepts list (or from standard prerequisites).
   - "target_name": Exact concept name that depends on or relates to source_name.
   - "relation_type": One of: "PREREQUISITE_OF", "APPLIES_TO", "DERIVED_FROM", "EXPLAINS", "RELATED_TO".
   - "chunk_id": Chunk ID evidencing this relationship.

Make sure concepts connect to each other logically (prerequisites flow into advanced topics). Output pure JSON only.
"""

        try:
            resp_str = ai_client.generate_content(prompt)
            # Remove any markdown code fence wrapping
            clean_str = resp_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            elif clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            clean_str = clean_str.strip()

            parsed = json.loads(clean_str)
            raw_concepts = parsed.get("concepts", [])
            raw_edges = parsed.get("edges", [])

            extracted_nodes: List[GraphNodeDTO] = []
            extracted_edges: List[GraphEdgeDTO] = []

            for c in raw_concepts:
                c_name = (c.get("name") or "").strip()
                if not c_name or len(c_name) < 2:
                    continue
                cid = c.get("chunk_id") or list(valid_chunk_map.keys())[0]
                chunk_obj = valid_chunk_map.get(cid, {})

                ev = GraphEvidenceDTO(
                    id=f"ev_node_{uuid.uuid4().hex[:8]}",
                    material_id=material_id,
                    chunk_id=cid,
                    page_number=chunk_obj.get("page_number", 1),
                    snippet=(chunk_obj.get("text", "") or "")[:200]
                )

                desc = c.get("description") or f"Core concept: {c_name}."
                if c.get("key_formula"):
                    desc += f" Formula: ${c['key_formula']}$"

                node_type = NodeType.CONCEPT
                raw_type = (c.get("concept_type") or "").upper()
                if "FORMULA" in raw_type:
                    node_type = NodeType.CONCEPT
                elif "THEOR" in raw_type:
                    node_type = NodeType.CONCEPT

                extracted_nodes.append(GraphNodeDTO(
                    id=f"concept_{c_name.lower().replace(' ', '_')}",
                    subject_id=subject_id,
                    canonical_key=c_name.lower(),
                    display_name=c_name,
                    node_type=node_type,
                    description=desc,
                    evidence_counts=1,
                    extraction_mode="ONLINE_STRUCTURED",
                    evidence=[ev]
                ))

            for e in raw_edges:
                src = (e.get("source_name") or "").strip()
                tgt = (e.get("target_name") or "").strip()
                if not src or not tgt or src == tgt:
                    continue

                rel_str = (e.get("relation_type") or "RELATED_TO").upper()
                try:
                    rel_type = RelationType(rel_str)
                except ValueError:
                    rel_type = RelationType.RELATED_TO

                cid = e.get("chunk_id") or list(valid_chunk_map.keys())[0]
                chunk_obj = valid_chunk_map.get(cid, {})
                ev = GraphEvidenceDTO(
                    id=f"ev_edge_{uuid.uuid4().hex[:8]}",
                    material_id=material_id,
                    chunk_id=cid,
                    page_number=chunk_obj.get("page_number", 1),
                    snippet="Semantic learning relationship"
                )

                extracted_edges.append(GraphEdgeDTO(
                    id=f"edge_{uuid.uuid4().hex[:8]}",
                    subject_id=subject_id,
                    source_node_id=f"concept_{src.lower().replace(' ', '_')}",
                    target_node_id=f"concept_{tgt.lower().replace(' ', '_')}",
                    relation_type=rel_type,
                    extraction_mode="ONLINE_STRUCTURED",
                    evidence=[ev],
                    evidence_counts=1
                ))

            if extracted_nodes:
                return extracted_nodes, extracted_edges
        except Exception as e:
            print(f"[SemanticGraphExtractor] AI extraction notice: {e}")

        return [], []

    def _extract_heuristically(self, subject_id: str, material_id: str, chunks: List[Dict]) -> Tuple[List[GraphNodeDTO], List[GraphEdgeDTO]]:
        """
        Deterministic, fast extraction of mathematical definitions, rules, and theorems.
        """
        nodes: List[GraphNodeDTO] = []
        edges: List[GraphEdgeDTO] = []
        seen_concepts = set()

        patterns = [
            (r"(?:Rule|Property|Law):\s*([^\.\n]+)", "Property / Rule"),
            (r"(?:Theorem|Lemma|Corollary):\s*([^\.\n]+)", "Theorem"),
            (r"(?:Definition):\s*([^\.\n]+)", "Definition"),
            (r"(?:Method|Technique):\s*([^\.\n]+)", "Technique"),
        ]

        for c in chunks:
            text = c.get("text") or ""
            cid = c.get("id")
            page_num = c.get("page_number", 1)

            # Look for explicit rules/properties
            for pat, kind in patterns:
                for match in re.finditer(pat, text, re.IGNORECASE):
                    full_desc = match.group(1).strip()
                    title_words = full_desc.split("—")[0].split(":")[0].split(",")[0].strip()
                    name = title_words[:35].strip()
                    if name and len(name) >= 3 and name.lower() not in seen_concepts:
                        seen_concepts.add(name.lower())
                        node_id = f"concept_{name.lower().replace(' ', '_')}"
                        ev = GraphEvidenceDTO(
                            id=f"ev_heur_{uuid.uuid4().hex[:8]}",
                            material_id=material_id,
                            chunk_id=cid,
                            page_number=page_num,
                            snippet=text[max(0, match.start() - 20):min(len(text), match.end() + 80)]
                        )
                        nodes.append(GraphNodeDTO(
                            id=node_id,
                            subject_id=subject_id,
                            canonical_key=name.lower(),
                            display_name=name,
                            node_type=NodeType.CONCEPT,
                            description=f"{kind}: {full_desc}",
                            evidence_counts=1,
                            extraction_mode="OFFLINE_STRUCTURAL",
                            evidence=[ev]
                        ))

            # Look for key algebraic patterns in text
            if "parentheses" in text.lower() or "outside multiplies" in text.lower():
                if "distributive property" not in seen_concepts:
                    seen_concepts.add("distributive property")
                    node_id = "concept_distributive_property"
                    ev = GraphEvidenceDTO(
                        id=f"ev_dist_{uuid.uuid4().hex[:8]}",
                        material_id=material_id,
                        chunk_id=cid,
                        page_number=page_num,
                        snippet="The number outside multiplies every term inside the parentheses."
                    )
                    nodes.append(GraphNodeDTO(
                        id=node_id,
                        subject_id=subject_id,
                        canonical_key="distributive property",
                        display_name="Distributive Property",
                        node_type=NodeType.CONCEPT,
                        description="Rule: The factor outside multiplies every term inside parentheses: a(b + c) = ab + ac.",
                        evidence_counts=1,
                        extraction_mode="OFFLINE_STRUCTURAL",
                        evidence=[ev]
                    ))

        # Build prerequisite / dependency edges between extracted concepts
        for i in range(len(nodes) - 1):
            n1 = nodes[i]
            n2 = nodes[i + 1]
            edges.append(GraphEdgeDTO(
                id=f"edge_heur_{uuid.uuid4().hex[:8]}",
                subject_id=subject_id,
                source_node_id=n1.id,
                target_node_id=n2.id,
                relation_type=RelationType.PREREQUISITE_OF,
                extraction_mode="OFFLINE_STRUCTURAL",
                evidence=[],
                evidence_counts=1
            ))

        return nodes, edges
