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
    const prompt = (formData.get('prompt') as string) ?? '';
    const pdfFile = formData.get('pdf') as File | null;

    let pdfBytes = '';
    if (pdfFile) {
      const buffer = await pdfFile.arrayBuffer();
      pdfBytes = Buffer.from(buffer).toString('base64');
    }

    const res = await fetch(generateUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, pdf_bytes: pdfBytes }),
    });

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
