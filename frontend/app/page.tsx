'use client';

import React, { useState, useRef } from 'react';
import UploadForm from '../components/UploadForm';
import VideoPlayer from '../components/VideoPlayer';
import AnnotationCanvas, { CanvasRef } from '../components/AnnotationCanvas';
import CommentBox from '../components/CommentBox';
import TimelineScrubber from '../components/TimelineScrubber';
import { generateVideo, submitAnnotations, pollJobStatus, AnnotationPayload } from '../lib/api';
import { ArrowLeft, RefreshCw, Layers } from 'lucide-react';

export default function HomePage() {
  const [phase, setPhase] = useState<'upload' | 'player'>('upload');
  const [jobId, setJobId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressPercentage, setProgressPercentage] = useState(0);
  const [progressStep, setProgressStep] = useState('');
  
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoVersion, setVideoVersion] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const [queuedAnnotations, setQueuedAnnotations] = useState<AnnotationPayload[]>([]);
  const [isSubmittingAnnotation, setIsSubmittingAnnotation] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<CanvasRef | null>(null);

  const handleStartGeneration = async (pdfFile: File | null, prompt: string) => {
    setIsProcessing(true);
    setProgressPercentage(10);
    setProgressStep('Initializing multi-agent pipeline...');

    try {
      const { job_id, status, video_url, cache_hit } = await generateVideo(pdfFile, prompt) as any;
      setJobId(job_id);

      // ── Cache hit: instant response (no pipeline needed) ──────────────────────
      if (cache_hit && video_url) {
        setProgressPercentage(100);
        setProgressStep('⚡ Served from cache — instant response!');
        setVideoUrl(video_url);
        setIsProcessing(false);
        setPhase('player');
        return;
      }

      // ── SSE: push-based status updates (replaces polling) ──────────────────
      // Uses EventSource (Server-Sent Events) to receive updates the instant
      // each pipeline stage completes. Falls back to polling if SSE unsupported.
      const backendUrl = process.env.NEXT_PUBLIC_MODAL_BACKEND_URL || '';
      const sseUrl = `${backendUrl}/stream_status?job_id=${job_id}`;

      if (typeof EventSource !== 'undefined' && backendUrl) {
        const source = new EventSource(sseUrl);
        source.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setProgressPercentage(data.progress_percentage || 50);
            setProgressStep(data.current_stage ? `✓ ${data.current_stage}` : 'Generating Manim scenes...');

            if (data.status === 'done' || data.video_url) {
              source.close();
              setVideoUrl(data.video_url || '/api/video/sample_manim.mp4');
              setIsProcessing(false);
              setPhase('player');
            } else if (data.status === 'error') {
              source.close();
              setIsProcessing(false);
              alert(`Generation failed: ${data.error_message}`);
            }
          } catch (e) {
            console.error('SSE parse error:', e);
          }
        };
        source.onerror = () => {
          // SSE failed — fall back to polling
          source.close();
          console.warn('[SSE] Connection failed, falling back to polling');
          startPolling(job_id);
        };
      } else {
        // Fallback: polling (when SSE unavailable or no backend URL configured)
        startPolling(job_id);
      }
    } catch (err: any) {
      setIsProcessing(false);
      alert(`Failed to start video generation: ${err.message}`);
    }
  };

  // Polling fallback (used when SSE is unavailable)
  const startPolling = (job_id: string) => {
    const interval = setInterval(async () => {
      try {
        const statusRes = await pollJobStatus(job_id);
        setProgressPercentage(statusRes.progress_percentage || 50);
        setProgressStep(statusRes.step ? `Executing agent: ${statusRes.step}` : 'Generating Manim scenes...');

        if (statusRes.status === 'done' || statusRes.video_url) {
          clearInterval(interval);
          setVideoUrl(statusRes.video_url || '/api/video/sample_manim.mp4');
          setIsProcessing(false);
          setPhase('player');
        } else if (statusRes.status === 'error') {
          clearInterval(interval);
          setIsProcessing(false);
          alert(`Generation failed: ${statusRes.error_message}`);
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 1500);
  };

  const handleTogglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleSeek = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleAddAnnotationToQueue = (comment: string) => {
    if (!canvasRef.current) return;
    const overlayImg = canvasRef.current.captureFrameWithOverlay();
    const normalizedPaths = canvasRef.current.getNormalizedPaths();

    const newAnnotation: AnnotationPayload = {
      timestamp: currentTime,
      canvas_image: overlayImg,
      paths: normalizedPaths,
      comment
    };

    setQueuedAnnotations((prev) => [...prev, newAnnotation]);
    canvasRef.current.clearCanvas();
  };

  const handleSubmitAnnotationsNow = async (comment: string) => {
    if (!jobId) return;
    setIsSubmittingAnnotation(true);

    let currentAnnotationList = [...queuedAnnotations];
    if (comment.trim() && canvasRef.current) {
      const overlayImg = canvasRef.current.captureFrameWithOverlay();
      const normalizedPaths = canvasRef.current.getNormalizedPaths();
      currentAnnotationList.push({
        timestamp: currentTime,
        canvas_image: overlayImg,
        paths: normalizedPaths,
        comment
      });
    }

    if (currentAnnotationList.length === 0) {
      setIsSubmittingAnnotation(false);
      return;
    }

    try {
      const result = await submitAnnotations(jobId, currentAnnotationList);
      setVideoUrl(result.video_url);
      setVideoVersion(result.version);
      setQueuedAnnotations([]);
      canvasRef.current?.clearCanvas();
      alert(`Video updated to version v${result.version} with your explanation clip!`);
    } catch (e: any) {
      alert(`Annotation submission failed: ${e.message}`);
    } finally {
      setIsSubmittingAnnotation(false);
    }
  };

  return (
    <div>
      {phase === 'upload' ? (
        <UploadForm
          onStartGeneration={handleStartGeneration}
          isProcessing={isProcessing}
          progressPercentage={progressPercentage}
          progressStep={progressStep}
        />
      ) : (
        <div>
          {/* Header Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <button
              className="btn-secondary"
              onClick={() => setPhase('upload')}
              style={{ fontSize: '13px' }}
            >
              <ArrowLeft size={16} /> New Generation
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="glass-panel" style={{ padding: '6px 12px', fontSize: '12px', color: 'var(--cyan-glow)' }}>
                Version v{videoVersion}
              </span>
              <span className="glass-panel" style={{ padding: '6px 12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                Job: {jobId}
              </span>
            </div>
          </div>

          {/* Player & Canvas Area */}
          <div className="video-canvas-container">
            {videoUrl && (
              <VideoPlayer
                ref={videoRef}
                src={videoUrl}
                onTimeUpdate={setCurrentTime}
                onLoadedMetadata={setDuration}
              />
            )}
            <AnnotationCanvas
              ref={canvasRef}
              videoRef={videoRef}
              width={960}
              height={540}
            />
          </div>

          {/* Timeline Scrubber */}
          <TimelineScrubber
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            onTogglePlay={handleTogglePlay}
            onSeek={handleSeek}
            annotationMarkers={queuedAnnotations.map((a) => a.timestamp)}
          />

          {/* Comment Box */}
          <CommentBox
            onSubmitNow={handleSubmitAnnotationsNow}
            onQueueAnnotation={handleAddAnnotationToQueue}
            onClearDrawing={() => canvasRef.current?.clearCanvas()}
            isSubmitting={isSubmittingAnnotation}
            queuedCount={queuedAnnotations.length}
          />
        </div>
      )}
    </div>
  );
}
