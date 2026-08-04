import assert from "node:assert/strict";
import test from "node:test";
import { getSafeReturnPath } from "../src/lib/safe-return-path.js";

test("accepts same-origin application paths", () => {
  assert.equal(getSafeReturnPath("/dashboard"), "/dashboard");
  assert.equal(getSafeReturnPath("/optimizer?slate=123"), "/optimizer?slate=123");
});

test("rejects external and normalized external return paths", () => {
  for (const payload of [
    "//evil.com",
    "/\\evil.com",
    "https://evil.com",
    "/%2fevil.com",
    "/%2F%2Fevil.com",
    "/%5Cevil.com",
    "/%255Cevil.com",
  ]) {
    assert.equal(getSafeReturnPath(payload), "/dashboard", payload);
  }
});
