import os
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
                                                         during actual rendering (NEW)
    """

    def validate_code(self, manim_code: str, scene_name: str = "MainScene") -> Tuple[bool, str]:
        if not manim_code or not manim_code.strip():
            return False, "Code compilation error: Empty Manim code string provided."

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
                    if scene_name not in exec_globals:
                        return False, f"[Stage2] Structure Error: Scene class `{scene_name}` not found in generated code."
                except Exception as e:
                    return False, f"[Stage2] Import/Runtime Error: {str(e)}"
            else:
                # Manim not installed locally — lightweight AST-only class name check
                import ast
                try:
                    tree = ast.parse(manim_code)
                    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    if scene_name not in class_names:
                        return False, f"[Stage2] Structure Error: Scene class `{scene_name}` not found in generated code."
                except SyntaxError as e:
                    return False, f"[Stage2] AST Parse Error: {str(e)}"

            # ── Stage 3: Manim --dry_run CLI scene graph check ────────────────────
            if MANIM_AVAILABLE:
                try:
                    cmd = ["manim", "render", "--dry_run", file_path, scene_name]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        return False, f"[Stage3] Manim Dry Run Error:\n{result.stderr}"
                except FileNotFoundError:
                    print("[CIPipelineHarness] Manim CLI not found. Skipping stage 3 dry-run CLI check.")
                except Exception as e:
                    return False, f"[Stage3] Manim Dry Run Execution Failed: {str(e)}"

            # ── Stage 4 (NEW): Low-quality frame-0 smoke render ───────────────────
            # Renders only the very first frame at lowest quality (-ql -s 0).
            # This is the only stage that catches runtime errors such as:
            #   - LaTeX compilation failures inside MathTex()
            #   - Incorrect .animate attribute calls
            #   - Bad Mobject references that only fail during scene construction
            # It is fast (~3-10s) compared to a full render (~60-300s on GPU).
            if MANIM_AVAILABLE:
                try:
                    smoke_media_dir = os.path.join(temp_dir, "smoke_media")
                    os.makedirs(smoke_media_dir, exist_ok=True)
                    cmd = [
                        "manim", "render", "-ql",
                        "--media_dir", smoke_media_dir,
                        "-s",   # save last frame (renders only the first frame snapshot)
                        file_path,
                        scene_name,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    if result.returncode != 0:
                        stderr = result.stderr or result.stdout or "Unknown smoke-render error"
                        # Extract the most relevant error line from LaTeX / Manim output
                        error_lines = [l for l in stderr.splitlines() if "Error" in l or "error" in l or "Exception" in l]
                        condensed = "\n".join(error_lines[:5]) if error_lines else stderr[-800:]
                        return False, f"[Stage4] Smoke Render Failed (LaTeX/Runtime Error):\n{condensed}"
                except FileNotFoundError:
                    print("[CIPipelineHarness] Manim CLI not found. Skipping stage 4 smoke render.")
                except subprocess.TimeoutExpired:
                    return False, "[Stage4] Smoke Render Timeout: frame-0 render exceeded 60s limit."
                except Exception as e:
                    return False, f"[Stage4] Smoke Render Execution Error: {str(e)}"

            return True, ""

