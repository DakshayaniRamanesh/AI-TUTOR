"""
Unit and integration tests for Kestrel Version History system.
Tests GitAdapter, ObjectDiffEngine, and VersionService for:
  - Version creation and auto-incrementing version numbers
  - Object-level visual diffing of canvas boards and markdown notes
  - Non-destructive safe restoration (pre-restore backup snapshot)
  - Copy creation (branching)
  - Error translation
"""

import os
import json
import shutil
import tempfile
import pytest

from app.backend.version_control.git_notes_manager import GitNotesManager, GitAdapter, GitError
from app.backend.version_control.version_service import (
    VersionService, ObjectDiffEngine, ObjectChange, ChangeAction, VersionSnapshot
)


@pytest.fixture
def temp_repo():
    """Provides an isolated temporary repository environment for testing."""
    tmp_dir = tempfile.mkdtemp(prefix="kestrel_test_repo_")
    repo_dir = os.path.join(tmp_dir, "git_notes_repo")
    boards_dir = os.path.join(tmp_dir, "boards")
    os.makedirs(repo_dir, exist_ok=True)
    os.makedirs(boards_dir, exist_ok=True)

    adapter = GitAdapter(repo_dir=repo_dir)
    adapter.boards_source_dir = boards_dir
    adapter.ensure_repo_exists()

    service = VersionService(adapter=adapter)

    yield {
        "tmp_dir": tmp_dir,
        "repo_dir": repo_dir,
        "boards_dir": boards_dir,
        "adapter": adapter,
        "service": service
    }

    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestGitAdapter:
    def test_repo_initialization(self, temp_repo):
        adapter = temp_repo["adapter"]
        assert os.path.exists(os.path.join(temp_repo["repo_dir"], ".git"))
        assert adapter.get_current_branch() in ["main", "master"]
        assert adapter.get_commit_count() >= 1

    def test_save_and_commit(self, temp_repo):
        adapter = temp_repo["adapter"]
        adapter.save_file_content("test_note.md", "# Test Note\nHello Kestrel\n")
        adapter.stage_all()
        res = adapter.commit("Add test note")
        assert "test note" in res or res != ""
        assert adapter.get_file_content("test_note.md") == "# Test Note\nHello Kestrel\n"

    def test_git_error_translation(self, temp_repo):
        adapter = temp_repo["adapter"]
        with pytest.raises(GitError) as exc_info:
            adapter._run_git(["checkout", "non_existent_branch_xyz"])
        assert "failed" in str(exc_info.value).lower() or "not match" in str(exc_info.value).lower()


class TestObjectDiffEngine:
    def test_diff_board_json_strokes(self):
        old_board = json.dumps({"items": []})
        new_board = json.dumps({
            "items": [
                {"type": "ink_stroke", "points": [[0, 0], [1, 1]]},
                {"type": "ink_stroke", "points": [[2, 2], [3, 3]]},
                {"type": "ink_stroke", "points": [[4, 4], [5, 5]]}
            ]
        })
        changes = ObjectDiffEngine.diff_board_json(old_board, new_board)
        assert len(changes) >= 1
        stroke_change = next((c for c in changes if c.category == "drawing"), None)
        assert stroke_change is not None
        assert stroke_change.action == ChangeAction.ADDED
        assert "3 ink strokes" in stroke_change.description

    def test_diff_board_json_sticky_note(self):
        old_board = json.dumps({"items": []})
        new_board = json.dumps({
            "items": [
                {"type": "sticky_note", "text": "Remember photosynthesis formula", "color": "#fff59d"}
            ]
        })
        changes = ObjectDiffEngine.diff_board_json(old_board, new_board)
        note_change = next((c for c in changes if c.category == "sticky_note"), None)
        assert note_change is not None
        assert note_change.action == ChangeAction.ADDED
        assert "photosynthesis" in note_change.description

    def test_diff_board_json_smart_shapes(self):
        old_board = json.dumps({"items": []})
        new_board = json.dumps({
            "items": [
                {"type": "smart_shape", "shape_type": "circle"},
                {"type": "smart_shape", "shape_type": "rectangle"}
            ]
        })
        changes = ObjectDiffEngine.diff_board_json(old_board, new_board)
        shape_change = next((c for c in changes if c.category == "smart_shape"), None)
        assert shape_change is not None
        assert "2 geometric shapes" in shape_change.description

    def test_diff_markdown_headings(self):
        old_md = "# Biology Notes\n\nIntroduction to cells.\n"
        new_md = "# Biology Notes\n\nIntroduction to cells.\n\n## Cell Membrane\nLipid bilayer structure.\n"
        changes = ObjectDiffEngine.diff_markdown(old_md, new_md, "biology.md")
        assert len(changes) >= 1
        heading_change = next((c for c in changes if c.category == "note_text"), None)
        assert heading_change is not None
        assert "Cell Membrane" in heading_change.description


class TestVersionService:
    def test_save_version_increments_version_number(self, temp_repo):
        service = temp_repo["service"]
        adapter = temp_repo["adapter"]

        # Create changes
        adapter.save_file_content("biology_cell.md", "# Cell Biology\nMitosis notes.\n")

        v1 = service.save_version("Completed cell overview")
        assert v1.version_number >= 1
        assert "Completed cell overview" in v1.description

        # Create further changes
        adapter.save_file_content("biology_cell.md", "# Cell Biology\nMitosis notes.\n## Prophase\nChromosomes condense.\n")
        v2 = service.save_version("Added prophase details")
        assert v2.version_number > v1.version_number
        assert "Added prophase details" in v2.description

    def test_get_version_history(self, temp_repo):
        service = temp_repo["service"]
        adapter = temp_repo["adapter"]

        adapter.save_file_content("calculus.md", "# Calculus\nLimits and continuity.\n")
        service.save_version("Added limits notes")

        history = service.get_version_history()
        assert len(history) >= 2
        latest = history[0]
        assert "limits" in latest.description.lower()
        assert latest.relative_time != ""

    def test_non_destructive_restore(self, temp_repo):
        service = temp_repo["service"]
        adapter = temp_repo["adapter"]

        # 1. State 1: Version A
        adapter.save_file_content("experiment.md", "State A: Initial experiment setup")
        snap_a = service.save_version("Version A: Setup")

        # 2. State 2: Version B
        adapter.save_file_content("experiment.md", "State B: Altered parameters with new results")
        snap_b = service.save_version("Version B: New results")

        assert adapter.get_file_content("experiment.md") == "State B: Altered parameters with new results"

        # 3. Restore to Version A
        res = service.restore_version(snap_a.version_id, create_backup=True)
        assert res["status"] == "restored"

        # Content is restored to State A
        restored_content = adapter.get_file_content("experiment.md")
        assert restored_content == "State A: Initial experiment setup"

        # Verify a safety backup checkpoint was created before restoring
        history = service.get_version_history()
        backup_versions = [s for s in history if s.is_backup or "backup" in s.title.lower() or "backup" in s.description.lower()]
        assert len(backup_versions) >= 1

    def test_create_copy(self, temp_repo):
        service = temp_repo["service"]
        adapter = temp_repo["adapter"]

        adapter.save_file_content("formula.md", "E = mc^2")
        snap = service.save_version("Base formula")

        copy_name = service.create_copy(snap.version_id, "relativity_branch")
        assert copy_name == "relativity_branch"
        assert copy_name in adapter.get_branches()
