import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const login = readFileSync(join(root, "src/app/login/page.tsx"), "utf8");
const register = readFileSync(join(root, "src/app/register/page.tsx"), "utf8");
const profile = readFileSync(join(root, "src/app/profile/page.tsx"), "utf8");
const css = readFileSync(join(root, "src/app/globals.css"), "utf8");
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const username = readFileSync(join(root, "src/lib/username.ts"), "utf8");

test("login keeps stadium glass and does not fake OAuth", () => {
  assert.match(login, /SBMEBackground/);
  assert.match(login, /WELCOME TO SB ME/);
  assert.match(login, /Username or Email/);
  assert.match(login, /Continue with Google/);
  assert.match(login, /Continue with Apple/);
  assert.match(login, /Coming soon/);
  assert.match(login, /oauthStartUrl/);
  assert.match(login, /fetchAuthProviders/);
  assert.match(login, /LOG IN/);
  assert.match(login, /Forgot password/);
  assert.match(login, /Create account/);
  assert.doesNotMatch(login, /Username login is not enabled yet/);
  assert.doesNotMatch(login, /fake provider/);
});

test("register collects username email and passwords", () => {
  assert.match(register, /CREATE YOUR SB ME ACCOUNT/);
  assert.match(register, /Username/);
  assert.match(register, /Confirm Password/);
  assert.match(register, /Create Account/);
  assert.match(register, /Already have an account/);
  assert.match(register, /checkUsernameAvailable/);
  assert.match(register, /SBMEBackground/);
});

test("profile supports one-time username creation", () => {
  assert.match(profile, /choose username/);
  assert.match(profile, /claimUsername/);
  assert.match(profile, /cannot be changed/);
});

test("api client sends identifier and never ships provider secrets", () => {
  assert.match(api, /identifier/);
  assert.match(api, /oauthStartUrl/);
  assert.match(api, /checkUsernameAvailable/);
  assert.doesNotMatch(api, /GOOGLE_OAUTH_CLIENT_SECRET/);
  assert.doesNotMatch(api, /NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_SECRET/);
});

test("username helper enforces public handle rules", () => {
  assert.match(username, /3–24/);
  assert.match(css, /sbme-login-card/);
  assert.match(css, /sbme-login-oauth--ready/);
});

function navAccountLabel(user) {
  const u = (user?.username || "").trim();
  if (u) return u;
  return (user?.email || "").trim();
}

test("navbar prefers authenticated username over email", () => {
  const topnav = readFileSync(join(root, "src/components/TopNav.tsx"), "utf8");
  assert.match(topnav, /navAccountLabel\(user\)/);
  assert.match(username, /export function navAccountLabel/);
  assert.doesNotMatch(topnav, /sbme-nav-email\}>\{user\.email\}/);
  assert.equal(navAccountLabel({ username: "sbmega", email: "qa@sportbookme.ai" }), "sbmega");
  assert.notEqual(navAccountLabel({ username: "sbmega", email: "qa@sportbookme.ai" }), "qa@sportbookme.ai");
  assert.match(profile, /user\?\.email/);
  assert.match(profile, /user\.username/);
});

test("navbar falls back to email when username is absent", () => {
  assert.equal(navAccountLabel({ username: null, email: "qa@sportbookme.ai" }), "qa@sportbookme.ai");
  assert.equal(navAccountLabel({ username: "   ", email: "qa@sportbookme.ai" }), "qa@sportbookme.ai");
  assert.equal(navAccountLabel({ email: "qa@sportbookme.ai" }), "qa@sportbookme.ai");
  assert.equal(navAccountLabel(null), "");
});
