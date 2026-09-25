"""
Floating Video Player Canvas Item
Renders video frames via QVideoSink -> QLabel to avoid the QGraphicsProxyWidget
native-window (HWND) issue where QVideoWidget renders behind the canvas on Windows.
Includes full local auto-saving, audio output, in-canvas theater expand, and
immersive FullScreenVideoDialog for optimal math video readability.
"""

import os
import shutil
import urllib.request
import base64
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QProgressBar, QStackedWidget, QSizePolicy,
    QDialog, QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont, QColor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame
from .base_item import BaseGraphicsItemMixin
from app.services.tutoring.video_gen_client import ManimVideoPollWorker, request_video_generation
from ...storage.downloads_manager import DownloadsManager, DOWNLOADS_DIR


class _VideoFrameLabel(QLabel):
    """
    A QLabel subclass that renders QVideoFrames via QPainter.
    Avoids native HWND overlay bugs while supporting double-click fullscreen.
    """
    doubleClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #000000; border-radius: 8px;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 130)
        self._current_pixmap: Optional[QPixmap] = None

    @pyqtSlot(QVideoFrame)
    def present_frame(self, frame: QVideoFrame):
        """Called by QVideoSink.videoFrameChanged for every decoded video frame."""
        if not frame.isValid():
            return
        img = frame.toImage()
        if img.isNull():
            return
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
            x = (self.width() - self._current_pixmap.width()) // 2
            y = (self.height() - self._current_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._current_pixmap)
            painter.end()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.doubleClicked.emit()


