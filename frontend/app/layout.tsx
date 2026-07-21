import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Manim AI Video Generator & Canvas Annotator',
  description: 'AI-powered Manim explainer video generation with interactive canvas annotation.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              color: 'white'
            }}>M</div>
            <h1 className="gradient-title">Manim AI Generator</h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '14px', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }}></span>
              Backend Ready
            </span>
          </div>
        </header>
        <main style={{ padding: '30px 20px', maxWidth: '1280px', margin: '0 auto' }}>
          {children}
        </main>
      </body>
    </html>
  );
}
