import { NextResponse } from 'next/server';

export async function GET(
  request: Request,
  { params }: { params: { filename: string } }
) {
  // Simple SVG/MP4 data stream mock response header
  return new NextResponse('Sample MP4 video binary data for testing player canvas', {
    headers: {
      'Content-Type': 'video/mp4',
      'Content-Disposition': 'inline'
    }
  });
}
