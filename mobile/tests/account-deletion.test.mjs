import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

test("Profile and Settings expose DELETE ACCOUNT with destructive confirmation", () => {
  const profile = read("app/(tabs)/profile.tsx");
  const settings = read("app/(tabs)/settings.tsx");
  assert.match(profile, /DELETE ACCOUNT/);
  assert.match(profile, /deleteAccount\(/);
  assert.match(profile, /Delete account permanently\?/);
  assert.match(profile, /style: "destructive"/);
  assert.match(settings, /Delete Account/);
  assert.match(settings, /deleteAccount\(/);
});

test("mobile API deletes the current account via DELETE /account", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export async function deleteAccount/);
  assert.match(api, /method: "DELETE"/);
  assert.match(api, /"\/account"/);
  assert.match(api, /confirm: "DELETE"/);
  assert.doesNotMatch(api, /user_id:/);
});
