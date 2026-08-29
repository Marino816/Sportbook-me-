"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { SBMEBackground } from "@/components/sbme-background";

export default function AuthCallbackPage() {
  const router = useRouter();
  const { applyToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const needsUsername = params.get("needs_username") === "1";
    if (!token) {
      setError("Sign-in did not complete.");
      return;
    }
    applyToken(token)
      .then(() => {
        router.replace(needsUsername ? "/onboarding/username" : "/dashboard");
      })
      .catch(() => setError("Sign-in did not complete."));
  }, [applyToken, router]);

  return (
    <SBMEBackground variant="hero" className="sbme-login-page">
      <div className="sbme-login-wrap">
        <div className="sbme-login-card">
          <p className="sbme-login-footer">{error || "Finishing sign-in…"}</p>
        </div>
      </div>
    </SBMEBackground>
  );
}
