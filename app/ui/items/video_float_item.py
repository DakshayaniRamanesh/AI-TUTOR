"""
Floating Video Player Canvas Item
Renders video frames via QVideoSink → QLabel to avoid the QGraphicsProxyWidget
native-window (HWND) issue where QVideoWidget renders behind the canvas on Windows.
"""

import os
from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QProgressBar, QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame
from .base_item import BaseGraphicsItemMixin
from app.services.tutoring.video_gen_client import ManimVideoPollWorker, request_video_generation
from ...storage.downloads_manager import DownloadsManager


class _VideoFrameLabel(QLabel):
    """
    A QLabel subclass that renders QVideoFrames via QPainter.
    This avoids the native HWND overlay bug that makes QVideoWidget invisible
    when embedded inside a QGraphicsProxyWidget (canvas scene).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: black; border-radius: 8px;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 130)
        self._current_pixmap: QPixmap | None = None

    @pyqtSlot(QVideoFrame)
    def present_frame(self, frame: QVideoFrame):
        """Called by QVideoSink.videoFrameChanged for every decoded video frame."""
        if not frame.isValid():
            return
        # Map the frame to system memory and convert to QImage
        img = frame.toImage()
        if img.isNull():
            return
        # Scale to widget size, maintaining aspect ratio
        scaled = img.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._current_pixmap = QPixmap.fromImage(scaled)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._current_pixmap:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            # Center the pixmap
            x = (self.width() - self._current_pixmap.width()) // 2
            y = (self.height() - self._current_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._current_pixmap)
            painter.end()


class VideoPlayerWidget(QWidget):
    download_clicked = pyqtSignal(str, str)  # title, file_path

    def __init__(self, job_id: str = "", title: str = "AI Tutor Video", video_url_or_path: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.job_id = job_id
        self.title = title
        self.video_path = video_url_or_path
        self.is_minimized = False
        self.resize(420, 280)

        self.setStyleSheet("""
            QWidget#VideoContainer {
                background-color: #1c1c1e;
                border-radius: 12px;
                border: 1px solid #2c2c2e;
            }
            QLabel {
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.3);
            }
            QProgressBar {
                background: #2c2c2e;
                border-radius: 4px;
                color: white;
                font-size: 10px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #34c759;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #3a3a3c;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #34c759;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: white;
                border-radius: 6px;
            }
        """)

        self.setObjectName("VideoContainer")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)

        # ── Header bar ──────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet("font-size: 12px; color: #34c759;")
        self.btn_min = QPushButton("–", self)
        self.btn_min.setFixedSize(22, 22)
        self.btn_min.clicked.connect(self._toggle_minimize)
        header_row.addWidget(self.lbl_title)
        header_row.addStretch()
        header_row.addWidget(self.btn_min)
        self.main_layout.addLayout(header_row)

        # ── Stacked: Loading vs Player ───────────────────────────────────────
        self.stack = QStackedWidget(self)
        self.main_layout.addWidget(self.stack)

        # Page 0: Loading
        loading_page = QWidget(self.stack)
        lp_layout = QVBoxLayout(loading_page)
        lp_layout.setContentsMargins(12, 12, 12, 12)
        lp_layout.setSpacing(8)
        self.lbl_status = QLabel("Preparing animated lesson...", loading_page)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #34c759; font-size: 12px;")
        self.progress_bar = QProgressBar(loading_page)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(15)
        lp_layout.addStretch()
        lp_layout.addWidget(self.lbl_status)
        lp_layout.addWidget(self.progress_bar)
        lp_layout.addStretch()
        self.stack.addWidget(loading_page)

        # Page 1: Player — uses _VideoFrameLabel instead of QVideoWidget
        player_page = QWidget(self.stack)
        pp_layout = QVBoxLayout(player_page)
        pp_layout.setContentsMargins(0, 0, 0, 4)
        pp_layout.setSpacing(4)

        self.frame_label = _VideoFrameLabel(player_page)
        pp_layout.addWidget(self.frame_label, stretch=1)

        # Controls
        controls = QHBoxLayout()
        controls.setContentsMargins(4, 0, 4, 0)

        self.btn_play = QPushButton("▶  Play", player_page)
        self.btn_play.setFixedWidth(72)
        self.btn_play.clicked.connect(self._toggle_play)

        self.lbl_time = QLabel("0:00 / 0:00", player_page)
        self.lbl_time.setStyleSheet("font-size: 10px; color: #8e8e93; font-weight: normal;")

        self.scrub_slider = QSlider(Qt.Orientation.Horizontal, player_page)
        self.scrub_slider.sliderMoved.connect(self._seek)
        self.scrub_slider.sliderPressed.connect(self._on_scrub_start)
        self.scrub_slider.sliderReleased.connect(self._on_scrub_end)

        self.btn_download = QPushButton("⬇ Save", player_page)
        self.btn_download.setStyleSheet("background-color: #007aff; font-weight: bold;")
        self.btn_download.setFixedWidth(62)
        self.btn_download.clicked.connect(self._on_download)

        controls.addWidget(self.btn_play)
        controls.addWidget(self.scrub_slider, stretch=1)
        controls.addWidget(self.lbl_time)
        controls.addWidget(self.btn_download)
        pp_layout.addLayout(controls)

        self.stack.addWidget(player_page)

        # ── QMediaPlayer + QVideoSink (not QVideoWidget) ─────────────────────
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        # QVideoSink captures decoded frames; we paint them manually
        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self.frame_label.present_frame)
        self.player.setVideoSink(self.video_sink)

        # Player signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        self._scrubbing = False

        # Load video immediately if path provided
        if self.video_path:
            self._load_video_source(self.video_path)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            self._start_worker_polling()

    # ── Polling ─────────────────────────────────────────────────────────────
    def _start_worker_polling(self):
        self.worker = ManimVideoPollWorker(self.job_id, self.title, parent=self)
        self.worker.status_updated.connect(self._on_status_update)
        self.worker.video_ready.connect(self._on_video_ready)
        self.worker.video_failed.connect(self._on_video_failed)
        self.worker.start()

    def _on_status_update(self, job_id, stage, progress):
        self.lbl_status.setText(stage)
        self.progress_bar.setValue(progress)

    def _on_video_ready(self, job_id, video_url):
        if not video_url:
            return
        self.video_path = video_url
        self._load_video_source(video_url)
        self.stack.setCurrentIndex(1)
        self.player.play()

    def _on_video_failed(self, job_id, err_msg):
        self.lbl_status.setText(f"Error: {err_msg}")
        self.progress_bar.setValue(0)

    # ── Source loading ───────────────────────────────────────────────────────
    def _load_video_source(self, path_or_url: str):
        if os.path.isabs(path_or_url) or path_or_url.startswith("C:") or path_or_url.startswith("D:"):
            url = QUrl.fromLocalFile(path_or_url)
        elif os.path.exists(path_or_url):
            url = QUrl.fromLocalFile(os.path.abspath(path_or_url))
        else:
            url = QUrl(path_or_url)
        print(f"[VideoPlayer] Loading: {url.toString()}")
        self.player.setSource(url)

    # ── Playback controls ────────────────────────────────────────────────────
    def _toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸  Pause")
        else:
            self.btn_play.setText("▶  Play")

    def _seek(self, position):
        self.player.setPosition(position)

    def _on_scrub_start(self):
        self._scrubbing = True

    def _on_scrub_end(self):
        self._scrubbing = False
        self.player.setPosition(self.scrub_slider.value())

    def _on_position_changed(self, pos):
        if not self._scrubbing:
            self.scrub_slider.setValue(pos)
        self.lbl_time.setText(f"{self._ms_to_str(pos)} / {self._ms_to_str(self.player.duration())}")

    def _on_duration_changed(self, dur):
        self.scrub_slider.setRange(0, dur)
        self.lbl_time.setText(f"0:00 / {self._ms_to_str(dur)}")

    def _on_player_error(self, error, error_string):
        print(f"[VideoPlayer] Error {error}: {error_string}")
        self.lbl_status.setText(f"Playback error: {error_string}")

    @staticmethod
    def _ms_to_str(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    # ── Minimize ─────────────────────────────────────────────────────────────
    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.stack.hide()
            self.resize(260, 38)
            self.btn_min.setText("+")
            self.player.pause()
        else:
            self.stack.show()
            self.resize(420, 280)
            self.btn_min.setText("–")

    # ── Download ─────────────────────────────────────────────────────────────
    def _on_download(self):
        if not self.video_path:
            self.btn_download.setText("⚠ No Video")
            return

        import shutil, urllib.request, base64, time
        from ...storage.downloads_manager import DownloadsManager, DOWNLOADS_DIR

        dl_mgr = DownloadsManager()
        if self.video_path.startswith("http"):
            filename = self.video_path.split("/")[-1]
        elif self.video_path.startswith("data:"):
            filename = f"ai_tutor_video_{int(time.time())}.mp4"
        else:
            filename = os.path.basename(self.video_path)

        local_path = os.path.join(DOWNLOADS_DIR, filename)
        try:
            if self.video_path.startswith("http"):
                urllib.request.urlretrieve(self.video_path, local_path)
            elif self.video_path.startswith("data:"):
                _, encoded = self.video_path.split(",", 1)
                with open(local_path, "wb") as f:
                    f.write(base64.b64decode(encoded))
            elif os.path.exists(self.video_path):
                shutil.copy2(self.video_path, local_path)

            entry = dl_mgr.add_download(self.title, local_path)
            self.download_clicked.emit(self.title, entry["file_path"])
            self.btn_download.setText("✓ Saved")
        except Exception as e:
            print(f"[VideoPlayer] Download failed: {e}")
            self.btn_download.setText("⚠ Failed")


class VideoFloatItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, job_id: str = "", title: str = "AI Tutor Video", video_url_or_path: str = "", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(15)  # Float above canvas items

        self.player_widget = VideoPlayerWidget(job_id, title, video_url_or_path)
        self.setWidget(self.player_widget)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "item_id": getattr(self, "item_id", ""),
            "type": "VideoFloatItem",
            "x": self.x(),
            "y": self.y(),
            "job_id": self.player_widget.job_id,
            "title": self.player_widget.title,
            "video_path": self.player_widget.video_path,
            "is_minimized": self.player_widget.is_minimized,
            "z_value": self.zValue()
        }
