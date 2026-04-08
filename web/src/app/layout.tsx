import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/lib/providers";
import { Navigation } from "@/components/Navigation";
import { DataSourceBadge } from "@/components/DataSourceBadge";
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
  title: "Sportsbook Me DFS AI — MLB, NBA, NFL & More",
  description:
    "The most powerful DFS AI platform. Optimize lineups across MLB, NBA, NFL, NHL, Soccer, MLS, UFC, PGA, NCAAF, NCAAM, NCAAW, and Boxing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen flex`}
        style={{ background: "#0d1117" }}
      >
        <Providers>
          {/* Navigation is hidden on "/" by internal logic */}
          <Navigation />
          <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
            {children}
          </main>
          <DataSourceBadge />
        </Providers>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
