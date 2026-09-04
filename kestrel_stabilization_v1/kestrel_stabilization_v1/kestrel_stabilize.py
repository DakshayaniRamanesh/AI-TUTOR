#!/usr/bin/env python3
"""Apply the Kestrel v1 stabilization patch from the AI-TUTOR repo root."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXPECTED_HEAD = "ae8198bf664fe0cc55f20a32962c2a5b946d5a52"
OVERLAY_FILES = [
    "backend/config.py",
    "app/backend/video_generation/video_gen_client.py",
    "app/backend/math_engine/latex_client.py",
    "backend/workspace/artifact_store.py",
    "backend/video_generation/agents/renderer_agent.py",
    "backend/video_generation/agents/latex_agents.py",
    "tests/test_stabilization_contracts.py",
]


class PatchError(RuntimeError):
    pass


def run_git(*args: str) -> str:
    p = subprocess.run(["git", *args], capture_output=True, text=True)
    if p.returncode:
        raise PatchError(p.stderr.strip() or f"git {' '.join(args)} failed")
    return p.stdout.strip()


def get_root() -> Path:
    root = Path.cwd()
    if not (root / ".git").exists():
        raise PatchError("Run this from the AI-TUTOR repository root.")
    return root


def backup(root: Path, backup_dir: Path, rel: str) -> None:
    src = root / rel
    if not src.exists():
        return
    dst = backup_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)


def put(root: Path, backup_dir: Path, rel: str, content: str) -> None:
    backup(root, backup_dir, rel)
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")


def mutate(root: Path, backup_dir: Path, rel: str, fn) -> None:
    path = root / rel
    if not path.exists():
        raise PatchError(f"Missing file: {rel}")
    old = path.read_text(encoding="utf-8")
    new = fn(old)
    if new == old:
        raise PatchError(f"{rel}: patch produced no change (source may have drifted)")
    backup(root, backup_dir, rel)
    path.write_text(new, encoding="utf-8")


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise PatchError(f"{label}: expected snippet once, found {n}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    new, n = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise PatchError(f"{label}: expected regex once, found {n}")
    return new


def patch_requirements(text: str) -> str:
    if "manim>=0.18.0" in text:
        text = text.replace("manim>=0.18.0", "manim==0.20.1", 1)
    elif "manim==0.20.1" not in text:
        raise PatchError("backend/requirements.txt: unknown Manim line")
    if "groq>=0.9.0" not in text:
        text = once(
            text,
            "google-generativeai\n",
            "google-generativeai\ngroq>=0.9.0\n",
            "backend Groq dependency",
        )
    return text


def patch_scene_compile(text: str) -> str:
    replacement = '''    def compile(self, scenes: List[SceneSpec]) -> str:
        """Compile every SceneSpec into one complete MainScene lesson."""
        body: List[str] = [
            "from manim import *",
            "import numpy as np",
            "import math",
            "",
            "class MainScene(Scene):",
            "    def construct(self):",
            "        self.camera.background_color = '#090d16'",
        ]

        if not scenes:
            body.append("        self.wait(0.5)")
            return "\\n".join(body) + "\\n"

        for index, scene in enumerate(scenes):
            body.extend(self._compile_scene(scene, index))
            if index < len(scenes) - 1:
                body.append("        if self.mobjects:")
                body.append(
                    "            self.play(*[FadeOut(m) for m in list(self.mobjects)], run_time=0.35)"
                )
                body.append("        self.clear()")

        body.append("        self.wait(0.5)")
        return "\\n".join(body) + "\\n"

'''
    text = regex_once(
        text,
        r"    def compile\(self, scenes: List\[SceneSpec\]\) -> str:\n.*?(?=    def _compile_scene)",
        replacement,
        "SceneCompileAgent.compile",
    )
    layout = '''        # If layout is 'equation_with_rule_below', shift up everything that is not a question or rule
        if scene.layout == "equation_with_rule_below":
            lines.append("        if self.mobjects:")
            lines.append("            self.play(VGroup(*self.mobjects).animate.shift(UP * 1.5), run_time=0.8)")

'''
    if layout in text:
        text = text.replace(
            layout,
            "        # Object positions are established before animation; do not shift self.mobjects before they exist.\n\n",
            1,
        )

    # Keep deterministic compiler output inside CI's own visible-text contract.
    text = once(
        text,
        '            text = str(obj.get("text") or obj.get("value") or obj.get("label") or "")[:180]\n',
        '            text = str(obj.get("text") or obj.get("value") or obj.get("label") or "")[:78]\n',
        "SceneCompile text length",
    )
    text = once(
        text,
        '        fallback_text = str(obj.get("text") or obj.get("label") or otype.replace("_", " ").title())[:120]\n',
        '        fallback_text = str(obj.get("text") or obj.get("label") or otype.replace("_", " ").title())[:78]\n',
        "SceneCompile fallback text length",
    )
    text = once(
        text,
        '            q = str(action.get("question", "Question?"))\n',
        '            q = str(action.get("question", "Question?"))[:78]\n',
        "SceneCompile question length",
    )
    return text



def patch_ci(text: str) -> str:
    old = '''    for pattern, suggestion in _BANNED_APIS:
        for i, line in enumerate(lines, 1):
            if pattern in line and not line.strip().startswith("#"):
                return False, (
                    f"[Stage0] Banned API on line {i}: '{pattern.strip()}'\\n"
                    f"Fix: {suggestion}\\n"
                    f"Line: {line.strip()}"
                )
'''
    new = '''    for pattern, suggestion in _BANNED_APIS:
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            # "Tex(" is a suffix of "MathTex(". A naive substring check therefore
            # banned MathTex even after the explicit MathTex ban was removed.
            if pattern == "Tex(":
                matched = bool(re.search(r"(?<![A-Za-z0-9_])Tex\\s*\\(", line))
            else:
                matched = pattern in line
            if matched:
                return False, (
                    f"[Stage0] Banned API on line {i}: '{pattern.strip()}'\\n"
                    f"Fix: {suggestion}\\n"
                    f"Line: {line.strip()}"
                )
'''
    return once(text, old, new, "CI Tex/MathTex substring bug")

def patch_graph(text: str) -> str:
    old = '''def _route_ci(state: VideoJob) -> str:
    if state.has_build_error:
        if state.status == JobStatus.ERROR:
            return END
        # Deterministic compiler is the preferred board path. On a CI failure,
        # use the existing LLM CodeGenAgent as a bounded repair fallback.
        return "codegen"
    return "render"
'''
    new = '''def _route_ci(state: VideoJob) -> str:
    if not state.has_build_error:
        return "render"
    if state.status == JobStatus.ERROR:
        return END

    selection = getattr(state, "board_selection", None)
    if selection and getattr(selection, "has_content", lambda: False)():
        state.status = JobStatus.ERROR
        state.error_message = (
            "STRUCTURED_SCENE_CI_FAILED: "
            + (state.build_error_trace or "Deterministic SceneSpec compilation failed.")
        )
        return END

    # Legacy text/PDF requests keep their bounded CodeGen repair path.
    return "codegen"
'''
    text = once(text, old, new, "structured CI routing")

    old = '''    def _validate_or_repair(self, state: VideoJob) -> VideoJob:
        passed, error_trace = self.ci_harness.validate_code(state.manim_code or "")
        if passed:
            state.has_build_error = False
            state.build_error_trace = None
            return state
        state.has_build_error = True
        state.build_error_trace = error_trace
        state.retry_count += 1
        return self._codegen_until_valid(state)
'''
    new = '''    def _validate_or_repair(self, state: VideoJob) -> VideoJob:
        passed, error_trace = self.ci_harness.validate_code(state.manim_code or "")
        if passed:
            state.has_build_error = False
            state.build_error_trace = None
            return state
        state.has_build_error = True
        state.build_error_trace = error_trace
        state.retry_count += 1

        selection = getattr(state, "board_selection", None)
        if selection and getattr(selection, "has_content", lambda: False)():
            state.status = JobStatus.ERROR
            state.error_message = (
                "STRUCTURED_SCENE_CI_FAILED: "
                + (error_trace or "Deterministic SceneSpec compilation failed.")
            )
            return state

        return self._codegen_until_valid(state)
'''
    return once(text, old, new, "fallback structured CI routing")


def patch_storyboard(text: str) -> str:
    replacement = '''    def _normalize_scenes(self, raw_scenes: Any) -> List[SceneSpec]:
        """Normalize SceneSpec JSON without deleting pedagogical actions."""
        if not isinstance(raw_scenes, list):
            return []

        out: List[SceneSpec] = []
        for idx, raw in enumerate(raw_scenes[:6]):
            if not isinstance(raw, dict):
                continue

            objects: List[Dict[str, Any]] = []
            seen_ids = set()
            valid_targets = set()

            def clean_id(value: Any, fallback: str) -> str:
                value = re.sub(r"[^A-Za-z0-9_]", "_", str(value or fallback))[:50]
                if not value:
                    value = fallback
                if value and value[0].isdigit():
                    value = f"obj_{value}"
                return value

            for obj_idx, obj in enumerate(raw.get("objects", [])[:24]):
                if not isinstance(obj, dict):
                    continue
                obj_type = str(obj.get("type", "text"))
                if obj_type not in _ALLOWED_OBJECT_TYPES:
                    continue

                oid = clean_id(obj.get("id"), f"obj_{obj_idx}")
                if oid in seen_ids:
                    oid = f"{oid}_{obj_idx}"
                seen_ids.add(oid)
                valid_targets.add(oid)

                clean = dict(obj)
                clean["id"] = oid
                clean["type"] = obj_type
                clean["position"] = str(obj.get("position", "center"))

                if obj_type == "vector_field":
                    pattern = str(obj.get("pattern", "uniform"))
                    clean["pattern"] = pattern if pattern in {
                        "radial_outward", "radial_inward", "rotational", "uniform"
                    } else "uniform"

                if obj_type == "plot":
                    curve = str(obj.get("curve", "parabola"))
                    clean["curve"] = curve if curve in {
                        "parabola", "sine", "cosine", "linear"
                    } else "parabola"

                if obj_type == "term_equation":
                    clean_terms = []
                    for term_idx, term in enumerate(obj.get("terms", [])[:24]):
                        if not isinstance(term, dict):
                            continue
                        tid = clean_id(term.get("id"), f"{oid}_term_{term_idx}")
                        if tid in valid_targets:
                            tid = f"{tid}_{term_idx}"
                        valid_targets.add(tid)
                        term_clean = dict(term)
                        term_clean["id"] = tid
                        term_clean["value"] = str(term.get("value", ""))[:120]
                        clean_terms.append(term_clean)
                    clean["terms"] = clean_terms

                objects.append(clean)

            if not objects:
                continue

            actions: List[Dict[str, Any]] = []
            for action in raw.get("actions", [])[:40]:
                if not isinstance(action, dict):
                    continue
                atype = str(action.get("type", "create"))
                if atype not in _ALLOWED_ACTION_TYPES:
                    continue

                # These teaching actions do not require a target.
                if atype == "AskQuestion":
                    question = str(action.get("question", "")).strip()
                    if question:
                        actions.append({"type": atype, "question": question[:240]})
                    continue
                if atype == "RevealRule":
                    rule = str(action.get("rule", "")).strip()
                    if rule:
                        actions.append({"type": atype, "rule": rule[:300]})
                    continue

                target = clean_id(action.get("target"), "")
                if target not in valid_targets:
                    continue

                if atype in {"MapTerms", "SubstituteValues"}:
                    source = clean_id(action.get("source"), "")
                    if source not in valid_targets:
                        continue
                    clean_action = dict(action)
                    clean_action.update(type=atype, source=source, target=target)
                    actions.append(clean_action)
                    continue

                if atype == "transform":
                    destination = clean_id(action.get("to"), "")
                    reason = str(action.get("reason", "")).strip()
                    if destination not in valid_targets:
                        continue
                    if not reason or reason.lower() in {"direct transition", "transition", "because"}:
                        continue
                    clean_action = dict(action)
                    clean_action.update(type=atype, target=target, to=destination, reason=reason[:500])
                    actions.append(clean_action)
                    continue

                clean_action = dict(action)
                clean_action.update(type=atype, target=target)
                actions.append(clean_action)

            try:
                duration = max(4.0, min(24.0, float(raw.get("duration_seconds", 8))))
            except Exception:
                duration = 8.0

            out.append(SceneSpec(
                scene_id=str(raw.get("scene_id") or f"scene_{idx + 1}"),
                title=str(raw.get("title", ""))[:160],
                learning_goal=str(raw.get("learning_goal", ""))[:500],
                duration_seconds=duration,
                layout=str(raw.get("layout", "default")),
                objects=objects,
                actions=actions,
                narration=str(raw.get("narration", ""))[:1200],
            ))
        return out

'''
    return regex_once(
        text,
        r"    def _normalize_scenes\(self, raw_scenes: Any\) -> List\[SceneSpec\]:\n.*?(?=    def _fallback_scenes)",
        replacement,
        "StoryboardPlannerAgent._normalize_scenes",
    )



def patch_local_server(text: str) -> str:
    text = text.replace(
        '''    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_tectonic = os.path.join(project_root, "tectonic.exe")
    tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"
''',
        '''    import shutil
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_tectonic = os.path.join(project_root, "tectonic.exe")
    tectonic_cmd = None
    if config.TECTONIC_BIN and os.path.isfile(config.TECTONIC_BIN):
        tectonic_cmd = config.TECTONIC_BIN
    elif os.path.isfile(local_tectonic):
        tectonic_cmd = local_tectonic
    else:
        tectonic_cmd = shutil.which("tectonic") or shutil.which("tectonic.exe")

    if not tectonic_cmd:
        return JSONResponse(
            {
                "status": "error",
                "message": (
                    "Tectonic compiler is not installed. Put tectonic on PATH "
                    "or set TECTONIC_BIN to the executable path."
                ),
            },
            status_code=503,
        )
'''
    )
    text = once(
        text,
        '''            capture_output=True,
            text=True,
            timeout=300
        )
''',
        '''            capture_output=True,
            text=True,
            timeout=180
        )
''',
        "local compile_pdf timeout",
    )
    return text

def patch_modal(text: str) -> str:
    if '"groq>=0.9.0",' not in text:
        text = once(
            text,
            '        "google-generativeai",\n',
            '        "google-generativeai",\n        "groq>=0.9.0",\n',
            "Modal Groq dependency",
        )

    text = once(
        text,
        '@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})\n@modal.fastapi_endpoint(method="POST")\nasync def generate(request: Request) -> dict:\n',
        '@app.function(image=manim_image, timeout=600, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})\n@modal.fastapi_endpoint(method="POST")\nasync def generate(request: Request) -> dict:\n',
        "Modal generate endpoint GPU",
    )
    text = once(
        text,
        '@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})\n@modal.fastapi_endpoint(method="POST")\nasync def annotate(request: Request) -> dict:\n',
        '@app.function(image=manim_image, timeout=300, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})\n@modal.fastapi_endpoint(method="POST")\nasync def annotate(request: Request) -> dict:\n',
        "Modal annotate endpoint GPU",
    )
    text = text.replace("body.get('prompt', '')", "body.get('user_prompt', '')")

    text = once(
        text,
        '''    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "pdf_b64": pdf_b64,
        "error_message": final_job.error_message,
        "step": final_job.step,
        "progress_percentage": final_job.progress_percentage,
    }
''',
        '''    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "pdf_b64": pdf_b64,
        "raw_transcription": final_job.raw_transcription,
        "structured_latex": final_job.structured_latex,
        "final_tex_code": final_job.final_tex_code,
        "latex_code": final_job.final_tex_code or final_job.structured_latex or "",
        "error_message": final_job.error_message,
        "step": final_job.step,
        "progress_percentage": final_job.progress_percentage,
    }
''',
        "Modal LaTeX result parity",
    )
    text = once(
        text,
        '''            "pdf_b64": job.get("pdf_b64"),
            "error_message": job.get("error_message"),
''',
        '''            "pdf_b64": job.get("pdf_b64"),
            "raw_transcription": job.get("raw_transcription"),
            "structured_latex": job.get("structured_latex"),
            "final_tex_code": job.get("final_tex_code"),
            "latex_code": job.get("latex_code"),
            "error_message": job.get("error_message"),
''',
        "Modal LaTeX status parity",
    )
    text = once(
        text,
        '''    return {
        "job_id": target_id,
        "status": "processing",
        "current_stage": "pipeline",
        "video_url": None,
        "error_message": None,
        "cache_hit": False,
    }
''',
        '''    return {
        "job_id": target_id,
        "status": "error",
        "current_stage": "not_found",
        "video_url": None,
        "error_message": "Job not found",
        "cache_hit": False,
    }
''',
        "Modal unknown video job",
    )
    return text


def patch_canvas_view(text: str) -> str:
    return once(
        text,
        "self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)",
        "self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)",
        "canvas viewport repaint mode",
    )


def patch_canvas_scene(text: str) -> str:
    text = once(
        text,
        '''        # Freehand Lasso Tool State
        self._lasso_path_item = None
        self._lasso_points = []
''',
        '''        # Freehand Lasso Tool State
        self._lasso_path_item = None
        self._lasso_points = []
        self._lasso_painter_path = None
''',
        "lasso painter state",
    )
    text = once(
        text,
        '''            self._lasso_points = [(pos.x(), pos.y())]
            path = QPainterPath()
            path.moveTo(pos)
            self._lasso_path_item = QGraphicsPathItem()
''',
        '''            self._lasso_points = [(pos.x(), pos.y())]
            self._lasso_painter_path = QPainterPath()
            self._lasso_painter_path.moveTo(pos)
            self._lasso_path_item = QGraphicsPathItem()
''',
        "lasso press path",
    )
    text = once(
        text,
        '''            self._lasso_path_item.setBrush(QBrush(QColor(59, 130, 246, 25)))
            self._lasso_path_item.setPath(path)
            self._lasso_path_item.setZValue(9998)
''',
        '''            self._lasso_path_item.setBrush(QBrush(QColor(59, 130, 246, 25)))
            self._lasso_path_item.setPath(self._lasso_painter_path)
            self._lasso_path_item.setZValue(9998)
''',
        "lasso press setPath",
    )
    text = once(
        text,
        '''        elif self.active_tool == "lasso" and self._lasso_path_item and self._lasso_points:
            self._lasso_points.append((pos.x(), pos.y()))
            path = QPainterPath()
            path.moveTo(QPointF(self._lasso_points[0][0], self._lasso_points[0][1]))
            for pt in self._lasso_points[1:]:
                path.lineTo(QPointF(pt[0], pt[1]))
            self._lasso_path_item.setPath(path)
            event.accept()
''',
        '''        elif self.active_tool == "lasso" and self._lasso_path_item and self._lasso_points:
            self._lasso_points.append((pos.x(), pos.y()))
            if self._lasso_painter_path is None:
                self._lasso_painter_path = QPainterPath()
                self._lasso_painter_path.moveTo(pos)
            else:
                # O(1) incremental update instead of rebuilding the full path every mouse event.
                self._lasso_painter_path.lineTo(pos)
            self._lasso_path_item.setPath(self._lasso_painter_path)
            event.accept()
''',
        "lasso O(n^2) mouse move",
    )
    text = once(
        text,
        '''            self._lasso_path_item = None
            
            if len(self._lasso_points) >= 3:
''',
        '''            self._lasso_path_item = None
            self._lasso_painter_path = None
            
            if len(self._lasso_points) >= 3:
''',
        "lasso release cleanup",
    )

    marker = '''                    self._recent_ink_strokes.append(final_item)
                    if self.auto_ai_enabled:
'''
    replacement = '''                    self._recent_ink_strokes.append(final_item)
                    self._recent_ink_strokes = [
                        s for s in self._recent_ink_strokes if s.scene() == self
                    ][-80:]
                    if self.auto_ai_enabled:
'''
    n = text.count(marker)
    if n < 1:
        raise PatchError("recent ink append marker not found")
    text = text.replace(marker, replacement)
    return text


def patch_main_window(text: str) -> str:
    text = once(text, "_AUTOSAVE_DELAY_MS = 1000", "_AUTOSAVE_DELAY_MS = 2500", "autosave debounce")
    text = once(
        text,
        '''            if hasattr(self, 'notebooks_panel'):
                self.notebooks_panel.refresh()
''',
        '''            # Rebuilding the notebook panel every autosave causes visible stalls.
            if manual and hasattr(self, 'notebooks_panel'):
                self.notebooks_panel.refresh()
''',
        "autosave notebook panel refresh",
    )
    text = once(
        text,
        '            item_data = {"item_id": str(id(item)), "type": type(item).__name__}\n',
        '''            item_data = {
                "item_id": str(getattr(item, "item_id", id(item))),
                "type": type(item).__name__,
            }
''',
        "persistent selection IDs",
    )
    text = once(
        text,
        '''        job_id = request_video_generation(prompt_text, selection_payload=selection_payload)

        if hasattr(self, 'speedometer_widget'):
''',
        '''        try:
            job_id = request_video_generation(prompt_text, selection_payload=selection_payload)
        except Exception as exc:
            QMessageBox.warning(self, "Video Generation Error", f"Could not submit video generation:\\n{exc}")
            return

        if hasattr(self, 'speedometer_widget'):
''',
        "selection video error handling",
    )
    text = once(
        text,
        '''    def _on_generate_video_requested(self, selected_text: str):
        job_id = request_video_generation(selected_text)
        
        if hasattr(self, 'speedometer_widget'):
''',
        '''    def _on_generate_video_requested(self, selected_text: str):
        try:
            job_id = request_video_generation(selected_text)
        except Exception as exc:
            QMessageBox.warning(self, "Video Generation Error", f"Could not submit video generation:\\n{exc}")
            return
        
        if hasattr(self, 'speedometer_widget'):
''',
        "text video error handling",
    )
    text = once(
        text,
        '''        job_id = request_video_generation(
            selected_text="Explain this document.", 
            pdf_path=pdf_path,
            page_range=page_range,         
            emphasis_note=emphasis,       
            output_type=out_type,
            subject_id=current_subject or ""
        )
''',
        '''        try:
            job_id = request_video_generation(
                selected_text="Explain this document.",
                pdf_path=pdf_path,
                page_range=page_range,
                emphasis_note=emphasis,
                output_type=out_type,
                subject_id=current_subject or "",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Video Generation Error", f"Could not submit document video generation:\\n{exc}")
            return
''',
        "PDF video error handling",
    )
    return text


def patch_notebook_storage(text: str) -> str:
    return once(
        text,
        '''        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as err:
            print(f"[NotebookStorage] ERROR writing notebook {notebook_id} to disk: {err}")
            traceback.print_exc()
            raise
''',
        '''        tmp_path = file_path + ".tmp"
        try:
            # Large boards contain thousands of stroke points and sometimes base64 images.
            # Compact JSON cuts autosave allocations and disk I/O substantially.
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp_path, file_path)
        except Exception as err:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            print(f"[NotebookStorage] ERROR writing notebook {notebook_id} to disk: {err}")
            traceback.print_exc()
            raise
''',
        "compact atomic notebook autosave",
    )


def patch_latex_editor(text: str) -> str:
    pairs = [
        ("PDF Page Live Preview (Pure Black & White):", "Approximate Preview (compiled PDF may differ):"),
        ("self.preview_browser.setOpenExternalLinks(True)", "self.preview_browser.setOpenExternalLinks(False)"),
        ("self._update_timer.setInterval(300)", "self._update_timer.setInterval(600)"),
        ("PDF Document Live Preview • Pure Black & White Render", "Approximate HTML Preview • Export uses real Tectonic compilation"),
        ("Page 1 of 1 • PDF Preview Mode (Uncompiled)", "Approximate Preview • Not the compiled PDF"),
    ]
    for old, new in pairs:
        if old not in text:
            raise PatchError(f"LaTeX editor snippet missing: {old}")
        text = text.replace(old, new, 1)
    return once(
        text,
        '''    def confirm_close(self) -> bool:
        if not self.is_dirty and not self.editor.toPlainText().strip():
            return True
''',
        '''    def confirm_close(self) -> bool:
        if not self.is_dirty:
            return True
''',
        "LaTeX editor clean close",
    )


def patch_backend_test(text: str) -> str:
    return once(
        text,
        '''    def test_mathtex_banned(self):
        code = self._minimal_valid().replace("Text(", "MathTex(", 1)
        passed, err = self._validate(code)
        assert not passed
        assert "Stage0" in err
        assert "MathTex" in err
''',
        '''    def test_mathtex_allowed_by_static_policy(self):
        from backend.ci.pipeline import _static_analysis
        code = self._minimal_valid().replace('Text("Test"', 'MathTex("x^2"')
        passed, err = _static_analysis(code)
        assert passed, err
''',
        "outdated MathTex regression test",
    )


def apply_patch(root: Path, package: Path, run_tests: bool) -> None:
    head = run_git("rev-parse", "HEAD")
    if head != EXPECTED_HEAD:
        print(f"[warning] HEAD {head} differs from reviewed base {EXPECTED_HEAD}.")
        print("          Strict snippet checks will abort rather than guess.")
    if run_git("status", "--porcelain"):
        raise PatchError("Working tree is not clean. Commit or stash your changes first.")

    backup_dir = root / ".git" / f"kestrel_rescue_backup_{time.strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for rel in OVERLAY_FILES:
        src = package / "overlay" / rel
        if not src.exists():
            raise PatchError(f"Overlay missing: {src}")
        put(root, backup_dir, rel, src.read_text(encoding="utf-8"))

    mutate(root, backup_dir, "backend/requirements.txt", patch_requirements)
    mutate(root, backup_dir, "backend/local_server.py", patch_local_server)
    mutate(root, backup_dir, "backend/modal_app.py", patch_modal)
    mutate(root, backup_dir, "backend/video_generation/agents/scene_compile_agent.py", patch_scene_compile)
    mutate(root, backup_dir, "backend/ci/pipeline.py", patch_ci)
    mutate(root, backup_dir, "backend/video_generation/graph.py", patch_graph)
    mutate(root, backup_dir, "backend/video_generation/agents/storyboard_agent.py", patch_storyboard)
    mutate(root, backup_dir, "app/ui/canvas_view.py", patch_canvas_view)
    mutate(root, backup_dir, "app/ui/canvas_scene.py", patch_canvas_scene)
    mutate(root, backup_dir, "app/ui/main_window.py", patch_main_window)
    mutate(root, backup_dir, "app/storage/notebook_storage.py", patch_notebook_storage)
    mutate(root, backup_dir, "app/ui/widgets/latex_editor_widget.py", patch_latex_editor)
    mutate(root, backup_dir, "backend/tests/test_video_pipeline.py", patch_backend_test)

    # This was a one-off Antigravity migration helper. The migration is already applied.
    dead = root / "fix_items.py"
    if dead.exists():
        backup(root, backup_dir, "fix_items.py")
        dead.unlink()

    print(f"[ok] Applied. Backups are in {backup_dir}")
    print(run_git("status", "--short"))

    print("\n[check] Python syntax compilation...")
    p = subprocess.run([sys.executable, "-m", "compileall", "-q", "app", "backend"])
    if p.returncode:
        raise PatchError("compileall failed; do not commit yet")

    if run_tests:
        print("\n[check] Focused regression tests...")
        p = subprocess.run([
            sys.executable, "-m", "pytest", "-q",
            "tests/test_stabilization_contracts.py",
            "tests/test_whiteboard_video_foundations.py",
            "backend/tests/test_video_pipeline.py",
        ])
        if p.returncode:
            raise PatchError("Focused tests failed; inspect before committing")


def check_only(root: Path) -> None:
    print("HEAD:", run_git("rev-parse", "HEAD"))
    print("Reviewed base:", EXPECTED_HEAD)
    clean = not bool(run_git("status", "--porcelain"))
    print("Working tree clean:", clean)
    if not clean:
        raise PatchError("Working tree is not clean; stash/commit before rescue patch")

    checks = [
        ("backend/requirements.txt", patch_requirements),
        ("backend/local_server.py", patch_local_server),
        ("backend/modal_app.py", patch_modal),
        ("backend/video_generation/agents/scene_compile_agent.py", patch_scene_compile),
        ("backend/ci/pipeline.py", patch_ci),
        ("backend/video_generation/graph.py", patch_graph),
        ("backend/video_generation/agents/storyboard_agent.py", patch_storyboard),
        ("app/ui/canvas_view.py", patch_canvas_view),
        ("app/ui/canvas_scene.py", patch_canvas_scene),
        ("app/ui/main_window.py", patch_main_window),
        ("app/storage/notebook_storage.py", patch_notebook_storage),
        ("app/ui/widgets/latex_editor_widget.py", patch_latex_editor),
        ("backend/tests/test_video_pipeline.py", patch_backend_test),
    ]
    for rel, fn in checks:
        path = root / rel
        if not path.exists():
            raise PatchError(f"Missing required file: {rel}")
        fn(path.read_text(encoding="utf-8"))
        print(f"  compatible: {rel}")
    print("Strict patch compatibility check: passed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if not args.check and not args.apply:
        ap.error("choose --check or --apply")

    try:
        root = get_root()
        package = Path(__file__).resolve().parent
        if args.check:
            check_only(root)
        if args.apply:
            apply_patch(root, package, args.test)
        return 0
    except PatchError as exc:
        print(f"[patch-error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
