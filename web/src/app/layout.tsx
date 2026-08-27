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
        style={{ background: "#0a0f24" }}
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
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}