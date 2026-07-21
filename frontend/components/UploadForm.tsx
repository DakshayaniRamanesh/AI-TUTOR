'use client';

import React, { useState } from 'react';
import { Upload, Sparkles, FileText, AlertCircle } from 'lucide-react';

interface UploadFormProps {
  onStartGeneration: (file: File | null, prompt: string) => void;
  isProcessing: boolean;
  progressPercentage: number;
  progressStep?: string;
}

export default function UploadForm({
  onStartGeneration,
  isProcessing,
  progressPercentage,
  progressStep
}: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.type !== 'application/pdf') {
        setError('Please upload a valid PDF document.');
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      setError('Please provide a prompt description for the explainer video.');
      return;
    }
    setError(null);
    onStartGeneration(file, prompt);
  };

  return (
    <div className="glass-panel" style={{ padding: '36px', maxWidth: '680px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Generate Manim Video</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '15px' }}>
          Upload a PDF document and prompt our AI agent pipeline to construct a custom Manim animation.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* PDF File Drag and Drop */}
        <div style={{
          border: '2px dashed var(--border-glass-glow)',
          borderRadius: 'var(--radius-md)',
          padding: '24px',
          textAlign: 'center',
          background: 'rgba(15, 23, 42, 0.4)',
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}>
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            id="pdf-upload"
            style={{ display: 'none' }}
          />
          <label htmlFor="pdf-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
            <FileText size={36} color="var(--primary-glow)" />
            {file ? (
              <span style={{ fontWeight: '600', color: 'var(--cyan-glow)' }}>{file.name}</span>
            ) : (
              <div>
                <span style={{ fontWeight: '500' }}>Drop PDF here or click to browse</span>
                <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>Maximum 20 pages</p>
              </div>
            )}
          </label>
        </div>

        {/* Prompt Input */}
        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '600' }}>
            Explainer Prompt
          </label>
          <textarea
            className="input-field"
            rows={4}
            placeholder="e.g., Explain page 3's equation E = mc^2 visually using geometric transformations and color highlights."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div style={{ textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>
            {prompt.length} characters
          </div>
        </div>

        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '14px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Action Button & Progress */}
        {!isProcessing ? (
          <button type="submit" className="btn-primary" style={{ justifyContent: 'center', width: '100%' }}>
            <Sparkles size={18} />
            <span>Generate Explainer Video</span>
          </button>
        ) : (
          <div style={{ marginTop: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px' }}>
              <span style={{ color: 'var(--primary-glow)' }}>{progressStep || 'Processing pipeline...'}</span>
              <span>{progressPercentage}%</span>
            </div>
            <div className="progress-bar-container">
              <div className="progress-bar-fill" style={{ width: `${progressPercentage}%` }}></div>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
