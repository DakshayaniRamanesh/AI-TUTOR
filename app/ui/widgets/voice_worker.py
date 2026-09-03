"""
VoiceWorker — Background QThread for mic recording + Groq Whisper transcription.

Design guarantees:
- Audio device released cleanly via threading.Event + stream.stop()/close() — never QThread.terminate().
- Temp WAV deleted in try/finally — always deleted even on API failure.
- All UI state communicated via Qt signals only — zero widget touches from this thread.
- Distinct error messages for rate-limit (429), network/timeout, and generic failures.
"""

import os
import uuid
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
from dotenv import load_dotenv

from PyQt6.QtCore import QThread, pyqtSignal

# ── Load env the same way stem_solver.py does ────────────────────────────────
load_dotenv()
load_dotenv("backend/.env")
_here = os.path.dirname(__file__)
load_dotenv(os.path.join(_here, "..", "..", "..", "..", "backend", ".env"))
load_dotenv(os.path.join(_here, "..", "..", "..", "backend", ".env"))

# ── Constants ─────────────────────────────────────────────────────────────────
_SAMPLE_RATE         = 16_000          # Whisper works best at 16 kHz
_CHANNELS            = 1              # Mono
_DTYPE               = "float32"
_MAX_SECONDS         = 75             # Hard recording cap
_GROQ_MODEL_PRIMARY  = "whisper-large-v3-turbo"
_GROQ_MODEL_FALLBACK = "whisper-large-v3"
_GROQ_AUDIO_URL      = "https://api.groq.com/openai/v1/audio/transcriptions"


class VoiceWorker(QThread):
    """
    Lifecycle managed by AskBar:
        worker = VoiceWorker()
        worker.recording_started.connect(...)
        worker.start()          # begins recording immediately on the worker thread
        # user clicks stop:
        worker.request_stop()   # sets threading.Event → graceful drain + transcribe
    """

    # Signals — cross-thread delivery to the main thread via Qt's event loop
    recording_started      = pyqtSignal()    # audio stream is live
    transcription_started  = pyqtSignal()    # upload begun
    transcription_complete = pyqtSignal(str) # transcribed text (may be empty)
    error                  = pyqtSignal(str) # user-facing error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event   = threading.Event()
        self._audio_chunks: list[np.ndarray] = []
        self._chunk_lock   = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def request_stop(self):
        """Call from the main thread to stop recording and trigger transcription."""
        self._stop_event.set()

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self):
        self._audio_chunks = []

        # 1. Open InputStream and record until stopped or max duration reached
        stream = None
        try:
            stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                callback=self._audio_callback,
            )
            stream.start()
            self.recording_started.emit()

            # Block this thread until stop requested or timeout
            self._stop_event.wait(timeout=_MAX_SECONDS)

            # Graceful release — PortAudio device freed before any network call
            stream.stop()
            stream.close()
            stream = None

        except Exception as exc:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self.error.emit(f"Couldn't start microphone: {exc}")
            return

        # 2. Assemble captured audio
        with self._chunk_lock:
            if not self._audio_chunks:
                self.error.emit("No audio captured — please try again.")
                return
            audio_data = np.concatenate(self._audio_chunks, axis=0)

        # 3. Transcribe — temp WAV guaranteed deleted in finally
        self.transcription_started.emit()
        tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"kestrel_voice_{uuid.uuid4().hex}.wav"
        )
        try:
            sf.write(tmp_path, audio_data, _SAMPLE_RATE)
            result = self._transcribe(tmp_path)
            if result is not None:
                self.transcription_complete.emit(result)
        finally:
            # Runs unconditionally — success, exception, 429, network failure, all cases
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """sounddevice callback — called on each audio block, must be fast."""
        if self._stop_event.is_set():
            return  # Don't append after stop requested
        with self._chunk_lock:
            self._audio_chunks.append(indata.copy())

    def _transcribe(self, wav_path: str) -> "str | None":
        """
        POST wav_path to Groq Whisper. Returns transcription string or None (after emitting error).
        Does NOT auto-retry on 429 — surfaces the error immediately.
        Falls back from turbo to standard model only on HTTP 404 (model not on account).
        """
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            self.error.emit("GROQ_API_KEY not configured — check backend/.env.")
            return None

        headers = {"Authorization": f"Bearer {api_key}"}

        models = [_GROQ_MODEL_PRIMARY, _GROQ_MODEL_FALLBACK]
        for model in models:
            try:
                with open(wav_path, "rb") as f:
                    resp = requests.post(
                        _GROQ_AUDIO_URL,
                        headers=headers,
                        files={"file": (os.path.basename(wav_path), f, "audio/wav")},
                        data={"model": model, "response_format": "text"},
                        timeout=30,
                    )

                if resp.status_code == 200:
                    return resp.text.strip()

                if resp.status_code == 429:
                    # Rate-limit: do NOT retry, surface immediately
                    self.error.emit("Rate limit reached — please wait a moment and try again.")
                    return None

                if resp.status_code == 404 and model == _GROQ_MODEL_PRIMARY:
                    # Turbo not available on this account — try fallback
                    continue

                self.error.emit(
                    f"Couldn't transcribe that — please try again. (HTTP {resp.status_code})"
                )
                return None

            except requests.exceptions.Timeout:
                self.error.emit("Couldn't reach the server — check your connection.")
                return None
            except requests.exceptions.ConnectionError:
                self.error.emit("Couldn't reach the server — check your connection.")
                return None
            except Exception:
                self.error.emit("Couldn't transcribe that — please try again.")
                return None

        # Both models exhausted (only reachable if fallback also 404s)
        self.error.emit("Couldn't transcribe that — please try again.")
        return None
