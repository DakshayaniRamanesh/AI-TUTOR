"""
Text-to-Speech Service for LaTeX Video Narration.

Provides a clean TTSService abstraction so the video pipeline is decoupled
from any specific TTS implementation.  The active provider (EdgeTTSProvider)
uses Microsoft Edge TTS via the `edge-tts` package and measures audio
duration with `mutagen` rather than relying on estimated values.

Provider contract
-----------------
* generate(text, output_path) -> AudioSegment | None
  Returns an AudioSegment on success, or None on any failure.
  The pipeline treats None as "no audio for this segment" and continues.

* generate_batch(segments) -> List[AudioSegment | None]
  Convenience wrapper for processing multiple segments.
"""

from __future__ import annotations

import asyncio
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AudioSegment:
    """Result of a single TTS generation request."""
    scene_index: int          # Which SlideScene this audio belongs to
    path: str                 # Absolute path to the generated MP3 file
    duration_seconds: float   # Actual audio duration (measured, not estimated)
    text: str                 # The narration text that was synthesised
    frame_index: int = 0      # Which progressive frame (1-indexed) this audio belongs to


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TTSService(ABC):
    """Abstract TTS provider — swap EdgeTTSProvider for any other provider."""

    @abstractmethod
    def generate(
        self,
        text: str,
        output_path: str,
        scene_index: int = 0,
        frame_index: int = 0,
    ) -> Optional[AudioSegment]:
        """
        Synthesise `text` to audio and write the file to `output_path`.

        Returns
        -------
        AudioSegment  on success
        None          on any failure (network, quota, bad text, …)
        """

    def generate_batch(
        self,
        items: List[tuple],
    ) -> List[Optional[AudioSegment]]:
        """
        Generate audio for multiple tuples:
        Either (scene_index, text, output_path)
        or (scene_index, text, output_path, frame_index).
        Items whose `text` is empty are skipped and return None.
        """
        results: List[Optional[AudioSegment]] = []
        for item in items:
            if len(item) == 4:
                scene_index, text, output_path, frame_index = item
            else:
                scene_index, text, output_path = item
                frame_index = 0

            if not text or not text.strip():
                results.append(None)
                continue
            results.append(self.generate(text, output_path, scene_index=scene_index, frame_index=frame_index))
        return results


# ---------------------------------------------------------------------------
# Edge TTS provider
# ---------------------------------------------------------------------------

class EdgeTTSProvider(TTSService):
    """
    TTS provider backed by Microsoft Edge TTS (edge-tts package).

    The package uses an undocumented but publicly accessible Microsoft API
    and supports a wide range of neural voices.  No API key required.
    """

    def __init__(
        self,
        voice: str = "en-GB-RyanNeural",
        rate: str = "+4%",
        pitch: str = "+0Hz",
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def generate(
        self,
        text: str,
        output_path: str,
        scene_index: int = 0,
        frame_index: int = 0,
    ) -> Optional[AudioSegment]:
        """Synthesise text to MP3 and return an AudioSegment with real duration."""
        if not text or not text.strip():
            return None

        try:
            import edge_tts  # noqa: PLC0415  (lazy import)
        except ImportError:
            print("[TTSService] edge-tts not installed. Run: pip install edge-tts")
            return None

        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            # edge-tts is async; run it in a new event loop
            asyncio.run(self._async_generate(edge_tts, text, output_path))
        except Exception as gen_err:
            label = f"frame {frame_index}" if frame_index else f"scene {scene_index}"
            print(f"[TTSService] TTS generation failed for {label}: {gen_err}")
            return None

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            label = f"frame {frame_index}" if frame_index else f"scene {scene_index}"
            print(f"[TTSService] TTS produced an empty file for {label}.")
            return None

        duration = _measure_mp3_duration(output_path)
        return AudioSegment(
            scene_index=scene_index,
            path=output_path,
            duration_seconds=duration,
            text=text,
            frame_index=frame_index,
        )

    async def _async_generate(self, edge_tts, text: str, output_path: str) -> None:
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicate.save(output_path)


# ---------------------------------------------------------------------------
# Duration measurement
# ---------------------------------------------------------------------------

def _measure_mp3_duration(path: str) -> float:
    """
    Measure the real duration of an MP3 file using mutagen.
    Falls back to a conservative estimate (reading_speed model) if mutagen
    is unavailable or the file cannot be parsed.
    """
    try:
        from mutagen.mp3 import MP3  # noqa: PLC0415
        audio = MP3(path)
        return float(audio.info.length)
    except Exception:
        pass

    # Rough fallback: estimate from file size assuming 128 kbps MP3
    try:
        size_bytes = os.path.getsize(path)
        return max(1.0, size_bytes / (128 * 1024 / 8))
    except Exception:
        return 3.0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_tts_service(
    provider: str = "edge_tts",
    voice: str = "en-GB-RyanNeural",
    rate: str = "+4%",
    pitch: str = "+0Hz",
) -> TTSService:
    """
    Factory that returns a TTSService for the requested provider.

    Parameters
    ----------
    provider : str
        "edge_tts" (default).  Extend here to support other providers.
    voice : str
        Provider-specific voice identifier (default: en-GB-RyanNeural — British English).
    rate : str
        Speech rate offset (default: +4% for active, responsive pacing).
    pitch : str
        Speech pitch offset (default: +0Hz for natural warm tone).
    """
    if provider == "edge_tts":
        return EdgeTTSProvider(voice=voice, rate=rate, pitch=pitch)
    raise ValueError(f"Unknown TTS provider: {provider!r}. Supported: 'edge_tts'")
