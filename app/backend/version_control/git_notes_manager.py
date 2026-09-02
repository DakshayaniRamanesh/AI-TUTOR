"""
Git Notes Manager Backend
Interfaces directly with native Git CLI / repository storage for notes AND Freeform Canvas Boards.
Handles repository creation, staging, commits, line diffs, branching, and commit history for both .md and .json boards.
"""

import os
import subprocess
import json
import shutil
import re
from typing import List, Dict, Any, Optional

class GitError(Exception):
    """Structured Git exception providing user-friendly and technical messages."""
    def __init__(self, friendly_message: str, technical_details: str = "", command: str = ""):
        super().__init__(friendly_message)
        self.friendly_message = friendly_message
        self.technical_details = technical_details
        self.command = command

    def __str__(self):
        if self.technical_details:
            return f"{self.friendly_message} (Details: {self.technical_details})"
        return self.friendly_message


class GitNotesManager:
    def __init__(self, repo_dir: Optional[str] = None):
        if not repo_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            repo_dir = os.path.join(base_dir, "storage_data", "git_notes_repo")
        
        self.repo_dir = repo_dir
        self.boards_source_dir = os.path.join(os.path.dirname(self.repo_dir), "boards")
        self.ensure_repo_exists()
        self.sync_boards_to_repo()

    def _run_git(self, args: List[str]) -> str:
        """Helper to run git CLI commands inside repo directory."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace"
            )
            return res.stdout.strip()
        except FileNotFoundError:
            raise GitError(
                "Git is not installed or not found on system PATH.",
                technical_details="FileNotFoundError: 'git' command missing",
                command="git " + " ".join(args)
            )
        except subprocess.CalledProcessError as e:
            err_output = e.stderr.strip() or e.stdout.strip()
            friendly = self._translate_error(args, err_output)
            raise GitError(friendly, technical_details=err_output, command="git " + " ".join(args))

    def _translate_error(self, args: List[str], raw_error: str) -> str:
        """Translates raw git stderr into human-friendly explanations."""
        cmd = args[0] if args else ""
        if "nothing to commit" in raw_error.lower():
            return "No changes detected to save."
        if "pathspec" in raw_error.lower() and "did not match any file" in raw_error.lower():
            return "The requested file or version was not found."
        if "already exists" in raw_error.lower():
            return "A copy or version with this name already exists."
        if "conflict" in raw_error.lower():
            return "Changes need review because conflicting edits were detected."
        return f"Version control operation '{cmd}' failed: {raw_error}"

    def ensure_repo_exists(self):
        """Initializes git repository and seeds sample note files & board files if empty."""
        os.makedirs(self.repo_dir, exist_ok=True)
        git_folder = os.path.join(self.repo_dir, ".git")

        if not os.path.exists(git_folder):
            self._run_git(["init"])
            try:
                self._run_git(["config", "user.name", "AI Tutor Note-taker"])
                self._run_git(["config", "user.email", "aitutor@notes.local"])
            except Exception:
                pass
            
            self._seed_initial_notes_and_boards()

    def sync_boards_to_repo(self):
        """Syncs all canvas board JSON files from storage_data/boards into git_notes_repo/boards/."""
        os.makedirs(self.boards_source_dir, exist_ok=True)
        target_boards_dir = os.path.join(self.repo_dir, "boards")
        os.makedirs(target_boards_dir, exist_ok=True)

        # Seed default main board if none exists
        main_board_path = os.path.join(self.boards_source_dir, "board_main.json")
        if not os.path.exists(main_board_path):
            sample_board = {
                "board_id": "board_main",
                "title": "Main Physics & STEM Board",
                "updated_at": "2026-07-24 06:00:00",
                "items": [
                    {
                        "type": "sticky_note",
                        "x": 100, "y": 120,
                        "text": "📌 Physics Exam Prep: Superposition & Wave Functions",
                        "color": "#fff59d"
                    },
                    {
                        "type": "handwriting_note",
                        "x": 420, "y": 120,
                        "text": "E = h * nu\nlambda = h / p"
                    },
                    {
                        "type": "answer_bubble",
                        "x": 100, "y": 320,
                        "title": "STEM Answer: Quantum Tunneling",
                        "question": "What is quantum tunneling?",
                        "full_text": "Quantum tunneling occurs when a particle passes through a potential barrier higher than its kinetic energy."
                    }
                ]
            }
            with open(main_board_path, "w", encoding="utf-8") as f:
                json.dump(sample_board, f, indent=2)

        # Copy all board JSON files into git repo
        for fname in os.listdir(self.boards_source_dir):
            if fname.endswith(".json"):
                src = os.path.join(self.boards_source_dir, fname)
                dst = os.path.join(target_boards_dir, fname)
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

    def _seed_initial_notes_and_boards(self):
        """Seeds initial physics notes, calculus reference, and sample canvas board."""
        physics_file = os.path.join(self.repo_dir, "physics_quantum_notes.md")
        math_file = os.path.join(self.repo_dir, "calculus_reference.md")

        if not os.path.exists(physics_file):
            with open(physics_file, "w", encoding="utf-8") as f:
                f.write("""# Quantum Mechanics & Physics Notes

