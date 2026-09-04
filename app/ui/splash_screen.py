"""
Animated Intro Splash Screen for Kestrel AI Tutor
Matches the 7-stage staggered fade-in and theme-flip sequence.
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
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
    a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
    return QColor(r, g, b, a)

class SplashScreen(QWidget):
    """
    7-stage animated splash screen sequence:
    0. Blank
    1. Logo fades in
    2. Wordmark fades in
    3. Tagline + scale-up
    4. Theme flip (dark -> light)
    5. Subtitle fades in
    6. CTA buttons fade in
    7. Footer link fades in
    """
    finished = pyqtSignal()

    def __init__(self, duration_ms: int = 4000):
        # We use a 4.0s total sequence (3.0s for anim, 1.0s hold)
        super().__init__(None)
        self.duration_ms = duration_ms
        self.elapsed_sec = 0.0
        self._opacity = 1.0

        # Window configuration
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        
        # Match typical app window size or full screen?
        # Let's make it a large splash screen: 900x600
        self.setFixedSize(900, 600)

        # Center on active screen
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(x, y)

        # Animation timer (60 FPS ~ 16ms)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self._is_closing = False
        self._fade_anim = None

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, val: float):
        self._opacity = max(0.0, min(1.0, val))
        self.setWindowOpacity(self._opacity)
        self.update()

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def _on_tick(self):
        self.elapsed_sec += 0.016
        self.update()

        # Finish sequence and fade out
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
        """Allow single-click to skip/fast-forward splash."""
        if not self._is_closing:
            self._start_fade_out()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())
        rect = QRectF(0, 0, w, h)
        
        t = self.elapsed_sec

        # Calculate states based on time t (seconds)
        icon_opacity = smoothstep(0.3, 0.6, t)
        wordmark_opacity = smoothstep(0.7, 1.0, t)
        tagline_opacity = smoothstep(1.0, 1.3, t)
        # Scale animates from 1.0 to 1.1 during 1.0s-1.3s
        scale_factor = 1.0 + 0.1 * smoothstep(1.0, 1.3, t)
        
        # Theme flip: 0 = dark, 1 = light
        theme_t = smoothstep(1.3, 1.8, t)
        
        subtitle_opacity = smoothstep(1.8, 2.2, t)
        buttons_opacity = smoothstep(2.2, 2.6, t)
        footer_opacity = smoothstep(2.6, 3.0, t)

        # Colors
        bg_dark = QColor(10, 10, 10)
        bg_light = QColor(250, 250, 250)
        bg_color = lerp_color(bg_dark, bg_light, theme_t)

        fg_dark = QColor(255, 255, 255) # Text color in dark mode
        fg_light = QColor(0, 0, 0)      # Text color in light mode
        fg_color = lerp_color(fg_dark, fg_light, theme_t)
        
        # Muted text colors
        muted_dark = QColor(150, 150, 150)
        muted_light = QColor(100, 100, 100)
        muted_color = lerp_color(muted_dark, muted_light, theme_t)

        # ── 0. Draw Background ─────────────────────────────────────────────
        painter.fillRect(rect, bg_color)
        
        center_x = w / 2.0
        # Base Y positions (will be scaled around a pivot)
        pivot_y = h / 2.0 - 50.0

        painter.save()
        painter.translate(center_x, pivot_y)
        painter.scale(scale_factor, scale_factor)

        # ── 1. Icon (Logo) ─────────────────────────────────────────────────
        if icon_opacity > 0:
            c = QColor(fg_color)
            c.setAlphaF(icon_opacity)
            self._draw_kestrel_icon(painter, 0, -40, c)

        # ── 2. Wordmark + Divider ──────────────────────────────────────────
        if wordmark_opacity > 0:
            c = QColor(fg_color)
            c.setAlphaF(wordmark_opacity)
            painter.setPen(c)
            font_wm = QFont("Consolas", 32, QFont.Weight.Bold)
            font_wm.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
            painter.setFont(font_wm)
            
            wm_rect = QRectF(-200, 20, 400, 50)
            painter.drawText(wm_rect, Qt.AlignmentFlag.AlignCenter, "Kestrel")
            
            # Divider
            div_c = QColor(muted_color)
            div_c.setAlphaF(wordmark_opacity * 0.5)
            painter.setPen(QPen(div_c, 1.0))
            painter.drawLine(QPointF(-25, 75), QPointF(25, 75))

        # ── 3. Tagline ─────────────────────────────────────────────────────
        if tagline_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(tagline_opacity)
            painter.setPen(c)
            font_tag = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
            font_tag.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
            painter.setFont(font_tag)
            
            tag_rect = QRectF(-200, -135, 400, 20)
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, "ADAPTIVE STEM LEARNING ENVIRONMENT")

        # ── 5. Subtitle ────────────────────────────────────────────────────
        if subtitle_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(subtitle_opacity)
            painter.setPen(c)
            font_sub = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
            font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
            painter.setFont(font_sub)
            
            sub_rect = QRectF(-200, 95, 400, 20)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "YOUR INTELLIGENT NOTEBOOK")

        # ── 6. CTA Buttons ─────────────────────────────────────────────────
        if buttons_opacity > 0:
            btn_w = 130
            btn_h = 36
            spacing = 15
            
            # Primary Button: "NEW CANVAS"
            btn1_rect = QRectF(-btn_w - spacing/2, 135, btn_w, btn_h)
            
            # Secondary Button: "SUBJECTS"
            btn2_rect = QRectF(spacing/2, 135, btn_w, btn_h)
            
            # Primary Button Styling (Bold Outline / Fill depending on theme)
            # Match the screenshot: "bold black outline, primary emphasis" in light mode
            primary_border = QColor(fg_color)
            primary_border.setAlphaF(buttons_opacity)
            
            painter.setPen(QPen(primary_border, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(btn1_rect, 4, 4)
            
            # Secondary Button Styling (Lighter outline)
            secondary_border = QColor(muted_color)
            secondary_border.setAlphaF(buttons_opacity * 0.7)
            painter.setPen(QPen(secondary_border, 1.0))
            painter.drawRoundedRect(btn2_rect, 4, 4)
            
            # Button Text
            btn_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            btn_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            painter.setFont(btn_font)
            
            painter.setPen(primary_border)
            painter.drawText(btn1_rect, Qt.AlignmentFlag.AlignCenter, "NEW CANVAS")
            
            btn2_text_c = QColor(fg_color)
            btn2_text_c.setAlphaF(buttons_opacity * 0.8)
            painter.setPen(btn2_text_c)
            painter.drawText(btn2_rect, Qt.AlignmentFlag.AlignCenter, "SUBJECTS")

        # ── 7. Footer Link ─────────────────────────────────────────────────
        if footer_opacity > 0:
            c = QColor(muted_color)
            c.setAlphaF(footer_opacity)
            painter.setPen(c)
            font_ft = QFont("Segoe UI", 8, QFont.Weight.Medium)
            font_ft.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            painter.setFont(font_ft)
            
            ft_rect = QRectF(-200, 190, 400, 20)
            painter.drawText(ft_rect, Qt.AlignmentFlag.AlignCenter, "+ VIEW FEATURE DEMO BOARD")

        painter.restore()

    def _draw_kestrel_icon(self, painter: QPainter, cx: float, cy: float, color: QColor):
        """
        Draws the Kestrel bird-mark icon (line-art bird head inside a rounded square).
        """
        painter.save()
        painter.translate(cx, cy)
        
        # 1. Outer rounded square
        size = 64
        rect = QRectF(-size/2, -size/2, size, size)
        
        painter.setPen(Qt.PenStyle.NoPen)
        # Background fill of the icon square (typically contrasting the BG)
        # In dark mode it's white, in light mode it's dark
        fill_c = QColor(color)
        painter.setBrush(QBrush(fill_c))
        painter.drawRoundedRect(rect, 8, 8)
        
        # 2. Inner bird head line art
        # Needs to be the opposite color (cut out from the square)
        # If color is close to white (dark mode fg), line art is dark (bg color).
        bg_brightness = color.lightnessF()
        line_c = QColor(0, 0, 0) if bg_brightness > 0.5 else QColor(255, 255, 255)
        
        painter.setPen(QPen(line_c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw abstract bird head path
        # A simple geometric bird profile facing right
        path = QPainterPath()
        
        # Start at back of head
        path.moveTo(-12, -8)
        # Top of head
        path.lineTo(4, -14)
        # Beak curve
        path.lineTo(16, -2)
        # Beak hook
        path.lineTo(14, 6)
        path.lineTo(6, 2)
        # Neck/throat
        path.lineTo(4, 16)
        path.lineTo(-4, 16)
        # Bottom jaw / neck
        path.lineTo(-14, 6)
        path.closeSubpath()
        
        painter.drawPath(path)
        
        # Eye
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(line_c))
        painter.drawEllipse(QPointF(4, -4), 2.5, 2.5)
        
        # Inner geometric line (network line)
        painter.setPen(QPen(line_c, 1.5))
        painter.drawLine(QPointF(-12, -8), QPointF(4, 4))
        painter.drawLine(QPointF(4, 4), QPointF(12, 0))
        
        painter.restore()
