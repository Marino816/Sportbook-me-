import assert from "node:assert/strict";
import test from "node:test";

test("upcoming schedule keeps only real dated matchups", async () => {
  const mod = await import("../src/lib/upcoming-schedule.ts");
  const future = new Date(Date.now() + 86400_000).toISOString();
  const past = new Date(Date.now() - 86400_000 * 3).toISOString();
  const kept = mod.upcomingScheduleEvents([
    {
      id: "1", sport: "FOOTBALL", league: "NFL", start_time: future, status: "SCHEDULED",
      status_display: "Scheduled", venue: "", home_team: { name: "Houston", abbreviation: "HOU", team_id: "HOU" },
      away_team: { name: "Buffalo", abbreviation: "BUF", team_id: "BUF" },
      home_score: null, away_score: null, period: null, players: [], markets: [{ odd_id: "x" }], bookmakers: ["draftkings"],
    },
    {
      id: "2", sport: "FOOTBALL", league: "NFL", start_time: past, status: "STATUS_FINAL",
      status_display: "Final", venue: "", home_team: { name: "Cincy", abbreviation: "CIN", team_id: "CIN" },
      away_team: { name: "Tampa", abbreviation: "TB", team_id: "TB" },
      home_score: 1, away_score: 0, period: null, players: [], markets: [], bookmakers: [],
    },
    {
      id: "3", sport: "FOOTBALL", league: "NFL", start_time: future, status: "SCHEDULED",
      status_display: "Scheduled", venue: "", home_team: { name: "", abbreviation: "", team_id: "" },
      away_team: { name: "", abbreviation: "", team_id: "" },
      home_score: null, away_score: null, period: null, players: [], markets: [], bookmakers: [],
    },
  ]);
  assert.equal(kept.length, 1);
  assert.equal(mod.scheduleMatchupLabel(kept[0]), "BUF @ HOU");
  assert.match(mod.formatKickoffEt(kept[0].start_time), /ET/);
  assert.equal(mod.eventsWithMarketContext(kept).length, 1);
  assert.match(mod.SCHEDULE_INTEL_NOTE, /DFS contest availability is tracked separately/);
});
