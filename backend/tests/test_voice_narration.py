"""
Tests for the Voice Narration Plugin.

Covers:
1. Narration text is educational (not raw LaTeX)
2. TTSService abstraction and EdgeTTSProvider (mocked)
3. Audio duration drives timeline hold_duration patching
4. Voice-disabled path delegates to LatexVideoPipeline unchanged
5. TTS failure is handled gracefully (silent MP4 still produced)
6. NarrationPlanner groups segments by SlideScene

Run with:
    python -m pytest backend/tests/test_voice_narration.py -v
"""

from __future__ import annotations

import os
import types
import unittest.mock as mock
from dataclasses import dataclass
from typing import Optional, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Helpers — lightweight document / timeline builders
# ---------------------------------------------------------------------------

from backend.latex_video.document_model import (
    DocumentElement,
    ElementType,
    ImportanceLevel,
    LessonDocument,
    LessonSection,
)
from backend.latex_video.animation_planner import (
    AnimationTimeline,
    AnimationPlanner,
    SlideScene,
    TimelineState,
    TransitionType,
)
from backend.latex_video.narration_planner import (
    NarrationPlanner,
    NarrationPlan,
    NarrationSegment,
    _LatexToSpeech,
)
from backend.latex_video.tts_service import (
    AudioSegment,
    TTSService,
    EdgeTTSProvider,
    _measure_mp3_duration,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_element(
    elem_id: str,
    etype: ElementType,
    raw: str,
    clean: str = "",
    complexity: float = 1.0,
    importance: ImportanceLevel = ImportanceLevel.NORMAL,
) -> DocumentElement:
    return DocumentElement(
        element_id=elem_id,
        type=etype,
        raw_content=raw,
        clean_text=clean or raw,
        complexity_score=complexity,
        importance=importance,
    )


def _make_simple_timeline() -> AnimationTimeline:
    """Build a minimal AnimationTimeline with 2 scenes for testing."""
    scene0 = SlideScene(scene_index=0, title="Derivatives")
    scene0.elements = [
        _make_element("e0", ElementType.TITLE, "Derivatives", "Derivatives"),
        _make_element("e1", ElementType.PARAGRAPH,
                      "The derivative measures rate of change.",
                      "The derivative measures rate of change."),
        _make_element("e2", ElementType.EQUATION_DISPLAY,
                      r"\[ f'(x) = 2x \]"),
    ]

    scene1 = SlideScene(scene_index=1, title="Result")
    scene1.elements = [
        _make_element("e3", ElementType.BOXED_RESULT,
                      r"\boxed{\frac{d}{dx} x^2 = 2x}"),
    ]

    states = [
        TimelineState(
            state_index=i, scene_index=s,
            visible_elements=[], new_element=None,
            start_time=i * 4.0, transition_duration=0.5,
            hold_duration=3.0, transition_type=TransitionType.FADE_IN,
        )
        for i, s in enumerate([0, 0, 0, 1])
    ]

    tl = AnimationTimeline(scenes=[scene0, scene1], states=states, total_duration=20.0)
    return tl


# ---------------------------------------------------------------------------
# 1. Narration text is educational (not raw LaTeX)
# ---------------------------------------------------------------------------

class TestNarrationTextIsEducational:

    def test_equation_display_not_raw_latex(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.EQUATION_DISPLAY,
                             r"\[ ax^2 + bx + c = 0 \]")
        result = planner._narrate_element(elem)

        assert result, "Expected non-empty narration for EQUATION_DISPLAY"
        # Must NOT contain raw LaTeX backslash commands
        assert "\\" not in result, f"Raw LaTeX leaked into narration: {result!r}"
        assert "equation" in result.lower() or "shows" in result.lower()

    def test_boxed_result_not_raw_latex(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.BOXED_RESULT,
                             r"\boxed{x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}}")
        result = planner._narrate_element(elem)

        assert result
        assert "\\" not in result, f"Raw LaTeX leaked: {result!r}"
        assert "result" in result.lower() or "key" in result.lower()

    def test_paragraph_uses_clean_text(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.PARAGRAPH,
                             r"In a right triangle, $a^2 + b^2 = c^2$.",
                             clean="In a right triangle, a squared plus b squared equals c squared.")
        result = planner._narrate_element(elem)

        assert "right triangle" in result.lower()

    def test_title_produces_welcome(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.TITLE, "Quadratic Equations",
                             clean="Quadratic Equations")
        result = planner._narrate_element(elem)

        assert "welcome" in result.lower() or "lesson" in result.lower()
        assert "Quadratic" in result

    def test_section_intro(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.SECTION, "Derivation", clean="Derivation",
                             importance=ImportanceLevel.HIGH)
        result = planner._narrate_element(elem)

        assert "section" in result.lower() or "explore" in result.lower()

    def test_equation_step_skipped_when_simple(self):
        """Low-complexity equation steps should produce no narration."""
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.EQUATION_STEP, r"x = 1",
                             complexity=0.8)
        result = planner._narrate_element(elem)
        assert result == "", f"Expected empty narration for simple step, got: {result!r}"

    def test_equation_step_narrated_when_complex(self):
        planner = NarrationPlanner()
        elem = _make_element("x", ElementType.EQUATION_STEP,
                             r"x^2 + \frac{b}{a}x + \left(\frac{b}{2a}\right)^2 = \frac{b^2-4ac}{4a^2}",
                             complexity=2.0)
        result = planner._narrate_element(elem)
        assert result != ""
        assert "\\" not in result