class FullScreenVideoDialog(QDialog):
    """
    Dedicated immersive fullscreen video player.
    Allows viewing animated math lessons at 100% monitor resolution with full controls.
    """
    dialog_closed = pyqtSignal(int, bool)  # current_pos_ms, was_playing

    def __init__(self, title: str, video_path: str, initial_pos_ms: int = 0, is_playing: bool = True, parent=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(title)
        self.title = title
        self.video_path = video_path
        self._scrubbing = False

        self.setStyleSheet("""
            QDialog {
                background-color: #0c0c0e;
            }
            QLabel {
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.28);
                border-color: rgba(255, 255, 255, 0.4);
            }
            QPushButton#BtnPrimary {
                background-color: #007aff;
                border: none;
            }
            QPushButton#BtnPrimary:hover {
                background-color: #0062cc;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2c2c2e;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #34c759;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: #ffffff;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        self.lbl_header_title = QLabel(f"🎬  {title}", self)
        self.lbl_header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #34c759;")
        
        self.btn_close = QPushButton("✕ Exit (Esc)", self)
        self.btn_close.setFixedWidth(110)
        self.btn_close.clicked.connect(self.close)

        header.addWidget(self.lbl_header_title)
        header.addStretch()
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        # Large video frame
        self.frame_label = _VideoFrameLabel(self)
        self.frame_label.doubleClicked.connect(self.close)
        layout.addWidget(self.frame_label, stretch=1)

        # Bottom control bar
        ctrl_card = QFrame(self)
        ctrl_card.setStyleSheet("background-color: #1c1c1e; border-radius: 10px; padding: 6px;")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(10, 8, 10, 8)
        ctrl_layout.setSpacing(8)

        # Progress slider & timestamps
        slider_row = QHBoxLayout()
        self.lbl_time = QLabel("0:00 / 0:00", ctrl_card)
        self.lbl_time.setStyleSheet("font-size: 12px; color: #a1a1a6; font-weight: 500;")
        self.scrub_slider = QSlider(Qt.Orientation.Horizontal, ctrl_card)
        self.scrub_slider.sliderMoved.connect(self._seek)
        self.scrub_slider.sliderPressed.connect(self._on_scrub_start)
        self.scrub_slider.sliderReleased.connect(self._on_scrub_end)

        slider_row.addWidget(self.scrub_slider, stretch=1)
        slider_row.addWidget(self.lbl_time)
        ctrl_layout.addLayout(slider_row)

        # Action buttons row
        btn_row = QHBoxLayout()
        self.btn_play = QPushButton("⏸  Pause" if is_playing else "▶  Play", ctrl_card)
        self.btn_play.setFixedWidth(100)
        self.btn_play.clicked.connect(self._toggle_play)

        # Volume
        lbl_vol = QLabel("🔊", ctrl_card)
        self.slider_vol = QSlider(Qt.Orientation.Horizontal, ctrl_card)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(100)
        self.slider_vol.setFixedWidth(100)
        self.slider_vol.valueChanged.connect(self._on_vol_changed)

        # Speed toggle
        self.btn_speed = QPushButton("1.0x", ctrl_card)
        self.btn_speed.setFixedWidth(60)
        self.btn_speed.clicked.connect(self._cycle_playback_rate)
        self._current_rate = 1.0

        self.btn_export = QPushButton("⬇ Export MP4", ctrl_card)
        self.btn_export.setObjectName("BtnPrimary")
        self.btn_export.setFixedWidth(110)
        self.btn_export.clicked.connect(self._on_export)

        btn_row.addWidget(self.btn_play)
        btn_row.addWidget(lbl_vol)
        btn_row.addWidget(self.slider_vol)
        btn_row.addWidget(self.btn_speed)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_close)
        ctrl_layout.addLayout(btn_row)

        layout.addWidget(ctrl_card)

        # Media Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self.frame_label.present_frame)
        self.player.setVideoSink(self.video_sink)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        # Load video and jump to initial position
        self._load_source(video_path)
        if initial_pos_ms > 0:
            self.player.setPosition(initial_pos_ms)
        if is_playing:
            self.player.play()

    def _load_source(self, path: str):
        if os.path.exists(path) or os.path.isabs(path):
            url = QUrl.fromLocalFile(os.path.abspath(path))
        else:
            url = QUrl(path)
        self.player.setSource(url)

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸  Pause")
        else:
            self.btn_play.setText("▶  Play")

    def _seek(self, pos):
        self.player.setPosition(pos)

    def _on_scrub_start(self):
        self._scrubbing = True

    def _on_scrub_end(self):
        self._scrubbing = False
        self.player.setPosition(self.scrub_slider.value())

    def _on_position_changed(self, pos):
        if not self._scrubbing:
            self.scrub_slider.setValue(pos)
        dur = self.player.duration()
        self.lbl_time.setText(f"{self._ms_to_str(pos)} / {self._ms_to_str(dur)}")

    def _on_duration_changed(self, dur):
        self.scrub_slider.setRange(0, dur)
        self.lbl_time.setText(f"0:00 / {self._ms_to_str(dur)}")

    def _on_vol_changed(self, val):
        self.audio_output.setVolume(val / 100.0)

    def _cycle_playback_rate(self):
        rates = [1.0, 1.25, 1.5, 2.0]
        curr_idx = rates.index(self._current_rate) if self._current_rate in rates else 0
        next_rate = rates[(curr_idx + 1) % len(rates)]
        self._current_rate = next_rate
        self.player.setPlaybackRate(next_rate)
        self.btn_speed.setText(f"{next_rate}x")

    def _on_export(self):
        if not self.video_path or not os.path.exists(self.video_path):
            QMessageBox.warning(self, "Export", "Video file is still downloading or not available.")
            return
        clean_name = "".join(c for c in self.title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        dest, _ = QFileDialog.getSaveFileName(self, "Export Lesson Video", f"{clean_name}.mp4", "MP4 Videos (*.mp4)")
        if dest:
            try:
                shutil.copy2(self.video_path, dest)
                QMessageBox.information(self, "Saved", f"Video exported successfully to:\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Could not save video: {e}")

    @staticmethod
    def _ms_to_str(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            self._toggle_play()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        pos = self.player.position()
        is_playing = (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.player.stop()
        self.dialog_closed.emit(pos, is_playing)
        super().closeEvent(event)


class VideoPlayerWidget(QWidget):
    download_clicked = pyqtSignal(str, str)  # title, file_path

    def __init__(self, job_id: str = "", title: str = "AI Tutor Video", video_url_or_path: str = "", subject_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.job_id = job_id
        self.title = title
        self.video_path = video_url_or_path
        self.subject_id = subject_id
        self.is_minimized = False
        self.is_theater = False
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
        self.lbl_title.setStyleSheet("font-size: 12px; color: #34c759; font-weight: bold;")

        # Expand Theater size button
        self.btn_theater = QPushButton("⤢ Expand", self)
        self.btn_theater.setToolTip("Toggle theater view on whiteboard")
        self.btn_theater.setFixedHeight(22)
        self.btn_theater.clicked.connect(self._toggle_theater)

        # Fullscreen button
        self.btn_fs = QPushButton("⛶ Fullscreen", self)
        self.btn_fs.setToolTip("Open full-screen video player (or double-click video)")
        self.btn_fs.setFixedHeight(22)
        self.btn_fs.setStyleSheet("background-color: rgba(52, 199, 89, 0.25); color: #34c759; font-weight: bold;")
        self.btn_fs.clicked.connect(self.open_fullscreen)

        # Minimize button
        self.btn_min = QPushButton("–", self)
        self.btn_min.setFixedSize(22, 22)
        self.btn_min.clicked.connect(self._toggle_minimize)

        header_row.addWidget(self.lbl_title)
        header_row.addStretch()
        header_row.addWidget(self.btn_theater)
        header_row.addWidget(self.btn_fs)
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
        self.lbl_status = QLabel("Preparing animated lesson with voiceover...", loading_page)
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

        # Page 1: Player
        player_page = QWidget(self.stack)
        pp_layout = QVBoxLayout(player_page)
        pp_layout.setContentsMargins(0, 0, 0, 4)
        pp_layout.setSpacing(4)

        self.frame_label = _VideoFrameLabel(player_page)
        self.frame_label.doubleClicked.connect(self.open_fullscreen)
        pp_layout.addWidget(self.frame_label, stretch=1)

        # Controls
        controls = QHBoxLayout()
        controls.setContentsMargins(4, 0, 4, 0)

        self.btn_play = QPushButton("▶  Play", player_page)
        self.btn_play.setFixedWidth(68)
        self.btn_play.clicked.connect(self._toggle_play)

        self.lbl_time = QLabel("0:00 / 0:00", player_page)
        self.lbl_time.setStyleSheet("font-size: 10px; color: #8e8e93; font-weight: normal;")

        self.scrub_slider = QSlider(Qt.Orientation.Horizontal, player_page)
        self.scrub_slider.sliderMoved.connect(self._seek)
        self.scrub_slider.sliderPressed.connect(self._on_scrub_start)
        self.scrub_slider.sliderReleased.connect(self._on_scrub_end)

        self.btn_fullscreen_icon = QPushButton("⛶", player_page)
        self.btn_fullscreen_icon.setToolTip("Fullscreen")
        self.btn_fullscreen_icon.setFixedSize(28, 22)
        self.btn_fullscreen_icon.clicked.connect(self.open_fullscreen)

        self.btn_download = QPushButton("⬇ Save", player_page)
        self.btn_download.setStyleSheet("background-color: #007aff; font-weight: bold;")
        self.btn_download.setFixedWidth(62)
        self.btn_download.clicked.connect(self._on_download)

        controls.addWidget(self.btn_play)
        controls.addWidget(self.scrub_slider, stretch=1)
        controls.addWidget(self.lbl_time)
        controls.addWidget(self.btn_fullscreen_icon)
        controls.addWidget(self.btn_download)
        pp_layout.addLayout(controls)

        self.stack.addWidget(player_page)

        # ── QMediaPlayer + QAudioOutput + QVideoSink ────────────────────────
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self.frame_label.present_frame)
        self.player.setVideoSink(self.video_sink)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        self._scrubbing = False

        if self.video_path:
            local_file = self._save_video_locally(self.video_path)
            self.video_path = local_file
            self._load_video_source(local_file)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            self._start_worker_polling()

    # ── Auto Save Video Locally ─────────────────────────────────────────────
    def _save_video_locally(self, video_url_or_path: str) -> str:
        """
        Ensures the generated/received video is saved into storage_data/videos/
        and registered in DownloadsManager and Subject database.
        """
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            storage_videos_dir = os.path.join(base_dir, "storage_data", "videos")
            os.makedirs(storage_videos_dir, exist_ok=True)
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)

            clean_title = "".join(c for c in self.title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")[:30]
            filename = f"{self.job_id or 'lesson'}_{clean_title or 'video'}.mp4"
            target_path = os.path.join(storage_videos_dir, filename)

            if video_url_or_path.startswith("http://") or video_url_or_path.startswith("https://"):
                urllib.request.urlretrieve(video_url_or_path, target_path)
            elif video_url_or_path.startswith("data:"):
                _, encoded = video_url_or_path.split(",", 1)
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(encoded))
            elif os.path.exists(video_url_or_path):
                abs_src = os.path.abspath(video_url_or_path)
                abs_dst = os.path.abspath(target_path)
                if abs_src != abs_dst:
                    shutil.copy2(abs_src, abs_dst)
                target_path = abs_dst

            # Register with DownloadsManager
            dl_mgr = DownloadsManager()
            dl_mgr.add_download(self.title, target_path)

            # Register in Subject database if subject_id is present
            if self.subject_id:
                try:
                    from ...storage.database_ops import add_video
                    add_video(self.subject_id, self.title, target_path)
                except Exception as db_e:
                    print(f"[VideoPlayer] DB add_video notice: {db_e}")

            print(f"[VideoPlayer] Video saved locally: {target_path} ({os.path.getsize(target_path)} bytes)")
            return target_path
        except Exception as e:
            print(f"[VideoPlayer] Local video save notice: {e}")
            return video_url_or_path

    # ── Polling ─────────────────────────────────────────────────────────────
    def _start_worker_polling(self):
        self.worker = ManimVideoPollWorker(self.job_id, self.title, parent=None)
        self.worker.status_updated.connect(self._on_status_update)
        self.worker.video_ready.connect(self._on_video_ready)
        self.worker.video_failed.connect(self._on_video_failed)
        self.worker.start()

    def hideEvent(self, event):
        super().hideEvent(event)

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        if hasattr(self, 'worker') and self.worker:
            try:
                self.worker.status_updated.disconnect(self._on_status_update)
                self.worker.video_ready.disconnect(self._on_video_ready)
                self.worker.video_failed.disconnect(self._on_video_failed)
            except Exception:
                pass
        super().destroy(destroyWindow, destroySubWindows)

    def _on_status_update(self, job_id, stage, progress):
        self.lbl_status.setText(stage)
        self.progress_bar.setValue(progress)

    def _on_video_ready(self, job_id, video_url):
        if not video_url:
            return
        # Automatically save locally so the video file is permanently accessible
        local_path = self._save_video_locally(video_url)
        self.video_path = local_path
        self._load_video_source(local_path)
        self.stack.setCurrentIndex(1)
        self.player.play()
        self.btn_download.setText("✓ Saved")

    def _on_video_failed(self, job_id, err_msg):
        self.lbl_status.setText(f"Error: {err_msg}")
        self.progress_bar.setValue(0)

    # ── Source loading ───────────────────────────────────────────────────────
    def _load_video_source(self, path_or_url: str):
        if os.path.exists(path_or_url) or os.path.isabs(path_or_url) or path_or_url.startswith("C:") or path_or_url.startswith("D:"):
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

    # ── Theater & Fullscreen ─────────────────────────────────────────────────
    def _toggle_theater(self):
        self.is_theater = not self.is_theater
        if self.is_theater:
            self.resize(760, 480)
            self.btn_theater.setText("⤡ Normal")
        else:
            self.resize(420, 280)
            self.btn_theater.setText("⤢ Expand")

    def open_fullscreen(self):
        """Launches the immersive FullScreenVideoDialog."""
        if not self.video_path:
            return
        curr_pos = self.player.position()
        is_playing = (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.player.pause()

        fs_dialog = FullScreenVideoDialog(
            title=self.title,
            video_path=self.video_path,
            initial_pos_ms=curr_pos,
            is_playing=is_playing,
            parent=self.window()
        )
        fs_dialog.dialog_closed.connect(self._on_fullscreen_closed)
        fs_dialog.showFullScreen()

    def _on_fullscreen_closed(self, resume_pos: int, was_playing: bool):
        """Resumes playback seamlessly when returning from fullscreen."""
        self.player.setPosition(resume_pos)
        if was_playing:
            self.player.play()

    # ── Minimize ─────────────────────────────────────────────────────────────
    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.stack.hide()
            self.btn_theater.hide()
            self.btn_fs.hide()
            self.resize(260, 38)
            self.btn_min.setText("+")
            self.player.pause()
        else:
            self.stack.show()
            self.btn_theater.show()
            self.btn_fs.show()
            if self.is_theater:
                self.resize(760, 480)
            else:
                self.resize(420, 280)
            self.btn_min.setText("–")

    # ── Download / Export ───────────────────────────────────────────────────
    def _on_download(self):
        if not self.video_path or not os.path.exists(self.video_path):
            self.btn_download.setText("⚠ No Video")
            return

        clean_name = "".join(c for c in self.title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        dest, _ = QFileDialog.getSaveFileName(self, "Export Video", f"{clean_name}.mp4", "MP4 Videos (*.mp4)")
        if dest:
            try:
                shutil.copy2(self.video_path, dest)
                self.download_clicked.emit(self.title, dest)
                self.btn_download.setText("✓ Exported")
                QMessageBox.information(self, "Video Saved", f"Lesson video saved successfully to:\n{dest}")
            except Exception as e:
                print(f"[VideoPlayer] Download failed: {e}")
                self.btn_download.setText("⚠ Failed")


class VideoFloatItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, job_id: str = "", title: str = "AI Tutor Video", video_url_or_path: str = "", subject_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(15)  # Float above canvas items

        self.player_widget = VideoPlayerWidget(job_id, title, video_url_or_path, subject_id=subject_id)
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
