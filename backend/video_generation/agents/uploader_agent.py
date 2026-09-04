import os
import shutil
from backend.video_generation.models import VideoJob, JobStatus

from backend.workspace.artifact_store import artifact_store


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

        # --- 2. Artifact already stored by RendererAgent ---
        # The video path is already in the artifact store.
        # We can just verify it exists.
        dest_key = f"v{job.version}.mp4"
        dest_path = artifact_store.get(job.job_id, dest_key)
        if not dest_path:
            # Fallback to copy if it's not already in the store
            dest_path = artifact_store.put(job.job_id, dest_key, job.video_path)
            job.video_path = dest_path
        
        print(f"[UploaderAgent] Using artifact store path: {job.video_path}")

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

        # --- 4. Local fallback: serve via the FastAPI artifact endpoint ---
        job.video_url = artifact_store.get_url(job.job_id, dest_key)
        print(f"[UploaderAgent] Serving locally at {job.video_url}")
        job.status = JobStatus.DONE
        job.progress_percentage = 100
        return job
