import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(join(root, "src/lib/optimal-pct.ts"), "utf8");
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");

function normalizeOptName(n) {
  return (n || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
    .trim();
}

function mapOptimalPctPlayers(players) {
  const m = {};
  for (const p of players || []) {
    if (p == null || p.optimal_pct == null) continue;
    const val = Number(p.optimal_pct);
    if (!Number.isFinite(val)) continue;
    const nm = normalizeOptName(p.name || "");
    if (nm) m[nm] = val;
    if (p.player_id != null && String(p.player_id)) m[String(p.player_id)] = val;
  }
  return m;
}

function lookupOptimalPct(map, namesOrIds) {
  for (const key of namesOrIds) {
    if (key == null || key === "") continue;
    const raw = map[String(key)];
    if (raw != null) return raw;
    const byName = map[normalizeOptName(String(key))];
    if (byName != null) return byName;
  }
  return null;
}

function mapOptimalPctResponse(res) {
  const status = res?.data?.status ?? "NOT_RUN";
  if (status !== "COMPLETE") return { status, map: {} };
  return { status, map: mapOptimalPctPlayers(res?.data?.result?.players) };
}

test("customer Optimal% source is GET /optimal-pct", () => {
  assert.match(api, /`\/optimal-pct\?\$\{params\.toString\(\)\}`/);
  assert.match(src, /GET \/api\/optimal-pct/);
  assert.match(optimizer, /fetchOptimalPct/);
});

test("maps COMPLETE envelope players by name and player_id", () => {
  const mapped = mapOptimalPctResponse({
    status: "success",
    data: {
      status: "COMPLETE",
      result: {
        players: [
          { player_id: "12345", name: "Jesús Luzardo", optimal_pct: 18.5 },
        ],
      },
    },
  });
  assert.equal(mapped.status, "COMPLETE");
  assert.equal(lookupOptimalPct(mapped.map, ["Jesus Luzardo"]), 18.5);
  assert.equal(lookupOptimalPct(mapped.map, ["12345"]), 18.5);
  assert.equal(lookupOptimalPct(mapped.map, ["Unknown"]), null);
});

test("COMPLETE with empty players does not invent Optimal%", () => {
  const mapped = mapOptimalPctResponse({
    data: { status: "COMPLETE", result: { players: [] } },
  });
  assert.equal(mapped.status, "COMPLETE");
  assert.deepEqual(mapped.map, {});
  assert.equal(lookupOptimalPct(mapped.map, ["Aaron Judge", "own40", 2.1]), null);
});

test("does not treat wrap status success as COMPLETE", () => {
  const mapped = mapOptimalPctResponse({
    status: "success",
    data: { status: "NOT_RUN", result: null },
  });
  assert.equal(mapped.status, "NOT_RUN");
  assert.deepEqual(mapped.map, {});
});

test("never substitutes ownership, leverage, or projection", () => {
  const mapped = mapOptimalPctResponse({
    data: {
      status: "COMPLETE",
      result: {
        players: [{
          player_id: "1",
          name: "Judge",
          optimal_pct: 11,
          sbme_ownership_pct: 40,
          leverage: 2.1,
          projected_fp: 12.5,
        }],
      },
    },
  });
  assert.equal(lookupOptimalPct(mapped.map, ["Judge"]), 11);
  assert.notEqual(lookupOptimalPct(mapped.map, ["Judge"]), 40);
  assert.notEqual(lookupOptimalPct(mapped.map, ["Judge"]), 2.1);
});

test("helper source indexes player_id and optimal_pct only", () => {
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.match(code, /p\.player_id/);
  assert.match(code, /p\.optimal_pct/);
  assert.doesNotMatch(code, /sbme_ownership_pct/);
  assert.doesNotMatch(code, /projected_fp/);
});
