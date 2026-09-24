"""
Animated Intro Splash Screen for Kestrel AI Tutor
Matches the 7-stage staggered fade-in and theme-flip sequence.
Includes the Kestrel falcon head logo (matching in-app icon) and
a live loading-status line updated from the background loader thread.
"""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal, QPropertyAnimation,
    QEasingCurve, pyqtProperty
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Returns smooth hermite interpolation between 0 and 1."""
    if x <= edge0: return 0.0
    if x >= edge1: return 1.0
    t = (x - edge0) / (edge1 - edge0)
    return t * t * (3.0 - 2.0 * t)


def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    """Linearly interpolate between two QColors."""
    r = int(c1.red()   + (c2.red()   - c1.red())   * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue()  + (c2.blue()  - c1.blue())  * t)
    a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
    return QColor(r, g, b, a)


class SplashScreen(QWidget):
    """
    7-stage animated splash screen sequence:
    0. Blank
    1. Falcon logo fades in
    2. Wordmark fades in
    3. Tagline + scale-up
    4. Theme flip (dark -> light)
    5. Subtitle fades in
    6. CTA buttons fade in
    7. Footer link fades in
    """
    finished = pyqtSignal()

    def __init__(self, duration_ms: int = 2400):
        super().__init__(None)
        self.duration_ms = duration_ms
        self.elapsed_sec = 0.0
        self._opacity = 1.0
        self._status_text = ""   # live loading message from background thread

        # Window configuration
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(900, 600)

        # Center on active screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move((geo.width() - self.width()) // 2,
                      (geo.height() - self.height()) // 2)

        # Animation timer (60 FPS ~ 16 ms)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self._is_closing = False
        self._fade_anim = None

    # ── Public API for background loader ──────────────────────────────────────
    def set_status(self, text: str):
        """Update the loading-status line (called from background thread via signal)."""
        self._status_text = text
        self.update()

    # ── Qt property for QPropertyAnimation ───────────────────────────────────
    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, val: float):
        self._opacity = max(0.0, min(1.0, val))
        self.setWindowOpacity(self._opacity)
        self.update()

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _on_tick(self):
        self.elapsed_sec += 0.016
        self.update()
        if self.elapsed_sec >= (self.duration_ms / 1000.0) and not self._is_closing:
            self._start_fade_out()

    def _start_fade_out(self):
        self._is_closing = True
        self.timer.stop()
        self._fade_anim = QPropertyAnimation(self, b"opacity")
        self._fade_anim.setDuration(400)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._fade_anim.start()

    def _on_fade_finished(self):
        self.finished.emit()
        self.close()

    def mousePressEvent(self, event):
        """Single-click to skip/fast-forward splash."""
        if not self._is_closing:
            self._start_fade_out()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())
        rect = QRectF(0, 0, w, h)
        t = self.elapsed_sec

        # Stage timings
        icon_opacity      = smoothstep(0.25, 0.55, t)
        wordmark_opacity  = smoothstep(0.60, 0.90, t)
        tagline_opacity   = smoothstep(0.90, 1.20, t)
        scale_factor      = 1.0 + 0.06 * smoothstep(0.90, 1.20, t)
        theme_t           = smoothstep(1.20, 1.70, t)
        subtitle_opacity  = smoothstep(1.70, 2.10, t)
        buttons_opacity   = smoothstep(2.10, 2.40, t)
        footer_opacity    = smoothstep(2.40, 2.80, t)

        # Colours
        bg_dark   = QColor(10, 10, 10)
        bg_light  = QColor(250, 250, 250)
        bg_color  = lerp_color(bg_dark, bg_light, theme_t)

        fg_dark   = QColor(255, 255, 255)
        fg_light  = QColor(0, 0, 0)
        fg_color  = lerp_color(fg_dark, fg_light, theme_t)

        muted_dark  = QColor(150, 150, 150)
        muted_light = QColor(100, 100, 100)
        muted_color = lerp_color(muted_dark, muted_light, theme_t)

        # Background
        painter.fillRect(rect, bg_color)

        center_x = w / 2.0
        pivot_y  = h / 2.0 - 50.0

        painter.save()
        painter.translate(center_x, pivot_y)
        painter.scale(scale_factor, scale_factor)

        # ── 1. Falcon Logo ────────────────────────────────────────────────────
        if icon_opacity > 0:
            c = QColor(fg_color)
            c.setAlphaF(icon_opacity)
            self._draw_falcon_logo(painter, 0, -52, c)

        # ── 2. Wordmark ───────────────────────────────────────────────────────
        if wordmark_opacity > 0:
            c = QColor(fg_color)
            c.setAlphaF(wordmark_opacity)
            painter.setPen(c)
            font_wm = QFont("Consolas", 32, QFont.Weight.Bold)
            font_wm.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
            painter.setFont(font_wm)
            painter.drawText(QRectF(-200, 18, 400, 50),
                             Qt.AlignmentFlag.AlignCenter, "Kestrel")
            # Divider
            div_c = QColor(muted_color)
            div_c.setAlphaF(wordmark_opacity * 0.5)
            painter.setPen(QPen(div_c, 1.0))
            painter.drawLine(QPointF(-25, 73), QPointF(25, 73))

        # ── 3. Tagline ────────────────────────────────────────────────────────
        if tagline_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(tagline_opacity)
            painter.setPen(c)
            font_tag = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
            font_tag.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
            painter.setFont(font_tag)
            painter.drawText(QRectF(-200, -138, 400, 20),
                             Qt.AlignmentFlag.AlignCenter,
                             "ADAPTIVE STEM LEARNING ENVIRONMENT")

        # ── 5. Subtitle ───────────────────────────────────────────────────────
        if subtitle_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(subtitle_opacity)
            painter.setPen(c)
            font_sub = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
            font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
            painter.setFont(font_sub)
            painter.drawText(QRectF(-200, 92, 400, 20),
                             Qt.AlignmentFlag.AlignCenter,
                             "YOUR INTELLIGENT NOTEBOOK")

        # ── 6. CTA Buttons ────────────────────────────────────────────────────
        if buttons_opacity > 0:
            btn_w, btn_h, spacing = 130, 36, 15
            btn1_rect = QRectF(-btn_w - spacing / 2, 132, btn_w, btn_h)
            btn2_rect = QRectF(spacing / 2,          132, btn_w, btn_h)

            primary_border = QColor(fg_color)
            primary_border.setAlphaF(buttons_opacity)
            painter.setPen(QPen(primary_border, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(btn1_rect, 4, 4)

            sec_border = QColor(muted_color)
            sec_border.setAlphaF(buttons_opacity * 0.7)
            painter.setPen(QPen(sec_border, 1.0))
            painter.drawRoundedRect(btn2_rect, 4, 4)

            btn_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            btn_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            painter.setFont(btn_font)
            painter.setPen(primary_border)
            painter.drawText(btn1_rect, Qt.AlignmentFlag.AlignCenter, "NEW CANVAS")
            t2c = QColor(fg_color); t2c.setAlphaF(buttons_opacity * 0.8)
            painter.setPen(t2c)
            painter.drawText(btn2_rect, Qt.AlignmentFlag.AlignCenter, "SUBJECTS")

        # ── 7. Footer ─────────────────────────────────────────────────────────
        if footer_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(footer_opacity)
            painter.setPen(c)
            font_ft = QFont("Segoe UI", 8, QFont.Weight.Medium)
            font_ft.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            painter.setFont(font_ft)
            painter.drawText(QRectF(-200, 188, 400, 20),
                             Qt.AlignmentFlag.AlignCenter,
                             "+ VIEW FEATURE DEMO BOARD")

        painter.restore()

        # ── Loading status text (bottom of window, always visible) ───────────
        if self._status_text:
            status_alpha = min(1.0, t * 4)   # fades in quickly
            sc = QColor(muted_color)
            sc.setAlphaF(status_alpha * 0.75)
            painter.setPen(sc)
            font_st = QFont("Segoe UI", 8)
            painter.setFont(font_st)
            painter.drawText(QRectF(0, h - 36, w, 20),
                             Qt.AlignmentFlag.AlignCenter,
                             self._status_text)

    # ── Falcon Logo Drawing ───────────────────────────────────────────────────
    def _draw_falcon_logo(self, painter: QPainter, cx: float, cy: float, color: QColor):
        """
        Draws the Kestrel falcon-head logo that matches the in-whiteboard icon:
        a stylised falcon head facing right, line-art style inside an implicit
        rounded square frame — identical geometry to the canvas watermark.
        """
        painter.save()
        painter.translate(cx, cy)

        size = 72
        rect = QRectF(-size / 2, -size / 2, size, size)

        # Filled rounded square
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(rect, 10, 10)

        # Contrast colour for the line art cut-out
        brightness = color.lightnessF()
        line_c = QColor(0, 0, 0) if brightness > 0.5 else QColor(255, 255, 255)

        pen = QPen(line_c, 2.8, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # ── Falcon head silhouette ────────────────────────────────────────
        # Outer head outline (counter-clockwise from crown)
        path = QPainterPath()
        path.moveTo(-14, -10)       # back of head / neck
        path.cubicTo(-14, -26, -2, -30, 6, -26)   # crown curve
        path.lineTo(20, -14)        # top beak ridge
        path.lineTo(22, -6)         # beak tip upper
        path.lineTo(17, 0)          # beak hook
        path.lineTo(12, -2)         # mouth corner
        path.lineTo(8, 8)           # lower jaw
        path.lineTo(2, 18)          # throat
        path.lineTo(-6, 20)         # chest
        path.lineTo(-16, 10)        # lower neck
        path.closeSubpath()
        painter.drawPath(path)

        # Beak hook (separate small detail)
        beak = QPainterPath()
        beak.moveTo(17, -4)
        beak.lineTo(22, -6)
        beak.lineTo(19, 2)
        painter.drawPath(beak)

        # Eye
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(line_c))
        painter.drawEllipse(QPointF(6, -14), 3.2, 3.2)

        # Inner geometric line — the cross-pattern inside the head
        painter.setPen(QPen(line_c, 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(-14, -10), QPointF(4,  2))   # nape → centre
        painter.drawLine(QPointF(4,   2),  QPointF(18, -8))   # centre → beak ridge
        painter.drawLine(QPointF(4,   2),  QPointF(2,  18))   # centre → throat

        painter.restore()
