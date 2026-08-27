"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { getSafeReturnPath } from "@/lib/safe-return-path";
import { Loader2, Mail, Lock, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const nextPath = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("next");
  const destination = getSafeReturnPath(nextPath);
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (isAuthenticated) router.replace(destination);
  }, [destination, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push(destination);
    } catch (err: any) {
      setError(err.message || "Invalid credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: 24, background: "#0a0f24" }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <Link href="/">
            <Image src="/logo.png" alt="SB ME DFS.AI" width={160} height={84} priority style={{ margin: "0 auto" }} />
          </Link>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#f0f6fc", marginTop: 12 }}>Welcome Back</h1>
          <p style={{ color: "#94a3b8", fontSize: 14, marginTop: 4 }}>Sign in to access your DFS tools</p>
        </div>

        {error && (
          <div style={{ marginBottom: 24, padding: 16, borderRadius: 14, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", display: "flex", alignItems: "center", gap: 12, fontSize: 14 }}>
            <AlertCircle size={20} />{error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 32, display: "flex", flexDirection: "column", gap: 20 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", display: "block", marginBottom: 8 }}>Email</label>
            <div style={{ position: "relative" }}>
              <Mail size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com"
                style={{ width: "100%", padding: "12px 12px 12px 40px", borderRadius: 12, border: "1px solid #1e293b", background: "#060b1a", color: "#f0f6fc", fontSize: 14, outline: "none" }} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", display: "block", marginBottom: 8 }}>Password</label>
            <div style={{ position: "relative" }}>
              <Lock size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password"
                style={{ width: "100%", padding: "12px 12px 12px 40px", borderRadius: 12, border: "1px solid #1e293b", background: "#060b1a", color: "#f0f6fc", fontSize: 14, outline: "none" }} />
            </div>
          </div>
          <button type="submit" disabled={loading}
            style={{ padding: "14px", borderRadius: 14, background: "#c9a84c", color: "#060b1a", border: "none", fontWeight: 800, fontSize: 15, textTransform: "uppercase", cursor: "pointer", boxShadow: "0 4px 20px rgba(201,168,76,0.3)" }}>
            {loading ? <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} /> : "Sign In"}
          </button>
        </form>

        <p style={{ textAlign: "center", color: "#94a3b8", fontSize: 14, marginTop: 24 }}>
          Don&apos;t have an account?{" "}
          <Link href="/register" style={{ color: "#c9a84c", fontWeight: 700 }}>Create One</Link>
        </p>
      </div>
    </div>
  );
}