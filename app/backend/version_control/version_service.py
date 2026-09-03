"""
Kestrel Version Service
Domain layer providing a human-friendly, object-aware Version History abstraction
over underlying Git operations.

Architecture:
    Kestrel UI -> VersionService -> GitAdapter -> Git
"""

import os
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

from .git_notes_manager import GitNotesManager, GitAdapter, GitError


class ChangeAction(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class ObjectChange:
    """Represents a human-readable change to a specific Kestrel object."""
    category: str               # "drawing", "sticky_note", "smart_shape", "formula", "note_text", "graph", "board"
    action: ChangeAction        # ADDED, MODIFIED, DELETED
    title: str                  # Short title e.g. "Sticky Note: Mitosis"
    description: str            # Friendly description e.g. "Added diagram with 14 strokes"
    icon: str                   # FontAwesome icon name for UI presentation
    badge_color: str            # Color code for action badge


@dataclass
class VersionSnapshot:
    """A human-readable version checkpoint representing a meaningful state."""
    version_id: str             # Underlying commit SHA
    version_number: int         # Sequence number (e.g. 1, 2, 12)
    title: str                  # e.g. "Version 12"
    description: str            # e.g. "Completed mitosis diagram"
    author: str                 # Author name
    created_at: datetime        # Timestamp
    relative_time: str          # e.g. "Today, 8:42 PM", "Yesterday, 3:15 PM"
    changes_count: int          # e.g. 3
    changes_summary: str        # e.g. "3 changes"
    object_changes: List[ObjectChange] = field(default_factory=list)
    is_backup: bool = False     # True if automatically created before a restore
    commit_hash: str = ""       # Short SHA for developer mode


@dataclass
class VersionDiff:
    """Object-level and line-level comparison between two versions."""
    filename: str
    object_changes: List[ObjectChange]
    line_additions: int
    line_deletions: int
    raw_diff: str
    lines: List[Dict[str, Any]] = field(default_factory=list)


class ObjectDiffEngine:
    """
    Analyzes differences between JSON canvas boards or Markdown study notes
    and translates them into high-level Kestrel object descriptions.
    """

    @staticmethod
    def diff_board_json(old_json_str: str, new_json_str: str, board_name: str = "Canvas Board") -> List[ObjectChange]:
        """Detects added, modified, and removed Kestrel items from board JSON."""
        changes: List[ObjectChange] = []

        try:
            old_data = json.loads(old_json_str) if old_json_str.strip() else {}
        except Exception:
            old_data = {}

        try:
            new_data = json.loads(new_json_str) if new_json_str.strip() else {}
        except Exception:
            new_data = {}

        old_items = old_data.get("items", [])
        new_items = new_data.get("items", [])

        # Categorize items by type
        def categorize_items(items):
            grouped = {
                "sticky_note": [],
                "handwriting_note": [],
                "answer_bubble": [],
                "smart_shape": [],
                "ink_stroke": [],
                "graph_card": [],
                "card": [],
                "table": [],
                "text_box": [],
                "other": []
            }
            for it in items:
                t = it.get("type", "other")
                if t in grouped:
                    grouped[t].append(it)
                else:
                    grouped["other"].append(it)
            return grouped

        old_grp = categorize_items(old_items)
        new_grp = categorize_items(new_items)

        # 1. Ink Drawing Strokes
        old_strokes = len(old_grp["ink_stroke"])
        new_strokes = len(new_grp["ink_stroke"])
        stroke_diff = new_strokes - old_strokes
        if stroke_diff > 0:
            changes.append(ObjectChange(
                category="drawing",
                action=ChangeAction.ADDED,
                title="Drawing Strokes",
                description=f"Added {stroke_diff} ink stroke{'s' if stroke_diff != 1 else ''}",
                icon="fa5s.paint-brush",
                badge_color="#28a745"
            ))
        elif stroke_diff < 0:
            changes.append(ObjectChange(
                category="drawing",
                action=ChangeAction.DELETED,
                title="Drawing Strokes",
                description=f"Erased {abs(stroke_diff)} ink stroke{'s' if abs(stroke_diff) != 1 else ''}",
                icon="fa5s.eraser",
                badge_color="#d32f2f"
            ))

        # 2. Sticky Notes
        old_notes = {it.get("text", ""): it for it in old_grp["sticky_note"] if it.get("text")}
        new_notes = {it.get("text", ""): it for it in new_grp["sticky_note"] if it.get("text")}
        for text in new_notes:
            if text not in old_notes:
                snippet = text[:40] + ("..." if len(text) > 40 else "")
                changes.append(ObjectChange(
                    category="sticky_note",
                    action=ChangeAction.ADDED,
                    title="Sticky Note",
                    description=f"Added sticky note: \"{snippet}\"",
                    icon="fa5s.sticky-note",
                    badge_color="#28a745"
                ))
        for text in old_notes:
            if text not in new_notes:
                snippet = text[:40] + ("..." if len(text) > 40 else "")
                changes.append(ObjectChange(
                    category="sticky_note",
                    action=ChangeAction.DELETED,
                    title="Sticky Note",
                    description=f"Removed sticky note: \"{snippet}\"",
                    icon="fa5s.sticky-note",
                    badge_color="#d32f2f"
                ))

        # 3. Formulas and Handwriting
        old_formulas = len(old_grp["handwriting_note"])
        new_formulas = len(new_grp["handwriting_note"])
        if new_formulas > old_formulas:
            changes.append(ObjectChange(
                category="formula",
                action=ChangeAction.ADDED,
                title="Math Formula",
                description=f"Added {new_formulas - old_formulas} formula card{'s' if new_formulas - old_formulas != 1 else ''}",
                icon="fa5s.square-root-alt",
                badge_color="#007aff"
            ))
        elif new_formulas < old_formulas:
            changes.append(ObjectChange(
                category="formula",
                action=ChangeAction.DELETED,
                title="Math Formula",
                description=f"Removed {old_formulas - new_formulas} formula card{'s' if old_formulas - new_formulas != 1 else ''}",
                icon="fa5s.square-root-alt",
                badge_color="#d32f2f"
            ))

        # 4. Smart Shapes & Diagrams
        old_shapes = len(old_grp["smart_shape"])
        new_shapes = len(new_grp["smart_shape"])
        if new_shapes > old_shapes:
            changes.append(ObjectChange(
                category="smart_shape",
                action=ChangeAction.ADDED,
                title="Diagram Shapes",
                description=f"Added {new_shapes - old_shapes} geometric shape{'s' if new_shapes - old_shapes != 1 else ''}",
                icon="fa5s.shapes",
                badge_color="#28a745"
            ))
        elif new_shapes < old_shapes:
            changes.append(ObjectChange(
                category="smart_shape",
                action=ChangeAction.DELETED,
                title="Diagram Shapes",
                description=f"Removed {old_shapes - new_shapes} geometric shape{'s' if old_shapes - new_shapes != 1 else ''}",
                icon="fa5s.shapes",
                badge_color="#d32f2f"
            ))

        # 5. Answer Bubbles / STEM Questions
        old_answers = len(old_grp["answer_bubble"])
        new_answers = len(new_grp["answer_bubble"])
        if new_answers > old_answers:
            changes.append(ObjectChange(
                category="answer_bubble",
                action=ChangeAction.ADDED,
                title="Answer Card",
                description="Added solved STEM explanation card",
                icon="fa5s.comment-alt",
                badge_color="#7c3aed"
            ))

        # If total items changed but no specific category caught it
        if not changes and len(old_items) != len(new_items):
            diff = len(new_items) - len(old_items)
            changes.append(ObjectChange(
                category="board",
                action=ChangeAction.MODIFIED if diff == 0 else (ChangeAction.ADDED if diff > 0 else ChangeAction.DELETED),
                title="Canvas Elements",
                description=f"{'Added' if diff > 0 else 'Removed'} {abs(diff)} canvas element{'s' if abs(diff) != 1 else ''}",
                icon="fa5s.th-large",
                badge_color="#007aff"
            ))
        elif not changes and old_items and new_items and old_items != new_items:
            changes.append(ObjectChange(
                category="board",
                action=ChangeAction.MODIFIED,
                title="Canvas Layout",
                description="Updated position or properties of canvas items",
                icon="fa5s.edit",
                badge_color="#ff9500"
            ))

        return changes

    @staticmethod
    def diff_markdown(old_text: str, new_text: str, filename: str) -> List[ObjectChange]:
        """Detects meaningful changes to Markdown study notes."""
        changes: List[ObjectChange] = []
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        # Extract headings (# Section)
        old_headings = set(re.findall(r'^#+\s+(.+)$', old_text, re.MULTILINE))
        new_headings = set(re.findall(r'^#+\s+(.+)$', new_text, re.MULTILINE))

        added_headings = new_headings - old_headings
        removed_headings = old_headings - new_headings

        for h in added_headings:
            changes.append(ObjectChange(
                category="note_text",
                action=ChangeAction.ADDED,
                title="Study Note Section",
                description=f"Added section: \"{h}\"",
                icon="fa5s.file-alt",
                badge_color="#28a745"
            ))

        for h in removed_headings:
            changes.append(ObjectChange(
                category="note_text",
                action=ChangeAction.DELETED,
                title="Study Note Section",
                description=f"Removed section: \"{h}\"",
                icon="fa5s.file-alt",
                badge_color="#d32f2f"
            ))

        line_diff = len(new_lines) - len(old_lines)
        if not changes and (old_text != new_text):
            changes.append(ObjectChange(
                category="note_text",
                action=ChangeAction.MODIFIED,
                title="Note Content",
                description=f"Updated note ({'+' if line_diff >= 0 else ''}{line_diff} lines)",
                icon="fa5s.edit",
                badge_color="#007aff"
            ))

        return changes


class VersionService:
    """
    High-level version history service for Kestrel.
    Encapsulates all Git operations and presents clean, human-readable snapshots.
    """

    def __init__(self, adapter: Optional[GitAdapter] = None):
        self.adapter = adapter or GitAdapter()
        self.diff_engine = ObjectDiffEngine()

    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """Formats a datetime into a friendly relative timestamp."""
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            mins = seconds // 60
            return f"{mins} min{'s' if mins != 1 else ''} ago"

        local_dt = dt.astimezone()
        local_now = now.astimezone()

        if local_dt.date() == local_now.date():
            return f"Today, {local_dt.strftime('%I:%M %p').lstrip('0')}"
        if (local_now.date() - local_dt.date()).days == 1:
            return f"Yesterday, {local_dt.strftime('%I:%M %p').lstrip('0')}"
        if (local_now.date() - local_dt.date()).days < 7:
            return local_dt.strftime("%A, %I:%M %p").lstrip('0')

        return local_dt.strftime("%b %d, %Y, %I:%M %p").lstrip('0')

    def save_version(self, description: str = "", notebook_id: Optional[str] = None) -> VersionSnapshot:
        """
        Creates a meaningful recoverable version checkpoint.
        Automatically assigns the next version sequence number and computes
        an object-aware description if none was provided.
        """
        # 1. Sync live canvas boards into Git repository
        self.adapter.sync_boards_to_repo()

        # 2. Check if there are changes
        status = self.adapter.get_files_status()
        if not status["staged"] and not status["unstaged"]:
            # Nothing to commit; return latest snapshot
            history = self.get_version_history(limit=1)
            if history:
                return history[0]

        # 3. Stage all modifications
        self.adapter.stage_all()

        # 4. Compute next version number
        count = self.adapter.get_commit_count()
        next_version_num = count + 1

        # 5. Format description
        desc = description.strip()
        if not desc:
            # Auto-generate a friendly summary from pending changes
            pending = self.get_pending_changes()
            if pending:
                desc = pending[0].description
            else:
                desc = "Saved study changes"

        # Structured commit message: "[Version N] Description"
        commit_msg = f"[Version {next_version_num}] {desc}"
        if notebook_id:
            commit_msg += f" (notebook:{notebook_id})"

        self.adapter.commit(commit_msg)

        # Sync back to ensure consistency
        self.adapter.sync_boards_to_repo()

        history = self.get_version_history(limit=1)
        if history:
            return history[0]

        return VersionSnapshot(
            version_id="HEAD",
            version_number=next_version_num,
            title=f"Version {next_version_num}",
            description=desc,
            author="You",
            created_at=datetime.now(timezone.utc),
            relative_time="Just now",
            changes_count=1,
            changes_summary="1 change",
            commit_hash="latest"
        )

    def get_version_history(self, notebook_id: Optional[str] = None, limit: int = 50) -> List[VersionSnapshot]:
        """
        Returns a list of human-readable version snapshots with sequence numbers,
        descriptions, and object change summaries.
        """
        commits = self.adapter.get_commit_history(max_count=limit)
        snapshots: List[VersionSnapshot] = []

        total_commits = len(commits)

        for i, c in enumerate(commits):
            msg = c.get("message", "")
            commit_hash = c.get("hash", "")
            full_hash = c.get("full_hash", commit_hash)

            # Check if this version targets a specific notebook
            if notebook_id and f"notebook:{notebook_id}" not in msg:
                # Still check if the commit actually touched files for this notebook
                commit_files = self.adapter.get_commit_files(commit_hash)
                touched = any(notebook_id in f.get("filename", "") for f in commit_files)
                if not touched and f"notebook:" in msg:
                    continue

            # Parse Version Number and Description
            v_match = re.match(r'^\[Version\s+(\d+)\]\s*(.*)$', msg, re.IGNORECASE)
            is_backup = "pre-restore backup" in msg.lower() or "safe backup" in msg.lower()

            if v_match:
                version_num = int(v_match.group(1))
                desc = v_match.group(2).split("(notebook:")[0].strip()
            else:
                version_num = total_commits - i
                desc = msg.split("(notebook:")[0].strip() or "Saved study notes"

            # Parse date
            raw_date = c.get("date", "")
            # Git %cr is relative (e.g. "2 hours ago"), %H is full hash
            # If relative, use as-is or format
            rel_time = raw_date if raw_date else "Recently"

            # Discover object changes for this snapshot
            commit_files = self.adapter.get_commit_files(commit_hash)
            changes_count = len(commit_files) if commit_files else 1
            changes_summary = f"{changes_count} change{'s' if changes_count != 1 else ''}"

            title = f"Version {version_num}"
            if is_backup:
                title = f"Backup ({title})"

            snapshots.append(VersionSnapshot(
                version_id=full_hash,
                version_number=version_num,
                title=title,
                description=desc,
                author=c.get("author", "You"),
                created_at=datetime.now(timezone.utc),
                relative_time=rel_time,
                changes_count=changes_count,
                changes_summary=changes_summary,
                is_backup=is_backup,
                commit_hash=commit_hash
            ))

        return snapshots

    def get_pending_changes(self) -> List[ObjectChange]:
        """Returns object-level descriptions of all currently uncommitted changes."""
        self.adapter.sync_boards_to_repo()
        status = self.adapter.get_files_status()
        all_changed = set()

        for it in status.get("staged", []):
            all_changed.add(it["filename"])
        for it in status.get("unstaged", []):
            all_changed.add(it["filename"])

        changes: List[ObjectChange] = []

        for fname in all_changed:
            diff_obj = self.compare_file_with_head(fname)
            changes.extend(diff_obj.object_changes)

        return changes

    def compare_file_with_head(self, filename: str) -> VersionDiff:
        """Compares the current working file against HEAD."""
        clean_name = filename.replace("\\", "/")
        old_content = self.adapter.show_file_at_commit(clean_name, "HEAD")
        new_content = self.adapter.get_file_content(clean_name)

        raw_diff_info = self.adapter.get_diff(clean_name, "HEAD")

        if clean_name.endswith(".json"):
            obj_changes = self.diff_engine.diff_board_json(old_content, new_content, clean_name)
        elif clean_name.endswith(".md"):
            obj_changes = self.diff_engine.diff_markdown(old_content, new_content, clean_name)
        else:
            obj_changes = [ObjectChange(
                category="file",
                action=ChangeAction.MODIFIED,
                title=clean_name,
                description="File modified",
                icon="fa5s.file",
                badge_color="#007aff"
            )]

        return VersionDiff(
            filename=clean_name,
            object_changes=obj_changes,
            line_additions=raw_diff_info.get("additions", 0),
            line_deletions=raw_diff_info.get("deletions", 0),
            raw_diff=raw_diff_info.get("raw", ""),
            lines=raw_diff_info.get("lines", [])
        )

    def restore_version(self, version_ref: str, create_backup: bool = True) -> Dict[str, Any]:
        """
        Non-destructively restores all files to an earlier version checkpoint.
        Automatically creates a pre-restore backup version first if uncommitted
        changes or modifications exist.
        """
        # 1. Sync live boards to ensure current state is captured
        self.adapter.sync_boards_to_repo()

        # 2. Non-destructive safety check: save a backup version first
        backup_snapshot = None
        if create_backup:
            try:
                if self.adapter.has_uncommitted_changes():
                    backup_snapshot = self.save_version(
                        description=f"Pre-restore backup (before restoring to {version_ref[:8]})"
                    )
                else:
                    # Create an explicit backup checkpoint commit so user can return to pre-restore state
                    count = self.adapter.get_commit_count()
                    next_version_num = count + 1
                    msg = f"[Version {next_version_num}] Pre-restore backup (before restoring to {version_ref[:8]})"
                    self.adapter._run_git(["commit", "--allow-empty", "-m", msg])
                    history = self.get_version_history(limit=1)
                    if history:
                        backup_snapshot = history[0]
            except Exception as e:
                print(f"[VersionService] Backup warning: {e}")

        # 3. Restore all tracked files from the specified version ref
        success = self.adapter.restore_working_tree_to_commit(version_ref)
        if not success:
            raise GitError(
                f"Could not restore Version '{version_ref}'. The requested snapshot might not be available.",
                technical_details=f"restore_working_tree_to_commit failed for ref {version_ref}"
            )

        # 4. Sync restored boards from repo back into live storage_data/boards
        self.adapter.sync_repo_boards_to_source()

        return {
            "status": "restored",
            "version_ref": version_ref,
            "backup_version": backup_snapshot.title if backup_snapshot else None,
            "message": "Version successfully restored. Your previous state was safely backed up."
        }

    def create_copy(self, version_ref: str, new_name: str) -> str:
        """
        Creates a named copy (branch) starting from a specific version snapshot.
        """
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', new_name.strip())
        if not clean_name:
            clean_name = f"copy_{version_ref[:7]}"

        # Check out branch from ref
        try:
            self.adapter._run_git(["branch", clean_name, version_ref])
            return clean_name
        except Exception as e:
            raise GitError(f"Could not create copy '{new_name}': {e}")
