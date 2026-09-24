import pytest
import os
import uuid
import base64
from unittest.mock import patch, MagicMock

from app.services.tutoring.video_gen_client import ManimVideoPollWorker
from backend.video_generation.models import LatexJob, JobStatus
from shared.contracts.latex import LatexGenerationRequest, LatexGenerationMode, LatexSourceAnchor
from shared.contracts.video import VideoGenerationRequest
from backend.video_generation.agents.latex_agents import LatexStructureAgent
from backend.ci.pipeline import _static_analysis

def test_latex_selection_exact_transcribe_intent():
    job = LatexJob(job_id="test", mode="selection_exact", raw_transcription="2x = 4")
    
    # In LatexStructureAgent.run, we check intent
    with patch("shared.ai_client.ai_client.generate_content") as mock_generate:
        mock_generate.return_value = r"\[ 2x = 4 \]"
        
        agent = LatexStructureAgent()
        result = agent.run(job)
        assert result.status != JobStatus.ERROR
        
        # Check what was passed to generate_content
        call_args = mock_generate.call_args[0][0]
        assert "strictly to TRANSCRIBE" in call_args
        assert "DO NOT solve any equations" in call_args

def test_video_poll_worker_stops_on_cancel():
    worker = ManimVideoPollWorker(job_id="test", prompt="test")
    assert worker._running == True
    worker.stop()
    assert worker._running == False

def test_stage0_static_analysis_bans_dangerous_apis():
    bad_code = "import os\nos.system('rm -rf /')"
    passed, msg = _static_analysis(bad_code)
    assert not passed
    assert "import os" in msg or "Banned API" in msg

def test_stage0_static_analysis_bans_sys():
    bad_code = "import sys\nsys.exit(1)"
    passed, msg = _static_analysis(bad_code)
    assert not passed
    assert "import sys" in msg or "Banned API" in msg
