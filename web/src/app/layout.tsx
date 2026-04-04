import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/lib/providers";
import { Navigation } from "@/components/Navigation";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import { Analytics } from "@vercel/analytics/next";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sportsbook Me DFS AI",
  description: "Next-generation Daily Fantasy Sports Optimizer & Predictions",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen flex bg-background`}
      >
        <Providers>
          <Navigation />
          <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
          <h1 className="text-xl font-bold tracking-tight text-white">SPORTSBOOK <span className="text-neon-green">ME DFS AI</span></h1>
            {children}
          </main>
          <DataSourceBadge />
        </Providers>
        <Analytics />
      </body>
    </html>
  );
}
