import os
import shutil
from backend.video_generation.models import VideoJob, JobStatus

# Permanent media directory — lives inside the backend folder so it's not cleaned by the OS.
_MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media")
os.makedirs(_MEDIA_DIR, exist_ok=True)


class UploaderAgent:
    def __init__(self):
        self.spaces_key = os.getenv("DO_SPACES_KEY", "")
        self.spaces_secret = os.getenv("DO_SPACES_SECRET", "")
        self.spaces_bucket = os.getenv("DO_SPACES_BUCKET", "manim-videos")
        self.spaces_region = os.getenv("DO_SPACES_REGION", "nyc3")
        self.spaces_endpoint = os.getenv("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com")

    def run(self, job: VideoJob) -> VideoJob:
        # Respect errors set by earlier agents (e.g. RendererAgent)
        if job.status == JobStatus.ERROR:
            return job

        job.step = "uploader_agent"
        job.progress_percentage = 95

        # --- 1. Validate that a real video file was produced ---
        if not job.video_path or not os.path.exists(job.video_path):
            job.status = JobStatus.ERROR
            job.error_message = (
                f"Renderer produced no video file. "
                f"video_path={job.video_path!r}"
            )
            print(f"[UploaderAgent] {job.error_message}")
            return job

        # --- 2. Copy to permanent media directory so the temp dir can be cleaned ---
        dest_filename = f"{job.job_id}_v{job.version}.mp4"
        dest_path = os.path.join(_MEDIA_DIR, dest_filename)
        try:
            shutil.copy2(job.video_path, dest_path)
            print(f"[UploaderAgent] Copied {job.video_path} -> {dest_path} ({os.path.getsize(dest_path)} bytes)")
            job.video_path = dest_path  # Update to the permanent path
        except Exception as e:
            print(f"[UploaderAgent] Copy to media dir failed: {e}")
            # Keep the temp path; at least status endpoint can still serve it

        # --- 3. Try DigitalOcean Spaces (only if real credentials are set) ---
        real_creds = (
            self.spaces_key and self.spaces_key != "your_spaces_key"
            and self.spaces_secret and self.spaces_secret != "your_spaces_secret"
        )
        if real_creds:
            try:
                import boto3
                object_name = f"videos/{job.job_id}_v{job.version}.mp4"
                session = boto3.session.Session()
                client = session.client(
                    "s3",
                    region_name=self.spaces_region,
                    endpoint_url=self.spaces_endpoint,
                    aws_access_key_id=self.spaces_key,
                    aws_secret_access_key=self.spaces_secret,
                )
                client.upload_file(
                    job.video_path,
                    self.spaces_bucket,
                    object_name,
                    ExtraArgs={"ACL": "public-read", "ContentType": "video/mp4"},
                )
                job.video_url = f"{self.spaces_endpoint}/{self.spaces_bucket}/{object_name}"
                print(f"[UploaderAgent] Uploaded to DO Spaces: {job.video_url}")
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                return job
            except Exception as e:
                print(f"[UploaderAgent] DO Spaces upload error: {e}")

        # --- 4. Local fallback: serve via the FastAPI /video/<filename> endpoint ---
        job.video_url = f"http://localhost:8000/video/{os.path.basename(job.video_path)}"
        print(f"[UploaderAgent] Serving locally at {job.video_url}")
        job.status = JobStatus.DONE
        job.progress_percentage = 100
        return job
