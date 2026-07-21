'use client';

import React, { useRef, useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import { AnnotationPoint } from '../lib/api';

export interface CanvasRef {
  clearCanvas: () => void;
  captureFrameWithOverlay: () => string;
  getNormalizedPaths: () => AnnotationPoint[][];
}

interface AnnotationCanvasProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  width: number;
  height: number;
}

const AnnotationCanvas = forwardRef<CanvasRef, AnnotationCanvasProps>(({
  videoRef,
  width,
  height
}, ref) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [paths, setPaths] = useState<AnnotationPoint[][]>([]);
  const [currentPath, setCurrentPath] = useState<AnnotationPoint[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#ec4899'; // Vibrant glowing magenta highlight stroke
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const renderPaths = (allPaths: AnnotationPoint[][]) => {
      allPaths.forEach((path) => {
        if (path.length < 2) return;
        ctx.beginPath();
        ctx.moveTo(path[0].x * width, path[0].y * height);
        for (let i = 1; i < path.length; i++) {
          ctx.lineTo(path[i].x * width, path[i].y * height);
        }
        ctx.stroke();
      });
    };

    renderPaths(paths);
    if (currentPath.length > 0) {
      renderPaths([currentPath]);
    }
  }, [paths, currentPath, width, height]);

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setIsDrawing(true);
    setCurrentPath([{ x, y }]);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setCurrentPath((prev) => [...prev, { x, y }]);
  };

  const handleMouseUp = () => {
    if (isDrawing && currentPath.length > 0) {
      setPaths((prev) => [...prev, currentPath]);
      setCurrentPath([]);
    }
    setIsDrawing(false);
  };

  useImperativeHandle(ref, () => ({
    clearCanvas: () => {
      setPaths([]);
      setCurrentPath([]);
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx?.clearRect(0, 0, width, height);
      }
    },
    getNormalizedPaths: () => paths,
    captureFrameWithOverlay: () => {
      const offscreen = document.createElement('canvas');
      offscreen.width = width || 960;
      offscreen.height = height || 540;
      const ctx = offscreen.getContext('2d');
      if (ctx && videoRef.current) {
        ctx.drawImage(videoRef.current, 0, 0, offscreen.width, offscreen.height);
        if (canvasRef.current) {
          ctx.drawImage(canvasRef.current, 0, 0, offscreen.width, offscreen.height);
        }
      }
      return offscreen.toDataURL('image/png');
    }
  }));

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="annotation-canvas-el"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    />
  );
});

AnnotationCanvas.displayName = 'AnnotationCanvas';
export default AnnotationCanvas;
