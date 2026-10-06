import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

test("delete-account is a public page that identifies Sportbook Me DFS AI", () => {
  const page = read("src/app/delete-account/page.tsx");
  const form = read("src/app/delete-account/delete-account-form.tsx");
  const guard = read("src/components/auth/ProtectedRoute.tsx");
  assert.match(page, /Sportbook Me DFS AI/);
  assert.match(page, /com\.sportbookme\.app/);
  assert.match(page, /sbmedfsai\.com/);
  assert.match(page, /DeleteAccountForm/);
  assert.doesNotMatch(guard, /\/delete-account/);
  assert.match(form, /login\?next=\/delete-account/);
  assert.match(form, /deleteAccount\(/);
  assert.match(form, /Type DELETE to confirm/);
  assert.match(form, /Permanently delete account/);
  assert.doesNotMatch(page, /placeholder/i);
  assert.doesNotMatch(form, /email support/i);
});

test("page documents actual request steps, retention, and subscriptions", () => {
  const page = read("src/app/delete-account/page.tsx");
  assert.match(page, /Sign in on the website/);
  assert.match(page, /same request/);
  assert.match(page, /no extra waiting period/);
  assert.match(page, /user identifier/);
  assert.match(page, /set to null/);
  assert.match(page, /does not cancel billing/);
  assert.match(page, /Cancel with the provider first/);
  assert.match(page, /PayKings/);
  assert.match(page, /support@sbmedfsai\.com/);
  assert.match(page, /does not issue or store refresh tokens/);
  assert.match(page, /AI chat usage rows/);
  assert.match(page, /hashed request\/response fingerprints/);
  assert.match(page, /play\.google\.com\/store\/account\/subscriptions/);
  assert.match(page, /apps\.apple\.com\/account\/subscriptions/);
});

test("web API uses DELETE /account for the current session", () => {
  const api = read("src/lib/api.ts");
  assert.match(api, /export async function deleteAccount/);
  assert.match(api, /\$\{API_BASE_URL\}\/account/);
  assert.match(api, /method: "DELETE"/);
  assert.match(api, /confirm: "DELETE"/);
});

test("authenticated profile and legal footer link to DELETE ACCOUNT", () => {
  const profile = read("src/app/profile/page.tsx");
  const legal = read("src/components/legal/legal-page.tsx");
  const home = read("src/app/page.tsx");
  assert.match(profile, /DELETE ACCOUNT/);
  assert.match(profile, /href="\/delete-account"/);
  assert.match(legal, /href="\/delete-account"/);
  assert.match(home, /\/delete-account/);
});

test("login still supports next-path return after deletion sign-in", () => {
  const login = read("src/app/login/page.tsx");
  assert.match(login, /getSafeReturnPath/);
  assert.match(login, /nextPath/);
});
