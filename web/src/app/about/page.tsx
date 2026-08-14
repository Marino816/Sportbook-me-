import type { Metadata } from "next";
export const metadata: Metadata = { title: "About SB ME DFS.AI", description: "SB ME DFS.AI provides sports analytics and daily fantasy sports intelligence software, not gambling or wagering services." };

import Link from "next/link";
import { LegalPage, H2, P, SUPPORT_EMAIL } from "@/components/legal/legal-page";
import { TrendingUp, Activity, Target, Layers, Bot, ShieldCheck, XCircle } from "lucide-react";

const gold = "#c9a84c";
const cardBg = "#0a0f24";
const cardElevated = "#10162f";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export default function AboutPage() {
  const features = [
    { icon: TrendingUp, title: "AI-Powered Projections", desc: "Advanced player projections driven by machine learning and real-time sports data." },
    { icon: Layers, title: "Lineup Optimization", desc: "Build optimized DFS lineups in seconds using constraint-based optimization." },
    { icon: Activity, title: "Real-Time Sports & Market Data", desc: "Live odds, line movement, and market information from across sportsbooks." },
    { icon: Target, title: "Player-Prop Analysis", desc: "Deep analysis of player props with fair-value comparison and edge detection." },
    { icon: Bot, title: "Sports Intelligence", desc: "AI-assisted insights and answers across projections, odds, and DFS strategy." },
  ];

  return (
    <LegalPage title="About SB ME DFS.AI" lastUpdated="August 14, 2026">
      <P>
        SB ME DFS.AI is a subscription-based sports analytics and daily fantasy sports intelligence software
        platform. We build technology and sports-data analytics for DFS users and sports fans who want a
        sharper, more data-driven approach to their daily fantasy sports and sports research.
      </P>
      <P>
        Our platform provides analytical tools — sports data, statistical analysis, player projections, lineup
        optimization, player-prop analysis, odds information, market information, and AI-assisted sports
        intelligence — in a single, premium workspace.
      </P>

      <H2>What We Offer</H2>
      <div className="grid sm:grid-cols-2 gap-4 mb-6">
        {features.map((f, i) => {
          const Icon = f.icon;
          return (
            <div key={i} className="rounded-2xl border p-5" style={{ background: cardElevated, borderColor: border }}>
              <div className="flex items-center gap-3 mb-2.5">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${gold}10` }}>
                  <Icon size={18} style={{ color: gold }} />
                </div>
                <h3 className="text-sm font-extrabold" style={{ color: textPrimary }}>{f.title}</h3>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: textSecondary }}>{f.desc}</p>
            </div>
          );
        })}
      </div>

      <H2>What SB ME DFS.AI Is — and Isn&rsquo;t</H2>
      <div className="rounded-2xl border p-6 mb-6" style={{ background: cardBg, borderColor: border }}>
        <div className="flex items-start gap-4 mb-4">
          <ShieldCheck size={20} className="shrink-0 mt-0.5" style={{ color: gold }} />
          <div>
            <h3 className="text-sm font-extrabold mb-1" style={{ color: textPrimary }}>What We Are</h3>
            <P>
              SB ME DFS.AI provides sports analytics and daily fantasy sports intelligence software. Customers
              pay for access to software and analytical features — projections, optimization tools, odds
              information, player-prop analysis, and AI-assisted insights.
            </P>
          </div>
        </div>
        <div className="flex items-start gap-4">
          <XCircle size={20} className="shrink-0 mt-0.5" style={{ color: "#ef4444" }} />
          <div>
            <h3 className="text-sm font-extrabold mb-1" style={{ color: textPrimary }}>What We Are Not</h3>
            <P>
              SB ME DFS.AI is not a sportsbook, bookmaker, casino, gambling operator, or paid-entry fantasy
              contest operator. We do not accept or place wagers, accept gambling deposits, hold customer
              gambling balances, collect contest entry fees, award monetary or material prizes based on sporting
              outcomes, process wagers for sportsbooks, or act as a bookmaker. Subscriptions are payment for
              software access and analytics — not wagers, contest entries, or prize payments.
            </P>
          </div>
        </div>
      </div>

      <H2>Our Approach</H2>
      <P>
        We combine statistical modeling with real-time sports data to help you research players, understand
        market movement, and build lineups. All projections, optimization results, odds information, and AI
        responses are estimates and informational outputs. We do not guarantee winnings, profits, successful
        wagers, or successful DFS lineups.
      </P>

      <H2>Contact</H2>
      <P>
        For questions about SB ME DFS.AI, contact us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a> or
        through the <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