# ---------------------------------------------------------------------------
# 2. LaTeX → speech translator
# ---------------------------------------------------------------------------

class TestLatexToSpeech:

    def test_fraction(self):
        assert "over" in _LatexToSpeech.translate(r"\frac{a}{b}")

    def test_sqrt(self):
        result = _LatexToSpeech.translate(r"\sqrt{x}")
        assert "square root" in result

    def test_pm(self):
        assert "plus or minus" in _LatexToSpeech.translate(r"\pm")

    def test_greek(self):
        assert "alpha" in _LatexToSpeech.translate(r"\alpha")
        assert "pi" in _LatexToSpeech.translate(r"\pi")

    def test_no_backslash_in_output(self):
        latex = r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
        result = _LatexToSpeech.translate(latex)
        assert "\\" not in result, f"Backslash remained in: {result!r}"

    def test_leq_geq(self):
        assert "less than or equal" in _LatexToSpeech.translate(r"\leq")
        assert "greater than or equal" in _LatexToSpeech.translate(r"\geq")


# ---------------------------------------------------------------------------
# 3. NarrationPlanner groups segments by SlideScene
# ---------------------------------------------------------------------------

class TestNarrationPlannerGroupsByScene:

    def test_one_segment_per_scene(self):
        timeline = _make_simple_timeline()
        planner = NarrationPlanner()
        plan = planner.plan(timeline)

        scene_indices = {seg.scene_index for seg in plan.segments}
        # We have 2 scenes; expect at most 2 segments (some may be empty and skipped)
        assert len(plan.segments) <= 2
        assert 0 in scene_indices  # Scene 0 has content

    def test_segment_text_non_empty(self):
        timeline = _make_simple_timeline()
        planner = NarrationPlanner()
        plan = planner.plan(timeline)

        for seg in plan.segments:
            assert seg.text.strip(), f"Segment {seg.scene_index} has empty text"

    def test_get_segment_lookup(self):
        timeline = _make_simple_timeline()
        planner = NarrationPlanner()
        plan = planner.plan(timeline)

        if plan.segments:
            seg = plan.get_segment(plan.segments[0].scene_index)
            assert seg is not None
            assert seg.text.strip()


# ---------------------------------------------------------------------------
# 4. Audio duration patches timeline hold_duration
# ---------------------------------------------------------------------------

