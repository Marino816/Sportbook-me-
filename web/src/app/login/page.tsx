"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Loader2, Zap, Mail, Lock, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Redirect if already authenticated
  React.useEffect(() => {
    if (isAuthenticated) router.replace("/dashboard");
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex-1 flex items-center justify-center min-h-screen px-4"
      style={{ background: "#0d1117" }}
    >
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-10">
          <Link href="/" className="inline-flex items-center gap-3 mb-4">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center text-lg font-black"
              style={{
                background: "linear-gradient(135deg, #00dc82, #00b368)",
              }}
            >
              S
            </div>
            <span
              className="text-xl font-black italic tracking-tight"
              style={{ color: "#00dc82" }}
            >
              SPORTBOOK ME
            </span>
          </Link>
          <h1 className="text-2xl font-black text-white">Welcome Back</h1>
          <p className="text-sm mt-2" style={{ color: "#8b949e" }}>
            Sign in to access your DFS tools
          </p>
        </div>

        {/* Error */}
        {error && (
          <div
            className="mb-6 p-4 rounded-xl flex items-center gap-3 text-sm"
            style={{
              background: "rgba(248,81,73,0.1)",
              border: "1px solid rgba(248,81,73,0.3)",
              color: "#f85149",
            }}
          >
            <AlertCircle className="size-5 shrink-0" />
            {error}
          </div>
        )}

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl p-8 space-y-5"
          style={{ background: "#161b22", border: "1px solid #30363d" }}
        >
          <div>
            <label
              className="block text-xs font-bold uppercase tracking-wider mb-2"
              style={{ color: "#8b949e" }}
            >
              Email
            </label>
            <div className="relative">
              <Mail
                className="absolute left-3 top-1/2 -translate-y-1/2 size-4"
                style={{ color: "#8b949e" }}
              />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full pl-10 pr-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "#0d1117",
                  border: "1px solid #30363d",
                  color: "#f0f6fc",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#00dc82")}
                onBlur={(e) => (e.target.style.borderColor = "#30363d")}
              />
            </div>
          </div>

          <div>
            <label
              className="block text-xs font-bold uppercase tracking-wider mb-2"
              style={{ color: "#8b949e" }}
            >
              Password
            </label>
            <div className="relative">
              <Lock
                className="absolute left-3 top-1/2 -translate-y-1/2 size-4"
                style={{ color: "#8b949e" }}
              />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full pl-10 pr-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "#0d1117",
                  border: "1px solid #30363d",
                  color: "#f0f6fc",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#00dc82")}
                onBlur={(e) => (e.target.style.borderColor = "#30363d")}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl font-black text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all hover:opacity-90 disabled:opacity-60"
            style={{
              background: "#00dc82",
              color: "#0d1117",
              boxShadow: "0 4px 20px rgba(0,220,130,0.4)",
            }}
          >
            {loading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Zap className="size-4" />
            )}
            {loading ? "Signing In..." : "Sign In"}
          </button>
        </form>

        <p className="text-center text-sm mt-6" style={{ color: "#8b949e" }}>
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-bold hover:underline"
            style={{ color: "#00dc82" }}
          >
            Create One
          </Link>
        </p>
      </div>
    </div>
  );
}
