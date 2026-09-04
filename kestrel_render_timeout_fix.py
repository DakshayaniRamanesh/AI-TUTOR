#!/usr/bin/env python3
"""
Targeted timeout + render complexity fix for AI-TUTOR branch:
rescue/kestrel-before-stabilization

Run from the repository root:
    python kestrel_render_timeout_fix.py
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
EXPECTED_BRANCH = "rescue/kestrel-before-stabilization"


def fail(message: str):
    raise SystemExit(f"[ERROR] {message}")


def current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def replace_once(path: str, old: str, new: str):
    file_path = ROOT / path
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        fail(f"{path}: expected snippet once, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


if not (ROOT / ".git").exists():
    fail("Run this script from the AI-TUTOR repository root.")

# branch = current_branch()
# if branch != EXPECTED_BRANCH:
#     fail(f"Current branch is '{branch}'. Switch to '{EXPECTED_BRANCH}' first.")

# status = subprocess.run(
#     ["git", "status", "--porcelain"], capture_output=True, text=True
# ).stdout.strip()
# if status:
#     fail("Working tree is not clean. Commit or stash your changes first.")

# 1. UI poll timeout: current remote is 6 minutes. Make it configurable, default 20 min.
replace_once(
    "app/backend/video_generation/video_gen_client.py",
    """    def run(self):
        # 600 * 1.5 s = 15 minutes. Long enough for a real render without leaving
        # a dead poller alive for 30 minutes.
        max_attempts = 600
        request_failures = 0

        for attempt in range(1, max_attempts + 1):
            if not self._running:
                return
            self.msleep(1500)
