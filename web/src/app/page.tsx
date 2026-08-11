import Link from "next/link";
import Image from "next/image";

export default function LandingPage() {
  return (
    <div style={{
      minHeight: "100vh", background: "#060b1a", color: "#f0f6fc",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: "40px 24px", textAlign: "center",
    }}>
      <Image src="/logo.png" alt="SB ME DFS.AI" width={240} height={126} priority />

      <p style={{ fontSize: 22, fontWeight: 700, color: "#94a3b8", marginTop: 32, maxWidth: 600 }}>
        AI-Powered DFS Intelligence
      </p>
      <p style={{ fontSize: 15, color: "#64748b", marginTop: 8 }}>
        Optimize. Analyze. Win.
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 32 }}>
        <Link href="/login" style={{
          padding: "14px 36px", borderRadius: 14, fontSize: 16, fontWeight: 700,
          background: "#c9a84c", color: "#060b1a", textDecoration: "none",
        }}>
          Sign In
        </Link>
        <Link href="/register" style={{
          padding: "14px 36px", borderRadius: 14, fontSize: 16, fontWeight: 700,
          background: "transparent", color: "#c9a84c", textDecoration: "none",
          border: "1px solid #c9a84c",
        }}>
          Get Started
        </Link>
      </div>

      {/* SGO Tier Info */}
      <div style={{ marginTop: 64, maxWidth: 700, width: "100%" }}>
        <div style={{
          background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b",
          padding: 32, textAlign: "left",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#c9a84c", textTransform: "uppercase" }}>
              Powered by SportsGameOdds — Amateur Tier
            </span>
            <span style={{
              background: "rgba(201,168,76,0.15)", color: "#c9a84c", fontWeight: 700, fontSize: 11,
              padding: "4px 12px", borderRadius: 20,
            }}>
              Free
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10, fontSize: 13 }}>
            {[
              "2.5k objects/month", "10 requests/minute", "10 min update frequency",
              "8 Leagues", "9 Bookmakers",
              "Sports, Leagues, Teams, Players, Events",
              "Results + Live Scores + Game Status",
              "Spreads + Moneylines + Over-Unders",
              "Pregame + Live (in-game) + Partials",
              "Fair Odds + Book Consensus",
              "Player Props + Team Props + Alt Lines",
              "DraftKings, FanDuel, BetMGM, Caesars, ESPN BET, Bovada, Unibet",
              "NFL, NBA, MLB, NHL, College Football, College Basketball, Champions League, MLS",
            ].map((feat, i) => (
              <div key={i} style={{ color: "#94a3b8", padding: "4px 0" }}>
                ✓ {feat}
              </div>
            ))}
          </div>
        </div>
      </div>

      <p style={{ marginTop: 48, fontSize: 12, color: "#475569", textAlign: "center" }}>
        &copy; {new Date().getFullYear()} SPORTBOOK ME DFS AI LLC. All rights reserved. SB ME Intelligent AI™.
      </p>
    </div>
  );
}