class TestTimelineDurationPatching:

    def _make_audio(self, scene_index: int, duration: float) -> AudioSegment:
        return AudioSegment(
            scene_index=scene_index,
            path="/tmp/fake.mp3",
            duration_seconds=duration,
            text="test",
        )

    def test_hold_duration_is_increased(self):
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        tl = _make_simple_timeline()

        # Scene 0 has 3 states (indices 0,1,2) with hold_duration=3.0 each
        original_holds = [s.hold_duration for s in tl.states if s.scene_index == 0]

        pipeline = VoiceEnabledPipeline()
        audio = [self._make_audio(scene_index=0, duration=20.0)]  # 20s for 3 states
        pipeline._patch_timeline_durations(tl, audio)

        patched_holds = [s.hold_duration for s in tl.states if s.scene_index == 0]
        # Each state should now hold ≥ 20*1.1/3 ≈ 7.33s
        for hold in patched_holds:
            assert hold >= 7.0, f"hold_duration not increased: {hold}"

    def test_hold_never_decreased(self):
        """If audio is shorter than the planned hold, the original hold is preserved."""
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        tl = _make_simple_timeline()
        for s in tl.states:
            s.hold_duration = 10.0  # already very long

        pipeline = VoiceEnabledPipeline()
        audio = [self._make_audio(scene_index=0, duration=1.0)]  # very short audio
        pipeline._patch_timeline_durations(tl, audio)

        for s in [st for st in tl.states if st.scene_index == 0]:
            assert s.hold_duration >= 10.0, "hold_duration was decreased unexpectedly"

    def test_none_audio_does_not_crash(self):
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        tl = _make_simple_timeline()
        pipeline = VoiceEnabledPipeline()
        pipeline._patch_timeline_durations(tl, [None, None])
        # Should not raise; timeline should be unchanged structurally


# ---------------------------------------------------------------------------
# 5. TTS generation (mocked edge-tts)
# ---------------------------------------------------------------------------

class TestTTSService:

    def test_generate_returns_audio_segment(self, tmp_path):
        """EdgeTTSProvider.generate returns AudioSegment with measured duration."""
        # Source MP3 written to a *different* path so shutil.copy doesn't hit same-file error
        src_mp3 = str(tmp_path / "source.mp3")
        dst_mp3 = str(tmp_path / "output.mp3")

        # Write a minimal fake MP3 (size-based duration fallback will kick in)
        with open(src_mp3, "wb") as f:
            f.write(b"\xff\xfb" + b"\x00" * 5000)

        provider = EdgeTTSProvider(voice="en-US-AriaNeural")

        async def fake_save(path):
            import shutil
            shutil.copy(src_mp3, path)

        fake_communicate = MagicMock()
        fake_communicate.save = fake_save

        fake_edge_tts = types.ModuleType("edge_tts")
        fake_edge_tts.Communicate = MagicMock(return_value=fake_communicate)

        with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}):
            result = provider.generate("Hello world", dst_mp3, scene_index=0)

        assert result is not None
        assert isinstance(result, AudioSegment)
        assert result.scene_index == 0
        assert result.duration_seconds > 0
        assert result.text == "Hello world"

    def test_generate_returns_none_on_import_error(self, tmp_path):
        """Returns None gracefully when edge-tts is not installed."""
        mp3_path = str(tmp_path / "out.mp3")
        provider = EdgeTTSProvider()

        with patch.dict("sys.modules", {"edge_tts": None}):
            result = provider.generate("Test", mp3_path, scene_index=0)

        assert result is None

    def test_generate_returns_none_on_empty_file(self, tmp_path):
        """Returns None when TTS writes an empty file."""
        mp3_path = str(tmp_path / "empty.mp3")

        async def fake_save_empty(path):
            open(path, "wb").close()  # empty file

        fake_communicate = MagicMock()
        fake_communicate.save = fake_save_empty

        fake_edge_tts = types.ModuleType("edge_tts")
        fake_edge_tts.Communicate = MagicMock(return_value=fake_communicate)

        provider = EdgeTTSProvider()
        with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}):
            result = provider.generate("Test", mp3_path, scene_index=1)

        assert result is None

    def test_generate_batch_skips_empty_text(self, tmp_path):
        provider = EdgeTTSProvider()
        items = [(0, "", str(tmp_path / "a.mp3")), (1, "  ", str(tmp_path / "b.mp3"))]
        results = provider.generate_batch(items)
        assert results == [None, None]

    def test_measure_mp3_duration_size_fallback(self, tmp_path):
        """Size-based fallback returns a positive duration when mutagen raises."""
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"\xff\xfb" + b"\x00" * 16000)  # 16 KB fake MP3

        # Patch mutagen.mp3.MP3 at the point it is imported inside the function
        with patch("mutagen.mp3.MP3", side_effect=Exception("parse error")):
            dur = _measure_mp3_duration(str(mp3))

        assert dur > 0


# ---------------------------------------------------------------------------
# 6. Voice-disabled path delegates unchanged
# ---------------------------------------------------------------------------

