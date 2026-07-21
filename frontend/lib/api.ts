export interface AnnotationPoint {
  x: float;
  y: float;
}

export interface AnnotationPayload {
  timestamp: number;
  canvas_image: string;
  paths: AnnotationPoint[][];
  comment: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  step?: string;
  progress_percentage: number;
  video_url?: string | null;
  stitched_video_url?: string | null;
  error_message?: string | null;
  version?: number;
}

export async function generateVideo(pdfFile: File | null, prompt: string): Promise<{ job_id: string }> {
  const formData = new FormData();
  if (pdfFile) {
    formData.append('pdf', pdfFile);
  }
  formData.append('prompt', prompt);

  const res = await fetch('/api/generate', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Generation request failed: ${res.statusText}`);
  }

  return res.json();
}

export async function submitAnnotations(jobId: string, annotations: AnnotationPayload[]): Promise<{ video_url: string; version: number }> {
  const res = await fetch('/api/annotate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, annotations }),
  });

  if (!res.ok) {
    throw new Error(`Annotation request failed: ${res.statusText}`);
  }

  return res.json();
}

export async function pollJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`/api/status/${jobId}`);
  if (!res.ok) {
    throw new Error(`Status check failed: ${res.statusText}`);
  }
  return res.json();
}
