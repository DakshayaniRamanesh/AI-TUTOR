import os
import boto3
from backend.pipeline.models import VideoJob, JobStatus

class UploaderAgent:
    def __init__(self):
        self.spaces_key = os.getenv("DO_SPACES_KEY")
        self.spaces_secret = os.getenv("DO_SPACES_SECRET")
        self.spaces_bucket = os.getenv("DO_SPACES_BUCKET", "manim-videos")
        self.spaces_region = os.getenv("DO_SPACES_REGION", "nyc3")
        self.spaces_endpoint = os.getenv("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com")

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "uploader_agent"
        job.progress_percentage = 95

        object_name = f"videos/{job.job_id}_v{job.version}.mp4"

        if self.spaces_key and self.spaces_secret and job.video_path and os.path.exists(job.video_path):
            try:
                session = boto3.session.Session()
                client = session.client(
                    's3',
                    region_name=self.spaces_region,
                    endpoint_url=self.spaces_endpoint,
                    aws_access_key_id=self.spaces_key,
                    aws_secret_access_key=self.spaces_secret
                )
                client.upload_file(
                    job.video_path,
                    self.spaces_bucket,
                    object_name,
                    ExtraArgs={'ACL': 'public-read', 'ContentType': 'video/mp4'}
                )
                job.video_url = f"{self.spaces_endpoint}/{self.spaces_bucket}/{object_name}"
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                return job
            except Exception as e:
                print(f"[UploaderAgent] DO Spaces upload error: {e}")

        # Fallback: Convert rendered video to base64 Data URL so browser plays it directly without S3
        if job.video_path and os.path.exists(job.video_path):
            try:
                import base64
                with open(job.video_path, "rb") as vf:
                    v_bytes = vf.read()
                b64_str = base64.b64encode(v_bytes).decode("utf-8")
                job.video_url = f"data:video/mp4;base64,{b64_str}"
                print(f"[UploaderAgent] Encoded {len(v_bytes)} video bytes into Data URL for job {job.job_id}")
            except Exception as e:
                print(f"[UploaderAgent] Base64 encoding error: {e}")
                job.video_url = f"/api/video/{job.job_id}_v{job.version}.mp4"
        else:
            job.video_url = f"/api/video/{job.job_id}_v{job.version}.mp4"

        job.status = JobStatus.DONE
        job.progress_percentage = 100
        return job
