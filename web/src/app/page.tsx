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

      <p style={{ marginTop: 48, fontSize: 12, color: "#475569", textAlign: "center" }}>
        &copy; {new Date().getFullYear()} SPORTBOOK ME DFS AI LLC. All rights reserved. SB ME Intelligent AI™.
      </p>
    </div>
  );
}