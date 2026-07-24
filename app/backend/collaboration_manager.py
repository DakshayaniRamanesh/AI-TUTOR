"""
Collaboration Manager Backend
Manages Asynchronous Contributor Branches, Shareable Links (Public/Restricted access),
Editor-Only permissions, and Git-backed Simultaneous Conflict Resolution.
"""

import os
import json
import uuid
import secrets
from typing import List, Dict, Any, Optional
from .git_notes_manager import GitNotesManager

class CollaborationManager:
    def __init__(self, git_mgr: Optional[GitNotesManager] = None):
        self.git_mgr = git_mgr or GitNotesManager()
        self.config_path = os.path.join(self.git_mgr.repo_dir, ".git_collab_config.json")
        self.share_links = {} # token -> ShareLinkData
        self.load_config()
        self.ensure_sample_contributions()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.share_links = data.get("share_links", {})
            except Exception:
                self.share_links = {}

    def save_config(self):
        data = {"share_links": self.share_links}
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # --- 1. Shareable Link Generator & Permissions ---
    def create_share_link(
        self,
        note_filename: str,
        access_mode: str = "public",  # "public" or "restricted"
        allowed_emails: Optional[List[str]] = None,
        role: str = "editor"  # "editor" or "viewer"
    ) -> Dict[str, Any]:
        """Generates a secure share link for Editor-Only access."""
        token = secrets.token_hex(8)
        allowed = [e.strip().lower() for e in (allowed_emails or []) if e.strip()]

        link_data = {
            "token": token,
            "filename": note_filename,
            "access_mode": access_mode,
            "allowed_emails": allowed,
            "role": role,
            "url": f"https://aitutor.notes/share?id={note_filename}&token={token}",
            "created_at": os.path.basename(self.git_mgr.repo_dir)
        }

        self.share_links[token] = link_data
        self.save_config()
        return link_data

    def validate_access(self, token: str, user_email: Optional[str] = None) -> Dict[str, Any]:
        """Validates access for incoming collaborator link."""
        if token not in self.share_links:
            return {"valid": False, "reason": "Invalid or expired share link"}

        link = self.share_links[token]
        if link["access_mode"] == "public":
            return {"valid": True, "link": link}

        if link["access_mode"] == "restricted":
            if not user_email:
                return {"valid": False, "reason": "Email authentication required for restricted link"}
            if user_email.lower() not in link["allowed_emails"]:
                return {"valid": False, "reason": f"Access denied: '{user_email}' is not on the allowed access list"}
            return {"valid": True, "link": link}

        return {"valid": False, "reason": "Unknown access restriction"}

    # --- 2. Asynchronous Contributions (Pull Requests & Contributor Branches) ---
    def ensure_sample_contributions(self):
        """Creates sample contributor branches to demonstrate asynchronous contribution workflows."""
        branches = self.git_mgr.get_branches()

        # Contributor 1: Alex's Quantum Wave Equations
        if "contrib/alex_quantum" not in branches:
            try:
                curr = self.git_mgr.get_current_branch()
                self.git_mgr.create_branch("contrib/alex_quantum")
                self.git_mgr.switch_branch("contrib/alex_quantum")

                # Modify physics note
                content = self.git_mgr.get_file_content("physics_quantum_notes.md")
                content += "\n\n## 5. Schrödinger Wave Equation (Contributed by Alex)\nThe time-dependent Schrödinger equation describes the deterministic evolution of quantum states:\n$$i\\hbar \\frac{\\partial}{\\partial t}\\Psi(\\mathbf{r},t) = \\hat{H}\\Psi(\\mathbf{r},t)$$\n"
                self.git_mgr.save_file_content("physics_quantum_notes.md", content)
                self.git_mgr.stage_all()
                self.git_mgr.commit("Contrib (Alex): Add Schrödinger Wave Equation & Operators")

                self.git_mgr.switch_branch(curr)
            except Exception as e:
                print("Failed seeding alex contribution branch:", e)

        # Contributor 2: Sam's Calculus Integration Rules
        if "contrib/sam_calculus" not in branches:
            try:
                curr = self.git_mgr.get_current_branch()
                self.git_mgr.create_branch("contrib/sam_calculus")
                self.git_mgr.switch_branch("contrib/sam_calculus")

                content = self.git_mgr.get_file_content("calculus_reference.md")
                content += "\n\n## Integration Formulas (Contributed by Sam)\n- $\\int x^n dx = \\frac{x^{n+1}}{n+1} + C$\n- $\\int e^x dx = e^x + C$\n"
                self.git_mgr.save_file_content("calculus_reference.md", content)
                self.git_mgr.stage_all()
                self.git_mgr.commit("Contrib (Sam): Add Integration formulas reference")

                self.git_mgr.switch_branch(curr)
            except Exception as e:
                print("Failed seeding sam contribution branch:", e)

    def get_incoming_contributions(self) -> List[Dict[str, Any]]:
        """Lists external contributor branches ready to review and merge."""
        branches = self.git_mgr.get_branches()
        curr_branch = self.git_mgr.get_current_branch()
        contribs = []

        for b in branches:
            if b.startswith("contrib/"):
                author = b.replace("contrib/", "").title()
                diff_data = self.git_mgr.get_diff("physics_quantum_notes.md", target=b)
                if diff_data["additions"] == 0 and diff_data["deletions"] == 0:
                    diff_data = self.git_mgr.get_diff("calculus_reference.md", target=b)

                contribs.append({
                    "branch": b,
                    "author": author,
                    "title": f"Contribution by {author}",
                    "diff": diff_data,
                    "target_branch": curr_branch
                })

        return contribs

    def merge_contribution(self, contrib_branch: str) -> bool:
        """Merges a contributor's branch into the current active branch."""
        try:
            self.git_mgr._run_git(["merge", contrib_branch, "-m", f"Merge contribution from '{contrib_branch}'"])
            return True
        except Exception:
            # Fallback manual tree merge if CLI conflicts
            try:
                self.git_mgr._run_git(["merge", "--abort"])
            except Exception:
                pass
            return False

    # --- 3. Simultaneous Git Conflict Detection & Resolution Engine ---
    def simulate_simultaneous_conflict(self, filename: str = "physics_quantum_notes.md") -> Dict[str, Any]:
        """Simulates an overlapping simultaneous edit conflict between local user and remote collaborator."""
        local_content = self.git_mgr.get_file_content(filename)
        
        # Local user version
        user_version = local_content + "\n\n## 6. Quantum Entanglement (Mine)\nParticles remain entangled regardless of distance: $$\\text{State } |\\Psi^+\\rangle = \\frac{1}{\\sqrt{2}}(|00\\rangle + |11\\rangle)$$\n"
        
        # Remote collaborator version on same line
        remote_version = local_content + "\n\n## 6. EPR Paradox & Entanglement (Collaborator Alex)\nEinstein called entanglement 'spooky action at a distance'. Quantum Bell test proves non-locality!\n"

        return {
            "filename": filename,
            "conflict_detected": True,
            "mine": user_version,
            "theirs": remote_version,
            "mine_snippet": "## 6. Quantum Entanglement (Mine)\nState: |Ψ+⟩ = 1/√2 (|00⟩ + |11⟩)",
            "theirs_snippet": "## 6. EPR Paradox & Entanglement (Collaborator Alex)\nEinstein called entanglement 'spooky action at a distance'."
        }

    def resolve_and_commit_conflict(
        self,
        filename: str,
        choice: str,  # "mine", "theirs", or "both"
        user_content: str,
        remote_content: str
    ) -> bool:
        """Resolves simultaneous edit conflict and records a clean Git commit."""
        base_content = self.git_mgr.get_file_content(filename)

        if choice == "mine":
            final_content = user_content
        elif choice == "theirs":
            final_content = remote_content
        else: # "both"
            final_content = user_content + "\n" + remote_content.split(base_content)[-1]

        # Save resolved content
        self.git_mgr.save_file_content(filename, final_content)
        self.git_mgr.stage_file(filename)
        self.git_mgr.commit(f"Resolve simultaneous edit conflict in '{filename}' ({choice})")
        return True
