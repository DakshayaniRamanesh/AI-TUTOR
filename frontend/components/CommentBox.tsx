'use client';

import React, { useState } from 'react';
import { Send, Plus, Trash2 } from 'lucide-react';

interface CommentBoxProps {
  onSubmitNow: (comment: string) => void;
  onQueueAnnotation: (comment: string) => void;
  onClearDrawing: () => void;
  isSubmitting: boolean;
  queuedCount: number;
}

export default function CommentBox({
  onSubmitNow,
  onQueueAnnotation,
  onClearDrawing,
  isSubmitting,
  queuedCount
}: CommentBoxProps) {
  const [comment, setComment] = useState('');

  const handleImmediateSubmit = () => {
    if (!comment.trim()) return;
    onSubmitNow(comment);
    setComment('');
  };

  const handleAddQueue = () => {
    if (!comment.trim()) return;
    onQueueAnnotation(comment);
    setComment('');
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', marginTop: '16px' }}>
      <h3 style={{ fontSize: '16px', marginBottom: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>Add Canvas Explanation Request</span>
        {queuedCount > 0 && (
          <span style={{ fontSize: '12px', background: 'var(--primary)', padding: '2px 8px', borderRadius: '12px' }}>
            {queuedCount} queued
          </span>
        )}
      </h3>
      <textarea
        className="input-field"
        rows={3}
        placeholder="e.g., What does this highlighted variable represent? Expand on this derivation step."
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
        <button
          type="button"
          className="btn-secondary"
          onClick={onClearDrawing}
          style={{ padding: '8px 14px', fontSize: '13px' }}
        >
          <Trash2 size={14} /> Clear Drawing
        </button>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleAddQueue}
            disabled={!comment.trim() || isSubmitting}
            style={{ padding: '8px 14px', fontSize: '13px' }}
          >
            <Plus size={14} /> Add Another
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleImmediateSubmit}
            disabled={!comment.trim() || isSubmitting}
            style={{ padding: '8px 16px', fontSize: '13px' }}
          >
            <Send size={14} /> Submit Request
          </button>
        </div>
      </div>
    </div>
  );
}
