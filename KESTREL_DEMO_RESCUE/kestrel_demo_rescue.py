#!/usr/bin/env python3
"""Kestrel demo rescue patch for AI-TUTOR main @ bfdabef720a9aeb52e5f6658a18f78f5d64a4094.

Applies only exact, verified source replacements. Creates backups before touching files.
It deliberately stops on any mismatch instead of guessing.
"""
from __future__ import annotations
import argparse
import pathlib
import shutil
import subprocess
import sys
import time

PINNED_HEAD = "bfdabef720a9aeb52e5f6658a18f78f5d64a4094"

class PatchError(RuntimeError):
    pass


def git_head(root: pathlib.Path) -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def replace_exact(root: pathlib.Path, rel: str, old: str, new: str, backups: pathlib.Path, count: int = 1):
    path = root / rel
    if not path.exists():
        raise PatchError(f"Missing file: {rel}")
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise PatchError(f"{rel}: expected exact block {count} time(s), found {found}. Refusing to guess.")
    backup = backups / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, count), encoding="utf-8")
    print(f"[patched] {rel}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".", help="AI-TUTOR repository root")
    ap.add_argument("--force", action="store_true", help="allow a HEAD other than the verified commit; exact text checks still apply")
    args = ap.parse_args()
    root = pathlib.Path(args.repo).resolve()
    if not (root / "app").is_dir() or not (root / "backend").is_dir():
        raise PatchError(f"{root} does not look like the AI-TUTOR repo root")

    head = git_head(root)
    if head and head != PINNED_HEAD and not args.force:
        raise PatchError(
            f"Your HEAD is {head}, but this rescue was verified against {PINNED_HEAD}.\n"
            "Refusing to patch a different tree. Re-run with --force only if you intentionally accept exact-block matching."
        )

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backups = root / ".kestrel_rescue_backup" / stamp
    print(f"Kestrel rescue patch -> {root}")
    print(f"Backups -> {backups}")

    # 1) LaTeX export crash: two imported class names do not exist in current main.
    replace_exact(root, "app/ui/main_window.py",
'''        from .items.answer_bubble import AnswerBubble
        from .items.video_float_item import VideoFloatItem
        from .items.group_selection import GroupSelectionBox
        from .items.remote_cursor import RemoteCursor
''',
'''        from .items.answer_bubble import AnswerBubble
        from .items.video_float_item import VideoFloatItem
        from .items.group_selection import GroupSelection
        from .items.remote_cursor import RemoteCollaboratorCursor
''', backups)
    replace_exact(root, "app/ui/main_window.py",
'''            if isinstance(item, (AnswerBubble, VideoFloatItem, GroupSelectionBox, RemoteCursor)):
''',
'''            if isinstance(item, (AnswerBubble, VideoFloatItem, GroupSelection, RemoteCollaboratorCursor)):
''', backups)

    # 2) Citation handler at bottom of MainWindow overrides the working earlier handler with nonexistent PDF methods.
    replace_exact(root, "app/ui/main_window.py",
'''    def _on_citation_clicked(self, citation_data: dict):
        material_id = citation_data.get("material_id")
        page_number = citation_data.get("page_number", 1)
        if not material_id:
            return
            
        if not hasattr(self, 'pdf_viewer_widget'):
            return
            
        self.pdf_viewer_widget.load_document(material_id)
        if page_number:
            self.pdf_viewer_widget.jump_to_page(page_number)
            
        self._show_or_update_tab(self.pdf_viewer_widget, "Subject Material")
''',
'''    def _on_citation_clicked(self, citation_data: dict):
        """Open a cited material by database material id and jump to its PDF page."""
        material_id = citation_data.get("material_id")
        page_number = citation_data.get("page_number")
        if not material_id:
            return
        try:
            from app.storage.database import SessionLocal, Material
            with SessionLocal() as db:
                mat = db.query(Material).filter(Material.id == material_id).first()
                if not mat or not mat.file_path or not os.path.exists(mat.file_path):
                    return
                self._on_subject_pdf_requested(mat.file_path)
            if page_number and hasattr(self.pdf_viewer_widget, "go_to_page"):
                self.pdf_viewer_widget.go_to_page(int(page_number))
        except Exception as e:
            print(f"[MainWindow] Citation click navigation error: {e}")
''', backups)

    # 3) Keep MainWindow's user identity aligned with SubjectsListView for session/memory rows.
    replace_exact(root, "app/ui/main_window.py",
'''        self._apply_global_styles()
        self._init_ui()
        self._setup_shortcuts()
''',
'''        self._apply_global_styles()
        self._init_ui()
        self.current_user_id = getattr(getattr(self.subjects_list_view, "current_user", None), "id", None)
        self._setup_shortcuts()
''', backups)

    # 4) Blank canvas must not retain old subject/notebook/session context.
    replace_exact(root, "app/ui/main_window.py",
'''        def _open_blank():
            self.subject_detail_view.current_subject_id = None
            self.main_stack.setCurrentWidget(canvas_wrapper)
            self._set_sidebar_active_button("canvas")
''',
'''        def _open_blank():
            self._clear_active_requests("blank_canvas")
            self.subject_detail_view.current_subject_id = None
            self.current_subject_id = None
            self._current_notebook_id = None
            self.current_learning_session_id = None
            self.current_attempt_id = None
            self.learning_controller.current_session_id = None
            self.learning_controller.current_attempt_id = None
            self.current_board = BoardModel("Untitled Notebook")
            self.title_edit.setText(self.current_board.title)
            self.scene.reset_context(notebook_id=None, clear_items=True)
            self._update_context_indicator()
            self.main_stack.setCurrentWidget(canvas_wrapper)
            self._set_sidebar_active_button("canvas")
''', backups)

    # 5) Saving a scratch notebook must also create the SQL notebook row used by learning-session FKs.
    replace_exact(root, "app/ui/main_window.py",
'''                meta = NotebookStorage.create_notebook(name.strip())
                self._current_notebook_id = meta["id"]
                self.current_board.board_id = meta["id"]
                self.current_board.title = meta["name"]
                self.title_edit.setText(meta["name"])
''',
'''                meta = NotebookStorage.create_notebook(name.strip(), subject_id=self.current_subject_id)
                from app.storage.database_ops import create_notebook as db_create_notebook
                db_create_notebook(name.strip(), self.current_subject_id, override_id=meta["id"])
                self._current_notebook_id = meta["id"]
                self.current_board.board_id = meta["id"]
                self.current_board.title = meta["name"]
                self.title_edit.setText(meta["name"])
                self.scene.set_notebook_id(meta["id"])
                self.current_learning_session_id = self.memory_repo.get_or_create_active_session(
                    notebook_id=meta["id"], user_id=self.current_user_id, subject_id=self.current_subject_id
                )
                self.current_attempt_id = self.memory_repo.get_or_create_active_attempt(self.current_learning_session_id)
                self.learning_controller.current_session_id = self.current_learning_session_id
                self.learning_controller.current_attempt_id = self.current_attempt_id
''', backups)
    replace_exact(root, "app/ui/main_window.py",
'''            NotebookStorage.save_notebook(self._current_notebook_id, name, items_data)
''',
'''            NotebookStorage.save_notebook(
                self._current_notebook_id, name, items_data, subject_id=self.current_subject_id
            )
''', backups)

    # 6) Notebook loading: restore subject from JSON or SQL and bind CanvasScene to the real notebook id.
    replace_exact(root, "app/ui/main_window.py",
'''            # Ensure subject_id is preserved if stored in notebook payload
            if payload.get("subject_id"):
                self.current_subject_id = payload.get("subject_id")

            user_id = getattr(self, "current_user_id", None)
''',
'''            # Restore subject context. New JSON files carry subject_id; legacy files can resolve it from SQL.
            self.current_subject_id = payload.get("subject_id")
            if not self.current_subject_id:
                try:
                    from app.storage.database import SessionLocal, Notebook
                    with SessionLocal() as db:
                        db_nb = db.query(Notebook).filter(Notebook.id == self._current_notebook_id).first()
                        self.current_subject_id = db_nb.subject_id if db_nb else None
                except Exception as e:
                    print(f"[MainWindow] Could not resolve legacy notebook subject: {e}")

            self.scene.reset_context(notebook_id=self._current_notebook_id, clear_items=False)
            user_id = getattr(self, "current_user_id", None)
''', backups)

    # 7) OCR stale-result protection: recognition itself must be registered and invalidated across context switches.
    replace_exact(root, "app/ui/main_window.py",
'''        self.magic_orb.set_state("thinking", "Recognizing handwriting...")
        
        from app.services.recognition.vision_recognizer import VisionRecognizer, RealProviderClient
''',
'''        self.magic_orb.set_state("thinking", "Recognizing handwriting...")
        self._register_active_request("recognition", payload)
        
        from app.services.recognition.vision_recognizer import VisionRecognizer, RealProviderClient
''', backups)
    replace_exact(root, "app/ui/main_window.py",
'''            self.scene.clear_ocr_in_flight()
            self._active_ocr_worker = None
            self._on_auto_ai_requested(result, target_pos)
            worker.deleteLater()
''',
'''            self.scene.clear_ocr_in_flight()
            self._active_ocr_worker = None
            if self._is_request_stale("recognition", payload):
                self._complete_active_request("recognition", getattr(payload, "request_id", None))
                worker.deleteLater()
                return
            self._complete_active_request("recognition", getattr(payload, "request_id", None))
            self._on_auto_ai_requested(result, target_pos)
            worker.deleteLater()
''', backups)
    replace_exact(root, "app/ui/main_window.py",
'''            self.scene.clear_ocr_in_flight()
            self._active_ocr_worker = None
            
            error_msg = getattr(failure, 'user_message', "Recognition failed")
''',
'''            self.scene.clear_ocr_in_flight()
            self._active_ocr_worker = None
            self._complete_active_request("recognition", getattr(payload, "request_id", None))
            
            error_msg = getattr(failure, 'user_message', "Recognition failed")
''', backups)

    # Preserve OCR request identity in tutor context and never draw a green check for UNKNOWN.
    replace_exact(root, "app/ui/main_window.py",
'''            canvas_revision=getattr(self.scene, "revision", 1),
            scope=ContextScope.SELECTION if getattr(query, "is_explicit_selection", False) else ContextScope.ACTIVE_BLOCK,
''',
'''            canvas_revision=getattr(query, "canvas_revision", getattr(self.scene, "revision", 1)),
            semantic_block_id=getattr(query, "group_id", None),
            scope=ContextScope.SELECTION if getattr(query, "is_explicit_selection", False) else ContextScope.ACTIVE_BLOCK,
''', backups)
    replace_exact(root, "app/ui/main_window.py",
'''            if stroke_ids and hasattr(self.scene, 'highlight_strokes_by_id'):
                self.scene.highlight_strokes_by_id(stroke_ids, is_error=is_error)
''',
'''            if stroke_ids and hasattr(self.scene, 'highlight_strokes_by_id') and verdict_val in ("VALID", "INVALID"):
                self.scene.highlight_strokes_by_id(stroke_ids, is_error=(verdict_val == "INVALID"))
''', backups)

    # 8) Canvas context reset and OCR retry safety.
    replace_exact(root, "app/ui/canvas_scene.py",
'''    def set_notebook_id(self, notebook_id: str):
        self.notebook_id = notebook_id

    def _on_theme_changed(self, theme_name: str):
''',
'''    def set_notebook_id(self, notebook_id: str):
        self.notebook_id = notebook_id

    def reset_context(self, notebook_id=None, clear_items: bool = False):
        """Reset transient ink/OCR grouping when switching notebook/subject context."""
        self._auto_ai_timer.stop()
        self._auto_convert_timer.stop()
        self._ocr_in_flight = False
        self._recent_ink_strokes.clear()
        from app.services.recognition.stroke_grouper import StrokeGrouper
        self.stroke_grouper = StrokeGrouper()
        self.notebook_id = notebook_id
        if clear_items:
            was_remote = self._is_remote_event
            self._is_remote_event = True  # do not broadcast a destructive collaboration clear on navigation
            try:
                self.deactivate_active_shape()
                self.clear()
                self.clear_remote_cursors()
            finally:
                self._is_remote_event = was_remote

    def _on_theme_changed(self, theme_name: str):
''', backups)

    # Do not discard the only recent-ink reference before OCR has succeeded.
    replace_exact(root, "app/ui/canvas_scene.py",
'''        self._ocr_in_flight = True
        self._recent_ink_strokes.clear()
        
        self.recognition_requested.emit(req, target_pos)
''',
'''        self._ocr_in_flight = True
        # Keep the recent-stroke buffer until a later stroke replaces it; this permits a retry after OCR failure.
        self.recognition_requested.emit(req, target_pos)
''', backups)

    # 9) Notebook JSON now carries subject identity; signatures remain backward compatible.
    replace_exact(root, "app/storage/notebook_storage.py",
'''    def create_notebook(cls, name: str = "Untitled Notebook", folder_id: str = None) -> dict:
''',
'''    def create_notebook(cls, name: str = "Untitled Notebook", folder_id: str = None, subject_id: str = None) -> dict:
''', backups)
    replace_exact(root, "app/storage/notebook_storage.py",
'''            "folder_id": folder_id,
            "created_at": now_str,
''',
'''            "folder_id": folder_id,
            "subject_id": subject_id,
            "created_at": now_str,
''', backups, count=1)
    replace_exact(root, "app/storage/notebook_storage.py",
'''            "title": meta["name"],
            "created_at": now_str,
''',
'''            "title": meta["name"],
            "subject_id": subject_id,
            "created_at": now_str,
''', backups)
    replace_exact(root, "app/storage/notebook_storage.py",
'''    def save_notebook(cls, notebook_id: str, name: str, items_data: list) -> dict:
''',
'''    def save_notebook(cls, notebook_id: str, name: str, items_data: list, subject_id: str = None) -> dict:
''', backups)
    replace_exact(root, "app/storage/notebook_storage.py",
'''            "title": name,
            "updated_at": now_str,
            "items": items_data or [],
''',
'''            "title": name,
            "subject_id": subject_id,
            "updated_at": now_str,
            "items": items_data or [],
''', backups)

    replace_exact(root, "app/ui/views/subject_detail_view.py",
'''        meta = NotebookStorage.create_notebook(name.strip())
        db_create_notebook(name.strip(), self.current_subject_id, override_id=meta["id"])
''',
'''        meta = NotebookStorage.create_notebook(name.strip(), subject_id=self.current_subject_id)
        db_create_notebook(name.strip(), self.current_subject_id, override_id=meta["id"])
''', backups)

    # 10) First recognized line is context, not a mathematically verified transition.
    replace_exact(root, "app/services/tutoring/orchestrator.py",
'''        verdict = ValidationVerdict.VALID
        explanation = "First step looks good."
        socratic_hints = ["What should we do next?"]
''',
'''        verdict = ValidationVerdict.UNKNOWN
        explanation = "First step captured. Write the next step and I can verify the transition."
        socratic_hints = ["What should we do next?"]
''', backups)
    replace_exact(root, "app/services/tutoring/orchestrator.py",
'''        if request.attempt_id:
            previous_step = self.repo.get_last_valid_step(request.attempt_id)
            if not previous_step:
                previous_step = self.repo.get_last_step(request.attempt_id)
''',
'''        if request.attempt_id:
            # Compare against the latest non-invalid step. This lets a corrected step branch from
            # the last trustworthy/captured line instead of from the mistake it is correcting.
            recent_steps = self.repo.get_recent_steps(request.attempt_id, limit=20)
            previous_step = next(
                (s for s in reversed(recent_steps) if s.validation_verdict != ValidationVerdict.INVALID.value),
                None,
            )
''', backups)
    replace_exact(root, "app/services/tutoring/orchestrator.py",
'''                content_type="EQUATION" if current_parsed.is_equation else "EXPRESSION",
                previous_step_id=previous_step.id if previous_step else None
''',
'''                content_type="EQUATION" if current_parsed.is_equation else "EXPRESSION",
                group_id=request.semantic_block_id,
                previous_step_id=previous_step.id if previous_step else None
''', backups)

    # Parser: verified normalization for common OCR/handwriting math symbols and ^ exponent syntax.
    replace_exact(root, "app/services/reasoning/math_parser.py",
'''from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
''',
'''from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
)
import re
''', backups)
    replace_exact(root, "app/services/reasoning/math_parser.py",
'''    clean_text = text.strip()
    
    # Safe transformations: handle implicit multiplication (2x -> 2*x) and ^ for exponents
    transformations = standard_transformations + (implicit_multiplication_application,)
''',
'''    clean_text = text.strip()
    # Normalize common handwriting/OCR math forms before SymPy parsing.
    clean_text = (clean_text
                  .replace("−", "-").replace("–", "-")
                  .replace("×", "*").replace("·", "*").replace("÷", "/")
                  .replace("\\\\times", "*").replace("\\\\cdot", "*").replace("\\\\div", "/")
                  .replace("\\\\left", "").replace("\\\\right", ""))
    supers = str.maketrans({"²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9", "⁰": "^0"})
    clean_text = clean_text.translate(supers)
    # Simple OCR LaTeX fractions, e.g. \\frac{2}{3} -> ((2)/(3)); nested fractions remain safely UNKNOWN.
    clean_text = re.sub(r"\\\\frac\\{([^{}]+)\\}\\{([^{}]+)\\}", r"((\\1)/(\\2))", clean_text)
    
    # Safe transformations: implicit multiplication (2x -> 2*x) and ^ -> exponentiation.
    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
''', backups)

    # 11) Video request contract must carry the PDF/video fields that MainWindow already collects.
    replace_exact(root, "shared/contracts/video.py",
'''    requested_duration: Optional[int] = None
    style: Optional[str] = None
''',
'''    requested_duration: Optional[int] = None
    style: Optional[str] = None

    # Source details used by the existing PDF/video pipeline.
    pdf_path: Optional[str] = None
    page_range: Optional[str] = None
    emphasis_note: Optional[str] = None
    output_type: str = "video"
    selection_payload: Optional[dict] = None
''', backups)

    replace_exact(root, "app/ui/main_window.py",
'''                explanation_goal="Explain this document.",
                # Note: Currently pdf_path, page_range, emphasis_note, output_type 
                # are not explicitly inside the new strict contract but they could be 
                # mapped or we just temporarily ignore them since we just built the basic contract.
                # But let's pass them as dict if we extend it, or just pass subject_id.
                subject_id=current_subject or "",
                tutor_mode=out_type
''',
'''                explanation_goal="Explain this document.",
                subject_id=current_subject or None,
                tutor_mode="EXPLAIN",
                pdf_path=pdf_path,
                page_range=page_range or None,
                emphasis_note=emphasis or None,
                output_type=out_type or "video"
''', backups)

    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''    _PENDING_JOBS[job_id] = {
        "prompt": request.explanation_goal,
        "subject_id": request.subject_id,
        "is_local_direct": True
    }
''',
'''    _PENDING_JOBS[job_id] = {
        "prompt": request.explanation_goal,
        "subject_id": request.subject_id,
        "pdf_path": request.pdf_path,
        "page_range": request.page_range,
        "emphasis_note": request.emphasis_note,
        "output_type": request.output_type,
        "selection_payload": request.selection_payload,
        "is_local_direct": True,
    }
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''                _PENDING_JOBS[ret_id]["is_local_direct"] = False
                _PENDING_JOBS[ret_id]["server_url"] = server_url
                return ret_id
''',
'''                _PENDING_JOBS[ret_id]["is_local_direct"] = False
                _PENDING_JOBS[ret_id]["server_url"] = server_url
                _PENDING_JOBS[ret_id]["status_url"] = data.get("status_url") or f"{server_url}/status/{ret_id}"
                return ret_id
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''            _PENDING_JOBS[ret_id]["is_local_direct"] = False
            _PENDING_JOBS[ret_id]["server_url"] = MODAL_ENDPOINT_URL
            return ret_id
    except Exception:
        pass
    except Exception:
        pass
''',
'''            _PENDING_JOBS[ret_id]["is_local_direct"] = False
            _PENDING_JOBS[ret_id]["status_url"] = data.get("status_url") or f"{MODAL_VIDEO_STATUS_URL.rstrip('/')}/{ret_id}"
            return ret_id
    except Exception:
        pass
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''        server_url = job_info.get("server_url") or _get_active_server()
''',
'''        server_url = job_info.get("server_url") or _get_active_server()
        status_url = job_info.get("status_url")
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''                r = requests.get(f"{server_url}/status/{self.job_id}", timeout=2.5)
''',
'''                r = requests.get(status_url or f"{server_url}/status/{self.job_id}", timeout=2.5)
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''            from backend.video_generation.models import VideoJob, JobStatus
''',
'''            from backend.video_generation.models import VideoJob, JobStatus, BoardSelection
''', backups)
    replace_exact(root, "app/services/tutoring/video_gen_client.py",
'''                board_selection=job_info.get("selection_payload") or {}
''',
'''                board_selection=BoardSelection.from_dict(job_info.get("selection_payload"))
''', backups)

    # Hard video endpoint crash: VideoJob requires user_prompt, not prompt.
    replace_exact(root, "backend/local_server.py",
'''    # The backend VideoJob model needs prompt/document_text fields right now
    # We will map the fields from VideoGenerationRequest to VideoJob
    job = VideoJob(
        job_id=job_id,
        prompt=request.explanation_goal or "Explain this content.",
        subject_id=request.subject_id,
    )
    
    # We construct BoardSelection from anchor_bbox if needed
    if request.anchor_bbox:
        bs = BoardSelection(
            board_id=request.notebook_id or "",
            bbox={"x": request.anchor_bbox.x, "y": request.anchor_bbox.y, 
                  "width": request.anchor_bbox.width, "height": request.anchor_bbox.height},
            user_instruction=request.explanation_goal
        )
        job.board_selection = bs
''',
'''    job = VideoJob(
        job_id=job_id,
        user_prompt=request.explanation_goal or "Explain this content.",
        document_text=request.recognized_content or "",
        pdf_path=request.pdf_path or "",
        page_range=request.page_range,
        emphasis_note=request.emphasis_note,
        output_type=request.output_type or "video",
        subject_id=request.subject_id,
        board_selection=BoardSelection.from_dict(request.selection_payload),
    )
    
    # Construct BoardSelection from the canvas anchor when no richer selection was supplied.
    if request.anchor_bbox and job.board_selection is None:
        job.board_selection = BoardSelection(
            board_id=request.notebook_id or "",
            bbox={"x": request.anchor_bbox.x, "y": request.anchor_bbox.y,
                  "width": request.anchor_bbox.width, "height": request.anchor_bbox.height},
            user_instruction=request.explanation_goal,
        )
''', backups)
    replace_exact(root, "backend/local_server.py",
'''        "prompt": job.prompt,
''',
'''        "prompt": job.user_prompt,
''', backups)

    # 12) LaTeX uses backend config defaults (8000) rather than a divergent hard-coded 8888 path.
    replace_exact(root, "app/services/reasoning/latex_client.py",
'''LOCAL_SERVER_URL = os.getenv("BACKEND_URL", f"http://localhost:{os.getenv('PORT', '8888')}")
MODAL_ENDPOINT_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")
''',
'''try:
    from backend.config import BACKEND_URL, MODAL_LATEX_GENERATE_URL, MODAL_LATEX_STATUS_URL
except Exception:
    BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    MODAL_LATEX_GENERATE_URL = os.getenv("MODAL_LATEX_GENERATE_URL", "")
    MODAL_LATEX_STATUS_URL = os.getenv("MODAL_LATEX_STATUS_URL", "")
LOCAL_SERVER_URL = BACKEND_URL.rstrip("/")
''', backups)
    replace_exact(root, "app/services/reasoning/latex_client.py",
'''        modal_url = MODAL_ENDPOINT_URL.replace("/generate", "/generate_latex")
        resp = requests.post(
            modal_url,
''',
'''        if not MODAL_LATEX_GENERATE_URL:
            raise RuntimeError("Modal LaTeX endpoint is not configured")
        resp = requests.post(
            MODAL_LATEX_GENERATE_URL,
''', backups)

    # 13) RAG: vector hits must carry chunk/material IDs or the fusion dictionary collapses them under None.
    replace_exact(root, "backend/workspace/subject_vector_store.py",
'''                    "score":          hit.score,
                    "text":           hit.payload.get("text", ""),
                    "subject_id":     hit.payload.get("subject_id", ""),
''',
'''                    "id":             hit.payload.get("chunk_id", str(hit.id)),
                    "chunk_id":       hit.payload.get("chunk_id", str(hit.id)),
                    "material_id":    hit.payload.get("material_id", ""),
                    "score":          hit.score,
                    "text":           hit.payload.get("text", ""),
                    "subject_id":     hit.payload.get("subject_id", ""),
''', backups)

    # Reuse one in-memory Qdrant client inside this process so ingestion and search see the same points.
    replace_exact(root, "backend/workspace/subject_vector_store.py",
'''COLLECTION      = "kestrel-subject-brain-v1"
EMBEDDING_DIM   = 3072   # models/gemini-embedding-2
''',
'''COLLECTION      = "kestrel-subject-brain-v1"
EMBEDDING_DIM   = 3072   # models/gemini-embedding-2
_LOCAL_MEMORY_CLIENT = None


def _shared_memory_client() -> QdrantClient:
    global _LOCAL_MEMORY_CLIENT
    if _LOCAL_MEMORY_CLIENT is None:
        _LOCAL_MEMORY_CLIENT = QdrantClient(location=":memory:")
    return _LOCAL_MEMORY_CLIENT
''', backups)
    replace_exact(root, "backend/workspace/subject_vector_store.py",
'''            return QdrantClient(location=":memory:")
''',
'''            return _shared_memory_client()
''', backups, count=2)

    # 14) Knowledge graph query must read the same layout table the layout writer updates; json is also used but not imported.
    replace_exact(root, "app/services/knowledge/graph_query_service.py",
'''from typing import List, Optional
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, Subject, ConceptNode, ConceptEdge, GraphEvidence, GraphLayoutState
''',
'''from typing import List, Optional
import json
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, Subject, ConceptNode, ConceptEdge, GraphEvidence, GraphLayout
''', backups)
    replace_exact(root, "app/services/knowledge/graph_query_service.py",
'''            layouts = session.query(GraphLayoutState).filter(GraphLayoutState.scope_type == "SUBJECT", GraphLayoutState.scope_id == subject_id).all()
''',
'''            layouts = session.query(GraphLayout).filter(GraphLayout.scope_type == "SUBJECT", GraphLayout.scope_id == subject_id).all()
''', backups)

    # Syntax gate: compile every touched Python file. This catches indentation/name syntax mistakes before demo launch.
    touched = [
        "app/ui/main_window.py",
        "app/ui/canvas_scene.py",
        "app/storage/notebook_storage.py",
        "app/ui/views/subject_detail_view.py",
        "app/services/tutoring/orchestrator.py",
        "app/services/reasoning/math_parser.py",
        "shared/contracts/video.py",
        "app/services/tutoring/video_gen_client.py",
        "backend/local_server.py",
        "app/services/reasoning/latex_client.py",
        "backend/workspace/subject_vector_store.py",
        "app/services/knowledge/graph_query_service.py",
    ]
    print("\nRunning syntax checks...")
    failures = []
    for rel in touched:
        p = root / rel
        cp = subprocess.run([sys.executable, "-m", "py_compile", str(p)], cwd=root, capture_output=True, text=True)
        if cp.returncode:
            failures.append((rel, cp.stderr.strip()))
        else:
            print(f"[syntax ok] {rel}")
    if failures:
        print("\nSYNTAX CHECK FAILED. Restore from backup before demo:")
        for rel, err in failures:
            print(f"--- {rel} ---\n{err}")
        raise PatchError("One or more patched files failed py_compile")

    print("\nRESCUE PATCH APPLIED SUCCESSFULLY")
    print(f"Backup folder: {backups}")
    print("Next: start backend, launch app, then run the demo smoke checklist supplied with this patch.")


if __name__ == "__main__":
    try:
        main()
    except PatchError as e:
        print(f"\n[ABORTED] {e}", file=sys.stderr)
        sys.exit(2)
