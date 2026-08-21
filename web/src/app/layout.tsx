import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/lib/providers";
import { AuthProvider } from "@/lib/auth";
import { TopNav } from "@/components/TopNav";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { WorkspaceProvider } from "@/lib/workspace-context";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SB ME DFS.AI — Sports Analytics & DFS Intelligence Software",
  description:
    "Subscription-based sports analytics and daily fantasy sports intelligence software with projections, lineup optimization, odds comparison, player-prop analytics, and AI insights. No wagering or contest-entry services.",
  icons: {
    icon: [
      { url: "/favicon.ico?v=2", sizes: "32x32" },
      { url: "/favicon.png?v=2", sizes: "32x32", type: "image/png" },
      { url: "/icon-48.png?v=2", sizes: "48x48", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png?v=2", sizes: "180x180" }],
    other: [
      { url: "/icon-192.png?v=2", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png?v=2", sizes: "512x512", type: "image/png" },
    ],
  },
  manifest: "/site.webmanifest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen`}
        style={{ background: "#060b1a" }}
      >
        <Providers>
          <AuthProvider>
            <WorkspaceProvider>
              <TopNav />
              <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
                <ProtectedRoute>{children}</ProtectedRoute>
              </main>
            </WorkspaceProvider>
          </AuthProvider>
        </Providers>
        {/* ── Global Footer ── */}
        <footer style={{ borderTop: "1px solid #1e293b", background: "#060b1a", padding: "14px 24px", display: "flex", justifyContent: "center", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <span style={{ color: "#64748b", fontSize: 12 }}>&copy; {new Date().getFullYear()} Sportbook Me DFS AI LLC</span>
          <a
            href="https://x.com/SportbookMeAI"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Follow Sportbook Me DFS AI on X"
            className="footer-x-link"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "#94a3b8", fontSize: 12, textDecoration: "none" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            <span>@SportbookMeAI</span>
          </a>
        </footer>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}