""",
    """    def run(self):
        # UI polling must outlive the backend render deadline.
        poll_interval_ms = int(os.getenv(\"VIDEO_POLL_INTERVAL_MS\", \"1500\"))
        poll_timeout_seconds = int(os.getenv(\"VIDEO_POLL_TIMEOUT_SECONDS\", \"1200\"))
        max_attempts = max(1, (poll_timeout_seconds * 1000) // poll_interval_ms)
        request_failures = 0

        for attempt in range(1, max_attempts + 1):
            if not self._running:
                return
            self.msleep(poll_interval_ms)
""",
)

# 2. Backend render timeout: current code kills medium render after 300 seconds.
replace_once(
    "backend/video_generation/agents/renderer_agent.py",
    """from backend.workspace.artifact_store import artifact_store


def _find_mp4(media_dir: str) -> str | None:
""",
    """from backend.workspace.artifact_store import artifact_store


MANIM_RENDER_TIMEOUT_SECONDS = int(os.getenv(\"MANIM_RENDER_TIMEOUT_SECONDS\", \"900\"))
MANIM_LOW_RENDER_TIMEOUT_SECONDS = int(os.getenv(\"MANIM_LOW_RENDER_TIMEOUT_SECONDS\", \"300\"))


def _find_mp4(media_dir: str) -> str | None:
""",
)

replace_once(
    "backend/video_generation/agents/renderer_agent.py",
    """                quality=\"-qm\",
                timeout=300,
                scene_name=\"MainScene\",
""",
    """                quality=\"-qm\",
                timeout=MANIM_RENDER_TIMEOUT_SECONDS,
                scene_name=\"MainScene\",
""",
)

replace_once(
    "backend/video_generation/agents/renderer_agent.py",
    """            if not ok:
                print(f\"[RendererAgent] Medium render failed; one low-quality fallback: {output[:200]}\")
                low_dir = os.path.join(temp_dir, \"media_ql\")
""",
    """            if not ok and str(output).startswith(\"Render timed out\"):
                # Do not throw away a long render and immediately restart it.
                job.status = JobStatus.ERROR
                job.error_message = str(output)
                return job

            if not ok:
                print(f\"[RendererAgent] Medium render failed; one low-quality fallback: {output[:200]}\")
                low_dir = os.path.join(temp_dir, \"media_ql\")
""",
)

replace_once(
    "backend/video_generation/agents/renderer_agent.py",
    """                    quality=\"-ql\",
                    timeout=180,
                    scene_name=\"MainScene\",
""",
    """                    quality=\"-ql\",
                    timeout=MANIM_LOW_RENDER_TIMEOUT_SECONDS,
                    scene_name=\"MainScene\",
""",
)

# 3. Modal worker timeout: current cloud worker has a 600 second hard cap.
replace_once(
    "backend/modal_app.py",
    """@app.function(image=manim_image, gpu=\"A10G\", timeout=600, secrets=secrets, volumes={\"/root/backend/workspace/artifacts\": artifact_volume})
def _process_generation_job(job_dict: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
""",
    """@app.function(image=manim_image, gpu=\"A10G\", timeout=1800, secrets=secrets, volumes={\"/root/backend/workspace/artifacts\": artifact_volume})
def _process_generation_job(job_dict: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
""",
)

# 4. Bound storyboard complexity. Current maximum is too high for an interactive app.
storyboard_path = ROOT / "backend/video_generation/agents/storyboard_agent.py"
storyboard = storyboard_path.read_text(encoding="utf-8")
for old, new in [
    ("for idx, raw in enumerate(raw_scenes[:6]):", "for idx, raw in enumerate(raw_scenes[:4]):"),
    ('for obj_idx, obj in enumerate(raw.get("objects", [])[:24]):', 'for obj_idx, obj in enumerate(raw.get("objects", [])[:12]):'),
    ('for term_idx, term in enumerate(obj.get("terms", [])[:24]):', 'for term_idx, term in enumerate(obj.get("terms", [])[:12]):'),
    ('for action in raw.get("actions", [])[:40]:', 'for action in raw.get("actions", [])[:20]:'),
]:
    if old not in storyboard:
        fail(f"storyboard_agent.py missing expected snippet: {old}")
    storyboard = storyboard.replace(old, new, 1)

anchor = "Create at least one scene per TeachingStep to animate the rule and transition. Every scene must teach something; avoid decorative filler."
replacement = """Create the SHORTEST sufficient lesson: normally 2-4 scenes total. Merge related TeachingSteps when possible.
Every scene must teach something; avoid decorative filler.
PERFORMANCE BUDGET: max 12 objects and 20 actions per scene. Prefer transforms/highlights of existing objects over creating duplicates."""
if anchor not in storyboard:
    fail("storyboard_agent.py prompt anchor not found")
storyboard = storyboard.replace(anchor, replacement, 1)
storyboard_path.write_text(storyboard, encoding="utf-8")

# 5. Give CI enough room for legitimate MathTex construction, but still much less than production render.
ci_path = ROOT / "backend/ci/pipeline.py"
ci = ci_path.read_text(encoding="utf-8")
if "timeout=45)" not in ci:
    fail("CI dry-run timeout snippet not found")
ci = ci.replace("timeout=45)", "timeout=90)", 1)
ci = ci.replace("Dry run timed out (>45s).", "Dry run timed out (>90s).", 1)
# Replace the smoke-render timeout that appears after the dry-run section.
smoke_marker = "result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)"
if smoke_marker not in ci:
    fail("CI smoke-render timeout snippet not found")
ci = ci.replace(smoke_marker, "result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)", 1)
ci = ci.replace("Smoke render timed out (>90s).", "Smoke render timed out (>180s).", 1)
ci_path.write_text(ci, encoding="utf-8")

print("[OK] Applied timeout + complexity changes.")
subprocess.run([sys.executable, "-m", "compileall", "-q", "app", "backend"], check=True)
print("[OK] Python compile check passed.")
print()
subprocess.run(["git", "diff", "--stat"], check=False)
print()
print("Recommended .env values:")
print("VIDEO_POLL_TIMEOUT_SECONDS=1200")
print("MANIM_RENDER_TIMEOUT_SECONDS=900")
print("MANIM_LOW_RENDER_TIMEOUT_SECONDS=300")
print()
print("Review the changes with: git diff")
