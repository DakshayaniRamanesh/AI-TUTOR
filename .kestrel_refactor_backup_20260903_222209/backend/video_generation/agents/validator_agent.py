from backend.video_generation.models import VideoJob

class ValidatorAgent:
    def run(self, job: VideoJob) -> VideoJob:
        job.step = "validator_agent"
        job.progress_percentage = 45

        # Check script validity
        if not job.story_script or len(job.story_script.strip()) < 20:
            job.needs_revision = True
        else:
            job.needs_revision = False

        if job.needs_revision:
            job.revision_count += 1
            # Limit maximum revisions to 2
            if job.revision_count >= 2:
                job.needs_revision = False

        return job
