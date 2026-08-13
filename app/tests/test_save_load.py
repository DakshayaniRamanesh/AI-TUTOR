"""
test_save_load.py
=================
Comprehensive tests for the notebook save / autosave system.

Coverage
--------
A. Round-trip serialization  : to_dict() -> create_item_from_dict() for every item class.
B. Autosave debounce flow    : scene_changed -> timer fires after delay -> disk written.
C. Manual Save button flow   : load notebook -> edit -> save -> reload -> edits present.
D. Unknown-type fallback     : unrecognized itype logs warning and returns None (no silent drop).

Run with:
    cd "d:\\ai tutor"
    python -m pytest app/tests/test_save_load.py -v
"""

import os
import json
import sys
import pytest

# ---------------------------------------------------------------------------
# PyQt6 application fixture (required for any Qt object instantiation)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def qt_app():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def scene(qt_app):
    from app.ui.canvas_scene import CanvasScene
    s = CanvasScene()
    yield s
    # Cleanup: clear scene to avoid dangling Qt objects
    try:
        s.clear()
    except Exception:
        pass


# ===========================================================================
# A. Round-trip serialization tests
# ===========================================================================

class TestRoundTripSerialization:
    """Each test: construct an item, call to_dict(), feed the dict back into
    create_item_from_dict(), verify the restored item has correct attributes.
    """

    def test_smartshape_rectangle(self, scene, qt_app):
        """SmartShapeItem (rectangle) round-trips with correct dimensions."""
        from app.ui.items.smart_shape_item import SmartShapeItem
        from PyQt6.QtGui import QPen, QColor
        pen = QPen(QColor("#ff0000"), 2.0)
        item = SmartShapeItem(shape_type="rectangle",
                              fit_data={"bbox": (10, 20, 120, 80)}, pen=pen)
        d = item.to_dict()
        assert d["type"] == "SmartShapeItem"
        assert d["stroke_type"] == "rectangle"

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.stroke_type == "rectangle"
        dims = restored.dimensions_px
        assert pytest.approx(dims.get("width", 0), abs=1) == 120
        assert pytest.approx(dims.get("height", 0), abs=1) == 80

    def test_smartshape_triangle_and_ngon(self, scene, qt_app):
        """SmartShapeItem (triangle) round-trips with num_sides, and editing num_sides updates geometry."""
        from app.ui.items.smart_shape_item import SmartShapeItem
        from PyQt6.QtGui import QPen, QColor
        pen = QPen(QColor("#00ff00"), 2.0)
        item = SmartShapeItem(shape_type="triangle",
                              fit_data={"bbox": (0, 0, 100, 100)}, pen=pen)
        assert item.dimensions_px["num_sides"] == 3.0

        # Change sides to 5 (pentagon)
        item.set_dimensions_px({"num_sides": 5.0})
        assert item.dimensions_px["num_sides"] == 5.0

        d = item.to_dict()
        assert d["type"] == "SmartShapeItem"
        assert d["stroke_type"] == "triangle"
        assert d["dimensions_px"]["num_sides"] == 5.0

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.stroke_type == "triangle"
        assert restored.dimensions_px["num_sides"] == 5.0

    def test_math_ruled_background_persistence(self, scene, qt_app):
        """Background mode 'math_ruled' persists through to_dict_list / load_from_dict_list."""
        scene.set_background_mode("math_ruled")
        assert scene.background_mode == "math_ruled"

        dict_list = scene.to_dict_list()
        assert dict_list[0]["type"] == "_canvas_meta"
        assert dict_list[0]["background_mode"] == "math_ruled"

        # Load into fresh scene
        from app.ui.canvas_scene import CanvasScene
        new_scene = CanvasScene()
        new_scene.load_from_dict_list(dict_list)
        assert new_scene.background_mode == "math_ruled"

    def test_ink_stroke_roundtrip(self, scene, qt_app):
        """InkStroke round-trips path elements (key fix: 'elements' not 'path_elements')."""
        from app.ui.items.ink_stroke import InkStroke
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(50, 30)
        path.lineTo(100, 10)
        item = InkStroke(path=path, tool_mode="pen", color="#1c1c1e", width=3.0)
        d = item.to_dict()

        # to_dict() must use key 'elements' (the fixed key that load now reads)
        assert "elements" in d, "to_dict() must use key 'elements', not 'path_elements'"
        assert d["type"] == "InkStroke"
        assert len(d["elements"]) == 3  # moveTo + 2 lineTo

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.path().elementCount() == 3
        assert restored.tool_mode == "pen"

    def test_ink_stroke_color_preserved(self, scene, qt_app):
        """InkStroke color survives round-trip (HexArgb format compatibility)."""
        from app.ui.items.ink_stroke import InkStroke
        from PyQt6.QtGui import QPainterPath, QColor
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(10, 10)
        item = InkStroke(path=path, tool_mode="pen", color="#3b82f6", width=2.0)
        d = item.to_dict()
        restored_color = QColor(d["color"])
        assert restored_color.isValid()
        # Blue component should be dominant
        assert restored_color.blue() > restored_color.red()

    def test_sticky_note_roundtrip(self, scene, qt_app):
        """StickyNote preserves text, color_key, and is_minimized state."""
        from app.ui.items.sticky_note import StickyNote
        item = StickyNote(text="Hello pytest!", color_key="blue")
        item.widget._toggle_minimize()
        assert item.widget.is_minimized is True

        d = item.to_dict()
        assert d["type"] == "StickyNote"
        assert d["text"] == "Hello pytest!"
        assert d["color_key"] == "blue"
        assert d["is_minimized"] is True

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.widget.text_edit.toPlainText() == "Hello pytest!"
        assert restored.widget.color_key == "blue"
        assert restored.widget.is_minimized is True

    def test_handwriting_note_roundtrip(self, scene, qt_app):
        """HandwritingNote preserves text content."""
        from app.ui.items.handwriting_note import HandwritingNote
        item = HandwritingNote(text="Integration notes from lecture.")
        d = item.to_dict()
        assert d["type"] == "HandwritingNote"
        assert d["text"] == "Integration notes from lecture."

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.widget.text_edit.toPlainText() == "Integration notes from lecture."

    def test_table_item_roundtrip(self, scene, qt_app):
        """TableItem preserves headers and cell content."""
        from app.ui.items.table_item import TableItem
        headers = ["Subject", "Grade", "Credits"]
        rows = [["Math", "A", "4"], ["Physics", "B+", "3"]]
        item = TableItem(headers=headers, rows=rows)
        d = item.to_dict()
        assert d["type"] == "TableItem"
        assert d["headers"] == headers
        assert d["rows"] == rows

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        tbl = restored.container.table
        assert tbl.columnCount() == 3
        assert tbl.rowCount() == 2
        assert tbl.horizontalHeaderItem(0).text() == "Subject"
        assert tbl.item(0, 1).text() == "A"

    def test_card_item_roundtrip(self, scene, qt_app):
        """CardItem round-trips title, subtitle, source_url (field name fix)."""
        from app.ui.items.card_item import CardItem
        item = CardItem(title="Nature Article", subtitle="A study of ecosystems",
                        source_url="https://nature.com/article")
        d = item.to_dict()
        assert d["type"] == "CardItem"
        # Key must be 'subtitle' (NOT 'content') to match the load branch
        assert "subtitle" in d, "to_dict() must serialize as 'subtitle' not 'content'"
        assert d["subtitle"] == "A study of ecosystems"
        assert d["source_url"] == "https://nature.com/article"

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.card.lbl_title.text() == "Nature Article"
        assert restored.card.lbl_sub.text() == "A study of ecosystems"

    def test_answer_bubble_roundtrip(self, scene, qt_app):
        """AnswerBubble preserves question, full_text, hints, and is_direct_math."""
        from app.ui.items.answer_bubble import AnswerBubble
        item = AnswerBubble(
            question="What is the integral of x^2?",
            full_text="x^3/3 + C",
            hints="Use power rule.",
            is_direct_math=True
        )
        d = item.to_dict()
        assert d["type"] == "AnswerBubble"
        assert d["question"] == "What is the integral of x^2?"
        assert d["full_text"] == "x^3/3 + C"
        assert d["hints"] == "Use power rule."
        assert d["is_direct_math"] is True

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.bubble.question == "What is the integral of x^2?"
        assert restored.bubble.full_solution == "x^3/3 + C"
        assert restored.bubble.hints == "Use power rule."
        assert restored.bubble.is_direct_math is True

    def test_map_pin_card_roundtrip(self, scene, qt_app):
        """MapPinCard now has a load branch -- was previously missing entirely."""
        from app.ui.items.map_pin_card import MapPinCard
        item = MapPinCard(title="MIT Campus", address="77 Massachusetts Ave, Cambridge, MA")
        d = item.to_dict()
        assert d["type"] == "MapPinCard"

        restored = scene.create_item_from_dict(d)
        assert restored is not None, (
            "MapPinCard must have a load branch -- was missing before this fix."
        )

    def test_group_selection_roundtrip(self, scene, qt_app):
        """GroupSelection restores title and is_collapsed state."""
        from app.ui.items.group_selection import GroupSelection
        item = GroupSelection(title="Calculus Notes")
        item.group_widget._toggle_collapse()
        assert item.group_widget.is_collapsed is True

        d = item.to_dict()
        assert d["type"] == "GroupSelection"
        assert "Calculus Notes" in d["title"]
        assert d["is_collapsed"] is True

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.group_widget.is_collapsed is True

    def test_image_item_roundtrip(self, scene, qt_app):
        """ImageItem round-trips via base64 with correct key ('image_b64') and scale."""
        from app.ui.items.image_item import ImageItem
        from PyQt6.QtGui import QPixmap, QColor
        pixmap = QPixmap(20, 20)
        pixmap.fill(QColor("#ff0000"))
        item = ImageItem(pixmap)
        item.setScale(0.75)

        d = item.to_dict()
        assert d["type"] == "ImageItem"
        assert "image_b64" in d, "ImageItem.to_dict() must use key 'image_b64'"
        assert d["scale"] == pytest.approx(0.75, abs=0.01)

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert not restored.pixmap().isNull()
        assert restored.scale() == pytest.approx(0.75, abs=0.01)

    def test_video_float_item_roundtrip(self, scene, qt_app):
        """VideoFloatItem preserves job_id, title, video_path."""
        from app.ui.items.video_float_item import VideoFloatItem
        item = VideoFloatItem(job_id="job_abc123", title="Calc Lesson",
                              video_url_or_path="/media/calc.mp4")
        d = item.to_dict()
        assert d["type"] == "VideoFloatItem"
        assert d["job_id"] == "job_abc123"
        assert d["video_path"] == "/media/calc.mp4"

        restored = scene.create_item_from_dict(d)
        assert restored is not None
        assert restored.player_widget.job_id == "job_abc123"
        assert restored.player_widget.title == "Calc Lesson"


