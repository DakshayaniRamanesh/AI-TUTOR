'use client';

import React, { forwardRef, useState, useEffect, useRef } from 'react';

interface VideoPlayerProps {
  src: string;
  onTimeUpdate?: (currentTime: number) => void;
  onLoadedMetadata?: (duration: number) => void;
}

const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>(({
  src,
  onTimeUpdate,
  onLoadedMetadata
}, ref) => {
  const [hasError, setHasError] = useState(false);
  const canvasFallbackRef = useRef<HTMLCanvasElement | null>(null);

  // Fallback animation loop for canvas preview if native video decoding fails offline
  useEffect(() => {
    if (!hasError) return;

    let animId: number;
    let startTime = Date.now();
    const durationSec = 15;
    onLoadedMetadata?.(durationSec);

    const renderFrame = () => {
      const elapsed = (Date.now() - startTime) / 1000;
      const time = elapsed % durationSec;
      onTimeUpdate?.(time);

      const canvas = canvasFallbackRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.fillStyle = '#090d16';
          ctx.fillRect(0, 0, canvas.width, canvas.height);

          // Grid lines background
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
          ctx.lineWidth = 1;
          for (let x = 0; x < canvas.width; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
          }
          for (let y = 0; y < canvas.height; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
          }

          // Manim visual shapes and text
          ctx.fillStyle = '#6366f1';
          ctx.font = 'bold 32px Outfit, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('Manim AI Visual Explanation', canvas.width / 2, 80);

          ctx.fillStyle = '#818cf8';
          ctx.font = '22px "Fira Code", monospace';
          ctx.fillText('Concept Analysis & Visual Proof', canvas.width / 2, 140);

          // Animated rotating geometric circle/polygon
          const centerX = canvas.width / 2;
          const centerY = canvas.height / 2 + 40;
          const radius = 70 + Math.sin(time * 2) * 10;

          ctx.save();
          ctx.translate(centerX, centerY);
          ctx.rotate(time * 0.8);
          ctx.strokeStyle = '#06b6d4';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(0, 0, radius, 0, Math.PI * 2);
          ctx.stroke();

          ctx.strokeStyle = '#ec4899';
          ctx.strokeRect(-radius / 1.5, -radius / 1.5, radius * 1.3, radius * 1.3);
          ctx.restore();
        }
      }
      animId = requestAnimationFrame(renderFrame);
    };

    renderFrame();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [hasError, onLoadedMetadata, onTimeUpdate]);

  if (hasError) {
    return (
      <canvas
        ref={canvasFallbackRef}
        width={960}
        height={540}
        className="video-player-el"
      />
    );
  }

  return (
    <video
      ref={ref}
      src={src}
      className="video-player-el"
      crossOrigin="anonymous"
      controls={false}
      onError={() => setHasError(true)}
      onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => onLoadedMetadata?.(e.currentTarget.duration)}
    />
  );
});

VideoPlayer.displayName = 'VideoPlayer';
export default VideoPlayer;
