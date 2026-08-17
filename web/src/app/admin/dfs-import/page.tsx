"use client";

import { useState, useCallback } from "react";
import { Upload, CheckCircle2, XCircle, AlertTriangle, RefreshCw } from "lucide-react";
import { resolveApiUrl } from "@/lib/api-base-url";
import { getStoredToken } from "@/lib/api";

const navy = "#060b1a";
const gold = "#c9a84c";
const border = "#1e293b";

interface ImportResponse {
  slate_id?: number;
  platform?: string;
  sport?: string;
  slate_name?: string;
  player_count?: number;
  game_count?: number;
  slate_date?: string;
  status?: string;
  freshness?: string;
  warnings?: string[];
}

interface SlateRow {
  id: number;
  platform: string;
  sport: string;
  slate_name: string;
  player_count: number;
  matched: number;
  review: number;
  unmatched: number;
  status: string;
  uploaded_at: string | null;
}

export default function DfsImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [platform, setPlatform] = useState<string>("auto");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slates, setSlates] = useState<SlateRow[]>([]);
  const [loadingSlates, setLoadingSlates] = useState(false);

  const apiBase = resolveApiUrl();
  const token = getStoredToken();
  const authHeaders = { Authorization: `Bearer ${token || ""}` };

  const loadSlates = useCallback(async () => {
    setLoadingSlates(true);
    try {
      const res = await fetch(`${apiBase}/admin/dfs/slates`, { headers: authHeaders });
      const json = await res.json();
      setSlates(json?.data ?? json ?? []);
    } catch { /* ignore */ }
    setLoadingSlates(false);
  }, [token]);

  const onUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${apiBase}/admin/dfs/slates/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token || ""}` },
        body: fd,
      });
      const json = await res.json();
      if (!res.ok) {
        const detail = json?.detail;
        if (typeof detail === "object") {
          setError([detail?.detail || "Validation failed", ...(detail?.errors ?? [])].join(" · "));
        } else {
          setError(detail || `Upload failed (HTTP ${res.status})`);
        }
      } else {
        setResult(json?.data ?? json);
        loadSlates();
      }
    } catch (e) {
      setError(String(e));
    }
    setUploading(false);
  };

  const detectedPlatform = platform === "auto" ? (file?.name.toLowerCase().includes("fan") ? "fanduel" : "draftkings") : platform;

  return (
    <div style={{ minHeight: "100vh", background: navy, padding: 32, color: "#f0f6fc" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>DFS Slate Import</h1>
      <p style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
        Canonical DK/FD CSV ingestion with validation. Stale or malformed slates are rejected — only CURRENT (today) slates become optimizer-eligible.
      </p>

      {/* Upload */}
      <div style={{ marginTop: 24, padding: 20, borderRadius: 14, border: `1px solid ${border}`, background: "#0a0f24" }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 18px", borderRadius: 10, border: `1px dashed ${gold}`, cursor: "pointer", fontWeight: 700, fontSize: 13, color: gold }}>
            <Upload size={16} />
            {file ? file.name : "Choose CSV file"}
            <input type="file" accept=".csv" style={{ display: "none" }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>

          <select value={platform} onChange={(e) => setPlatform(e.target.value)}
            style={{ padding: "12px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "#0a0f24", border: `1px solid ${border}`, color: "#94a3b8" }}>
            <option value="auto">Auto-detect platform</option>
            <option value="draftkings">DraftKings</option>
            <option value="fanduel">FanDuel</option>
          </select>

          <button onClick={onUpload} disabled={!file || uploading}
            style={{ padding: "12px 22px", borderRadius: 10, fontWeight: 800, fontSize: 13, background: file && !uploading ? gold : "#1e293b", color: file && !uploading ? navy : "#64748b", border: "none", cursor: file && !uploading ? "pointer" : "not-allowed" }}>
            {uploading ? "Importing…" : "Import & Validate"}
          </button>

          {detectedPlatform !== "auto" && (
            <span style={{ fontSize: 12, color: "#64748b" }}>Detected: <strong style={{ color: "#94a3b8" }}>{detectedPlatform === "draftkings" ? "DraftKings" : "FanDuel"}</strong></span>
          )}
        </div>
      </div>

      {/* Result */}
      {error && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10, border: "1px solid #7f1d1d", background: "rgba(127,29,29,0.15)", color: "#fca5a5", fontSize: 13 }}>
          <XCircle size={14} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} />{error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 16, padding: 16, borderRadius: 12, border: `1px solid ${result.freshness === "CURRENT" ? "#16a34a" : "#c9a84c"}`, background: "#0a0f24" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            {result.freshness === "CURRENT" ? <CheckCircle2 size={18} style={{ color: "#22c55e" }} /> : <AlertTriangle size={18} style={{ color: gold }} />}
            <strong style={{ color: "#f0f6fc" }}>{result.slate_name}</strong>
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: result.freshness === "CURRENT" ? "rgba(34,197,94,0.15)" : "rgba(201,168,76,0.15)", color: result.freshness === "CURRENT" ? "#22c55e" : gold, fontWeight: 700 }}>
              {result.freshness}
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10, fontSize: 12 }}>
            {[["Platform", result.platform], ["Sport", result.sport], ["Slate date", result.slate_date], ["Players", String(result.player_count)], ["Games", String(result.game_count)], ["Status", result.status]].map(([k, v]) => (
              <div key={k}><span style={{ color: "#64748b" }}>{k}:</span> <strong style={{ color: "#94a3b8" }}>{v}</strong></div>
            ))}
          </div>
          {result.warnings && result.warnings.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 12, color: "#fbbf24" }}>
              <AlertTriangle size={12} style={{ display: "inline", marginRight: 4, verticalAlign: -1 }} />{result.warnings.join(" · ")}
            </div>
          )}
        </div>
      )}

      {/* Slate list */}
      <div style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Imported Slates</h2>
          <button onClick={loadSlates} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: "#0a0f24", border: `1px solid ${border}`, color: "#94a3b8", cursor: "pointer" }}>
            <RefreshCw size={12} style={{ display: "inline", marginRight: 4, verticalAlign: -1 }} />Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto", borderRadius: 12, border: `1px solid ${border}` }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${border}`, background: "#0a0f24" }}>
                {["ID", "Platform", "Sport", "Slate", "Players", "Status", "Uploaded"].map((h) => (
                  <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(slates.length === 0 && !loadingSlates) && (
                <tr><td colSpan={7} style={{ padding: 16, textAlign: "center", color: "#64748b" }}>No slates imported yet.</td></tr>
              )}
              {slates.map((s) => (
                <tr key={s.id} style={{ borderBottom: `1px solid ${border}40` }}>
                  <td style={{ padding: "10px 12px", color: "#64748b" }}>{s.id}</td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{s.platform === "draftkings" ? "DraftKings" : "FanDuel"}</td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{s.sport}</td>
                  <td style={{ padding: "10px 12px", color: "#f0f6fc", fontWeight: 700 }}>{s.slate_name}</td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{s.player_count}</td>
                  <td style={{ padding: "10px 12px" }}><span style={{ padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700, background: s.status === "PUBLISHED" ? "rgba(34,197,94,0.15)" : "rgba(100,116,139,0.15)", color: s.status === "PUBLISHED" ? "#22c55e" : "#94a3b8" }}>{s.status}</span></td>
                  <td style={{ padding: "10px 12px", color: "#64748b" }}>{s.uploaded_at ? new Date(s.uploaded_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
