import os
import sys
import base64
from dotenv import load_dotenv

root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path = [root_dir] + [p for p in sys.path if p != root_dir]
load_dotenv(os.path.join(root_dir, "backend", ".env"))

from backend.video_generation.models import LatexJob, JobStatus
from backend.math_engine.latex_graph import LatexGenerationPipeline

# create a 1x1 white pixel png base64 for testing
dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="

job = LatexJob(
    job_id="test_123",
    image_b64=dummy_b64,
    template_type="Document",
    mode="VIEWPORT_DOCUMENT",
    classroom_action="Export LaTeX"
)

pipeline = LatexGenerationPipeline()
final_job = pipeline.run_pipeline(job)

print(f"Status: {final_job.status}")
if final_job.status == JobStatus.ERROR:
    print(f"Error: {final_job.error_message}")
else:
    print("LaTeX Generated:")
    print(final_job.final_tex_code[:200] + "...")
    print(f"Build error? {final_job.has_build_error}")
    if final_job.has_build_error:
        print(f"Trace:\n{final_job.build_error_trace[:500]}")
    print(f"PDF Path: {final_job.pdf_path}")
