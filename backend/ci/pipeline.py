"""
CIPipelineHarness — 5-stage Manim code validation.

Stage 0 (NEW): Static structural analysis — detects banned APIs, unreadable text,
               missing self.wait(), excessive text length before running any subprocess.
Stage 1: Python syntax check (py_compile)
Stage 2: Import/exec check + MainScene class detection
Stage 3: Manim --dry_run CLI scene graph check
Stage 4: Low-quality frame-0 smoke render (catches runtime/LaTeX errors)

Each stage returns a structured, actionable error message including:
  - Stage number and category
  - The specific problem found
  - A fix suggestion for CodeGenAgent retry
"""

import os
import re
import sys
import ast
import py_compile
import subprocess
import tempfile
from typing import Tuple

try:
    import manim
    MANIM_AVAILABLE = True
except ImportError:
    MANIM_AVAILABLE = False


# ── Stage 0 checks ────────────────────────────────────────────────────────────

_BANNED_APIS = [
    ("MathTex(", "MathTex is not supported — replace with Text()"),
    ("Tex(", "Tex is not supported — replace with Text()"),
    ("time.sleep(", "time.sleep() blocks the renderer — remove it"),
    ("while True", "Infinite loop detected — remove the while loop"),
    ("input(", "input() call detected — remove it"),
    ("import requests", "Network calls not allowed — remove import requests"),
    ("import urllib", "Network calls not allowed — remove import urllib"),
]

_MIN_FONT_SIZE = 16
_MAX_FONT_SIZE = 80
_MAX_TEXT_CHARS = 80   # max chars in a single Text("...") argument


def _static_analysis(code: str) -> Tuple[bool, str]:
    """
    Stage 0: Fast static checks without running any subprocess.
    Returns (passed, error_message).
    """
    lines = code.splitlines()

    # ── Check 1: Banned APIs ────────────────────────────────────────────────
    for pattern, suggestion in _BANNED_APIS:
        for i, line in enumerate(lines, 1):
            if pattern in line and not line.strip().startswith("#"):
                return False, (
                    f"[Stage0] Banned API on line {i}: '{pattern.strip()}'\n"
                    f"Fix: {suggestion}\n"
                    f"Line: {line.strip()}"
                )

    # ── Check 2: Unreadable font sizes ─────────────────────────────────────
    font_size_pattern = re.compile(r'font_size\s*=\s*(\d+)')
    for i, line in enumerate(lines, 1):
        m = font_size_pattern.search(line)
        if m:
            size = int(m.group(1))
            if size < _MIN_FONT_SIZE:
                return False, (
                    f"[Stage0] Unreadable font_size={size} on line {i}. "
                    f"Minimum is {_MIN_FONT_SIZE}. Fix: increase font_size to at least 20."
                )
            if size > _MAX_FONT_SIZE:
                return False, (
                    f"[Stage0] Oversized font_size={size} on line {i}. "
                    f"Maximum is {_MAX_FONT_SIZE}. Fix: reduce font_size to 36-48 for titles, 20-28 for body."
                )

    # ── Check 3: Excessively long text strings ──────────────────────────────
    text_str_pattern = re.compile(r'Text\s*\(\s*["\'](.+?)["\']')
    for i, line in enumerate(lines, 1):
        m = text_str_pattern.search(line)
        if m:
            text_content = m.group(1)
            if len(text_content) > _MAX_TEXT_CHARS:
                return False, (
                    f"[Stage0] Text string too long ({len(text_content)} chars) on line {i}. "
                    f"Maximum is {_MAX_TEXT_CHARS} chars per Text() call. "
                    f"Fix: break into multiple lines using \\n or split into separate Text() objects."
                )

    # ── Check 4: No self.wait() at all → scene plays too fast ──────────────
    has_wait = any("self.wait(" in line for line in lines)
    if not has_wait:
        return False, (
            "[Stage0] No self.wait() calls found. "
            "The animation will play too fast to understand. "
            "Fix: add self.wait(1.5) to self.wait(3) between major animation steps."
        )

    # ── Check 5: MainScene class present ───────────────────────────────────
    if "class MainScene" not in code:
        return False, (
            "[Stage0] Class 'MainScene' not found. "
            "Fix: define exactly one class named MainScene(Scene) with a construct(self) method."
        )

    # ── Check 6: Dangerous CYAN color constant ─────────────────────────────
    # CYAN is undefined in some Manim CE versions
    if re.search(r'\bCYAN\b', code):
        return False, (
            "[Stage0] CYAN color constant is not available in all Manim CE versions. "
            "Fix: replace CYAN with TEAL or BLUE."
        )

    return True, ""