## 1. Wave-Particle Duality
Light and subatomic particles exhibit both wave-like and particle-like properties.

- **Planck-Einstein Relation**: $E = h \\nu$
- **de Broglie Wavelength**: $\\lambda = \\frac{h}{p}$

## 2. Quantum Superposition
A physical system exists partly in all its theoretical, possible states simultaneously.

```python
# Quantum State Superposition Demo
import numpy as np

psi = (1 / np.sqrt(2)) * np.array([1, 1])  # |+> State
print("State vector superposition:", psi)
```
""")

        if not os.path.exists(math_file):
            with open(math_file, "w", encoding="utf-8") as f:
                f.write("""# Calculus & STEM Derivatives Quick Guide

## Core Differentiation Rules
1. Power Rule: $\\frac{d}{dx}[x^n] = n x^{n-1}$
2. Product Rule: $\\frac{d}{dx}[u \\cdot v] = u'v + uv'$
3. Chain Rule: $\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x)$
""")

        self.sync_boards_to_repo()

        try:
            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "Initial commit: Add Quantum & Calculus notes + Main Canvas Board"])
        except Exception:
            pass

    def get_branches(self) -> List[str]:
        try:
            out = self._run_git(["branch", "--format=%(refname:short)"])
            branches = [line.strip() for line in out.split("\n") if line.strip()]
            return branches if branches else ["main"]
        except Exception:
            return ["main"]

    def get_current_branch(self) -> str:
        try:
            return self._run_git(["branch", "--show-current"]) or "main"
        except Exception:
            return "main"

    def create_branch(self, branch_name: str) -> bool:
        try:
            self._run_git(["branch", branch_name])
            return True
        except Exception:
            return False

    def switch_branch(self, branch_name: str) -> bool:
        try:
            self._run_git(["checkout", branch_name])
            return True
        except Exception:
            return False

    def get_files_status(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Parses `git status --porcelain` for both notes and board JSON files.
        """
        self.sync_boards_to_repo()
        staged = []
        unstaged = []
        all_files = set()

        for root, _, files in os.walk(self.repo_dir):
            if ".git" in root:
                continue
            for fname in files:
                rel_path = os.path.relpath(os.path.join(root, fname), self.repo_dir).replace("\\", "/")
                all_files.add(rel_path)

        try:
            out = self._run_git(["status", "--porcelain"])
            for line in out.split("\n"):
                if not line or len(line) < 3:
                    continue
                x = line[0]
                y = line[1]
                filename = line[3:].strip()

                if x != " " and x != "?":
                    staged.append({"filename": filename, "status": x, "label": self._code_to_label(x)})
                
                if y == "?" or y != " ":
                    code = "U" if y == "?" else y
                    unstaged.append({"filename": filename, "status": code, "label": self._code_to_label(code)})
        except Exception as e:
            print("Status fetch error:", e)

        return {
            "staged": staged,
            "unstaged": unstaged,
            "all_files": sorted(list(all_files))
        }

    def _code_to_label(self, code: str) -> str:
        mapping = {"M": "Modified", "A": "Added", "D": "Deleted", "U": "Untracked", "R": "Renamed"}
        return mapping.get(code, "Changed")

    def stage_file(self, filename: str):
        self._run_git(["add", filename])

    def unstage_file(self, filename: str):
        self._run_git(["reset", "HEAD", filename])

    def stage_all(self):
        self._run_git(["add", "-A"])

    def unstage_all(self):
        self._run_git(["reset"])

    def discard_changes(self, filename: str):
        try:
            self._run_git(["checkout", "--", filename])
        except Exception:
            fpath = os.path.join(self.repo_dir, filename)
            if os.path.exists(fpath):
                os.remove(fpath)

    def commit(self, message: str, amend: bool = False) -> str:
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        return self._run_git(args)

    def get_file_content(self, filename: str) -> str:
        fpath = os.path.join(self.repo_dir, filename)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save_file_content(self, filename: str, content: str):
        fpath = os.path.join(self.repo_dir, filename)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

    def create_new_note(self, filename: str) -> str:
        if not filename.endswith(".md") and not filename.endswith(".json"):
            filename += ".md"
        fpath = os.path.join(self.repo_dir, filename)
        if not os.path.exists(fpath):
            title = filename.replace(".md", "").replace("_", " ").title()
            content = f"# {title}\n\nType your study notes here...\n"
            self.save_file_content(filename, content)
        return filename

    def get_diff(self, filename: str, target: str = "HEAD") -> Dict[str, Any]:
        """Computes line diff comparing working tree against HEAD."""
        try:
            diff_text = self._run_git(["diff", target, "--", filename])
            if not diff_text:
                diff_text = self._run_git(["diff", "--staged", "--", filename])
        except Exception:
            diff_text = ""

        old_content = ""
        try:
            old_content = self._run_git(["show", f"{target}:{filename}"])
        except Exception:
            pass

        new_content = self.get_file_content(filename)

        lines = []
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        additions = 0
        deletions = 0

        import difflib
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

        old_idx = 1
        new_idx = 1

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for line in old_lines[i1:i2]:
                    lines.append({"type": "same", "text": line, "old_num": old_idx, "new_num": new_idx})
                    old_idx += 1
                    new_idx += 1
            elif tag == 'replace' or tag == 'delete':
                for line in old_lines[i1:i2]:
                    lines.append({"type": "del", "text": line, "old_num": old_idx, "new_num": ""})
                    old_idx += 1
                    deletions += 1
                if tag == 'replace':
                    for line in new_lines[j1:j2]:
                        lines.append({"type": "add", "text": line, "old_num": "", "new_num": new_idx})
                        new_idx += 1
                        additions += 1
            elif tag == 'insert':
                for line in new_lines[j1:j2]:
                    lines.append({"type": "add", "text": line, "old_num": "", "new_num": new_idx})
                    new_idx += 1
                    additions += 1

        return {
            "filename": filename,
            "additions": additions,
            "deletions": deletions,
            "lines": lines,
            "raw": diff_text
        }

    def get_commit_history(self, max_count: int = 20) -> List[Dict[str, Any]]:
        try:
            fmt = '{"hash":"%h","full_hash":"%H","author":"%an","date":"%cr","message":"%s"}'
            out = self._run_git(["log", f"-n{max_count}", f"--pretty=format:{fmt}"])
            if not out:
                return []

            commits = []
            for line in out.split("\n"):
                if line.strip():
                    try:
                        commits.append(json.loads(line.strip()))
                    except Exception:
                        pass
            return commits
        except Exception:
            return []

    def create_tag(self, tag_name: str, message: str = "") -> bool:
        try:
            args = ["tag", "-a", tag_name, "-m", message or tag_name]
            self._run_git(args)
            return True
        except Exception:
            return False

    def get_tags(self) -> List[str]:
        try:
            out = self._run_git(["tag"])
            return [line.strip() for line in out.split("\n") if line.strip()]
        except Exception:
            return []

    def sync_repo_boards_to_source(self):
        """Syncs all board JSON files from git_notes_repo/boards/ back into storage_data/boards/."""
        target_boards_dir = os.path.join(self.repo_dir, "boards")
        if not os.path.exists(target_boards_dir):
            return
        os.makedirs(self.boards_source_dir, exist_ok=True)
        for fname in os.listdir(target_boards_dir):
            if fname.endswith(".json"):
                src = os.path.join(target_boards_dir, fname)
                dst = os.path.join(self.boards_source_dir, fname)
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

    def get_commit_count(self) -> int:
        """Returns total commit count on current branch."""
        try:
            out = self._run_git(["rev-list", "--count", "HEAD"])
            return int(out.strip())
        except Exception:
            return 0

    def show_file_at_commit(self, filename: str, commit_ref: str = "HEAD") -> str:
        """Returns file text content at a specific commit/ref without checking it out."""
        clean_name = filename.replace("\\", "/")
        try:
            return self._run_git(["show", f"{commit_ref}:{clean_name}"])
        except Exception:
            return ""

    def has_uncommitted_changes(self) -> bool:
        """Checks if working tree has any uncommitted or staged changes."""
        try:
            status = self._run_git(["status", "--porcelain"])
            return bool(status.strip())
        except Exception:
            return False

    def checkout_file(self, filename: str, commit_ref: str = "HEAD") -> bool:
        """Checks out a specific file from a commit/ref into working directory."""
        clean_name = filename.replace("\\", "/")
        try:
            self._run_git(["checkout", commit_ref, "--", clean_name])
            if clean_name.startswith("boards/"):
                # Also sync back to storage_data/boards
                board_fname = os.path.basename(clean_name)
                src = os.path.join(self.repo_dir, "boards", board_fname)
                dst = os.path.join(self.boards_source_dir, board_fname)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    def restore_working_tree_to_commit(self, commit_ref: str) -> bool:
        """
        Safely checks out all tracked files from target commit into the working tree
        without changing the current branch HEAD.
        """
        try:
            self._run_git(["checkout", commit_ref, "--", "."])
            self.sync_repo_boards_to_source()
            return True
        except Exception as e:
            print(f"[GitNotesManager] Restore error: {e}")
            return False

    def get_commit_files(self, commit_ref: str) -> List[Dict[str, str]]:
        """Returns list of files modified/added/deleted in a specific commit."""
        try:
            out = self._run_git(["show", "--name-status", "--pretty=format:", commit_ref])
            files = []
            for line in out.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    status_code, fname = parts
                    files.append({
                        "status": status_code,
                        "filename": fname.replace("\\", "/"),
                        "label": self._code_to_label(status_code)
                    })
            return files
        except Exception:
            return []


# Architecture Alias: Kestrel UI -> VersionService -> GitAdapter -> Git
GitAdapter = GitNotesManager

