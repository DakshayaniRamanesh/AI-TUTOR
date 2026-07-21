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
    def validate_code(self, manim_code: str, scene_name: str = "MainScene") -> Tuple[bool, str]:
        if not manim_code or not manim_code.strip():
            return False, "Code compilation error: Empty Manim code string provided."

        with tempfile.TemporaryDirectory(prefix="manim_ci_") as temp_dir:
            file_path = os.path.join(temp_dir, "test_scene.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(manim_code)

            # Stage 1: Syntax check with py_compile
            try:
                py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"Syntax Error: {e.msg}"
            except Exception as e:
                return False, f"Syntax Verification Error: {str(e)}"

            # Stage 2: Runtime/import check — only if manim is installed locally
            if MANIM_AVAILABLE:
                try:
                    exec_globals = {}
                    exec(manim_code, exec_globals)
                    if scene_name not in exec_globals:
                        return False, f"Structure Error: Scene class `{scene_name}` not found in generated code."
                except Exception as e:
                    return False, f"Import/Runtime Error: {str(e)}"
            else:
                # Manim not installed locally — do a lightweight AST-only class name check
                import ast
                try:
                    tree = ast.parse(manim_code)
                    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    if scene_name not in class_names:
                        return False, f"Structure Error: Scene class `{scene_name}` not found in generated code."
                except SyntaxError as e:
                    return False, f"AST Parse Error: {str(e)}"

            # Stage 3: Manim dry run CLI check — only if manim CLI available
            if MANIM_AVAILABLE:
                try:
                    cmd = ["manim", "render", "--dry_run", file_path, scene_name]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        return False, f"Manim Dry Run Error:\n{result.stderr}"
                except FileNotFoundError:
                    print("[CIPipelineHarness] Manim CLI not found. Skipping stage 3 dry-run CLI check.")
                except Exception as e:
                    return False, f"Manim Dry Run Execution Failed: {str(e)}"

            return True, ""

