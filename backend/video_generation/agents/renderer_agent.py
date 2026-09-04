"""
RendererAgent — Two-stage Manim rendering with reliable temp directory cleanup.

Improvements over v1:
  - Two-stage render: fast validation render (-ql, 480p) → production render (-qm, 720p)
  - Final video moved to persistent workspace/videos/ before temp dir cleanup
  - Temp directories always cleaned up via try/finally (no more disk leaks)
  - Improved error message extraction: shows Python exception type + line, not raw Manim log
  - Records render_quality on the job for traceability
"""

import os
import sys
import shutil
import subprocess
import tempfile
from backend.video_generation.models import VideoJob, JobStatus

from backend.workspace.artifact_store import artifact_store


def _nvenc_available() -> bool:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if result.returncode != 0:
            return False
        ffmpeg_check = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        return "h264_nvenc" in ffmpeg_check.stdout
    except Exception:
        return False


_GPU_ENCODE = _nvenc_available()
if _GPU_ENCODE:
    print("[RendererAgent] GPU detected — using h264_nvenc encoder (3-5x faster encode)")
else:
    print("[RendererAgent] No GPU encoder — using libx264 CPU encoder")


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        return ffmpeg_exe
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def _find_mp4(media_dir: str) -> str | None:
    """Walk media_dir and return the first non-partial .mp4 file found."""
    for root, dirs, files in os.walk(media_dir):
        # Skip partial/temp movie subdirs
        dirs[:] = [d for d in dirs if "partial" not in d.lower()]
        for f in files:
            if f.endswith(".mp4"):
                return os.path.join(root, f)
    return None


def _clean_stderr(stderr: str) -> str:
    """Remove tqdm progress bar noise."""
    return "\n".join(
        l for l in (stderr or "").splitlines()
        if not ("|" in l and "%" in l and "it/s" in l)
    )


def _extract_error(stderr: str, stdout: str = "") -> str:
    """Extract the most meaningful error message from Manim's output."""
    combined = _clean_stderr(stderr) + "\n" + (stdout or "")
    lines = combined.splitlines()
    # Python exceptions first
    error_lines = [l for l in lines if any(
        kw in l for kw in ["Error:", "Exception:", "Traceback", "line "]
    )]
    if error_lines:
        return "\n".join(error_lines[:6])
    # Fall back to last 800 chars of cleaned stderr
    return combined[-800:].strip()


