"use client";

export type SBMEBackgroundVariant = "hero" | "app";

export function SBMEBackground({
  variant = "app",
  children,
  className = "",
}: {
  variant?: SBMEBackgroundVariant;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`sbme-bg sbme-bg--${variant} ${className}`.trim()}>
      <div className="sbme-bg-layer" aria-hidden>
        <div className="sbme-bg-beams" />
      </div>
      <div className="sbme-bg-content">{children}</div>
    </div>
  );
}