class TestVoiceDisabledPath:

    def test_disabled_delegates_to_base_pipeline(self):
        """When VOICE_ENABLED=False, VoiceEnabledPipeline calls LatexVideoPipeline unchanged."""
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        from backend.video_generation.models import VideoJob, JobStatus
        import backend.config as config

        original = config.VOICE_ENABLED
        config.VOICE_ENABLED = False

        try:
            pipeline = VoiceEnabledPipeline()
            fake_job = VideoJob(job_id="test_disabled", user_prompt="Test", document_text="")

            sentinel_job = VideoJob(job_id="test_disabled", user_prompt="Test", document_text="")
            sentinel_job.status = JobStatus.DONE
            sentinel_job.video_path = "/fake/video.mp4"

            with patch.object(pipeline._base, "run_pipeline", return_value=sentinel_job) as mock_run:
                result = pipeline.run_pipeline(fake_job)

            mock_run.assert_called_once_with(fake_job, progress_callback=None)
            assert result is sentinel_job
        finally:
            config.VOICE_ENABLED = original

    def test_disabled_never_calls_tts(self):
        """TTS service must not be created or called when voice is disabled."""
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        from backend.video_generation.models import VideoJob, JobStatus
        import backend.config as config

        original = config.VOICE_ENABLED
        config.VOICE_ENABLED = False

        try:
            pipeline = VoiceEnabledPipeline()
            fake_job = VideoJob(job_id="test_no_tts", user_prompt="Test", document_text="")

            sentinel = VideoJob(job_id="test_no_tts", user_prompt="Test", document_text="")
            sentinel.status = JobStatus.DONE

            with patch.object(pipeline._base, "run_pipeline", return_value=sentinel):
                with patch.object(pipeline, "_get_tts") as mock_tts:
                    pipeline.run_pipeline(fake_job)
                    mock_tts.assert_not_called()
        finally:
            config.VOICE_ENABLED = original


# ---------------------------------------------------------------------------
# 7. TTS failure — graceful fallback to silent video
# ---------------------------------------------------------------------------

class TestTTSFailureGraceful:

    def test_all_tts_fail_still_returns_done(self, tmp_path):
        """Pipeline returns a DONE job with a silent MP4 when all TTS calls fail."""
        from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
        from backend.video_generation.models import VideoJob, JobStatus
        import backend.config as config

        original_enabled = config.VOICE_ENABLED
        original_videos = config.VIDEOS_DIR
        original_audio = config.AUDIO_DIR

        config.VOICE_ENABLED = True
        config.VIDEOS_DIR = str(tmp_path)
        config.AUDIO_DIR = str(tmp_path)

        # Create a fake silent MP4
        silent_mp4 = tmp_path / "test_fail_silent.mp4"
        silent_mp4.write_bytes(b"\x00" * 2048)

        try:
            pipeline = VoiceEnabledPipeline()
            job = VideoJob(job_id="test_fail", user_prompt="Test", document_text="")

            # Stub out the heavy steps
            with patch.object(pipeline._base, "_obtain_educational_latex",
                               return_value=r"\section*{Test}\[ x = 1 \]"), \
                 patch.object(pipeline._base.parser, "parse") as mock_parse, \
                 patch.object(pipeline._base.planner, "plan",
                               return_value=_make_simple_timeline()), \
                 patch.object(pipeline._base.renderer, "render_state_images",
                               return_value=[MagicMock()]), \
                 patch.object(pipeline._base.assembler, "assemble",
                               return_value=str(silent_mp4)), \
                 patch.object(pipeline._tts or MagicMock(), "generate_batch",
                               return_value=[None, None]):

                mock_parse.return_value = LessonDocument(
                    title="Test",
                    sections=[
                        LessonSection(
                            section_id="s0",
                            title="Test",
                            elements=[_make_element("e0", ElementType.PARAGRAPH,
                                                    "Hello world", "Hello world")],
                        )
                    ]
                )

                # Force TTS to return None for all segments
                with patch.object(pipeline, "_synthesise_audio", return_value=[None]):
                    result = pipeline.run_pipeline(job)

            assert result.status == JobStatus.DONE
            assert result.video_path is not None

        finally:
            config.VOICE_ENABLED = original_enabled
            config.VIDEOS_DIR = original_videos
            config.AUDIO_DIR = original_audio
