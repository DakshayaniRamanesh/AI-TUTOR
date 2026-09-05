"""
Video Assembler for LaTeX Animated Lessons.

Streams raw RGB24 video frames directly into an FFmpeg subprocess pipe,
producing standard, high-quality, web-compatible MP4 files (H.264 / yuv420p).
"""

from __future__ import annotations
import os
import subprocess
from typing import List, Callable, Optional
from PIL import Image

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"

from .animation_planner import AnimationTimeline, TimelineState
from .frame_renderer import LatexFrameRenderer


class VideoAssembler:
    """Assembles temporal frames into a finalized MP4 video file using FFmpeg."""

    def __init__(self, fps: int = 30, width: int = 1920, height: int = 1080):
        self.fps = fps
        self.width = width
        self.height = height

    def assemble(
        self,
        timeline: AnimationTimeline,
        state_images: List[Image.Image],
        renderer: LatexFrameRenderer,
        output_path: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        Renders transition and hold frames for every timeline state,
        streaming them into FFmpeg stdin to produce the MP4 file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

        cmd = [
            FFMPEG_EXE, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "rgb24",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            output_path
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        total_states = len(timeline.states)
        blank_frame = Image.new("RGB", (self.width, self.height), (255, 255, 255))
        prev_img = blank_frame

        try:
            for idx, state in enumerate(timeline.states):
                curr_img = state_images[idx] if idx < len(state_images) else prev_img
                
                # Report progress
                if progress_callback:
                    pct = 65 + int((idx / max(1, total_states)) * 30)
                    progress_callback(pct, f"Animating state {idx + 1} of {total_states}...")

                # 1. Transition Frames
                num_trans_frames = max(1, int(state.transition_duration * self.fps))
                is_new_scene = (idx > 0 and state.scene_index != timeline.states[idx - 1].scene_index)

                if is_new_scene:
                    # Dissolve between slides
                    trans_frames = renderer.generate_transition_frames(
                        prev_img, curr_img, state.transition_type, num_trans_frames
                    )
                else:
                    # Reveal new element on same slide
                    trans_frames = renderer.generate_transition_frames(
                        prev_img, curr_img, state.transition_type, num_trans_frames
                    )

                for frame in trans_frames:
                    proc.stdin.write(frame.tobytes())

                # 2. Hold Frames
                hold_frames_count = max(1, int(state.hold_duration * self.fps))
                curr_bytes = curr_img.tobytes()
                for _ in range(hold_frames_count):
                    proc.stdin.write(curr_bytes)

                # 3. Pause After Frames
                if state.pause_after > 0:
                    pause_frames_count = int(state.pause_after * self.fps)
                    for _ in range(pause_frames_count):
                        proc.stdin.write(curr_bytes)

                prev_img = curr_img

            # Trailing pause at end of video (1.0 second)
            end_bytes = prev_img.tobytes()
            for _ in range(self.fps):
                proc.stdin.write(end_bytes)

            proc.stdin.close()
            proc.wait(timeout=120)

        except Exception as e:
            if proc.poll() is None:
                proc.kill()
            raise RuntimeError(f"FFmpeg video encoding failed: {e}")

        if proc.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"FFmpeg returned code {proc.returncode} and failed to produce valid MP4.")

        if progress_callback:
            progress_callback(100, "Video Complete!")

        return output_path