class CIPipelineHarness:
    """
    5-stage CI harness for Manim code validation.

    Stage 0: Static structural analysis  — fast, no subprocess
    Stage 1: Python syntax check          — py_compile
    Stage 2: Import/exec check            — exec() or AST
    Stage 3: Manim --dry_run CLI          — scene graph construction
    Stage 4: Low-quality frame-0 render   — runtime/LaTeX errors
    """

    def validate_code(self, manim_code: str, scene_name: str = "MainScene") -> Tuple[bool, str]:
        if not manim_code or not manim_code.strip():
            return False, "[Stage0] Empty Manim code string provided."

        # ── Stage 0: Static analysis ──────────────────────────────────────────
        passed, err = _static_analysis(manim_code)
        if not passed:
            print(f"[CI Stage 0] Static analysis failed: {err[:100]}")
            return False, err

        with tempfile.TemporaryDirectory(prefix="manim_ci_") as temp_dir:
            file_path = os.path.join(temp_dir, "test_scene.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(manim_code)

            # ── Stage 1: Syntax check ─────────────────────────────────────────
            try:
                py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"[Stage1] Syntax Error: {e.msg}\nFix: correct the Python syntax error above."
            except Exception as e:
                return False, f"[Stage1] Syntax Verification Error: {str(e)}"

            # ── Stage 2: Runtime/import check ────────────────────────────────
            if MANIM_AVAILABLE:
                try:
                    exec_globals = {}
                    exec(manim_code, exec_globals)
                    if scene_name not in exec_globals:
                        return False, (
                            f"[Stage2] Class `{scene_name}` not found. "
                            f"Fix: define exactly one class named {scene_name}(Scene)."
                        )
                except Exception as e:
                    return False, (
                        f"[Stage2] Import/Runtime Error: {type(e).__name__}: {str(e)}\n"
                        f"Fix: check the error above and correct the offending code."
                    )
            else:
                # AST-only check when manim is not installed
                try:
                    tree = ast.parse(manim_code)
                    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    if scene_name not in class_names:
                        return False, f"[Stage2] Class `{scene_name}` not found. Fix: define class {scene_name}(Scene)."
                except SyntaxError as e:
                    return False, f"[Stage2] AST Parse Error: {str(e)}"

            # ── Stage 3: Manim --dry_run CLI ──────────────────────────────────
            if MANIM_AVAILABLE:
                try:
                    cmd = [
                        sys.executable, "-m", "manim", "render",
                        "-ql", "-v", "WARNING", "--dry_run",
                        file_path, scene_name
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                    if result.returncode != 0:
                        clean_stderr = _clean_manim_stderr(result.stderr)
                        error_line = _extract_python_error(clean_stderr)
                        return False, (
                            f"[Stage3] Manim Dry Run Error:\n{error_line or clean_stderr[-2000:]}\n"
                            f"Fix: correct the animation code causing this error."
                        )
                except subprocess.TimeoutExpired:
                    return False, (
                        "[Stage3] Dry run timed out (>45s). "
                        "Fix: remove infinite loops, time.sleep(), or input() calls."
                    )
                except FileNotFoundError:
                    print("[CI Stage3] Manim CLI not found — skipping dry run.")
                except Exception as e:
                    return False, f"[Stage3] Dry Run Execution Failed: {str(e)}"

            # ── Stage 4: Smoke render (frame-0) ──────────────────────────────
            if MANIM_AVAILABLE:
                try:
                    smoke_media_dir = os.path.join(temp_dir, "smoke_media")
                    os.makedirs(smoke_media_dir, exist_ok=True)
                    cmd = [
                        sys.executable, "-m", "manim", "render",
                        "-ql", "-v", "WARNING",
                        "--media_dir", smoke_media_dir,
                        "-s",   # snapshot last frame (fast)
                        file_path, scene_name,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                    if result.returncode != 0:
                        stderr = result.stderr or result.stdout or "Unknown smoke-render error"
                        clean_stderr = _clean_manim_stderr(stderr)
                        error_line = _extract_python_error(clean_stderr)
                        return False, (
                            f"[Stage4] Smoke Render Failed:\n{error_line or clean_stderr[-2000:]}\n"
                            f"Fix: correct the runtime error above. It occurs during actual scene construction."
                        )
                except FileNotFoundError:
                    print("[CI Stage4] Manim CLI not found — skipping smoke render.")
                except subprocess.TimeoutExpired:
                    return False, (
                        "[Stage4] Smoke render timed out (>90s). "
                        "Fix: simplify the animation — use fewer objects or shorter animations."
                    )
                except Exception as e:
                    return False, f"[Stage4] Smoke Render Execution Error: {str(e)}"

        return True, ""


def _clean_manim_stderr(stderr: str) -> str:
    """Filter out tqdm progress bar noise from Manim stderr."""
    lines = [l for l in stderr.splitlines() if not ("|" in l and "%" in l and "it/s" in l)]
    return "\n".join(lines)


def _extract_python_error(stderr: str) -> str:
    """Extract the most relevant error line(s) from Manim/Python stderr."""
    error_lines = [
        l for l in stderr.splitlines()
        if any(kw in l for kw in ["Error", "error", "Exception", "Traceback", "line "])
    ]
    return "\n".join(error_lines[:6]) if error_lines else ""
