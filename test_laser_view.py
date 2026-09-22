"""
test_laser_view.py — Standalone Test Scene for Developer 1: Visual and Audio Canvas Studio.

Specifications from Plan:
- Blank canvas with interactive buttons.
- Button: Move laser pointer from (0, 0) to (400, 300) and demonstrate idle pulse.
- Button: Animate Ghost Chalk around QRectF(200, 150, 120, 50) in Error mode (#ff6b6b).
- Button: Animate Ghost Chalk in Verified mode (#2ecc71).
- Button: VoiceSpeaker test speaking 'Take a look at your second step'.
- Button: SocraticHintBubble test with progressive disclosure.
- Button: Run Full Coordinated Chain.
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsView, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont

from app.ui.canvas_scene import CanvasScene
from app.ui.items.laser_pointer_item import LaserPointerItem
from app.ui.items.ghost_chalk_item import GhostChalkItem, GhostChalkMode
from app.ui.audio.voice_speaker import VoiceSpeaker
from app.ui.widgets.socratic_hint_bubble import SocraticHintBubble
from app.ui.kestrel_theme import MONO_FONT


class TestLaserViewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Developer 1 Test Studio: Laser Pointer, Ghost Chalk & Audio Copilot")
        self.resize(1000, 720)

        # Central Widget
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # ── Header Bar ──
        header = QHBoxLayout()
        title_lbl = QLabel("DEVELOPER 1: VISUAL & AUDIO TEST STUDIO", self)
        title_lbl.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 13px; font-weight: 800; color: #0f172a;")
        header.addWidget(title_lbl)
        header.addStretch(1)

        self.status_lbl = QLabel("Ready for test triggers.", self)
        self.status_lbl.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 11px; color: #64748b;")
        header.addWidget(self.status_lbl)
        root_layout.addLayout(header)

        # ── Canvas View ──
        self.scene = CanvasScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        root_layout.addWidget(self.view, stretch=1)

        # ── Add Reference Math Sample Item on Canvas ──
        math_label = self.scene.addText("Step 1:  3x - (2x - 5) = 14\nStep 2:  3x - 2x - 5 = 14\nStep 3:  x - 5 = 14")
        math_label.setDefaultTextColor(QColor("#0f172a"))
        math_label.setFont(QFont("Consolas", 14))
        math_label.setPos(180, 120)

        # ── Control Toolbar ──
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        # 1. Laser Pointer Test (0, 0) -> (400, 300)
        self.btn_laser = QPushButton("1. Move Laser (0,0 → 400,300)", self)
        self._style_button(self.btn_laser, "#2563eb")
        self.btn_laser.clicked.connect(self._test_laser_movement)
        btn_bar.addWidget(self.btn_laser)

        # 2. Ghost Chalk Error Mode
        self.btn_chalk_err = QPushButton("2. Ghost Chalk (Error #ff6b6b)", self)
        self._style_button(self.btn_chalk_err, "#dc2626")
        self.btn_chalk_err.clicked.connect(self._test_ghost_chalk_error)
        btn_bar.addWidget(self.btn_chalk_err)

        # 3. Ghost Chalk Verified Mode
        self.btn_chalk_ver = QPushButton("3. Ghost Chalk (Verified #2ecc71)", self)
        self._style_button(self.btn_chalk_ver, "#059669")
        self.btn_chalk_ver.clicked.connect(self._test_ghost_chalk_verified)
        btn_bar.addWidget(self.btn_chalk_ver)

        # 4. Voice Audio Test
        self.btn_voice = QPushButton("4. Voice Speaker Test", self)
        self._style_button(self.btn_voice, "#475569")
        self.btn_voice.clicked.connect(self._test_voice_speaker)
        btn_bar.addWidget(self.btn_voice)

        # 5. Full Check My Work Chain
        self.btn_full = QPushButton("5. Run Full 'Check My Work' Chain", self)
        self._style_button(self.btn_full, "#0f172a")
        self.btn_full.clicked.connect(self._test_full_chain)
        btn_bar.addWidget(self.btn_full)

        # 6. Reset
        self.btn_reset = QPushButton("Reset Canvas", self)
        self._style_button(self.btn_reset, "#94a3b8")
        self.btn_reset.clicked.connect(self._reset_canvas)
        btn_bar.addWidget(self.btn_reset)

        root_layout.addLayout(btn_bar)

        # Center on test region
        self.view.centerOn(300, 220)

    def _style_button(self, btn: QPushButton, bg: str):
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)

    # ── Test Actions ──

    def _test_laser_movement(self):
        """Moves laser pointer from (0,0) to (400, 300) and starts idle breathing."""
        if not hasattr(self, '_laser') or self._laser is None:
            self._laser = LaserPointerItem()
            self.scene.addItem(self._laser)
        self._laser.show()
        self._laser.setPos(0, 0)
        self._laser.move_to(QPointF(400, 300), duration_ms=800)
        self.status_lbl.setText("Laser moving to (400, 300) with idle pulse.")

    def _test_ghost_chalk_error(self):
        """Animates Ghost Chalk oval around QRectF(200, 150, 120, 50)."""
        test_rect = QRectF(200, 150, 120, 50)
        if not hasattr(self, '_chalk') or self._chalk is None:
            self._chalk = GhostChalkItem(test_rect, mode=GhostChalkMode.ERROR)
            self.scene.addItem(self._chalk)
        else:
            self._chalk.show()
            self._chalk.set_target_rect(test_rect, mode=GhostChalkMode.ERROR)
        self.status_lbl.setText("Ghost Chalk animated around QRectF(200, 150, 120, 50) in Error mode.")

    def _test_ghost_chalk_verified(self):
        """Animates Ghost Chalk underline in Verified mode."""
        test_rect = QRectF(200, 150, 120, 50)
        if not hasattr(self, '_chalk') or self._chalk is None:
            self._chalk = GhostChalkItem(test_rect, mode=GhostChalkMode.VERIFIED)
            self.scene.addItem(self._chalk)
        else:
            self._chalk.show()
            self._chalk.set_target_rect(test_rect, mode=GhostChalkMode.VERIFIED)
        self.status_lbl.setText("Ghost Chalk animated in Verified mode (#2ecc71).")

    def _test_voice_speaker(self):
        """Plays speech test sentence."""
        sentence = "Take a look at your second step"
        VoiceSpeaker.instance().speak(sentence)
        self.status_lbl.setText(f"Voice speaker speaking: '{sentence}'")

    def _test_full_chain(self):
        """Demonstrates the coordinated tutor feedback sequence."""
        test_rect = QRectF(200, 150, 180, 45)
        pointer_pos = QPointF(test_rect.right() + 18, test_rect.center().y())
        self.scene.show_tutor_feedback(
            target_rect=test_rect,
            pointer_pos=pointer_pos,
            spoken_message="Take a look at your second step. The signs do not match the previous line.",
            citation="Calculus: Early Transcendentals, §3.4, p.142",
            hints=[
                "Check the signs when applying the distributive property.",
                "Recall: -(a - b) = -a + b or factor out (-1).",
                "In line 2, -(2x - 5) should become -2x + 5, not -2x - 5."
            ],
            mode="error"
        )
        self.status_lbl.setText("Full Socratic feedback chain executing: Laser + Chalk + Voice + Hint Bubble.")

    def _reset_canvas(self):
        self.scene.clear_tutor_feedback()
        if hasattr(self, '_laser') and self._laser:
            self._laser.hide()
        if hasattr(self, '_chalk') and self._chalk:
            self._chalk.hide()
        self.status_lbl.setText("Canvas feedback cleared.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TestLaserViewWindow()
    win.show()
    sys.exit(app.exec())
