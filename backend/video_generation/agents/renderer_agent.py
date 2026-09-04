"""
RendererAgent — one authoritative render of MainScene.

CI already performs construction/smoke validation. Re-rendering every SceneSpec
at low quality and then again at medium quality made the pipeline slow and, in
the previous refactor, introduced an undefined _VIDEOS_DIR crash plus fragile
FFmpeg concatenation. SceneCompileAgent now emits one complete MainScene.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from backend.video_generation.models import JobStatus, VideoJob
from backend.workspace.artifact_store import artifact_store


def _find_mp4(media_dir: str) -> str | None:
    candidates: list[str] = []
    for root, dirs, filenames in os.walk(media_dir):
        dirs[:] = [d for d in dirs if "partial" not in d.lower()]
        for filename in filenames:
            if filename.lower().endswith(".mp4"):
                candidates.append(os.path.join(root, filename))
    if not candidates:
        return None
    # Prefer the newest final output when Manim leaves more than one file.
    return max(candidates, key=os.path.getmtime)


def _clean_stderr(stderr: str) -> str:
    return "\n".join(
        line
        for line in (stderr or "").splitlines()
        if not ("|" in line and "%" in line and "it/s" in line)
    )


def _extract_error(stderr: str, stdout: str = "") -> str:
    combined = (_clean_stderr(stderr) + "\n" + (stdout or "")).strip()
    lines = combined.splitlines()
    useful = [
        line
        for line in lines
        if any(k in line for k in ("Error:", "Exception:", "Traceback", "line "))
    ]
    return "\n".join(useful[:8]) if useful else combined[-1200:]


class RendererAgent:
    def run(self, job: VideoJob) -> VideoJob:
        job.step = "renderer_agent"
        job.friendly_step = "Rendering video..."
        job.progress_percentage = 85

        if not job.manim_code:
            job.status = JobStatus.ERROR
            job.error_message = "No animation code available to render."
            return job

        temp_dir = tempfile.mkdtemp(prefix=f"manim_{job.job_id}_")
        script_path = os.path.join(temp_dir, "scene.py")

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(job.manim_code)

            # CI already smoke-renders MainScene. Render production once.
            media_dir = os.path.join(temp_dir, "media_qm")
            ok, output = self._manim_render(
                script_path,
                media_dir,
                quality="-qm",
                timeout=300,
                scene_name="MainScene",
            )
            job.render_quality = "medium"

            # A production-quality failure can still be recoverable at low
            # quality; this is a single bounded fallback, not another loop.
            if not ok:
                print(f"[RendererAgent] Medium render failed; one low-quality fallback: {output[:200]}")
                low_dir = os.path.join(temp_dir, "media_ql")
                ok, output = self._manim_render(
                    script_path,
                    low_dir,
                    quality="-ql",
                    timeout=180,
                    scene_name="MainScene",
                )
                job.render_quality = "low"

            if not ok or not output:
                job.status = JobStatus.ERROR
                job.error_message = f"Animation rendering failed.\n{str(output)[:800]}"
                return job

            dest_key = f"v{job.version}.mp4"
            job.video_path = artifact_store.put(job.job_id, dest_key, output)
            print(f"[RendererAgent] Saved video: {job.video_path}")
            return job

        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = (
                f"Rendering failed unexpectedly: {type(exc).__name__}: {str(exc)[:400]}"
            )
            return job
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _manim_render(
        self,
        script_path: str,
        media_dir: str,
        quality: str = "-qm",
        timeout: int = 300,
        scene_name: str = "MainScene",
    ) -> tuple[bool, str]:
        os.makedirs(media_dir, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "manim",
            "render",
            quality,
            "-v",
            "WARNING",
            "--media_dir",
            media_dir,
            script_path,
            scene_name,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"Render timed out after {timeout}s."
        except FileNotFoundError as exc:
            return False, f"Manim executable/runtime not found: {exc}"

        if result.returncode != 0:
            return False, _extract_error(result.stderr, result.stdout)

        mp4 = _find_mp4(media_dir)
        if not mp4:
            return False, "Manim completed but produced no MP4."
        return True, mp4
