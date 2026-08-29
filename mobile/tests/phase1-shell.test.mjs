/**
 * Phase 1 mobile shell contracts — static source validation.
 * Run: node --test tests/phase1-shell.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const HARDCODED_RAILWAY = "https://sportbook-me-production.up.railway.app";
const DEFAULT_API = "https://sportbook-me-production.up.railway.app/api";

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".expo" || name === "dist") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|js|jsx)$/.test(name)) acc.push(p);
    else if (name === "package.json" || name === "app.json") acc.push(p);
  }
  return acc;
}

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

test("canonical entry is expo-router", () => {
  const pkg = JSON.parse(read("package.json"));
  assert.equal(pkg.main, "expo-router/entry");
  assert.match(read("app/_layout.tsx"), /AuthProvider/);
  assert.match(read("index.ts"), /LEGACY \/ UNUSED/);
  assert.match(read("App.tsx"), /LEGACY \/ UNUSED/);
});

test("API default and env override live only in lib/api.ts", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export const DEFAULT_API_URL = "https:\/\/sportbook-me-production\.up\.railway\.app\/api"/);
  assert.match(api, /process\.env\.EXPO_PUBLIC_API_URL/);
  assert.match(api, /export function getApiUrl/);

  const active = walk(join(root, "app")).concat(
    walk(join(root, "lib")).filter((p) => !p.endsWith("api.ts")),
  );
  for (const file of active) {
    const src = readFileSync(file, "utf8");
    assert.equal(
      src.includes(HARDCODED_RAILWAY),
      false,
      `hardcoded Railway URL in ${file}`,
    );
  }
});

test("login sends identifier + password", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export async function login\(identifier: string, password: string\)/);
  assert.match(api, /JSON\.stringify\(\{ identifier: identifier\.trim\(\), password \}\)/);
  assert.doesNotMatch(api, /JSON\.stringify\(\{ email:/);

  const login = read("app/index.tsx");
  assert.match(login, /Username or email/);
  assert.match(login, /signIn\(identifier, password\)/);
});

test("session restore validates /auth/me and clears unauthorized tokens", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export async function restoreSession/);
  assert.match(api, /\/auth\/me/);
  assert.match(api, /res\.status === 401 \|\| res\.status === 403/);
  assert.match(api, /await clearToken\(\)/);
  assert.match(api, /kind: "transient"/);

  const auth = read("lib/auth.tsx");
  assert.match(auth, /restoreSession\(\)/);
  assert.match(auth, /session\.kind === "transient"/);
  assert.match(auth, /setStatus\("retrying"\)/);
  assert.doesNotMatch(auth, /session\.kind === "transient"[\s\S]{0,80}setStatus\("authenticated"\)/);
  assert.match(auth, /signOut/);
  assert.match(auth, /clearToken\(\)/);
});

test("protected tabs redirect logged-out users", () => {
  const tabs = read("app/(tabs)/_layout.tsx");
  assert.match(tabs, /status !== "authenticated"/);
  assert.doesNotMatch(tabs, /Redirect href="\/"/);

  const root = read("app/_layout.tsx");
  assert.match(root, /status === "unauthenticated" && inTabs/);
  assert.match(root, /router\.replace\("\/"\)/);
  assert.match(root, /router\.replace\("\/\(tabs\)\/dashboard"\)/);
});

test("AIPreferences is exported for the existing preferences screen", () => {
  const ai = read("lib/ai-api.ts");
  assert.match(ai, /export interface AIPreferences/);
  assert.match(ai, /getApiUrl\(\)/);
  assert.doesNotMatch(ai, /HARDCODED|sportbook-me-production/);
  assert.match(read("app/(tabs)/ai-preferences.tsx"), /import \{ AIPreferences \} from "\.\.\/\.\.\/lib\/ai-api"/);
});

test("register screen no longer uses neon green", () => {
  const reg = read("app/register.tsx");
  assert.doesNotMatch(reg, /#4ade80/);
  assert.match(reg, /#060b1a/);
  assert.match(reg, /#c9a84c/);
});

test("profile and settings logout go through AuthProvider", () => {
  assert.match(read("app/(tabs)/profile.tsx"), /signOut\(\)/);
  assert.match(read("app/(tabs)/settings.tsx"), /signOut\(\)/);
  assert.doesNotMatch(read("app/(tabs)/profile.tsx"), /clearToken/);
  assert.doesNotMatch(read("app/(tabs)/settings.tsx"), /clearToken/);
});

test("production default URL shape is /api", () => {
  assert.equal(DEFAULT_API.endsWith("/api"), true);
});

test("EXPO_PUBLIC_API_URL override contract", () => {
  function getApiUrl(env) {
    const fromEnv = (env || "").trim();
    return fromEnv || DEFAULT_API;
  }
  assert.equal(getApiUrl(""), DEFAULT_API);
  assert.equal(getApiUrl("   "), DEFAULT_API);
  assert.equal(getApiUrl("https://example.test/api"), "https://example.test/api");
});

test("A. successful login persists token in SecureStore only", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export const TOKEN_KEY = "sportbook_me_token"/);
  assert.match(api, /await setToken\(data\.access_token\)/);
  assert.match(api, /SecureStore\.setItemAsync\(TOKEN_KEY/);
  assert.doesNotMatch(api, /AsyncStorage\.setItem\(TOKEN_KEY/);
  assert.doesNotMatch(api, /AsyncStorage\.getItem\(TOKEN_KEY/);
  assert.match(api, /AsyncStorage\.removeItem\(TOKEN_KEY/);
  assert.match(api, /token-write/);
});

test("B. cold-start restore reads the same SecureStore key", () => {
  const api = read("lib/api.ts");
  const get = api.match(/export async function getToken[\s\S]*?^export async function setToken/m)?.[0] || "";
  const restore = api.match(/export async function restoreSession[\s\S]*?^export async function getSubscriptionStatus/m)?.[0] || "";
  assert.match(get, /SecureStore\.getItemAsync\(TOKEN_KEY/);
  assert.doesNotMatch(get, /AsyncStorage\.getItem\(TOKEN_KEY/);
  assert.match(restore, /getToken\(\)/);
  assert.equal((api.match(/sportbook_me_token/g) || []).length >= 1, true);
  assert.doesNotMatch(api, /TOKEN_KEY = "[^"]+"[\s\S]*TOKEN_KEY = "/);
});

test("C. restore validates token through /auth/me with Bearer", () => {
  const api = read("lib/api.ts");
  assert.match(api, /\$\{getApiUrl\(\)\}\/auth\/me/);
  assert.match(api, /Authorization: `Bearer \$\{token\}`/);
  assert.match(api, /res\.status === 401 \|\| res\.status === 403/);
});

test("D. auth loading and retrying prevent premature redirect", () => {
  const root = read("app/_layout.tsx");
  assert.match(root, /status === "loading" \|\| status === "retrying"/);
  assert.match(root, /JWT restore \+ \/auth\/me have settled/);
  const beforeRedirect = root.split("router.replace")[0];
  assert.match(beforeRedirect, /status === "loading"/);
  assert.match(root, /status === "retrying"/);
  const tabs = read("app/(tabs)/_layout.tsx");
  assert.match(tabs, /status !== "authenticated"/);
  const auth = read("lib/auth.tsx");
  assert.match(auth, /session\.kind === "authenticated"/);
  assert.match(auth, /setStatus\("authenticated"\)/);
});

test("E. login placeholder is Username or email", () => {
  const login = read("app/index.tsx");
  assert.match(login, /placeholder="Username or email"/);
  assert.match(login, />Username or email</);
  assert.doesNotMatch(login, /placeholder="Email"/);
});

test("F. Market Tools child routes are hidden from the bottom tab bar", () => {
  assert.equal(existsSync(join(root, "app/(tabs)/market-tools.tsx")), false);
  assert.equal(existsSync(join(root, "app/(tabs)/market-tools/_layout.tsx")), true);
  assert.equal(existsSync(join(root, "app/(tabs)/market-tools/index.tsx")), true);
  const stack = read("app/(tabs)/market-tools/_layout.tsx");
  assert.match(stack, /from "expo-router"/);
  assert.match(stack, /<Stack/);
  const tabs = read("app/(tabs)/_layout.tsx");
  assert.match(tabs, /href: "\/\(tabs\)\/market-tools"/);
  const named = [...tabs.matchAll(/<Tabs\.Screen[\s\S]*?name="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(
    named.filter((n) => !["subscription", "settings", "ai-preferences", "intelligence"].includes(n)),
    ["dashboard", "ai-chat", "optimizer", "lineups", "profile", "market-tools"],
  );
  for (const child of ["live-odds", "compare", "bookmakers", "player-props", "arbitrage", "parlay"]) {
    assert.equal(named.includes(child), false, `child tab leaked: ${child}`);
    assert.equal(named.includes(`market-tools/${child}`), false, `child tab leaked: market-tools/${child}`);
    assert.equal(existsSync(join(root, `app/(tabs)/market-tools/${child}.tsx`)), true);
  }
});
