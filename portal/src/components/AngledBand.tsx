'use client';

import React from 'react';

/**
 * Full-bleed diagonal gradient band.
 *
 * Borrows the *grammar* of an angled section edge — a band of colour cut on a
 * slant rather than a flat horizontal rule — without borrowing anyone's
 * palette. The colours here are InterMesh's own cyan and violet, run through
 * a magenta transition so the band has somewhere to travel.
 *
 * `variant` picks which corner the cut falls on, so consecutive sections can
 * alternate instead of repeating the same silhouette down the page.
 */

type Variant = 'bottom-left' | 'bottom-right' | 'both';

const CLIPS: Record<Variant, string> = {
  'bottom-left': 'polygon(0 0, 100% 0, 100% 100%, 0 88%)',
  'bottom-right': 'polygon(0 0, 100% 0, 100% 88%, 0 100%)',
  both: 'polygon(0 4%, 100% 0, 100% 96%, 0 100%)',
};

export default function AngledBand({
  variant = 'bottom-right',
  opacity = 0.14,
  className = '',
}: {
  variant?: Variant;
  opacity?: number;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 ${className}`}
      style={{ clipPath: CLIPS[variant] }}
    >
      <div
        className="absolute inset-0"
        style={{
          opacity,
          background:
            'linear-gradient(115deg, #00D4FF 0%, #3B82F6 26%, #8B5CF6 52%, #C026D3 74%, transparent 100%)',
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 90% 80% at 30% 0%, transparent 0%, rgba(8,8,10,0.65) 70%, #08080A 100%)',
        }}
      />
    </div>
  );
}
