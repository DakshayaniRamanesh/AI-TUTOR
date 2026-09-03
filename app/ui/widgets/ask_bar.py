"""
Persistent STEM / Math & PDF Question Bar docked at the bottom of the canvas
Monochrome / Technical Aesthetic

Voice input added: mic button (click-to-toggle) → background VoiceWorker thread
→ Groq Whisper transcription → text placed in input field for user to review.
"""

import traceback
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox, QLabel,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QPropertyAnimation, QEasingCurve, QTimer, QSize
import qtawesome as qta

from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss
from .voice_worker import VoiceWorker


# ── State sentinel values ──────────────────────────────────────────────────────
_STATE_IDLE         = "idle"
_STATE_RECORDING    = "recording"
_STATE_TRANSCRIBING = "transcribing"
_COOLDOWN_MS        = 4_000   # ms before mic re-enables after transcription


class AskBar(QWidget):
    question_submitted = pyqtSignal(str)
    mode_changed = pyqtSignal(str)  # Emits "classroom" or "study"
    question_with_context_submitted = pyqtSignal(str, str, int, str)
    pdf_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pdf_mode = False
        self.current_selected_text = ""
        self.current_page_num = None
        self.surrounding_context = ""
        self.doc_filename = ""

        self._mic_state = _STATE_IDLE
        self._voice_worker: VoiceWorker | None = None
        self._pulse_anim: QPropertyAnimation | None = None
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self._cooldown_active = False

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        # AskBar lives inside the pill's QHBoxLayout — must itself be a flat
        # single-row widget. No vertical stacking here.
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget(self)
        container.setObjectName("AskBarContainer")
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(8, 4, 8, 4)
        c_layout.setSpacing(6)

        # PDF upload button
        self.btn_pdf = QPushButton("PDF", container)
        self.btn_pdf.setObjectName("BtnPdf")
        self.btn_pdf.clicked.connect(self.pdf_requested.emit)

        self.input_field = QLineEdit(container)
        self.input_field.setPlaceholderText(
            "Ask AI a question (e.g. 25*14, d/dx(x^3), integral of sin(x)...)"
        )
        self.input_field.returnPressed.connect(self._submit)

        # ── Mic button (fixed 28×28 — never changes size in any state) ────────
        self.btn_mic = QPushButton(container)
        self.btn_mic.setObjectName("BtnMic")
        self.btn_mic.setFixedSize(28, 28)
        self.btn_mic.setIconSize(QSize(18, 18))
        self.btn_mic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_mic.setAutoDefault(False)
        self.btn_mic.setToolTip("Click to start voice input")
        self.btn_mic.clicked.connect(self._on_mic_clicked)
        self.btn_mic.setStyleSheet(self._mic_idle_qss(ThemeManager.instance().get_colors()))

        self.mode_combo = QComboBox(container)
        self.mode_combo.addItem("Classroom Mode", "classroom")
        self.mode_combo.addItem("Study Mode", "study")
        self.mode_combo.setCurrentIndex(1)
        self.mode_combo.setToolTip(
            "Classroom Mode: Direct answer only\nStudy Mode: Detailed step-by-step solution"
        )
        self.mode_combo.currentIndexChanged.connect(self._on_combo_mode_changed)

        self.btn_ask = QPushButton("ASK AI", container)
        self.btn_ask.setObjectName("BtnAsk")
        self.btn_ask.clicked.connect(self._submit)

        c_layout.addWidget(self.btn_pdf)
        c_layout.addWidget(self.input_field, stretch=1)
        c_layout.addWidget(self.btn_mic)
        c_layout.addWidget(self.mode_combo)
        c_layout.addWidget(self.btn_ask)

        main_layout.addWidget(container)

        # Initialise mic to idle visual state
        self._set_mic_state(_STATE_IDLE)

        # ── DIAGNOSTIC PRINTS (Immediate & Post-Layout) ────────────────────────
        print("\n" + "="*50)
        print("[AskBar DIAGNOSTIC - Immediate _init_ui]")
        print(f"AskBar main_layout count: {main_layout.count()}")
        print(f"btn_mic object: {self.btn_mic}")
        print(f"btn_mic isVisible (pre-show): {self.btn_mic.isVisible()}")
        print(f"btn_mic geometry: x={self.btn_mic.x()}, y={self.btn_mic.y()}, w={self.btn_mic.width()}, h={self.btn_mic.height()}")
        print(f"btn_mic active stylesheet:\n{self.btn_mic.styleSheet()}")
        print("="*50 + "\n")

        # Delayed inspection after main window completes layout and renders
        QTimer.singleShot(1500, self._print_runtime_diagnostics)

    def _print_runtime_diagnostics(self):
        print("\n" + "#"*60)
        print("[AskBar DIAGNOSTIC - Post-Layout / Runtime Check]")
        print(f"AskBar visible: {self.isVisible()}, size: {self.width()}x{self.height()}, pos: ({self.x()}, {self.y()})")
        print(f"AskBar parent: {self.parent()}")
        
        container = self.findChild(QWidget, "AskBarContainer")
        if container:
            cl = container.layout()
            print(f"AskBarContainer visible: {container.isVisible()}, size: {container.width()}x{container.height()}")
            print(f"AskBarContainer layout items count: {cl.count() if cl else 'No layout'}")
            if cl:
                for i in range(cl.count()):
                    item = cl.itemAt(i)
                    w = item.widget()
                    if w:
                        print(f"  Item [{i}] Class={w.__class__.__name__}, ObjectName='{w.objectName()}', "
                              f"Visible={w.isVisible()}, Geometry=({w.x()}, {w.y()}, {w.width()}x{w.height()})")
                    else:
                        print(f"  Item [{i}] Non-widget item: {item}")
        else:
            print("AskBarContainer NOT found!")

        print(f"\nbtn_mic Details:")
        print(f"  btn_mic isVisible(): {self.btn_mic.isVisible()}")
        print(f"  btn_mic isHidden(): {self.btn_mic.isHidden()}")
        print(f"  btn_mic isEnabled(): {self.btn_mic.isEnabled()}")
        print(f"  btn_mic geometry(): x={self.btn_mic.x()}, y={self.btn_mic.y()}, w={self.btn_mic.width()}, h={self.btn_mic.height()}")
        print(f"  btn_mic icon isNull: {self.btn_mic.icon().isNull()}")
        print(f"  btn_mic iconSize: {self.btn_mic.iconSize().width()}x{self.btn_mic.iconSize().height()}")
        print(f"  btn_mic active stylesheet:\n{self.btn_mic.styleSheet()}")
        print("#"*60 + "\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Mic state machine
    # ─────────────────────────────────────────────────────────────────────────

    def _set_mic_state(self, state: str):
        self._mic_state = state
        c = ThemeManager.instance().get_colors()

        if state == _STATE_IDLE:
            self._stop_pulse()
            icon = qta.icon("ri.mic-line", color=c["text_primary"])
            self.btn_mic.setIcon(icon)
            self.btn_mic.setEnabled(not self._cooldown_active)
            self.btn_mic.setStyleSheet(self._mic_idle_qss(c))
            self.btn_mic.setToolTip("Click to start voice input")
            # Restore placeholder if it was set to "Transcribing…"
            if self.input_field.placeholderText() == "Transcribing…":
                self._restore_placeholder()

        elif state == _STATE_RECORDING:
            icon = qta.icon("ri.mic-fill", color=c["accent_text"])
            self.btn_mic.setIcon(icon)
            self.btn_mic.setEnabled(True)
            self.btn_mic.setStyleSheet(self._mic_recording_qss(c))
            self.btn_mic.setToolTip("Click to stop and transcribe")
            self._start_pulse()

        elif state == _STATE_TRANSCRIBING:
            self._stop_pulse()
            spinner_icon = qta.icon(
                "fa5s.spinner",
                color=c["text_secondary"],
                animation=qta.Spin(self.btn_mic),
            )
            self.btn_mic.setIcon(spinner_icon)
            self.btn_mic.setEnabled(False)
            self.btn_mic.setStyleSheet(self._mic_idle_qss(c))
            self.btn_mic.setToolTip("Transcribing…")
            self.input_field.setPlaceholderText("Transcribing…")

    def _start_pulse(self):
        """Breathing pulse via QGraphicsOpacityEffect — dynamically attached only while recording."""
        self._stop_pulse()
        self._opacity_effect = QGraphicsOpacityEffect(self.btn_mic)
        self._opacity_effect.setOpacity(1.0)
        self.btn_mic.setGraphicsEffect(self._opacity_effect)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(900)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.5, 0.55)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)  # infinite loop
        anim.start()
        self._pulse_anim = anim

    def _stop_pulse(self):
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None
        if self._opacity_effect is not None:
            self.btn_mic.setGraphicsEffect(None)
            self._opacity_effect = None

    def _show_error(self, message: str):
        """Show error briefly in the input field placeholder — zero layout impact."""
        # Save current placeholder so we can restore it
        self._saved_placeholder = self.input_field.placeholderText()
        c = ThemeManager.instance().get_colors()
        self.input_field.setPlaceholderText(f"⚠ {message}")
        QTimer.singleShot(4000, self._clear_error)

    def _clear_error(self):
        # Restore the placeholder that was active before the error
        placeholder = getattr(self, '_saved_placeholder', "")
        if placeholder:
            self.input_field.setPlaceholderText(placeholder)
        else:
            self._restore_placeholder()
    def _start_cooldown(self):
        """Prevent rapid-fire requests burning free-tier quota."""
        self._cooldown_active = True
        self.btn_mic.setEnabled(False)
        QTimer.singleShot(_COOLDOWN_MS, self._end_cooldown)

    def _end_cooldown(self):
        self._cooldown_active = False
        if self._mic_state == _STATE_IDLE:
            self.btn_mic.setEnabled(True)

    # ─────────────────────────────────────────────────────────────────────────
    # Mic click handler
    # ─────────────────────────────────────────────────────────────────────────

    def _on_mic_clicked(self):
        print(f"\n[AskBar DEBUG] >>> _on_mic_clicked() triggered! Current state: '{self._mic_state}', cooldown: {self._cooldown_active} <<<")
        if self._cooldown_active:
            return

        if self._mic_state == _STATE_IDLE:
            self._start_recording()
        elif self._mic_state == _STATE_RECORDING:
            self._stop_recording()
        # TRANSCRIBING state: button is disabled, click can't happen

    def _start_recording(self):
        """Create a fresh VoiceWorker and begin recording."""
        # Clean up any previous (finished) worker
        if self._voice_worker is not None:
            self._voice_worker.deleteLater()
            self._voice_worker = None

        worker = VoiceWorker(parent=None)
        worker.recording_started.connect(self._on_recording_started)
        worker.transcription_started.connect(self._on_transcription_started)
        worker.transcription_complete.connect(self._on_transcription_complete)
        worker.error.connect(self._on_voice_error)
        worker.finished.connect(self._on_worker_finished)
        self._voice_worker = worker
        worker.start()

    def _stop_recording(self):
        """Signal the worker to stop and begin transcription."""
        if self._voice_worker is not None and self._voice_worker.isRunning():
            self._set_mic_state(_STATE_TRANSCRIBING)
            self._voice_worker.request_stop()

    # ─────────────────────────────────────────────────────────────────────────
    # Worker signal handlers — all run on the main thread
    # ─────────────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_recording_started(self):
        self._set_mic_state(_STATE_RECORDING)

    @pyqtSlot()
    def _on_transcription_started(self):
        self._set_mic_state(_STATE_TRANSCRIBING)

    @pyqtSlot(str)
    def _on_transcription_complete(self, text: str):
        self._set_mic_state(_STATE_IDLE)
        if text:
            self.input_field.setText(text)
            self.input_field.setFocus()
            self.input_field.setCursorPosition(len(text))
        self._start_cooldown()

    @pyqtSlot(str)
    def _on_voice_error(self, message: str):
        self._set_mic_state(_STATE_IDLE)
        self._show_error(message)
        self._start_cooldown()

    @pyqtSlot()
    def _on_worker_finished(self):
        """Safety net: ensure idle state if worker finishes without emitting a terminal signal."""
        if self._mic_state != _STATE_IDLE:
            self._set_mic_state(_STATE_IDLE)

    # ─────────────────────────────────────────────────────────────────────────
    # QSS helpers for mic button states
    # ─────────────────────────────────────────────────────────────────────────

    def _mic_idle_qss(self, c: dict) -> str:
        # High contrast styling: #f0f0f0 background, #888888 border in light mode
        is_dark = ThemeManager.instance().is_dark()
        bg_col = "#1a1a1f" if is_dark else "#f0f0f0"
        border_col = "#666666" if is_dark else "#888888"
        hover_bg = "#282830" if is_dark else "#e0e0e0"

        return (
            "QPushButton#BtnMic {"
            f" background-color: {bg_col};"
            f" color: {c['text_primary']};"
            f" border: 1px solid {border_col};"
            "  border-radius: 4px;"
            "  padding: 0px;"
            "}"
            "QPushButton#BtnMic:hover {"
            f" background-color: {hover_bg};"
            f" border-color: {c['accent']};"
            f" color: {c['text_primary']};"
            "}"
            "QPushButton#BtnMic:disabled {"
            "  opacity: 0.4;"
            "}"
        )

    def _mic_recording_qss(self, c: dict) -> str:
        return (
            "QPushButton#BtnMic {"
            f" background-color: {c['accent']};"
            f" border: 1px solid {c['accent']};"
            "  border-radius: 4px;"
            "  padding: 0px;"
            "}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Existing AskBar methods — unchanged
    # ─────────────────────────────────────────────────────────────────────────

    def _on_combo_mode_changed(self, index: int):
        mode = self.get_mode()
        if mode == "classroom":
            self.input_field.setPlaceholderText("Classroom Mode: Ask for direct solutions...")
        else:
            self.input_field.setPlaceholderText("Study Mode: Ask for step-by-step explanations...")
        self.mode_changed.emit(mode)

    def get_mode(self) -> str:
        return self.mode_combo.currentData() or "study"

    def set_mode(self, mode: str):
        idx = 0 if mode == "classroom" else 1
        self.mode_combo.setCurrentIndex(idx)

    def _restore_placeholder(self):
        """Restore the appropriate placeholder text after transcription."""
        if self.is_pdf_mode:
            doc_name = self.doc_filename[:20] + "..." if len(self.doc_filename) > 22 else self.doc_filename
            self.input_field.setPlaceholderText(f"Analyze '{doc_name}'...")
        elif self.get_mode() == "classroom":
            self.input_field.setPlaceholderText("Classroom Mode: Ask for direct solutions...")
        else:
            self.input_field.setPlaceholderText("Study Mode: Ask for step-by-step explanations...")

    def set_pdf_mode(self, active: bool, filename: str = ""):
        self.is_pdf_mode = active
        self.doc_filename = filename
        self.current_selected_text = ""
        self.current_page_num = None
        c = ThemeManager.instance().get_colors()

        if active:
            doc_name = filename[:20] + "..." if len(filename) > 22 else filename
            self.input_field.setPlaceholderText(f"Analyze '{doc_name}'...")
            self.btn_pdf.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['accent']};
                    color: {c['accent_text']};
                    border: 1px solid {c['accent']};
                    border-radius: 2px;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 8px;
                }}
            """)
        else:
            self.input_field.setPlaceholderText("Ask AI a question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
            self.btn_pdf.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text_secondary']};
                    border: 1px solid {c['border_color']};
                    border-radius: 2px;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    border-color: {c['accent']};
                    color: {c['text_primary']};
                }}
            """)

    def set_selection_context(self, selected_text: str, page_num: int, surrounding_context: str = ""):
        self.current_selected_text = selected_text
        self.current_page_num = page_num
        self.surrounding_context = surrounding_context

        snippet = selected_text[:35].replace('\n', ' ')
        if not snippet:
            snippet = f"Passage on Page {page_num}"

        self.input_field.setPlaceholderText(f"Question about [P.{page_num}]: \"{snippet}...\"")
        self.input_field.setFocus()

    def _submit(self):
        text = self.input_field.text().strip()

        if self.current_selected_text:
            q_text = text if text else "Explain and solve this selected passage step-by-step."
            self.question_with_context_submitted.emit(
                q_text, self.current_selected_text,
                self.current_page_num or 1, self.surrounding_context
            )
            self.current_selected_text = ""
            self.current_page_num = None
            self.surrounding_context = ""
            if self.is_pdf_mode:
                doc_name = self.doc_filename[:20] + "..." if len(self.doc_filename) > 22 else self.doc_filename
                self.input_field.setPlaceholderText(f"Analyze '{doc_name}'...")
        elif text:
            self.question_submitted.emit(text)

        self.input_field.clear()

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            QWidget#AskBarContainer {{
                background-color: {c['bg_toolbar']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                font-family: {MONO_FONT};
                font-size: 13px;
                padding-left: 6px;
                color: {c['text_primary']};
            }}
            QComboBox {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 3px 8px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 14px;
            }}
            QPushButton#BtnPdf {{
                background-color: transparent;
                color: {c['text_secondary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 8px;
            }}
            QPushButton#BtnPdf:hover {{
                border-color: {c['accent']};
                color: {c['text_primary']};
            }}
            QPushButton#BtnMic {{
                background-color: {c['panel_card_bg'] if not ThemeManager.instance().is_dark() else '#1a1a1f'};
                color: {c['text_primary']};
                border: 1px solid {'#888888' if not ThemeManager.instance().is_dark() else '#666666'};
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton#BtnMic:hover {{
                background-color: {c['border_color'] if not ThemeManager.instance().is_dark() else '#282830'};
                border-color: {c['accent']};
            }}
            QPushButton#BtnAsk {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                border: 1px solid {c['accent']};
                border-radius: 2px;
                padding: 4px 12px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#BtnAsk:hover {{
                background-color: {c['accent_hover']};
            }}
        """)
        # Re-apply mic button style for current state
        self._set_mic_state(self._mic_state)


