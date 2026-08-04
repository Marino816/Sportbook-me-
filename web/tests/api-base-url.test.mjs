import assert from "node:assert/strict";
import test from "node:test";
import { getApiBaseUrl } from "../src/lib/api-base-url.js";

test("adds the API prefix to an origin-only URL", () => {
  assert.equal(
    getApiBaseUrl("https://sportbook-me-production.up.railway.app"),
    "https://sportbook-me-production.up.railway.app/api",
  );
});

test("preserves an existing API prefix", () => {
  assert.equal(
    getApiBaseUrl("https://sportbook-me-production.up.railway.app/api/"),
    "https://sportbook-me-production.up.railway.app/api",
  );
});
