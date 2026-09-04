import os
import re
import sys
import py_compile
import subprocess
import tempfile
from typing import Tuple

# Check if manim is available locally
try:
    import manim
    MANIM_AVAILABLE = True
except ImportError:
    MANIM_AVAILABLE = False


class CIPipelineHarness:
    """
    4-stage CI harness for Manim code validation.

    Stage 1: Python syntax check (py_compile)         — catches typos, bad indentation
    Stage 2: Import/exec check                         — catches missing imports, class structure
    Stage 3: Manim --dry_run CLI                       — validates scene graph construction
    Stage 4: Low-quality frame-0 smoke render          — catches LaTeX errors, bad .animate calls,
                                                         runtime Mobject errors that only surface
                                                         during actual rendering
    """

    def _discover_scene_classes(self, manim_code: str) -> list:
        """Extract all Scene subclass names from generated Manim code."""
        classes = re.findall(r'^class\s+(\w+)\(Scene\):', manim_code, re.MULTILINE)
        return classes if classes else ["MainScene"]  # Legacy fallback

    def validate_code(self, manim_code: str, scene_name: str = None) -> Tuple[bool, str]:
        if not manim_code or not manim_code.strip():
            return False, "Code compilation error: Empty Manim code string provided."

        scene_classes = self._discover_scene_classes(manim_code)
        if scene_name:
            scene_classes = [scene_name]

        with tempfile.TemporaryDirectory(prefix="manim_ci_") as temp_dir:
            file_path = os.path.join(temp_dir, "test_scene.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(manim_code)

            # ── Stage 1: Syntax check with py_compile ─────────────────────────────
            try:
                py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"[Stage1] Syntax Error: {e.msg}"
            except Exception as e:
                return False, f"[Stage1] Syntax Verification Error: {str(e)}"

            # ── Stage 2: Runtime/import check ─────────────────────────────────────
            if MANIM_AVAILABLE:
                try:
                    exec_globals = {}
                    exec(manim_code, exec_globals)
                    for sc in scene_classes:
                        if sc not in exec_globals:
                            return False, f"[Stage2] Structure Error: Scene class `{sc}` not found in generated code."
                except Exception as e:
                    return False, f"[Stage2] Import/Runtime Error: {str(e)}"
            else:
                # Manim not installed locally — lightweight AST-only class name check
                import ast
                try:
                    tree = ast.parse(manim_code)
                    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    for sc in scene_classes:
                        if sc not in class_names:
                            return False, f"[Stage2] Structure Error: Scene class `{sc}` not found in generated code."
                except SyntaxError as e:
                    return False, f"[Stage2] AST Parse Error: {str(e)}"

            # ── Stage 3: Manim --dry_run CLI scene graph check ────────────────────
            if MANIM_AVAILABLE:
                for sc in scene_classes:
                    try:
                        cmd = [
                            sys.executable, "-m", "manim", "render",
                            "--dry_run", "--disable_caching",
                            "--renderer=cairo", "-v", "WARNING",
                            file_path, sc
                        ]
                        try:
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                        except subprocess.TimeoutExpired:
                            return False, f"[Stage3] Manim Dry Run Error ({sc}): Execution timed out. Did you use an infinite loop, time.sleep(), or input()? REMOVE THEM."
                        
                        if result.returncode != 0:
                            clean_stderr = "\n".join([l for l in result.stderr.splitlines() if not ("|" in l and "%" in l and "it/s" in l)])
                            return False, f"[Stage3] Manim Dry Run Error ({sc}):\n{clean_stderr[-3500:]}"
                    except FileNotFoundError:
                        print("[CIPipelineHarness] Manim CLI not found. Skipping stage 3 dry-run CLI check.")
                        break
                    except Exception as e:
                        return False, f"[Stage3] Manim Dry Run Execution Failed ({sc}): {str(e)}"

            # ── Stage 4: Low-quality frame-0 smoke render ─────────────────────────
            # Only smoke-test the FIRST scene class to keep CI fast.
            if MANIM_AVAILABLE and scene_classes:
                first_scene = scene_classes[0]
                try:
                    smoke_media_dir = os.path.join(temp_dir, "smoke_media")
                    os.makedirs(smoke_media_dir, exist_ok=True)
                    cmd = [
                        sys.executable, "-m", "manim", "render", "-ql", "-v", "WARNING",
                        "--renderer=cairo", "--disable_caching",
                        "--media_dir", smoke_media_dir,
                        "-s",   # save last frame only (fastest possible render)
                        file_path,
                        first_scene,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                    if result.returncode != 0:
                        stderr = result.stderr or result.stdout or "Unknown smoke-render error"
                        clean_stderr = "\n".join([l for l in stderr.splitlines() if not ("|" in l and "%" in l and "it/s" in l)])
                        error_lines = [l for l in clean_stderr.splitlines() if "Error" in l or "error" in l or "Exception" in l]
                        condensed = "\n".join(error_lines[:5]) if error_lines else clean_stderr[-3500:]
                        return False, f"[Stage4] Smoke Render Failed ({first_scene}):\n{condensed}"
                except FileNotFoundError:
                    print("[CIPipelineHarness] Manim CLI not found. Skipping stage 4 smoke render.")
                except subprocess.TimeoutExpired:
                    return False, f"[Stage4] Smoke Render Timeout ({first_scene}): frame-0 render exceeded 90s limit."
                except Exception as e:
                    return False, f"[Stage4] Smoke Render Execution Error ({first_scene}): {str(e)}"

            return True, ""
