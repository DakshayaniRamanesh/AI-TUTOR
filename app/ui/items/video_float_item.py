"""
Floating Video Player Canvas Item (Connected to Manim AI Pipeline with Loading Progress & Download Sync)
"""

import os
from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QProgressBar, QStackedWidget
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from .base_item import BaseGraphicsItemMixin
from ...backend.video_gen_client import ManimVideoPollWorker, request_video_generation
from ...storage.downloads_manager import DownloadsManager

class VideoPlayerWidget(QWidget):
    download_clicked = pyqtSignal(str, str) # title, file_path

    def __init__(self, job_id: str = "", title: str = "Manim Video", video_url_or_path: str = "", parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.title = title
        self.video_path = video_url_or_path
        self.is_minimized = False
        self.resize(380, 250)

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
                padding: 4px 8px;
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
                width: 10px;
                height: 10px;
                margin: -3px 0;
                background: white;
                border-radius: 5px;
            }
        """)

        self.setObjectName("VideoContainer")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)

        # Header bar
        self.header = QHBoxLayout()
        self.lbl_title = QLabel(f"🎬 {title}", self)
        self.lbl_title.setStyleSheet("font-size: 12px; color: #34c759;")

        self.btn_min = QPushButton("–", self)
        self.btn_min.setFixedSize(22, 22)
        self.btn_min.clicked.connect(self._toggle_minimize)

        self.header.addWidget(self.lbl_title)
        self.header.addStretch()
        self.header.addWidget(self.btn_min)
        self.main_layout.addLayout(self.header)

        # Stacked view for Loading vs Active Player
        self.stack = QStackedWidget(self)
        self.main_layout.addWidget(self.stack)

        # Page 0: Loading view
        self.loading_page = QWidget(self.stack)
        lp_layout = QVBoxLayout(self.loading_page)
        lp_layout.setContentsMargins(12, 12, 12, 12)
        lp_layout.setSpacing(8)

        self.lbl_status = QLabel("🎬 Generating Manim 2D Animation...", self.loading_page)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #34c759; font-size: 12px;")

        self.progress_bar = QProgressBar(self.loading_page)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(15)

        lp_layout.addStretch()
        lp_layout.addWidget(self.lbl_status)
        lp_layout.addWidget(self.progress_bar)
        lp_layout.addStretch()

        self.stack.addWidget(self.loading_page)

        # Page 1: Player view
        self.player_page = QWidget(self.stack)
        pp_layout = QVBoxLayout(self.player_page)
        pp_layout.setContentsMargins(0, 0, 0, 0)
        pp_layout.setSpacing(4)

        self.video_widget = QVideoWidget(self.player_page)
        self.video_widget.setStyleSheet("background: black; border-radius: 8px;")
        pp_layout.addWidget(self.video_widget)

        # QMediaPlayer Setup
        self.player = QMediaPlayer(self.player_page)
        self.audio_output = QAudioOutput(self.player_page)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        # Controls bar
        self.controls = QHBoxLayout()
        self.controls.setContentsMargins(0, 2, 0, 0)
        
        self.btn_play = QPushButton("▶ Play", self.player_page)
        self.btn_play.clicked.connect(self._toggle_play)
        
        self.scrub_slider = QSlider(Qt.Orientation.Horizontal, self.player_page)
        self.scrub_slider.sliderMoved.connect(self.player.setPosition)
        
        self.btn_download = QPushButton("💾 Download", self.player_page)
        self.btn_download.setStyleSheet("background-color: #007aff; font-weight: bold;")
        self.btn_download.clicked.connect(self._on_download)

        self.controls.addWidget(self.btn_play)
        self.controls.addWidget(self.scrub_slider)
        self.controls.addWidget(self.btn_download)
        pp_layout.addLayout(self.controls)

        self.stack.addWidget(self.player_page)

        # Check if video is already ready or needs polling
        if self.video_path:
            self._load_video_source(self.video_path)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            self._start_worker_polling()

        # Signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

    def _start_worker_polling(self):
        self.worker = ManimVideoPollWorker(self.job_id, self.title, parent=self)
        self.worker.status_updated.connect(self._on_status_update)
        self.worker.video_ready.connect(self._on_video_ready)
        self.worker.video_failed.connect(self._on_video_failed)
        self.worker.start()

    def _on_status_update(self, job_id, stage, progress):
        self.lbl_status.setText(f"🎬 {stage}")
        self.progress_bar.setValue(progress)

    def _on_video_ready(self, job_id, video_url):
        self.video_path = video_url
        if video_url:
            self._load_video_source(video_url)
        self.stack.setCurrentIndex(1)

    def _on_video_failed(self, job_id, err_msg):
        self.lbl_status.setText(f"⚠️ {err_msg}")
        self.progress_bar.setValue(0)

    def _load_video_source(self, path_or_url: str):
        if os.path.exists(path_or_url):
            self.player.setSource(QUrl.fromLocalFile(path_or_url))
        else:
            self.player.setSource(QUrl(path_or_url))

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶ Play")
        else:
            self.player.play()
            self.btn_play.setText("⏸ Pause")

    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.stack.hide()
            self.resize(240, 38)
            self.btn_min.setText("+")
        else:
            self.stack.show()
            self.resize(380, 250)
            self.btn_min.setText("–")

    def _on_position_changed(self, pos):
        self.scrub_slider.setValue(pos)

    def _on_duration_changed(self, dur):
        self.scrub_slider.setRange(0, dur)

    def _on_download(self):
        dl_mgr = DownloadsManager()
        entry = dl_mgr.add_download(self.title, self.video_path or "downloads/manim_video.mp4")
        self.download_clicked.emit(self.title, entry["file_path"])
        self.btn_download.setText("✓ Saved")

class VideoFloatItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, job_id: str = "", title: str = "Manim Video", video_url_or_path: str = "", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(15) # Floating on top
        
        self.player_widget = VideoPlayerWidget(job_id, title, video_url_or_path)
        self.setWidget(self.player_widget)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "VideoFloatItem",
            "x": self.x(),
            "y": self.y(),
            "job_id": self.player_widget.job_id,
            "title": self.player_widget.title,
            "video_path": self.player_widget.video_path,
            "is_minimized": self.player_widget.is_minimized,
            "z_value": self.zValue()
        }