# ===========================================================================
# B. Autosave debounce simulation
# ===========================================================================

class TestAutosaveDebounce:
    """Tests that scene_changed -> timer -> disk write chain works correctly."""

    def test_autosave_fires_after_delay(self, qt_app, tmp_path, monkeypatch):
        """
        Simulates: create notebook -> emit scene_changed ->
        advance timer -> verify file on disk has updated items list.
        """
        from app.storage.notebook_storage import NotebookStorage

        tmp_boards = tmp_path / "boards"
        tmp_boards.mkdir()
        tmp_index = tmp_path / "notebooks_index.json"

        monkeypatch.setattr("app.storage.notebook_storage.BOARDS_DIR", str(tmp_boards))
        monkeypatch.setattr("app.storage.notebook_storage.INDEX_FILE", str(tmp_index))

        meta = NotebookStorage.create_notebook("Autosave Test NB")
        nb_id = meta["id"]

        from app.ui.canvas_scene import CanvasScene
        from app.ui.items.sticky_note import StickyNote
        from PyQt6.QtCore import QTimer, QEventLoop

        s = CanvasScene()
        autosave_fired = []

        def do_save():
            items_data = s.to_dict_list()
            NotebookStorage.save_notebook(nb_id, "Autosave Test NB", items_data)
            autosave_fired.append(True)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(do_save)
        s.scene_changed.connect(lambda: timer.start(50))

        # Add note and emit scene_changed
        note = StickyNote(text="autosaved content", color_key="green")
        s.addItem(note)
        s.scene_changed.emit()

        # Process events until timer fires
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()

        assert len(autosave_fired) > 0, "Autosave timer did not fire"

        board_file = tmp_boards / f"{nb_id}.json"
        assert board_file.exists(), "Board file not found after autosave"

        saved = json.loads(board_file.read_text(encoding="utf-8"))
        real_items = [i for i in saved["items"] if i.get("type") != "_canvas_meta"]
        assert len(real_items) == 1
        assert real_items[0]["type"] == "StickyNote"
        assert real_items[0]["text"] == "autosaved content"

    def test_debounce_collapses_rapid_changes(self, qt_app, tmp_path, monkeypatch):
        """
        Multiple rapid scene_changed emissions should produce only ONE disk write
        (the debounce timer is reset each time, not stacked).
        """
        from app.storage.notebook_storage import NotebookStorage

        tmp_boards = tmp_path / "boards"
        tmp_boards.mkdir()
        tmp_index = tmp_path / "notebooks_index.json"
        monkeypatch.setattr("app.storage.notebook_storage.BOARDS_DIR", str(tmp_boards))
        monkeypatch.setattr("app.storage.notebook_storage.INDEX_FILE", str(tmp_index))

        meta = NotebookStorage.create_notebook("Debounce Test")
        nb_id = meta["id"]

        from app.ui.canvas_scene import CanvasScene
        from PyQt6.QtCore import QTimer, QEventLoop

        s = CanvasScene()
        save_count = [0]

        def do_save():
            NotebookStorage.save_notebook(nb_id, "Debounce Test", s.to_dict_list())
            save_count[0] += 1

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(do_save)
        s.scene_changed.connect(lambda: timer.start(80))

        # Fire 10 rapid changes
        for _ in range(10):
            s.scene_changed.emit()

        loop = QEventLoop()
        QTimer.singleShot(400, loop.quit)
        loop.exec()

        assert save_count[0] == 1, (
            f"Expected exactly 1 save for 10 rapid changes (debounce), got {save_count[0]}"
        )


