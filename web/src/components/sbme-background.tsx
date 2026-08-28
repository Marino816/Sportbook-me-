"use client";

import type { ReactNode } from "react";

export type SBMEBackgroundVariant = "hero" | "app";

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
            <div className="sbme-bg-bowl" />
            <div className="sbme-bg-structure" />
            <div className="sbme-bg-flood sbme-bg-flood--tl" />
            <div className="sbme-bg-flood sbme-bg-flood--tr" />
            <div className="sbme-bg-flood sbme-bg-flood--ml" />
            <div className="sbme-bg-flood sbme-bg-flood--mr" />
            <div className="sbme-bg-flood sbme-bg-flood--bl" />
            <div className="sbme-bg-flood sbme-bg-flood--br" />
            <div className="sbme-bg-beams" />
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