def _reencode(src: str, dst: str) -> bool:
    """Re-encode with FFmpeg for browser compatibility. Returns True on success."""
    encoder = "h264_nvenc" if _GPU_ENCODE else "libx264"
    ffmpeg = _get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", src,
        "-c:v", encoder,
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        dst,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(dst):
            print(f"[RendererAgent] Re-encoded with {encoder}: {dst}")
            return True
        print(f"[RendererAgent] Re-encode failed ({encoder}): {result.stderr[:150]}")
        return False
    except Exception as e:
        print(f"[RendererAgent] FFmpeg re-encode skipped ({e}) — using raw Manim output")
        return False


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
                
            # Determine scene names
            scene_names = ["MainScene"]
            if job.scene_specs:
                if len(job.scene_specs) == 1:
                    scene_names = ["MainScene"]
                else:
                    scene_names = []
                    for idx, s in enumerate(job.scene_specs):
                        safe_id = "".join(c if c.isalnum() else "_" for c in s.scene_id) or str(idx)
                        scene_names.append(f"Scene_{safe_id}")
            
            rendered_mp4s = []
            job.render_quality = "medium" if job.retry_count == 0 else "low"

            for scene_name in scene_names:
                print(f"[RendererAgent] Stage A: fast validation render (-ql) for {scene_name}")
                ql_media = os.path.join(temp_dir, f"media_ql_{scene_name}")
                ok, mp4 = self._manim_render(script_path, ql_media, quality="-ql", timeout=120, scene_name=scene_name)

                if not ok or not mp4:
                    err = _extract_error(mp4 or "")  # mp4 is error string when ok=False
                    job.status = JobStatus.ERROR
                    job.error_message = f"Animation rendering failed for {scene_name}.\n{err[:400]}"
                    print(f"[RendererAgent] Stage A failed for {scene_name}: {err[:150]}")
                    return job

                final_mp4 = mp4
                if job.retry_count == 0:
                    print(f"[RendererAgent] Stage B: production render (-qm) for {scene_name}")
                    qm_media = os.path.join(temp_dir, f"media_qm_{scene_name}")
                    ok_prod, mp4_prod = self._manim_render(script_path, qm_media, quality="-qm", timeout=240, scene_name=scene_name)
                    if ok_prod and mp4_prod:
                        final_mp4 = mp4_prod
                        print(f"[RendererAgent] Production render succeeded for {scene_name}")
                    else:
                        print(f"[RendererAgent] Production render failed for {scene_name} — using fast render output")
                        job.render_quality = "low"
                
                rendered_mp4s.append(final_mp4)

            # If there's only one video, use it. If multiple, we need to stitch them.
            persistent_path = os.path.join(_VIDEOS_DIR, f"{job.job_id}_v{job.version}.mp4")
            if len(rendered_mp4s) == 1:
                final_output = rendered_mp4s[0]
            else:
                # Concatenate with FFmpeg
                concat_list = os.path.join(temp_dir, "concat.txt")
                with open(concat_list, "w", encoding="utf-8") as f:
                    for mp4 in rendered_mp4s:
                        f.write(f"file '{mp4.replace(chr(92), '/')}'\n")
                
                stitched_mp4 = os.path.join(temp_dir, "stitched.mp4")
                ffmpeg = _get_ffmpeg()
                cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", stitched_mp4]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=60, check=True)
                    final_output = stitched_mp4
                except subprocess.CalledProcessError as e:
                    print(f"[RendererAgent] FFmpeg concat failed: {e}")
                    final_output = rendered_mp4s[0]  # Fallback to first scene

            # ── FFmpeg re-encode for browser compatibility ─────────────────────
            # Save the file to artifact store
            dest_key = f"v{job.version}.mp4"
            if _reencode(final_output, final_output + ".reencoded.mp4"):
                persistent_path = artifact_store.put(job.job_id, dest_key, final_output + ".reencoded.mp4")
            else:
                persistent_path = artifact_store.put(job.job_id, dest_key, final_output)
            
            job.video_path = persistent_path
            print(f"[RendererAgent] Saved video to artifact store: {persistent_path}")

            return job

        except Exception as e:
            print(f"[RendererAgent] Unexpected exception: {e}")
            job.status = JobStatus.ERROR
            job.error_message = f"Rendering failed unexpectedly: {type(e).__name__}: {str(e)[:200]}"
            return job

        finally:
            # Always clean up temp dir, even on error
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"[RendererAgent] Cleaned up temp dir: {temp_dir}")
            except Exception as cleanup_err:
                print(f"[RendererAgent] Temp dir cleanup failed: {cleanup_err}")

    def _manim_render(
        self, script_path: str, media_dir: str, quality: str = "-ql", timeout: int = 180, scene_name: str = "MainScene"
    ) -> tuple[bool, str]:
        """
        Run manim render and return (success, mp4_path_or_error_message).
        """
        os.makedirs(media_dir, exist_ok=True)
        cmd = [
            sys.executable, "-m", "manim", "render",
            quality,
            "--media_dir", media_dir,
            script_path, scene_name
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"Render timed out after {timeout}s. Simplify the animation."


        if result.returncode != 0:
            return False, _extract_error(result.stderr, result.stdout)

        mp4 = _find_mp4(media_dir)
        if not mp4:
            return False, "Manim finished but no .mp4 output file was found."

        return True, mp4
