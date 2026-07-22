import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const isMock = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';
    const generateUrl =
      process.env.MODAL_GENERATE_URL ||
      (process.env.MODAL_BACKEND_URL ? `${process.env.MODAL_BACKEND_URL.replace(/\/$/, '')}/generate` : null) ||
      (process.env.BACKEND_URL ? `${process.env.BACKEND_URL.replace(/\/$/, '')}/generate` : null) ||
      'http://localhost:8000/generate';

    if (isMock) {
      const jobId = `mock_job_${Math.random().toString(36).substring(2, 9)}`;
      return NextResponse.json({
        job_id: jobId,
        status: 'processing',
        video_url: null,
        estimated_seconds: 90,
      });
    }

    const formData = await request.formData();

    const res = await fetch(generateUrl, {
      method: 'POST',
      body: formData, // Forward the multipart form data directly to FastAPI
    });

    if (!res.ok) {
      // Read the actual error body from the backend for easier debugging
      let detail = res.statusText;
      try {
        const errBody = await res.json();
        detail = errBody.detail || errBody.error || JSON.stringify(errBody);
      } catch {
        try { detail = await res.text(); } catch { /* ignore */ }
      }
      console.error(`[/api/generate] Backend error ${res.status}: ${detail}`);
      return NextResponse.json(
        { error: `Backend returned ${res.status}: ${detail}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('[/api/generate] Fetch/network error:', error.message);
    return NextResponse.json(
      { error: `Cannot reach backend: ${error.message}` },
      { status: 500 }
    );
  }
}
