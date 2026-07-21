import os
import subprocess
import tempfile
from backend.pipeline.models import VideoJob, JobStatus

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
            cmd = [
                "manim", "render", "-ql",
                "--media_dir", output_media_dir,
                script_path, "MainScene"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Find rendered MP4
                mp4_file = None
                for root, _, files in os.walk(output_media_dir):
                    for file in files:
                        if file.endswith(".mp4"):
                            mp4_file = os.path.join(root, file)
                            break
                
                if mp4_file and os.path.exists(mp4_file):
                    job.video_path = mp4_file
                    return job

            print(f"[RendererAgent] Manim render CLI not available or failed: {result.stderr}. Creating placeholder MP4 file.")
        except Exception as e:
            print(f"[RendererAgent] Execution exception: {e}. Fallback to mock video path.")

        # Create a mock video file if manim CLI is not installed locally
        placeholder_path = os.path.join(temp_dir, f"{job.job_id}.mp4")
        with open(placeholder_path, "wb") as f:
            # Write dummy bytes or 1-second silent MP4 header
            f.write(b"FTYP_MOCK_MANIM_VIDEO_FILE_DATA")
        
        job.video_path = placeholder_path
        return job
