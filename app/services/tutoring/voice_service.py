import re
import threading
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from backend.latex_video.narration_planner import _LatexToSpeech

def clean_text_for_speech(text: str) -> str:
    """
    Cleans markdown formatting, citations, and converts LaTeX into natural spoken English.
    """
    if not text:
        return ""

    # 1. Translate mathematical LaTeX to spoken English
    spoken = _LatexToSpeech.translate(text)

    # 2. Strip Markdown headings, asterisks, backticks
    spoken = re.sub(r'#+\s*', '', spoken)
    spoken = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', spoken)
    spoken = re.sub(r'`([^`]+)`', r'\1', spoken)

    # 3. Strip bracket citations like [1], [Page 3]
    spoken = re.sub(r'\[\d+\]', '', spoken)

    # 4. Collapse whitespace
    spoken = re.sub(r'\s+', ' ', spoken).strip()
    return spoken

class VoiceNarrationService(QObject):
    """
    Asynchronous text-to-speech service for Kestrel.
    Speaks the exact feedback shown on screen, translated to conversational mathematics.
    Runs non-blocking on Windows SAPI.SpVoice with immediate cancellation support.
    """

    _instance: Optional['VoiceNarrationService'] = None
    narration_finished = pyqtSignal()

    @classmethod
    def instance(cls) -> 'VoiceNarrationService':
        if cls._instance is None:
            cls._instance = VoiceNarrationService()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._current_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_playing = False
        self._lock = threading.Lock()

    def is_playing(self) -> bool:
        return self._is_playing

    def stop(self):
        """Immediately stop any current active narration."""
        with self._lock:
            self._stop_event.set()
            self._is_playing = False

    def speak(self, text: str, on_finished: Optional[Callable[[], None]] = None):
        """
        Asynchronously speaks the provided text.
        Cancels any ongoing playback first.
        """
        self.stop()

        clean_spoken = clean_text_for_speech(text)
        if not clean_spoken:
            if on_finished:
                on_finished()
            return

        if on_finished:
            def _once():
                try:
                    self.narration_finished.disconnect(_once)
                except (TypeError, RuntimeError):
                    pass
                on_finished()
            self.narration_finished.connect(_once)

        with self._lock:
            self._stop_event.clear()
            self._is_playing = True

            def _run():
                try:
                    import win32com.client
                    import pythoncom
                    # Initialize COM for the background thread
                    pythoncom.CoInitialize()
                    try:
                        voice = win32com.client.Dispatch("SAPI.SpVoice")
                        # SVSFlagsAsync = 1, SVSFPurgeBeforeSpeak = 2
                        # We speak in chunks or check stop_event
                        sentences = re.split(r'(?<=[.!?])\s+', clean_spoken)
                        for sentence in sentences:
                            if self._stop_event.is_set():
                                break
                            if sentence.strip():
                                # Speak synchronously inside the background thread
                                voice.Speak(sentence.strip())
                    finally:
                        pythoncom.CoUninitialize()
                except Exception as e:
                    print(f"[VoiceNarrationService] Playback warning: {e}")
                finally:
                    with self._lock:
                        self._is_playing = False
                    self.narration_finished.emit()

            self._current_thread = threading.Thread(target=_run, daemon=True)
            self._current_thread.start()
