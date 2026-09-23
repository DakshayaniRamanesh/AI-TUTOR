"""
VoiceSpeaker — Offline Voice Copilot Audio Engine for Kestrel.
Developer 1: Visual and Audio Canvas Studio.

Specifications:
- Native Qt text-to-speech via PyQt6.QtTextToSpeech (zero API key or network calls).
- Non-blocking speak(text) so the canvas and UI remain completely responsive.
- stop() immediately cancels speech when the student writes or interrupts.
- Configurable pitch, speech rate (0.9x to 1.1x natural range), and volume.
- Standalone execution speaks: 'Take a look at your second step'.
"""

import sys
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
        self._rate = 1.0       # 0.9x to 1.1x default natural range
        self._pitch = 0.0      # -1.0 to 1.0 in QtTextToSpeech
        self._volume = 1.0     # 0.0 to 1.0 in QtTextToSpeech

        if QT_TTS_AVAILABLE:
            try:
                self._engine = QTextToSpeech()
                self._engine.stateChanged.connect(self._on_state_changed)
                # Configure defaults
                self.set_rate(1.0)
                self.set_volume(1.0)
            except Exception as e:
                print(f"[VoiceSpeaker] Warning: Could not initialize QTextToSpeech: {e}")
                self._engine = None
        else:
            print("[VoiceSpeaker] Warning: PyQt6.QtTextToSpeech module is unavailable.")

    # ── Configuration Methods ─────────────────────────────────────────────────

    def set_rate(self, rate: float):
        """
        Sets speech rate. The specified natural speech range is 0.9x to 1.1x.
        In QtTextToSpeech: -1.0 is slowest, 0.0 is normal, 1.0 is 2x.
        We map 0.9x -> -0.1, 1.0x -> 0.0, 1.1x -> 0.1.
        """
        self._rate = max(0.5, min(2.0, float(rate)))
        if self._engine:
            # Map [0.5, 2.0] to Qt range [-1.0, 1.0]
            qt_rate = max(-1.0, min(1.0, (self._rate - 1.0)))
            self._engine.setRate(qt_rate)

    def set_pitch(self, pitch: float):
        """Sets voice pitch in range [-1.0, 1.0]. 0.0 is normal."""
        self._pitch = max(-1.0, min(1.0, float(pitch)))
        if self._engine:
            self._engine.setPitch(self._pitch)

    def set_volume(self, volume: float):
        """Sets playback volume in range [0.0, 1.0]."""
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._engine:
            self._engine.setVolume(self._volume)

    # ── Playback Controls ─────────────────────────────────────────────────────

    def speak(self, text: str):
        """
        Begins non-blocking text-to-speech. If currently speaking, interrupts
        and replaces with the new utterance immediately.
        """
        if not text or not text.strip():
            return

        clean_text = text.strip()
        self._current_text = clean_text

        if not self._engine:
            print(f"[VoiceSpeaker Simulation] Speaking: \"{clean_text}\"")
            self.speech_started.emit(clean_text)
            self.speech_finished.emit()
            return

        # Cancel any ongoing speech first
        self.stop()

        self.speech_started.emit(clean_text)
        self._engine.say(clean_text)

    def stop(self):
        """
        Immediately cancels ongoing speech. Crucial when the student starts
        drawing or writing on the canvas so the tutor doesn't talk over them.
        """
        if self._engine:
            # QTextToSpeech.stop() cancels speech immediately
            self._engine.stop()
        self.speech_stopped.emit()

    def is_speaking(self) -> bool:
        """Returns True if the TTS engine is currently speaking."""
        if self._engine:
            return self._engine.state() == QTextToSpeech.State.Speaking
        return False

    def _on_state_changed(self, state):
        if state == QTextToSpeech.State.Ready:
            self.speech_finished.emit()
        elif state == QTextToSpeech.State.Error:
            self.speech_error.emit("TTS Engine encountered an error.")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)
    speaker = VoiceSpeaker()

    print("[VoiceSpeaker Test] Initializing speech test...")
    test_sentence = "Take a look at your second step"
    
    speaker.speech_started.connect(lambda txt: print(f"[VoiceSpeaker] Spoken output started: '{txt}'"))
    speaker.speech_finished.connect(lambda: print("[VoiceSpeaker] Spoken output finished cleanly."))

    speaker.speak(test_sentence)

    # Allow event loop to run long enough for audio output, then exit
    QTimer.singleShot(3500, app.quit)
    sys.exit(app.exec())
