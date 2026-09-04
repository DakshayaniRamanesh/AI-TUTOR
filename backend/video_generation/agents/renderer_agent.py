import os
import re
import subprocess
import tempfile
import sys
from backend.video_generation.models import VideoJob, JobStatus


def _nvenc_available() -> bool:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if result.returncode != 0:
            return False
        ffmpeg_check = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "h264_nvenc" in ffmpeg_check.stdout
    except Exception:
        return False


_GPU_ENCODE = _nvenc_available()
if _GPU_ENCODE:
    print("[RendererAgent] GPU encoder detected — using h264_nvenc for final encode")
else:
    print("[RendererAgent] No NVENC encoder — using libx264")


def _find_final_mp4(media_dir: str) -> str | None:
    """
    Walk media_dir and return the path of the largest .mp4 file that is NOT
    inside a partial_movie_files directory.  Largest = most likely the final
    stitched scene (Manim always writes the combined video as one big file).
    Returns None if nothing is found.
    """
    candidates = []
    for root, dirs, files in os.walk(media_dir):
        # Skip partial files directory entirely
        dirs[:] = [d for d in dirs if d != "partial_movie_files"]
        if "partial_movie_files" in root:
            continue
        for fname in files:
            if fname.endswith(".mp4"):
                full = os.path.join(root, fname)
                try:
                    size = os.path.getsize(full)
                    if size > 1000:  # must be at least ~1 KB — not a stub
                        candidates.append((size, full))
                except OSError:
                    pass
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


class RendererAgent:
    def run(self, job: VideoJob) -> VideoJob:
        job.step = "renderer_agent"
        job.progress_percentage = 85

        if not job.manim_code:
            job.status = JobStatus.ERROR
            job.error_message = "No Manim code available to render."
            return job

        temp_dir = tempfile.mkdtemp(prefix=f"manim_{job.job_id}_")
        script_path = os.path.join(temp_dir, "scene.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(job.manim_code)
        output_media_dir = os.path.join(temp_dir, "media")

        try:
            # Discover all Scene class names from the generated code
            scene_classes = re.findall(r'^class\s+(\w+)\(Scene\):', job.manim_code, re.MULTILINE)
            if not scene_classes:
                # Legacy fallback: try MainScene
                scene_classes = ["MainScene"]

            rendered_mp4s = []
            for scene_class in scene_classes:
                # Try Cairo first (most reliable, no GPU/display required)
                cmd = [
                    sys.executable, "-m", "manim", "render",
                    "-qh", "--renderer=cairo",
                    "--media_dir", output_media_dir,
                    script_path, scene_class,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    # Fallback to medium quality if high-quality Cairo failed
                    print(f"[RendererAgent] Cairo -qh failed for {scene_class} (rc={result.returncode}); retrying with -qm")
                    cmd_qm = [
                        sys.executable, "-m", "manim", "render",
                        "-qm", "--renderer=cairo",
                        "--media_dir", output_media_dir,
                        script_path, scene_class,
                    ]
                    result = subprocess.run(cmd_qm, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    print(f"[RendererAgent] Scene {scene_class} failed: {(result.stderr or '')[-500:]}")
                    continue  # Skip failed scenes rather than aborting everything

                mp4 = _find_final_mp4(output_media_dir)
                if mp4 and os.path.exists(mp4) and mp4 not in rendered_mp4s:
                    rendered_mp4s.append(mp4)

            if not rendered_mp4s:
                job.status = JobStatus.ERROR
                job.error_message = f"Manim render failed: no scenes produced output."
                return job

            # Use the last (or only) rendered mp4 as primary output
            mp4_file = rendered_mp4s[-1]
            if mp4_file and os.path.exists(mp4_file):
                # Re-encode for web compatibility (faststart for streaming)
                encoded_path = os.path.join(temp_dir, f"{job.job_id}_encoded.mp4")
                encoder = "h264_nvenc" if _GPU_ENCODE else "libx264"
                try:
                    import imageio_ffmpeg
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                except ImportError:
                    ffmpeg_exe = "ffmpeg"

                encode_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", mp4_file,
                    "-c:v", encoder,
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                ]
                if encoder == "h264_nvenc":
                    encode_cmd += ["-cq", "23"]
                else:
                    encode_cmd += ["-crf", "23"]
                encode_cmd.append(encoded_path)

                enc_result = subprocess.run(encode_cmd, capture_output=True, text=True, timeout=120)
                if enc_result.returncode == 0 and os.path.exists(encoded_path):
                    job.video_path = encoded_path
                    print(f"[RendererAgent] Re-encoded video: {encoded_path} ({os.path.getsize(encoded_path)} bytes)")
                else:
                    print(f"[RendererAgent] Re-encode failed; using raw output. ffmpeg stderr: {enc_result.stderr[:200]}")
                    job.video_path = mp4_file
                return job

            job.status = JobStatus.ERROR
            job.error_message = f"Manim render failed: rendered mp4 not found on disk."
            return job

        except Exception as e:
            print(f"[RendererAgent] Execution exception: {e}")
            job.status = JobStatus.ERROR
            job.error_message = f"Renderer exception: {str(e)}"
            return job
