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
    with patch("backend.video_generation.agents.latex_agents.Groq") as mock_groq:
        mock_groq.return_value = None  # Force fallback
        with patch("google.generativeai.GenerativeModel") as mock_genai_model, patch("google.generativeai.configure") as mock_configure:
            mock_model = MagicMock()
            mock_genai_model.return_value = mock_model
            
            mock_resp = MagicMock()
            mock_resp.text = r"\[ 2x = 4 \]"
            mock_model.generate_content.return_value = mock_resp
            
            agent = LatexStructureAgent()
            agent.google_api_key = "test_key"
            agent.groq_api_key = None
            
            result = agent.run(job)
            assert result.status != JobStatus.ERROR
            
            # Check what was passed to generate_content
            # The prompt should contain TRANSCRIBE instructions because of mode="selection_exact"
            call_args = mock_model.generate_content.call_args[0][0]
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
