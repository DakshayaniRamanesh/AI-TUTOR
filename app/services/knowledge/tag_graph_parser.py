"""
Tag & Document Link Parser for Obsidian-Style Knowledge Graph
Scans saved notebook canvas boards (JSON) and Git notes repository (MD) to extract
#hashtags and cross-document links, returning a node-edge graph data structure.
"""

import os
import json
import re
from typing import Dict, List, Any

class TagGraphParser:
    def __init__(self, boards_dir: str = "storage_data/boards", git_repo_dir: str = "storage_data/git_notes_repo"):
        self.boards_dir = boards_dir
        self.git_repo_dir = git_repo_dir

    def build_knowledge_graph(self) -> Dict[str, List[Any]]:
        nodes = []
        edges = []
        node_ids = set()
        edge_set = set()

        def add_node(node_id: str, label: str, node_type: str, metadata: dict = None):
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": label,
                    "type": node_type,  # 'note', 'tag', 'board', 'subject', 'concept'
                    "metadata": metadata or {}
                })

        def add_edge(source_id: str, target_id: str, edge_type: str = "tagged"):
            pair = (source_id, target_id)
            rev_pair = (target_id, source_id)
            if pair not in edge_set and rev_pair not in edge_set and source_id != target_id:
                edge_set.add(pair)
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type
                })

        # Topic keyword inference rules
        TOPIC_RULES = [
            ("physics", ["physics", "quantum", "mechanics", "vector", "oscillation", "wave", "thermal", "field", "potential"]),
            ("calculus", ["calculus", "differentiat", "limit", "integrat", "differential equation"]),
            ("mechanics", ["mechanic", "vector", "static", "equilibrium", "dynamic", "kinematic"]),
            ("chemistry", ["chemist", "kinetic", "rate law", "organic", "reaction", "electrochemist", "metal", "complex"]),
            ("semester_notes", ["week 0", "foundations", "notation", "problem set", "lab walkthrough"]),
            ("exam_prep", ["past paper", "walkthrough", "formula", "theorem", "revision"]),
        ]

        board_records = []

        # 1. Parse Notebook Canvas Boards (JSON)
        if os.path.exists(self.boards_dir):
            for fname in sorted(os.listdir(self.boards_dir)):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.boards_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        nb_id = data.get("board_id") or fname.replace(".json", "")
                        nb_title = data.get("title") or fname.replace(".json", "")
                        doc_node_id = f"doc_{nb_id}"

                        add_node(doc_node_id, nb_title, "board", {"filepath": fpath, "id": nb_id, "title": nb_title})
                        board_records.append((doc_node_id, nb_title))

                        # Extract text from items
                        combined_text = nb_title
                        for item in data.get("items", []):
                            if isinstance(item, dict):
                                combined_text += " " + str(item.get("text", ""))
                                combined_text += " " + str(item.get("title", ""))
                                combined_text += " " + str(item.get("full_text", ""))

                        # Extract explicit #hashtags
                        tags = set(re.findall(r'#([\w-]+)', combined_text))
                        for t in tags:
                            tag_node_id = f"tag_{t.lower()}"
                            add_node(tag_node_id, f"#{t}", "tag", {"tag": t})
                            add_edge(doc_node_id, tag_node_id, "tagged")

                        # Infer topic tags from title/content
                        lower_text = combined_text.lower()
                        for topic_name, keywords in TOPIC_RULES:
                            if any(kw in lower_text for kw in keywords):
                                topic_node_id = f"tag_{topic_name}"
                                add_node(topic_node_id, f"#{topic_name}", "tag", {"tag": topic_name})
                                add_edge(doc_node_id, topic_node_id, "references")

                    except Exception as e:
                        print(f"Error parsing board {fname}: {e}")

        # 2. Sequential & Series Linking for Notebooks
        # (A) Numbered Board Series (e.g., Notebook Board 1 -> Notebook Board 2 -> 3 -> 4)
        generic_boards = []
        for doc_id, title in board_records:
            match = re.search(r'^(Notebook\s*Board|Board)\s*(\d+)$', title, re.IGNORECASE)
            if match:
                generic_boards.append((int(match.group(2)), doc_id, title))
        generic_boards.sort(key=lambda x: x[0])
        for i in range(len(generic_boards) - 1):
            add_edge(generic_boards[i][1], generic_boards[i+1][1], "sequence")

        # (B) Unit / Module Sequences (e.g. Unit 01 -> Unit 02 in Math, Physics, Chemistry)
        unit_groups = {}
        for doc_id, title in board_records:
            match = re.search(r'Unit\s*0?(\d+)\s*-\s*(.*)', title, re.IGNORECASE)
            if match:
                unit_num = int(match.group(1))
                unit_topic = match.group(2).lower()
                # Group by domain
                if any(w in unit_topic for w in ["differentiat", "integrat", "static", "dynamic", "limit", "equation"]):
                    domain = "math"
                elif any(w in unit_topic for w in ["mechanic", "vector", "oscillation", "wave", "thermal", "field", "quantum"]):
                    domain = "physics"
                elif any(w in unit_topic for w in ["kinetic", "organic", "reaction", "electrochemist", "transition", "metal"]):
                    domain = "chemistry"
                else:
                    domain = "general"
                unit_groups.setdefault(domain, []).append((unit_num, doc_id, title))

        for domain, units in unit_groups.items():
            units.sort(key=lambda x: x[0])
            for i in range(len(units) - 1):
                add_edge(units[i][1], units[i+1][1], "next_unit")

        # (C) Week Sequences (e.g. Week 01 -> Week 02 -> Week 03)
        week_boards = []
        for doc_id, title in board_records:
            match = re.search(r'Week\s*0?(\d+)', title, re.IGNORECASE)
            if match:
                week_boards.append((int(match.group(1)), doc_id, title))
        week_boards.sort(key=lambda x: x[0])
        for i in range(len(week_boards) - 1):
            add_edge(week_boards[i][1], week_boards[i+1][1], "next_week")

        # (D) Cross-disciplinary and reference links
        titles_to_id = {title: doc_id for doc_id, title in board_records}
        if "Physics Notebook 1" in titles_to_id and "Unit 01 - Mechanics & Vectors" in titles_to_id:
            add_edge(titles_to_id["Physics Notebook 1"], titles_to_id["Unit 01 - Mechanics & Vectors"], "references")
        if "Notebook Board 1" in titles_to_id and "Unit 01 - Differentiation & Limits" in titles_to_id:
            add_edge(titles_to_id["Notebook Board 1"], titles_to_id["Unit 01 - Differentiation & Limits"], "scratchpad")

        # Connect inter-topic tag relations
        tag_relations = [
            ("tag_physics", "tag_mechanics", "includes"),
            ("tag_calculus", "tag_mechanics", "applies_to"),
            ("tag_physics", "tag_calculus", "uses_math"),
            ("tag_semester_notes", "tag_exam_prep", "leads_to"),
        ]
        for src_tag, tgt_tag, rel in tag_relations:
            if src_tag in node_ids and tgt_tag in node_ids:
                add_edge(src_tag, tgt_tag, rel)

        # 3. Parse Git Markdown Notes (.md)
        if os.path.exists(self.git_repo_dir):
            for root, _, files in os.walk(self.git_repo_dir):
                for fname in files:
                    if fname.endswith(".md"):
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()

                            doc_name = fname.replace(".md", "")
                            doc_node_id = f"md_{doc_name}"
                            add_node(doc_node_id, doc_name, "note", {"filepath": fpath})

                            # Extract #hashtags
                            tags = set(re.findall(r'#([\w-]+)', content))
                            for t in tags:
                                tag_node_id = f"tag_{t.lower()}"
                                add_node(tag_node_id, f"#{t}", "tag", {"tag": t})
                                add_edge(doc_node_id, tag_node_id, "tagged")

                            # Extract Wiki Links [[Note]]
                            wiki_links = set(re.findall(r'\[\[(.*?)\]\]', content))
                            for wl in wiki_links:
                                target_id = f"md_{wl}"
                                add_node(target_id, wl, "note", {"filepath": ""})
                                add_edge(doc_node_id, target_id, "links")

                        except Exception as e:
                            print(f"Error parsing md {fname}: {e}")

        return {"nodes": nodes, "edges": edges}
