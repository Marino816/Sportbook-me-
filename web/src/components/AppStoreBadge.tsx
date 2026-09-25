"use client";

import {
  APP_STORE_BADGE_ALT,
  APP_STORE_CTA,
  APP_STORE_URL,
  trackAppStoreClick,
} from "@/lib/app-store";

type AppStoreLinkProps = {
  placement: string;
  className?: string;
  style?: React.CSSProperties;
  "aria-label"?: string;
  children: React.ReactNode;
};

function AppStoreLink({
  placement,
  className = "",
  style,
  children,
  "aria-label": ariaLabel,
}: AppStoreLinkProps) {
  return (
    <a
      href={APP_STORE_URL}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() => trackAppStoreClick(placement)}
      className={className}
      style={style}
      aria-label={ariaLabel}
    >
      {children}
    </a>
  );
}

export function AppStoreBadge({
  placement,
  className = "",
}: {
  placement: string;
  className?: string;
}) {
  return (
    <AppStoreLink
      placement={placement}
      aria-label={APP_STORE_BADGE_ALT}
      className={`inline-flex shrink-0 self-start rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c9a84c] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0f24] ${className}`}
    >
      {/* Official Apple “Download on the App Store” badge */}
      <img
        src="/badges/download-on-the-app-store.svg"
        alt={APP_STORE_BADGE_ALT}
        width={160}
        height={54}
        className="h-10 w-auto max-w-[160px] sm:h-12"
      />
    </AppStoreLink>
  );
}

export function AppStoreCtaLink({
  placement,
  className = "",
}: {
  placement: string;
  className?: string;
}) {
  return (
    <AppStoreLink
      placement={placement}
      aria-label={APP_STORE_CTA}
      className={`flex items-center justify-center w-full min-w-0 max-w-[calc(100vw-2rem)] sm:max-w-md sm:w-auto px-5 sm:px-6 py-3.5 rounded-2xl font-bold text-sm tracking-wide
        hover:brightness-110 transition-all duration-200 text-center whitespace-normal break-words shadow-[0_4px_24px_rgba(201,168,76,0.35)]
        focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c9a84c] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0f24] ${className}`}
      style={{ background: "#c9a84c", color: "#0a0f24" }}
    >
      {APP_STORE_CTA}
    </AppStoreLink>
  );
}
