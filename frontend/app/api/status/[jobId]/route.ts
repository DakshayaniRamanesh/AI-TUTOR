import { NextResponse } from 'next/server';

const mockProgressMap: Record<string, number> = {};

export async function GET(
  request: Request,
  { params }: { params: { jobId: string } }
) {
  const { jobId } = params;
  const isMock = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

  let statusUrl =
    process.env.MODAL_STATUS_URL ||
    (process.env.MODAL_BACKEND_URL ? `${process.env.MODAL_BACKEND_URL.replace(/\/$/, '')}/status/${jobId}` : null) ||
    (process.env.BACKEND_URL ? `${process.env.BACKEND_URL.replace(/\/$/, '')}/status/${jobId}` : null) ||
    `http://localhost:8000/status/${jobId}`;

  // If statusUrl is a direct Modal endpoint like https://...status-dev.modal.run, append ?job_id=jobId if query param expected or /jobId
  if (process.env.MODAL_STATUS_URL && !statusUrl.includes(jobId)) {
    statusUrl = `${process.env.MODAL_STATUS_URL}?job_id=${jobId}`;
  }

  if (isMock) {
    const current = mockProgressMap[jobId] || 10;
    const nextProgress = Math.min(100, current + 20);
    mockProgressMap[jobId] = nextProgress;

    const isDone = nextProgress >= 100;
    return NextResponse.json({
      job_id: jobId,
      status: isDone ? 'done' : 'processing',
      step: isDone ? 'uploader' : 'rendering',
      progress_percentage: nextProgress,
      video_url: isDone ? 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4' : null,
      error_message: null,
    });
  }

  try {
    const res = await fetch(statusUrl);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
