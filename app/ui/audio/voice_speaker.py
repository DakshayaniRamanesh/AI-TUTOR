"""
VoiceSpeaker — Offline Voice Copilot Audio Engine for Kestrel.
"""
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

try:
    from PyQt6.QtTextToSpeech import QTextToSpeech
    QT_TTS_AVAILABLE = True
except ImportError:
    QT_TTS_AVAILABLE = False


class VoiceSpeaker(QObject):
    """
    Local Text-to-Speech engine providing spoken feedback from the Socratic tutor.
    """
    speech_started = pyqtSignal(str)
    speech_finished = pyqtSignal()
    speech_stopped = pyqtSignal()
    speech_error = pyqtSignal(str)

    _instance = None

    @classmethod
    def instance(cls) -> "VoiceSpeaker":
        """Singleton accessor for coordinated canvas audio control."""
        if cls._instance is None:
            cls._instance = VoiceSpeaker()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine: Optional[QTextToSpeech] = None
        self._current_text = ""
        self._last_spoken_text = ""
        self._rate = 1.0
        self._pitch = 0.0
        self._volume = 1.0
        self.enabled = True

        if QT_TTS_AVAILABLE:
            try:
                self._engine = QTextToSpeech()
                self._engine.stateChanged.connect(self._on_state_changed)
                self.set_rate(1.0)
                self.set_volume(1.0)
            except Exception as e:
                self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def set_rate(self, rate: float):
        self._rate = max(0.5, min(2.0, float(rate)))
        if self._engine:
            qt_rate = max(-1.0, min(1.0, (self._rate - 1.0)))
            self._engine.setRate(qt_rate)

    def set_pitch(self, pitch: float):
        self._pitch = max(-1.0, min(1.0, float(pitch)))
        if self._engine:
            self._engine.setPitch(self._pitch)

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._engine:
            self._engine.setVolume(self._volume)

    def speak(self, text: str):
        if not self.enabled:
            return

        if not text or not text.strip():
            return

        clean_text = text.strip()
        
        if clean_text == self._last_spoken_text:
            return

        self._current_text = clean_text
        self._last_spoken_text = clean_text

        if not self._engine:
            self.speech_error.emit("TTS Engine unavailable")
            return

        self.stop()
        self.speech_started.emit(clean_text)
        self._engine.say(clean_text)

    def stop(self):
        if self._engine and self._engine.state() == QTextToSpeech.State.Speaking:
            self._engine.stop()
        self._last_spoken_text = ""
        self.speech_stopped.emit()

    def is_speaking(self) -> bool:
        if self._engine:
            return self._engine.state() == QTextToSpeech.State.Speaking
        return False

    def _on_state_changed(self, state):
        if state == QTextToSpeech.State.Ready:
            self.speech_finished.emit()
        elif state == QTextToSpeech.State.Error:
            self.speech_error.emit("TTS Engine encountered an error.")
