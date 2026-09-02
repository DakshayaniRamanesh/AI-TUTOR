"""
Script to run and evaluate the 8 representative test scenarios requested:
1. Basic arithmetic/calculus
2. Graph/function explanation
3. Physics concept
4. Computer science concept
5. Chemistry concept
6. Document-grounded explanation
7. A deliberately difficult/ambiguous prompt
8. A case that causes generated code failure

Outputs a structured report detailing:
Input -> Generated lesson -> Generated code -> Validation result -> Render result -> Final video -> Problems found
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.video_generation.models import VideoJob, JobStatus
from backend.video_generation.agents.story_agent import StoryAgent, classify_subject
from backend.video_generation.agents.validator_agent import ValidatorAgent
from backend.video_generation.agents.codegen_agent import CodeGenAgent
from backend.ci.pipeline import CIPipelineHarness
from backend.video_generation.agents.renderer_agent import RendererAgent
from backend.workspace.qdrant_store import QdrantRAGStore


def run_single_scenario(scenario_num: int, title: str, prompt: str, doc_text: str = "", simulate_failure: bool = False):
    print(f"\n=======================================================")
    print(f"SCENARIO {scenario_num}: {title}")
    print(f"PROMPT: {prompt}")
    print(f"=======================================================")

    report = {
        "scenario": scenario_num,
        "title": title,
        "input_prompt": prompt,
        "subject": "",
        "lesson_script": "",
        "validation_passed": False,
        "validation_error": "",
        "code_snippet": "",
        "ci_passed": False,
        "ci_error": "",
        "render_passed": False,
        "render_quality": "",
        "video_path": "",
        "problems_found": []
    }

    rag_store = MagicRAG(doc_text) if doc_text else QdrantRAGStore()
    story_agent = StoryAgent(rag_store)
    validator_agent = ValidatorAgent()
    codegen_agent = CodeGenAgent()
    ci = CIPipelineHarness()
    renderer = RendererAgent()

    job = VideoJob(
        job_id=f"scen_{scenario_num}_{int(time.time())}",
        user_prompt=prompt,
        document_text=doc_text
    )

    # Step 1: Story generation
    job = story_agent.run(job)
    report["subject"] = job.topic_subject
    report["lesson_script"] = job.story_script[:300] + "..." if job.story_script else "NONE"
    print(f"[1] Story generated (subject: {job.topic_subject}, length: {len(job.story_script or '')})")

    # Step 2: Story validation
    job = validator_agent.run(job)
    if job.needs_revision:
        report["validation_passed"] = False
        report["validation_error"] = job.metadata.get("revision_reason", "Needs revision")
        print(f"[2] Story validation flagged revision: {report['validation_error']}")
        # Retry story once
        job = story_agent.run(job)
        job = validator_agent.run(job)

    report["validation_passed"] = not job.needs_revision
    print(f"[2] Final story validation: {'PASSED' if report['validation_passed'] else 'FORCED'}")

    # Step 3: Code generation
    if simulate_failure:
        print("[3] Simulating intentional code failure (MathTex + syntax error)...")
        job.manim_code = """from manim import *
class MainScene(Scene):
    def construct(self):
        t = MathTex("x^2") # Intentionally banned MathTex
        self.play(Write(t))
"""
    else:
        job = codegen_agent.run(job)

    report["code_snippet"] = (job.manim_code[:250] + "...") if job.manim_code else "NONE"
    print(f"[3] Code generated ({len(job.manim_code or '')} chars)")

    # Step 4: CI validation
    ci_passed, ci_error = ci.validate_code(job.manim_code or "")
    report["ci_passed"] = ci_passed
    report["ci_error"] = ci_error
    print(f"[4] CI Validation: {'PASSED' if ci_passed else 'FAILED: ' + ci_error[:120]}")

    if not ci_passed:
        if simulate_failure:
            print("[4] Expected failure caught by CI! Now simulating retry with error feedback...")
            job.retry_count += 1
            job.build_error_trace = ci_error
            # Retrying code generation with error feedback
            job = codegen_agent.run(job)
            ci_passed, ci_error = ci.validate_code(job.manim_code or "")
            print(f"[4b] Retry CI Validation: {'PASSED' if ci_passed else 'FAILED'}")
            report["ci_passed"] = ci_passed
            report["ci_error"] = ci_error if not ci_passed else "Resolved on retry"
        else:
            report["problems_found"].append(f"CI failed: {ci_error[:100]}")

    # Step 5: Render
    if ci_passed:
        print("[5] Rendering video with RendererAgent...")
        job = renderer.run(job)
        if job.status != JobStatus.ERROR and job.video_path and os.path.exists(job.video_path):
            report["render_passed"] = True
            report["render_quality"] = job.render_quality
            report["video_path"] = job.video_path
            print(f"[5] Render PASSED: {job.video_path} (quality: {job.render_quality})")
        else:
            report["render_passed"] = False
            report["problems_found"].append(f"Render failed: {job.error_message}")
            print(f"[5] Render FAILED: {job.error_message}")
    else:
        report["render_passed"] = False
        print("[5] Skipping render due to CI failure.")

    return report


class MagicRAG:
    """Mock RAG store providing document chunks."""
    def __init__(self, doc_text: str):
        self.doc_text = doc_text

    def search(self, prompt, job_id, top_k=5):
        return [{"text": self.doc_text[:600], "page": 1}]


if __name__ == "__main__":
    scenarios = [
        (1, "Basic arithmetic/calculus", "Explain the derivative of x squared", "", False),
        (2, "Graph/function explanation", "Visualizing a sinusoidal wave and frequency", "", False),
        (3, "Physics concept", "Newton's second law: force equals mass times acceleration", "", False),
        (4, "Computer science concept", "Binary search algorithm step by step", "", False),
        (5, "Chemistry concept", "Chemical reaction between hydrogen and oxygen to form water", "", False),
        (6, "Document-grounded explanation", "Explain photosynthesis light reactions", "Photosynthesis in plants occurs in the thylakoid membrane where chlorophyll absorbs light photon energy to excite electrons in Photosystem II, splitting water molecules into oxygen and hydrogen protons.", False),
        (7, "Deliberately difficult/ambiguous prompt", "Explain the thing that does the stuff when it goes fast", "", False),
        (8, "Generated code failure & recovery", "Explain quadratic equation derivation", "", True),
    ]

    results = []
    for s in scenarios:
        res = run_single_scenario(*s)
        results.append(res)

    print("\n\n=======================================================")
    print("FINAL SUMMARY REPORT")
    print("=======================================================")
    for r in results:
        status_sym = "✅" if r["render_passed"] or (r["scenario"] == 8 and r["ci_passed"]) else "❌"
        print(f"Scenario {r['scenario']} ({r['title']}): {status_sym} [Subject: {r['subject']}] [CI: {'PASS' if r['ci_passed'] else 'FAIL'}] [Render: {'PASS' if r['render_passed'] else 'N/A'}]")
        if r["video_path"]:
            print(f"   Video: {r['video_path']}")
        if r["problems_found"]:
            print(f"   Issues: {r['problems_found']}")

    with open("backend/tests/scenario_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved results to backend/tests/scenario_results.json")