# ===========================================================================
# C. Manual Save button flow
# ===========================================================================

class TestManualSaveFlow:
    """Tests the save/reload cycle: edit -> save -> load from disk -> edits present."""

    def test_manual_save_and_reload(self, qt_app, tmp_path, monkeypatch):
        """
        Simulates: add sticky note -> save -> reload from disk -> note present.
        """
        from app.storage.notebook_storage import NotebookStorage

        tmp_boards = tmp_path / "boards"
        tmp_boards.mkdir()
        tmp_index = tmp_path / "notebooks_index.json"
        monkeypatch.setattr("app.storage.notebook_storage.BOARDS_DIR", str(tmp_boards))
        monkeypatch.setattr("app.storage.notebook_storage.INDEX_FILE", str(tmp_index))

        meta = NotebookStorage.create_notebook("Manual Save Test")
        nb_id = meta["id"]

        from app.ui.canvas_scene import CanvasScene
        from app.ui.items.sticky_note import StickyNote

        s = CanvasScene()
        note = StickyNote(text="Important formula!", color_key="pink")
        s.addItem(note)

        # Save (equivalent of _do_autosave being called by Save button)
        items_data = s.to_dict_list()
        NotebookStorage.save_notebook(nb_id, "Manual Save Test", items_data)

        # Reload from disk into a fresh scene
        payload = NotebookStorage.load_notebook(nb_id)
        loaded_items = payload.get("items", [])
        real_items = [i for i in loaded_items if i.get("type") != "_canvas_meta"]

        assert len(real_items) == 1
        assert real_items[0]["type"] == "StickyNote"
        assert real_items[0]["text"] == "Important formula!"
        assert real_items[0]["color_key"] == "pink"

        fresh_scene = CanvasScene()
        fresh_scene.load_from_dict_list(loaded_items)
        restored = [i for i in fresh_scene.items() if hasattr(i, 'to_dict')]
        assert len(restored) == 1
        assert isinstance(restored[0], StickyNote)
        assert restored[0].widget.color_key == "pink"

    def test_ink_stroke_save_reload(self, qt_app, tmp_path, monkeypatch):
        """Ink stroke survives save -> disk -> reload (the key-name bug fix)."""
        from app.storage.notebook_storage import NotebookStorage

        tmp_boards = tmp_path / "boards"
        tmp_boards.mkdir()
        tmp_index = tmp_path / "notebooks_index.json"
        monkeypatch.setattr("app.storage.notebook_storage.BOARDS_DIR", str(tmp_boards))
        monkeypatch.setattr("app.storage.notebook_storage.INDEX_FILE", str(tmp_index))

        meta = NotebookStorage.create_notebook("InkStroke Save Test")
        nb_id = meta["id"]

        from app.ui.canvas_scene import CanvasScene
        from app.ui.items.ink_stroke import InkStroke
        from PyQt6.QtGui import QPainterPath

        s = CanvasScene()
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(80, 40)
        path.lineTo(160, 0)
        stroke = InkStroke(path=path, tool_mode="pen", color="#1c1c1e", width=3.0)
        s.addItem(stroke)

        NotebookStorage.save_notebook(nb_id, "InkStroke Save Test", s.to_dict_list())

        payload = NotebookStorage.load_notebook(nb_id)
        loaded_items = payload.get("items", [])
        real_items = [i for i in loaded_items if i.get("type") != "_canvas_meta"]
        assert len(real_items) == 1
        assert real_items[0]["type"] == "InkStroke"
        # Key fix: must be 'elements'
        assert "elements" in real_items[0]
        assert len(real_items[0]["elements"]) == 3

        fresh = CanvasScene()
        fresh.load_from_dict_list(loaded_items)
        restored = [i for i in fresh.items() if hasattr(i, 'to_dict')]
        assert len(restored) == 1
        assert restored[0].path().elementCount() == 3

    def test_existing_notebook_updated_not_duplicated(self, qt_app, tmp_path, monkeypatch):
        """Saving the same notebook_id twice must UPDATE, never duplicate the index entry."""
        from app.storage.notebook_storage import NotebookStorage

        tmp_boards = tmp_path / "boards"
        tmp_boards.mkdir()
        tmp_index = tmp_path / "notebooks_index.json"
        monkeypatch.setattr("app.storage.notebook_storage.BOARDS_DIR", str(tmp_boards))
        monkeypatch.setattr("app.storage.notebook_storage.INDEX_FILE", str(tmp_index))

        meta = NotebookStorage.create_notebook("Dedup Test")
        nb_id = meta["id"]

        NotebookStorage.save_notebook(nb_id, "Dedup Test v1", [])
        NotebookStorage.save_notebook(nb_id, "Dedup Test v2", [])

        index = NotebookStorage.get_index()
        matching = [e for e in index if e["id"] == nb_id]
        assert len(matching) == 1, "Saving the same notebook twice must NOT create duplicates"
        assert matching[0]["name"] == "Dedup Test v2"


# ===========================================================================
# D. Unknown type fallback warning
# ===========================================================================

class TestUnknownTypeFallback:
    def test_unknown_type_returns_none_and_warns(self, scene, qt_app, capsys):
        """Unrecognized item type must return None and print a warning."""
        data = {"type": "AlienWidget", "x": 0, "y": 0, "some_field": "value"}
        result = scene.create_item_from_dict(data)
        assert result is None, "Unknown type must return None, not raise"

        captured = capsys.readouterr()
        assert "AlienWidget" in captured.out, (
            "A warning mentioning the unknown type must be printed to stdout"
        )

    def test_none_type_returns_none(self, scene, qt_app):
        """Dict with no 'type' key is handled gracefully."""
        result = scene.create_item_from_dict({"x": 10, "y": 20})
        assert result is None
