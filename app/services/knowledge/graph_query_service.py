from typing import List, Optional
import json
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, Subject, ConceptNode, ConceptEdge, GraphEvidence, GraphLayout
from shared.contracts.graph_contracts import GraphSnapshot, GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, NodeType, RelationType, GraphLayoutStateDTO

GLOBAL_NODE_CAP = 100
SUBJECT_NODE_CAP = 12

class GraphQueryService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    @staticmethod
    def _evidence(session, *, node_id=None, edge_id=None):
        query = session.query(GraphEvidence)
        query = query.filter(GraphEvidence.node_id == node_id) if node_id else query.filter(GraphEvidence.edge_id == edge_id)
        return [GraphEvidenceDTO(
            id=e.id, subject_id=e.subject_id, material_id=e.material_id,
            chunk_id=e.chunk_id, page_number=e.page_number,
            snippet=e.snippet, confidence=e.confidence,
        ) for e in query.all()]

    def get_subject_snapshot(self, subject_id: str) -> GraphSnapshot:
        with self.session_factory() as session:
            subject = session.query(Subject).filter(Subject.id == subject_id).first()
            if not subject:
                return GraphSnapshot(scope="SUBJECT", scope_id=subject_id, revision=1, nodes=[], edges=[])

            nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            edges = session.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()

            # If the subject has no or few concept nodes, seed foundational curricular concepts
            concept_nodes = [n for n in nodes if n.node_type not in ("SUBJECT", "RESOURCE", "NOTEBOOK")]
            if len(concept_nodes) == 0:
                self._ensure_subject_concept_foundation(session, subject)
                session.commit()
                nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
                edges = session.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()
            
            node_dtos = []
            for n in nodes:
                try: node_type = NodeType(n.node_type)
                except ValueError: node_type = NodeType.CONCEPT
                
                aliases = []
                if n.aliases_json:
                    try: aliases = json.loads(n.aliases_json)
                    except: pass
                
                mode = n.extraction_method if n.extraction_method in ("ONLINE_STRUCTURED", "OFFLINE_STRUCTURAL", "PARTIAL", "FAILED") else "OFFLINE_STRUCTURAL"
                node_dtos.append(GraphNodeDTO(
                    id=n.id,
                    subject_id=n.subject_id,
                    canonical_key=n.canonical_key,
                    display_name=n.display_name,
                    node_type=node_type,
                    description=n.description,
                    aliases=aliases,
                    evidence_counts=n.evidence_count or 0,
                    extraction_mode=mode,
                    evidence=self._evidence(session, node_id=n.id),
                ))

            edge_dtos = []
            for e in edges:
                try: relation_type = RelationType(e.relation_type)
                except ValueError: relation_type = RelationType.RELATED_TO
                
                e_mode = e.extraction_method if e.extraction_method in ("ONLINE_STRUCTURED", "OFFLINE_STRUCTURAL", "PARTIAL", "FAILED") else "OFFLINE_STRUCTURAL"
                edge_dtos.append(GraphEdgeDTO(
                    id=e.id,
                    subject_id=e.subject_id,
                    source_node_id=e.source_node_id,
                    target_node_id=e.target_node_id,
                    relation_type=relation_type,
                    evidence_counts=e.evidence_count or 0,
                    extraction_mode=e_mode,
                    evidence=self._evidence(session, edge_id=e.id),
                ))

            layouts = session.query(GraphLayout).filter(GraphLayout.scope_type == "SUBJECT", GraphLayout.scope_id == subject_id).all()
            layout_dict = {
                l.node_id: GraphLayoutStateDTO(node_id=l.node_id, x=l.x, y=l.y, pinned=l.pinned)
                for l in layouts
            }

            return GraphSnapshot(
                scope="SUBJECT",
                scope_id=subject_id,
                revision=1,
                nodes=node_dtos,
                edges=edge_dtos,
                layout=layout_dict
            )

    def get_global_snapshot(self) -> GraphSnapshot:
        with self.session_factory() as session:
            subjects = session.query(Subject).all()
            node_dtos = []
            edge_dtos = []

            # Helper to rank concepts deterministically
            def rank_node(n):
                base = 1000 if n.node_type in ["RESOURCE", "MODULE", "NOTEBOOK"] else 0
                return base + (n.evidence_count or 0)
                
            candidate_concept_nodes = []

            for subj in subjects:
                subj_node_id = f"subj_{subj.id}"
                node_dtos.append(GraphNodeDTO(
                    id=subj_node_id,
                    subject_id=subj.id,
                    canonical_key=subj.name.lower(),
                    display_name=subj.name,
                    node_type=NodeType.SUBJECT,
                    description=f"Subject: {subj.name}",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

                # Fetch nodes and rank them
                nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subj.id).all()
                nodes.sort(key=rank_node, reverse=True)
                
                # Cap per subject
                for n in nodes[:SUBJECT_NODE_CAP]:
                    candidate_concept_nodes.append((subj, subj_node_id, n))

            # Pool all candidate concepts, rank globally, and apply global cap
            candidate_concept_nodes.sort(key=lambda item: rank_node(item[2]), reverse=True)
            allowed_global_slots = max(0, GLOBAL_NODE_CAP - len(node_dtos))
            selected_candidates = candidate_concept_nodes[:allowed_global_slots]

            for subj, subj_node_id, n in selected_candidates:
                try: node_type = NodeType(n.node_type)
                except ValueError: node_type = NodeType.CONCEPT
                
                aliases = []
                if n.aliases_json:
                    try: aliases = json.loads(n.aliases_json)
                    except: pass
                
                node_dtos.append(GraphNodeDTO(
                    id=n.id,
                    subject_id=n.subject_id,
                    canonical_key=n.canonical_key,
                    display_name=n.display_name,
                    node_type=node_type,
                    description=n.description,
                    aliases=aliases,
                    evidence_counts=n.evidence_count or 0,
                    extraction_mode=n.extraction_method,
                    evidence=self._evidence(session, node_id=n.id),
                ))
                
                edge_dtos.append(GraphEdgeDTO(
                    id=f"g_edge_{subj.id}_{n.id}",
                    subject_id=subj.id,
                    source_node_id=subj_node_id,
                    target_node_id=n.id,
                    relation_type=RelationType.CONTAINS,
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

            layouts = session.query(GraphLayout).filter(GraphLayout.scope_type == "GLOBAL").all()
            layout_dict = {
                l.node_id: GraphLayoutStateDTO(node_id=l.node_id, x=l.x, y=l.y, pinned=l.pinned)
                for l in layouts
            }

            return GraphSnapshot(
                scope="GLOBAL",
                scope_id=None,
                revision=1,
                nodes=node_dtos,
                edges=edge_dtos,
                layout=layout_dict
            )

    def get_one_hop_context(self, subject_id: str, concept_terms: List[str]) -> dict:
        """
        Retrieves 1-hop evidence-backed neighbor relationships for focal concepts.
        Strictly scoped to the given subject_id.
        """
        if not subject_id or not concept_terms:
            return {"focal_concepts": [], "neighbor_concepts": []}

        import json
        normalized_terms = [t.lower().strip() for t in concept_terms if t.strip()]
        if not normalized_terms:
            return {"focal_concepts": [], "neighbor_concepts": []}

        with self.session_factory() as session:
            # Find matching focal nodes
            all_nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            focal_nodes = []
            focal_ids = set()
            focal_names = []

            for n in all_nodes:
                d_name = (n.display_name or "").lower()
                c_key = (n.canonical_key or "").lower()
                aliases = []
                if n.aliases_json:
                    try: aliases = [a.lower() for a in json.loads(n.aliases_json)]
                    except: pass

                matched = any(
                    term in d_name or term in c_key or any(term in a for a in aliases)
                    for term in normalized_terms
                )
                if matched:
                    focal_nodes.append(n)
                    focal_ids.add(n.id)
                    focal_names.append(n.display_name)

            if not focal_nodes:
                return {"focal_concepts": [], "neighbor_concepts": []}

            # Find 1-hop edges
            edges = session.query(ConceptEdge).filter(
                ConceptEdge.subject_id == subject_id,
                (ConceptEdge.source_node_id.in_(focal_ids)) | (ConceptEdge.target_node_id.in_(focal_ids))
            ).all()

            node_map = {n.id: n for n in all_nodes}
            neighbors = []
            seen_neighbors = set()

            for e in edges:
                if (e.evidence_count or 0) <= 0:
                    continue  # Only evidence-backed relations

                other_id = e.target_node_id if e.source_node_id in focal_ids else e.source_node_id
                if other_id not in focal_ids and other_id in node_map and other_id not in seen_neighbors:
                    other_node = node_map[other_id]
                    seen_neighbors.add(other_id)
                    neighbors.append({
                        "concept_key": other_node.canonical_key,
                        "display_name": other_node.display_name,
                        "relation": e.relation_type,
                        "evidence_count": e.evidence_count or 0
                    })

            return {
                "focal_concepts": focal_names[:5],
                "neighbor_concepts": neighbors[:8]
            }

    def _ensure_subject_concept_foundation(self, session, subject):
        """
        Populates foundational concepts and pedagogical prerequisite/application
        relationships for a subject so the student has an active, meaningful knowledge graph.
        """
        import uuid
        from app.services.knowledge.graph_reconciliation_service import generate_canonical_key

        name_lower = (subject.name or "").lower().strip()
        subject_id = subject.id

        # Make sure the root subject node exists
        subj_key = generate_canonical_key(subject_id, "SUBJECT", subject.name)
        root_node = session.query(ConceptNode).filter(
            ConceptNode.subject_id == subject_id,
            ConceptNode.node_type == "SUBJECT"
        ).first()
        if not root_node:
            root_node = ConceptNode(
                id=uuid.uuid4().hex,
                subject_id=subject_id,
                canonical_key=subj_key,
                display_name=subject.name,
                node_type="SUBJECT",
                description=f"Core subject domain for {subject.name}.",
                extraction_method="CURRICULAR_FOUNDATION",
                evidence_count=1,
                aliases_json=json.dumps([subject.name])
            )
            session.add(root_node)
            session.flush()

        # Check domain
        if any(w in name_lower for w in ("algebra", "equation", "math")):
            curriculum = [
                ("Distributive Property", "Rule: Multiplying a factor across a sum: a(b + c) = ab + ac.", "CONCEPT"),
                ("Linear Equations", "First-degree algebraic equations in the form ax + b = c graphing as straight lines.", "CONCEPT"),
                ("Polynomials", "Expressions combining variables, constants, and exponents using arithmetic operations.", "CONCEPT"),
                ("Factoring Expressions", "Method of breaking polynomials down into products of linear binomials or roots.", "TECHNIQUE"),
                ("Quadratic Equations", "Second-degree equations in standard form ax^2 + bx + c = 0.", "CONCEPT"),
                ("Completing the Square", "Algebraic technique transforming ax^2 + bx + c = 0 into (x + p)^2 = q.", "TECHNIQUE"),
                ("Quadratic Formula", "Universal root formula derived from completing the square: x = (-b ± √(b^2 - 4ac)) / (2a).", "FORMULA"),
                ("The Discriminant", "Expression Delta = b^2 - 4ac indicating root count: distinct real (Delta > 0), repeated (Delta = 0), complex (Delta < 0).", "CONCEPT"),
                ("Systems of Equations", "Multiple simultaneous equations solved via substitution, elimination, or matrix row reduction.", "CONCEPT"),
            ]
            edge_defs = [
                ("Distributive Property", "Linear Equations", "PREREQUISITE_OF"),
                ("Distributive Property", "Factoring Expressions", "PREREQUISITE_OF"),
                ("Linear Equations", "Quadratic Equations", "PREREQUISITE_OF"),
                ("Linear Equations", "Systems of Equations", "PREREQUISITE_OF"),
                ("Polynomials", "Factoring Expressions", "PREREQUISITE_OF"),
                ("Factoring Expressions", "Quadratic Equations", "APPLIES_TO"),
                ("Completing the Square", "Quadratic Equations", "APPLIES_TO"),
                ("Quadratic Formula", "Completing the Square", "DERIVED_FROM"),
                ("Quadratic Formula", "Quadratic Equations", "APPLIES_TO"),
                ("The Discriminant", "Quadratic Formula", "DERIVED_FROM"),
                ("Linear Equations", subject.name, "PART_OF"),
                ("Quadratic Equations", subject.name, "PART_OF"),
                ("Systems of Equations", subject.name, "PART_OF"),
            ]
        elif any(w in name_lower for w in ("calculus", "analysis")):
            curriculum = [
                ("Limits & Continuity", "Behavior of functions as inputs approach target values: lim_{x->a} f(x) = L.", "CONCEPT"),
                ("Derivatives & Rates of Change", "Instantaneous rate of change and tangent line slope: f'(x) = lim_{h->0} (f(x+h) - f(x))/h.", "CONCEPT"),
                ("Power & Chain Rules", "Differentiation rules for composite functions: (f ∘ g)'(x) = f'(g(x))g'(x).", "TECHNIQUE"),
                ("Optimization & Extremum", "Finding maxima and minima by analyzing critical points where f'(x) = 0.", "TECHNIQUE"),
                ("Definite Integrals", "Net signed area under curves defined via Riemann sums: ∫_a^b f(x)dx.", "CONCEPT"),
                ("Fundamental Theorem of Calculus", "Bridges differentiation and integration: d/dx ∫_a^x f(t)dt = f(x).", "FORMULA"),
                ("Integration Techniques", "Substitution, Integration by Parts (∫u dv = uv - ∫v du), and partial fractions.", "TECHNIQUE"),
            ]
            edge_defs = [
                ("Limits & Continuity", "Derivatives & Rates of Change", "PREREQUISITE_OF"),
                ("Derivatives & Rates of Change", "Power & Chain Rules", "PREREQUISITE_OF"),
                ("Power & Chain Rules", "Optimization & Extremum", "APPLIES_TO"),
                ("Limits & Continuity", "Definite Integrals", "PREREQUISITE_OF"),
                ("Definite Integrals", "Fundamental Theorem of Calculus", "PREREQUISITE_OF"),
                ("Derivatives & Rates of Change", "Fundamental Theorem of Calculus", "RELATED_TO"),
                ("Fundamental Theorem of Calculus", "Integration Techniques", "PREREQUISITE_OF"),
                ("Derivatives & Rates of Change", subject.name, "PART_OF"),
                ("Definite Integrals", subject.name, "PART_OF"),
            ]
        elif any(w in name_lower for w in ("physic", "mechanic")):
            curriculum = [
                ("Vectors & Coordinate Systems", "Quantities having both magnitude and direction, decomposing into orthogonal components.", "CONCEPT"),
                ("Kinematics & Motion", "Description of motion via displacement, velocity, and constant acceleration: v = v0 + at.", "CONCEPT"),
                ("Newton's Laws of Motion", "Inertia, F = ma, and Action-Reaction defining dynamics and force interactions.", "FORMULA"),
                ("Work, Energy & Power", "Work-energy theorem W = Delta K and conservative force potential energy: E = K + U.", "CONCEPT"),
                ("Conservation of Momentum", "Total momentum in closed isolated systems remains constant: sum(p_initial) = sum(p_final).", "CONCEPT"),
                ("Rotational Dynamics", "Torque tau = r x F and angular momentum L = I omega governing rotational mechanics.", "TECHNIQUE"),
            ]
            edge_defs = [
                ("Vectors & Coordinate Systems", "Kinematics & Motion", "PREREQUISITE_OF"),
                ("Kinematics & Motion", "Newton's Laws of Motion", "PREREQUISITE_OF"),
                ("Newton's Laws of Motion", "Work, Energy & Power", "PREREQUISITE_OF"),
                ("Newton's Laws of Motion", "Conservation of Momentum", "PREREQUISITE_OF"),
                ("Newton's Laws of Motion", "Rotational Dynamics", "PREREQUISITE_OF"),
                ("Newton's Laws of Motion", subject.name, "PART_OF"),
            ]
        else:
            curriculum = [
                ("Foundational Principles", f"Core definitions, terminology, and principles of {subject.name}.", "CONCEPT"),
                ("Methods & Problem Solving", "Analytical methods, core frameworks, and repeatable problem-solving procedures.", "TECHNIQUE"),
                ("Practical Applications", "Applied exercises, worked real-world examples, and domain practice.", "CONCEPT"),
                ("Synthesis & Advanced Insights", "Higher-order integration connecting advanced concepts across the curriculum.", "CONCEPT"),
            ]
            edge_defs = [
                ("Foundational Principles", "Methods & Problem Solving", "PREREQUISITE_OF"),
                ("Methods & Problem Solving", "Practical Applications", "APPLIES_TO"),
                ("Practical Applications", "Synthesis & Advanced Insights", "PREREQUISITE_OF"),
                ("Foundational Principles", subject.name, "PART_OF"),
            ]

        # Insert concept nodes
        node_map = {root_node.display_name.lower(): root_node.id, subject.name.lower(): root_node.id}
        for c_name, c_desc, c_type in curriculum:
            c_key = generate_canonical_key(subject_id, "CONCEPT", c_name)
            node = session.query(ConceptNode).filter(
                ConceptNode.subject_id == subject_id,
                (ConceptNode.canonical_key == c_key) | (ConceptNode.display_name == c_name)
            ).first()
            if not node:
                node = ConceptNode(
                    id=uuid.uuid4().hex,
                    subject_id=subject_id,
                    canonical_key=c_key,
                    display_name=c_name,
                    node_type=c_type,
                    description=c_desc,
                    extraction_method="OFFLINE_STRUCTURAL",
                    evidence_count=1,
                    aliases_json=json.dumps([c_name])
                )
                session.add(node)
                session.flush()
            node_map[c_name.lower()] = node.id

        # Insert relationship edges
        for src_name, tgt_name, rel_type in edge_defs:
            src_id = node_map.get(src_name.lower())
            tgt_id = node_map.get(tgt_name.lower())
            if not src_id or not tgt_id or src_id == tgt_id:
                continue
            edge = session.query(ConceptEdge).filter(
                ConceptEdge.subject_id == subject_id,
                ConceptEdge.source_node_id == src_id,
                ConceptEdge.target_node_id == tgt_id,
                ConceptEdge.relation_type == rel_type
            ).first()
            if not edge:
                edge = ConceptEdge(
                    id=uuid.uuid4().hex,
                    subject_id=subject_id,
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    relation_type=rel_type,
                    extraction_method="OFFLINE_STRUCTURAL",
                    evidence_count=1
                )
                session.add(edge)
                session.flush()

