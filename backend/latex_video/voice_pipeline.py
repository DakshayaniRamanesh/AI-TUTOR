"""
Voice-Enabled LaTeX Video Pipeline.

A thin wrapper around LatexVideoPipeline that adds an optional Edge TTS
narration layer.  When voice is disabled (the default), this class delegates
directly to LatexVideoPipeline.run_pipeline() — no changes to that code path.

When voice is enabled:
1.  Runs the existing pipeline up to the point where the silent MP4 is ready.
2.  Uses NarrationPlanner to build educational narration text per SlideScene.
3.  Calls TTSService to synthesise audio (one MP3 per scene).
4.  Patches each TimelineState's hold_duration to match the real audio duration
    so visuals stay on screen long enough for the narration to complete.
5.  Re-renders the visual video with the patched timeline.
6.  Uses FFmpeg to mux the audio segments alongside the video stream.
7.  On any TTS failure the silent MP4 is returned unchanged (graceful fallback).

Configuration
-------------
All settings are read from backend.config:
    VOICE_ENABLED  bool   — master on/off switch
    VOICE_PROVIDER str    — "edge_tts" (only provider currently)
    VOICE_LANG     str    — Edge TTS voice name, e.g. "en-US-AriaNeural"
    AUDIO_DIR      str    — directory for temporary MP3 files
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional, Callable, List

import backend.config as config
from backend.video_generation.models import VideoJob, JobStatus

from .pipeline import LatexVideoPipeline
from .narration_planner import NarrationPlanner, NarrationPlan, NarrationSegment
from .tts_service import TTSService, AudioSegment, create_tts_service
from .animation_planner import AnimationTimeline

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG_EXE = "ffmpeg"


class VoiceEnabledPipeline:
    """
    Entry point for the voice-narrated video pipeline.

    When voice is disabled, this behaves exactly as LatexVideoPipeline.
    When voice is enabled, it wraps LatexVideoPipeline with TTS and FFmpeg muxing.
    """

    def __init__(self):
        self._base = LatexVideoPipeline()
        self._narration_planner = NarrationPlanner()
        self._tts: Optional[TTSService] = None   # created lazily only when needed

    def run_pipeline(
        self,
        job: VideoJob,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> VideoJob:
        """Run the full pipeline, with voice if enabled."""
        if not config.VOICE_ENABLED:
            # Delegate entirely — no modification to the existing code path
            return self._base.run_pipeline(job, progress_callback=progress_callback)

        return self._run_with_voice(job, progress_callback)

    # ------------------------------------------------------------------
    # Voice-enabled path
    # ------------------------------------------------------------------

    def _run_with_voice(
        self,
        job: VideoJob,
        progress_callback: Optional[Callable[[int, str], None]],
    ) -> VideoJob:
        """Pipeline with TTS narration and audio/video muxing."""
        try:
            job.status = JobStatus.PROCESSING
            self._progress(job, 10, "latex_structuring", "Understanding your material…", progress_callback)

            # ── Step 1-4: obtain LaTeX, parse, plan, render frames ──────────
            latex_code = self._base._obtain_educational_latex(job)
            if not latex_code or not latex_code.strip():
                raise ValueError("No educational LaTeX content could be generated.")

            self._progress(job, 25, "latex_parsing", "Structuring educational content…", progress_callback)
            doc_title = (job.user_prompt or "Lesson").strip()[:40]
            document = self._base.parser.parse(latex_code, fallback_title=doc_title)

            self._progress(job, 40, "animation_planning", "Designing visual timeline…", progress_callback)
            timeline = self._base.planner.plan(document)

            # ── Step 5: build narration plan ─────────────────────────────────
            self._progress(job, 50, "narration_planning", "Writing narration…", progress_callback)
            narration_plan = self._narration_planner.plan(timeline)
            print(f"[{job.job_id}] Narration plan: {len(narration_plan.segments)} scene segments.")

            # ── Step 6: synthesise audio ──────────────────────────────────────
            self._progress(job, 57, "tts_generation", "Generating voice narration…", progress_callback)
            audio_segments = self._synthesise_audio(job.job_id, narration_plan)

            # ── Step 7: patch timeline hold_durations ────────────────────────
            if any(a is not None for a in audio_segments):
                self._patch_timeline_durations(timeline, audio_segments)

            # ── Step 8: render frames with patched durations ─────────────────
            self._progress(job, 63, "frame_rendering", "Rendering lesson frames…", progress_callback)
            state_images = self._base.renderer.render_state_images(timeline)

            # ── Step 9: assemble silent MP4 ───────────────────────────────────
            self._progress(job, 76, "video_encoding", "Assembling video…", progress_callback)
            silent_path = os.path.join(config.VIDEOS_DIR, f"{job.job_id}_silent.mp4")

            def sub_progress(pct: int, label: str):
                self._progress(job, pct, "video_encoding", label, progress_callback)

            self._base.assembler.assemble(
                timeline=timeline,
                state_images=state_images,
                renderer=self._base.renderer,
                output_path=silent_path,
                progress_callback=sub_progress,
            )

            # ── Step 10: mux audio into final MP4 ────────────────────────────
            output_filename = f"{job.job_id}.mp4"
            output_path = os.path.join(config.VIDEOS_DIR, output_filename)

            valid_audio = [a for a in audio_segments if a is not None]
            if valid_audio:
                self._progress(job, 90, "audio_mux", "Merging narration audio…", progress_callback)
                mux_ok = self._mux_audio(
                    silent_path, valid_audio, timeline, output_path
                )
                if not mux_ok:
                    print(f"[{job.job_id}] Audio mux failed — using silent video.")
                    os.replace(silent_path, output_path)
            else:
                print(f"[{job.job_id}] No audio segments available — using silent video.")
                os.replace(silent_path, output_path)

            # Clean up silent temp file if it still exists
            if os.path.exists(silent_path):
                try:
                    os.remove(silent_path)
                except Exception:
                    pass

            # ── Register artifact ─────────────────────────────────────────────
            try:
                import shutil
                from backend.workspace.artifact_store import artifact_store
                dest = os.path.join(artifact_store.base_dir, output_filename)
                shutil.copy2(output_path, dest)
            except Exception as art_err:
                print(f"[{job.job_id}] Artifact store copy notice: {art_err}")

            job.status = JobStatus.DONE
            job.video_path = output_path
            job.video_url = f"{config.BACKEND_URL}/artifacts/{output_filename}"
            job.step = "completed"
            job.friendly_step = "Video Complete!"
            job.progress_percentage = 100
            print(f"[{job.job_id}] Voice video ready: {output_path} ({os.path.getsize(output_path)} bytes)")

        except Exception as exc:
            import traceback
            trace = traceback.format_exc()
            print(f"[{job.job_id}] Voice pipeline failed:\n{trace}")
            job.status = JobStatus.ERROR
            job.error_message = str(exc)
            job.friendly_step = "Video generation failed"
            if progress_callback:
                progress_callback(0, f"Error: {exc}")

        return job

    # ------------------------------------------------------------------
    # TTS generation
    # ------------------------------------------------------------------

    def _get_tts(self) -> TTSService:
        if self._tts is None:
            self._tts = create_tts_service(
                provider=config.VOICE_PROVIDER,
                voice=config.VOICE_LANG,
            )
        return self._tts

    def _synthesise_audio(
        self,
        job_id: str,
        narration_plan: NarrationPlan,
    ) -> List[Optional[AudioSegment]]:
        """
        Synthesise TTS for each narration segment.
        Returns a list aligned to narration_plan.segments (None on failure).
        """
        tts = self._get_tts()
        items: List[tuple[int, str, str]] = []

        for seg in narration_plan.segments:
            audio_filename = f"{job_id}_scene_{seg.scene_index:03d}.mp3"
            audio_path = os.path.join(config.AUDIO_DIR, audio_filename)
            seg.audio_path = audio_path
            items.append((seg.scene_index, seg.text, audio_path))

        raw_results = tts.generate_batch(items)

        # Attach durations back to narration segments
        results: List[Optional[AudioSegment]] = []
        for seg, audio in zip(narration_plan.segments, raw_results):
            if audio is not None:
                seg.duration_seconds = audio.duration_seconds
                print(
                    f"[TTS] Scene {seg.scene_index}: {audio.duration_seconds:.2f}s — "
                    f"{seg.text[:60]}…"
                )
            results.append(audio)

        return results

    # ------------------------------------------------------------------
    # Timeline patching
    # ------------------------------------------------------------------

    def _patch_timeline_durations(
        self,
        timeline: AnimationTimeline,
        audio_segments: List[Optional[AudioSegment]],
    ) -> None:
        """
        Replace hold_duration in each TimelineState so the visual stays
        on screen for at least the duration of its scene's narration audio.

        Strategy: for each scene, total narration time is distributed evenly
        across all states in that scene.  A 10% buffer is added so the audio
        always finishes before the next slide appears.
        """
        # Build scene_index → audio_duration mapping
        duration_by_scene: dict[int, float] = {}
        for audio in audio_segments:
            if audio is not None:
                duration_by_scene[audio.scene_index] = audio.duration_seconds

        if not duration_by_scene:
            return

        # Group states by scene
        states_by_scene: dict[int, list] = {}
        for state in timeline.states:
            states_by_scene.setdefault(state.scene_index, []).append(state)

        total_duration = 0.0

        for scene_idx, audio_dur in duration_by_scene.items():
            scene_states = states_by_scene.get(scene_idx, [])
            if not scene_states:
                continue

            # Distribute audio duration evenly; keep transition + pause_after intact
            per_state_hold = (audio_dur * 1.1) / len(scene_states)
            for state in scene_states:
                # Only increase hold — never shorten a state that was already longer
                state.hold_duration = max(state.hold_duration, per_state_hold)

        # Recompute total_duration on the timeline
        current_time = 0.0
        for idx, state in enumerate(timeline.states):
            state.start_time = current_time
            current_time += state.total_state_duration
            # Inter-scene pause (replicate original planner logic)
            if idx < len(timeline.states) - 1:
                next_state = timeline.states[idx + 1]
                if next_state.scene_index != state.scene_index:
                    current_time += 0.5

        timeline.total_duration = current_time + 1.0  # trailing pause

    # ------------------------------------------------------------------
    # Audio/video mux
    # ------------------------------------------------------------------

    def _mux_audio(
        self,
        silent_video: str,
        audio_segments: List[AudioSegment],
        timeline: AnimationTimeline,
        output_path: str,
    ) -> bool:
        """
        Merge the silent video with the narration audio segments using FFmpeg.

        Strategy
        --------
        Each audio segment belongs to a SlideScene.  We look up the start_time
        of the first state in that scene and use FFmpeg's `adelay` filter to
        place the audio at the correct timestamp.  All delayed streams are then
        mixed together (amix) and muxed with the video.

        Returns True on success, False on any FFmpeg error.
        """
        if not audio_segments:
            return False

        # Map scene_index → scene start_time (first state in scene)
        scene_start: dict[int, float] = {}
        for state in timeline.states:
            if state.scene_index not in scene_start:
                scene_start[state.scene_index] = state.start_time

        # Build FFmpeg filter_complex for audio mixing
        # Each audio input gets an adelay equal to scene start time (milliseconds)
        inputs: List[str] = ["-i", silent_video]
        filter_parts: List[str] = []
        audio_labels: List[str] = []

        valid_segs = [
            seg for seg in audio_segments
            if seg.path and os.path.exists(seg.path) and os.path.getsize(seg.path) > 0
        ]
        if not valid_segs:
            return False

        for i, seg in enumerate(valid_segs):
            delay_ms = int(scene_start.get(seg.scene_index, 0.0) * 1000)
            inputs += ["-i", seg.path]
            label = f"[a{i}]"
            audio_labels.append(label)
            filter_parts.append(
                f"[{i + 1}:a]adelay={delay_ms}|{delay_ms}[a{i}]"
            )

        # Mix all audio streams together.
        # IMPORTANT: use duration=longest so FFmpeg waits for all adelay-placed
        # segments to finish, not just the first one (which is only ~3s long).
        n = len(valid_segs)
        mix_inputs = "".join(audio_labels)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={n}:duration=longest:dropout_transition=2:normalize=0[aout]"
        )

        filter_complex = ";".join(filter_parts)

        cmd = [
            _FFMPEG_EXE, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            # Do NOT pass -shortest: the audio may extend slightly beyond the
            # video because of the trailing narration, and that is fine.
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
            )
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")[-500:]
                print(f"[VoicePipeline] FFmpeg mux failed (rc={result.returncode}): {err}")
                return False
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                return False
            return True

        except Exception as exc:
            print(f"[VoicePipeline] FFmpeg mux exception: {exc}")
            return False

    # ------------------------------------------------------------------
    # Progress helper
    # ------------------------------------------------------------------

    @staticmethod
    def _progress(
        job: VideoJob,
        pct: int,
        step: str,
        friendly: str,
        callback: Optional[Callable[[int, str], None]],
    ) -> None:
        job.progress_percentage = pct
        job.step = step
        job.friendly_step = friendly
        if callback:
            callback(pct, friendly)
