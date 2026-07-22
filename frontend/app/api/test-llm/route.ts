import { NextResponse } from 'next/server';

export async function GET() {
  try {
    const isMock = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';
    if (isMock) {
      return NextResponse.json({ status: 'success', message: 'Mock mode active.' });
    }

    const testUrl =
      process.env.MODAL_BACKEND_URL ? `${process.env.MODAL_BACKEND_URL.replace(/\/$/, '')}/test-llm` :
      process.env.BACKEND_URL ? `${process.env.BACKEND_URL.replace(/\/$/, '')}/test-llm` :
      'http://localhost:8000/test-llm';

    const res = await fetch(testUrl);
    
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const errBody = await res.json();
        detail = errBody.message || errBody.detail || errBody.error || JSON.stringify(errBody);
      } catch {
        try { detail = await res.text(); } catch { /* ignore */ }
      }
      return NextResponse.json(
        { status: 'error', message: `Backend returned ${res.status}: ${detail}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { status: 'error', message: `Cannot reach backend: ${error.message}` },
      { status: 500 }
    );
  }
}
