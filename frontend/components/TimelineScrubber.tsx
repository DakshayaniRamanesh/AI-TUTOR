'use client';

import React from 'react';
import { Play, Pause } from 'lucide-react';

interface TimelineScrubberProps {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  annotationMarkers: number[];
}

export default function TimelineScrubber({
  currentTime,
  duration,
  isPlaying,
  onTogglePlay,
  onSeek,
  annotationMarkers
}: TimelineScrubberProps) {
  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onSeek(parseFloat(e.target.value));
  };

  return (
    <div className="glass-panel" style={{ padding: '16px 24px', marginTop: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
      <button
        type="button"
        className="btn-secondary"
        onClick={onTogglePlay}
        style={{ width: '40px', height: '40px', padding: 0, borderRadius: '50%', justifyContent: 'center' }}
      >
        {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
      </button>

      <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center' }}>
        <input
          type="range"
          min={0}
          max={duration || 100}
          step={0.1}
          value={currentTime}
          onChange={handleSliderChange}
          style={{
            width: '100%',
            accentColor: 'var(--primary-glow)',
            cursor: 'pointer'
          }}
        />

        {/* Render markers on timeline */}
        {duration > 0 && annotationMarkers.map((timestamp, i) => {
          const leftPercent = (timestamp / duration) * 100;
          return (
            <div
              key={i}
              title={`Annotation marker at ${formatTime(timestamp)}`}
              style={{
                position: 'absolute',
                left: `${leftPercent}%`,
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: 'var(--magenta-glow)',
                transform: 'translate(-50%, -12px)',
                boxShadow: '0 0 8px var(--magenta-glow)'
              }}
            />
          );
        })}
      </div>

      <div style={{ fontSize: '13px', fontFamily: 'Fira Code, monospace', color: 'var(--text-muted)', minWidth: '85px' }}>
        {formatTime(currentTime)} / {formatTime(duration)}
      </div>
    </div>
  );
}
