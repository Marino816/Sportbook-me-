"use client";

import type { ReactNode } from "react";

export type SBMEBackgroundVariant = "hero" | "app";

function FloodBank({ id, bulbs = 6 }: { id: string; bulbs?: number }) {
  const cols = Array.from({ length: bulbs }, (_, i) => i);
  const gap = 200 / Math.max(bulbs - 1, 1);
  const start = 28;
  return (
    <svg viewBox="0 0 256 96" fill="none" aria-hidden className="sbme-bg-bank-svg">
      <defs>
        <filter id={`${id}-glow`} x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="3.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id={`${id}-bulb`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="38%" stopColor="#eef4ff" />
          <stop offset="100%" stopColor="#9eb6e8" stopOpacity="0.15" />
        </radialGradient>
      </defs>
      <rect x="14" y="30" width="228" height="40" rx="5" fill="#07080c" opacity="0.72" />
      <rect x="18" y="34" width="220" height="32" rx="3" fill="#12141a" opacity="0.9" />
      {cols.map((i) => (
        <g key={`t-${i}`} filter={`url(#${id}-glow)`}>
          <circle cx={start + i * gap} cy="42" r="7.2" fill={`url(#${id}-bulb)`} />
          <circle cx={start + i * gap} cy="42" r="3.4" fill="#fff" opacity="0.95" />
        </g>
      ))}
      {cols.map((i) => (
        <g key={`b-${i}`} filter={`url(#${id}-glow)`}>
          <circle cx={start + i * gap} cy="58" r="7.2" fill={`url(#${id}-bulb)`} />
          <circle cx={start + i * gap} cy="58" r="3.4" fill="#fff" opacity="0.95" />
        </g>
      ))}
    </svg>
  );
}

function EmberField() {
  const dots = [
    [12, 18, 1.1, 0.55], [28, 8, 0.7, 0.35], [41, 22, 1.4, 0.7], [58, 11, 0.8, 0.4],
    [71, 27, 1.2, 0.62], [84, 9, 0.6, 0.3], [18, 41, 0.9, 0.45], [36, 48, 1.3, 0.58],
    [53, 39, 0.7, 0.32], [67, 52, 1.0, 0.5], [81, 44, 1.5, 0.68], [91, 31, 0.8, 0.38],
    [8, 62, 0.6, 0.28], [24, 71, 1.1, 0.48], [47, 66, 0.9, 0.42], [63, 78, 1.3, 0.6],
    [78, 69, 0.7, 0.33], [92, 58, 1.0, 0.5], [15, 88, 0.8, 0.36], [33, 84, 1.2, 0.52],
    [56, 91, 0.6, 0.26], [74, 86, 1.4, 0.64], [88, 80, 0.9, 0.4], [6, 34, 0.7, 0.3],
    [96, 16, 1.1, 0.46], [49, 14, 0.8, 0.34],
  ] as const;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden className="sbme-bg-ember-svg">
      {dots.map(([x, y, r, o], i) => (
        <circle key={i} cx={x} cy={y} r={r} fill="#c9a84c" opacity={o} />
      ))}
    </svg>
  );
}

export function SBMEBackground({
  variant = "app",
  children,
  className = "",
}: {
  variant?: SBMEBackgroundVariant;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`sbme-bg sbme-bg--${variant} ${className}`.trim()}>
      <div className="sbme-bg-layer" aria-hidden>
        {variant === "hero" ? (
          <>
            <div className="sbme-bg-plate sbme-bg-plate--hero" />
            <div className="sbme-bg-plate sbme-bg-plate--features" />
            <div className="sbme-bg-plate sbme-bg-plate--parlay" />
            <div className="sbme-bg-plate sbme-bg-plate--leagues" />
            <div className="sbme-bg-plate sbme-bg-plate--intel" />
            <div className="sbme-bg-plate sbme-bg-plate--pricing" />
            <div className="sbme-bg-plate sbme-bg-plate--cta" />
            <div className="sbme-bg-haze" />
            <div className="sbme-bg-bank sbme-bg-bank--tr"><FloodBank id="rig-tr" /></div>
            <div className="sbme-bg-bank sbme-bg-bank--tl"><FloodBank id="rig-tl" bulbs={5} /></div>
            <div className="sbme-bg-bank sbme-bg-bank--ml"><FloodBank id="rig-ml" bulbs={5} /></div>
            <div className="sbme-bg-bank sbme-bg-bank--mr"><FloodBank id="rig-mr" /></div>
            <div className="sbme-bg-bank sbme-bg-bank--cta-l"><FloodBank id="rig-cl" bulbs={5} /></div>
            <div className="sbme-bg-bank sbme-bg-bank--cta-r"><FloodBank id="rig-cr" /></div>
            <div className="sbme-bg-rays" />
            <div className="sbme-bg-embers sbme-bg-embers--hero"><EmberField /></div>
            <div className="sbme-bg-embers sbme-bg-embers--parlay"><EmberField /></div>
            <div className="sbme-bg-embers sbme-bg-embers--cta"><EmberField /></div>
            <div className="sbme-bg-grain" />
            <div className="sbme-bg-read" />
            <div className="sbme-bg-vignette" />
          </>
        ) : (
          <div className="sbme-bg-beams" />
        )}
      </div>
      <div className="sbme-bg-content">{children}</div>
    </div>
  );
}
