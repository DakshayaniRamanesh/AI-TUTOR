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
                    "type": node_type,  # 'note', 'tag', 'board'
                    "metadata": metadata or {}
                })

        def add_edge(source_id: str, target_id: str, edge_type: str = "tagged"):
            pair = (source_id, target_id)
            rev_pair = (target_id, source_id)
            if pair not in edge_set and rev_pair not in edge_set:
                edge_set.add(pair)
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type
                })

        # 1. Parse Notebook Canvas Boards (JSON)
        if os.path.exists(self.boards_dir):
            for fname in os.listdir(self.boards_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.boards_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        nb_id = data.get("board_id") or fname.replace(".json", "")
                        nb_title = data.get("title") or fname.replace(".json", "")
                        doc_node_id = f"doc_{nb_id}"

                        add_node(doc_node_id, nb_title, "board", {"filepath": fpath, "id": nb_id})

                        # Extract text from items
                        combined_text = ""
                        for item in data.get("items", []):
                            if isinstance(item, dict):
                                combined_text += " " + str(item.get("text", ""))
                                combined_text += " " + str(item.get("title", ""))
                                combined_text += " " + str(item.get("full_text", ""))

                        # Extract #hashtags
                        tags = set(re.findall(r'#([\w-]+)', combined_text))
                        for t in tags:
                            tag_node_id = f"tag_{t.lower()}"
                            add_node(tag_node_id, f"#{t}", "tag", {"tag": t})
                            add_edge(doc_node_id, tag_node_id, "tagged")

                    except Exception as e:
                        print(f"Error parsing board {fname}: {e}")

        # 2. Parse Git Markdown Notes (.md)
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

        # 3. Add Default Fallback Tags if dataset is minimal for demonstration
        if len(nodes) < 4:
            demo_tags = ["physics", "quantum", "calculus", "chemistry", "notes"]
            add_node("doc_demo_main", "Quantum Physics Board", "board", {"id": "board_main"})
            for t in demo_tags:
                tag_node_id = f"tag_{t}"
                add_node(tag_node_id, f"#{t}", "tag", {"tag": t})
                add_edge("doc_demo_main", tag_node_id, "tagged")

        return {"nodes": nodes, "edges": edges}
