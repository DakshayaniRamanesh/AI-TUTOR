import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const isMock = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';
    const annotateUrl =
      process.env.MODAL_ANNOTATE_URL ||
      (process.env.MODAL_BACKEND_URL ? `${process.env.MODAL_BACKEND_URL.replace(/\/$/, '')}/annotate` : null) ||
      (process.env.BACKEND_URL ? `${process.env.BACKEND_URL.replace(/\/$/, '')}/annotate` : null) ||
      'http://localhost:8000/annotate';

    const body = await request.json();

    if (isMock) {
      return NextResponse.json({
        job_id: body.job_id || 'mock_job',
        status: 'done',
        version: (body.version || 1) + 1,
        video_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
      });
    }

    const res = await fetch(annotateUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
