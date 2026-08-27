import Link from "next/link";
import Image from "next/image";

const navy = "#0a0f24";
const cardBg = "#0a0f24";
export const gold = "#c9a84c";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export const SUPPORT_EMAIL = "support@sbmedfsai.com";

export function LegalPage({
  title,
  lastUpdated,
  children,
}: {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ background: navy, color: textPrimary, fontFamily: "'Inter', sans-serif", minHeight: "100vh" }}>
      {/* Header */}
      <header className="sticky top-0 z-50 border-b" style={{ background: "rgba(10,15,36,0.92)", backdropFilter: "blur(16px)", borderColor: border }}>
        <div className="max-w-5xl mx-auto flex items-center justify-between h-16 px-4 sm:px-6">
          <Link href="/" className="shrink-0">
            <Image src="/logo.png" alt="SB ME DFS.AI" width={100} height={53} priority />
          </Link>
          <nav className="flex items-center gap-1">
            <Link href="/about" className="px-3 py-2 rounded-lg text-sm font-semibold" style={{ color: textSecondary }}>About</Link>
            <Link href="/contact" className="px-3 py-2 rounded-lg text-sm font-semibold" style={{ color: textSecondary }}>Contact</Link>
            <Link href="/" className="px-3 py-2 rounded-lg text-sm font-semibold" style={{ color: gold }}>Home</Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 md:py-14">
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-2" style={{ color: textPrimary }}>{title}</h1>
        <p className="text-sm mb-10" style={{ color: textMuted }}>Last Updated: {lastUpdated}</p>
        <div className="legal-content">{children}</div>
      </main>

      {/* Footer */}
      <footer style={{ borderTop: `1px solid ${border}`, background: cardBg }}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs" style={{ color: textMuted }}>
            &copy; {new Date().getFullYear()} SPORTBOOK ME DFS AI LLC. All rights reserved.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/terms" className="text-xs hover:underline" style={{ color: textMuted }}>Terms</Link>
            <Link href="/privacy" className="text-xs hover:underline" style={{ color: textMuted }}>Privacy</Link>
            <Link href="/refund-policy" className="text-xs hover:underline" style={{ color: textMuted }}>Refund Policy</Link>
            <Link href="/contact" className="text-xs hover:underline" style={{ color: textMuted }}>Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ── Typography helpers ── */
export function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight mt-10 mb-4" style={{ color: textPrimary }}>{children}</h2>;
}

export function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="text-base font-bold mt-6 mb-2" style={{ color: gold }}>{children}</h3>;
}

export function P({ children }: { children: React.ReactNode }) {
  return <p className="text-sm leading-relaxed mb-4" style={{ color: textSecondary }}>{children}</p>;
}

export function UL({ children }: { children: React.ReactNode }) {
  return <ul className="list-disc pl-5 mb-4 space-y-2 text-sm leading-relaxed" style={{ color: textSecondary }}>{children}</ul>;
}

export function LI({ children }: { children: React.ReactNode }) {
  return <li>{children}</li>;
}
