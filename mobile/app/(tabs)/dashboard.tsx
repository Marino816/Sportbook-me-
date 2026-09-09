import { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  ImageBackground,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { HomeWordmark } from "../../components/HomeWordmark";
import {
  getIntelligence,
  getLiveOdds,
  getMe,
  getPublishedSlates,
  getSubscriptionStatus,
  unwrapUser,
} from "../../lib/api";
import { displayPlanLabel, lineupCopyForPlan, lineupLimitForPlan } from "../../lib/plan-copy";

const STADIUM = require("../../assets/stadium-night.jpg");

const HOME_FEED_LEAGUES = new Set(["MLB", "NBA", "NFL"]);

const SPORT_SHORTCUTS: { id: string; label: string }[] = [
  { id: "NFL", label: "NFL" },
  { id: "NCAAF", label: "NCAAF" },
  { id: "MLB", label: "MLB" },
  { id: "UEFA_CHAMPIONS_LEAGUE", label: "UCL" },
  { id: "NBA", label: "NBA" },
  { id: "NHL", label: "NHL" },
  { id: "NCAAB", label: "NCAAB" },
  { id: "WNBA", label: "WNBA" },
  { id: "UFC", label: "UFC" },
  { id: "EPL", label: "EPL" },
  { id: "MLS", label: "MLS" },
  { id: "LA_LIGA", label: "La Liga" },
  { id: "BUNDESLIGA", label: "Bundesliga" },
  { id: "FR_LIGUE_1", label: "Ligue 1" },
  { id: "IT_SERIE_A", label: "Serie A" },
  { id: "INTERNATIONAL_SOCCER", label: "Intl Soccer" },
  { id: "EHF_EURO", label: "EHF" },
];

const ACTIONS: { id: string; icon: keyof typeof Ionicons.glyphMap; label: string; route: string; params: Record<string, string> }[] = [
  { id: "best", icon: "sparkles" as const, label: "Build Best\nLineup", route: "/(tabs)/optimizer", params: {} },
  { id: "cash", icon: "shield-checkmark" as const, label: "Cash\nLineup", route: "/(tabs)/optimizer", params: { strategy: "cash" } },
  { id: "gpp", icon: "rocket" as const, label: "GPP\nLineup", route: "/(tabs)/optimizer", params: { strategy: "gpp" } },
  { id: "parlay", icon: "layers" as const, label: "Parlay\nBuilder", route: "/(tabs)/market-tools/parlay", params: {} },
  { id: "markets", icon: "trending-up" as const, label: "Live\nOdds", route: "/(tabs)/market-tools/live-odds", params: {} },
  { id: "ai", icon: "chatbubble-ellipses" as const, label: "Ask\nSB ME AI", route: "/(tabs)/ai-chat", params: {} },
];

function fmtOdds(v: number | null | undefined) {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : String(v);
}

function gameLabel(game: any) {
  const away = game.away_team_name || game.away || "Away";
  const home = game.home_team_name || game.home || "Home";
  return `${away} @ ${home}`;
}

function gameStatus(game: any) {
  const raw = String(game.status || "").toLowerCase();
  if (raw.includes("live") || raw === "inprogress") return "LIVE";
  if (raw.includes("final")) return "FINAL";
  if (game.start_time) {
    try {
      return new Date(game.start_time).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return "Upcoming";
    }
  }
  return "Upcoming";
}

export default function DashboardScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [user, setUser] = useState<any>(null);
  const [billing, setBilling] = useState<any>(null);
  const [league, setLeague] = useState("MLB");
  const [games, setGames] = useState<any[]>([]);
  const [slates, setSlates] = useState<any[]>([]);
  const [intel, setIntel] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [oddsError, setOddsError] = useState<string | null>(null);
  const [slateError, setSlateError] = useState<string | null>(null);
  const [intelError, setIntelError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const me = getMe()
      .then((body) => setUser(unwrapUser(body) || body))
      .catch(() => {});
    const bill = getSubscriptionStatus()
      .then((body) => setBilling((body as any)?.data || body))
      .catch(() => {});
    const odds = getLiveOdds(league)
      .then((payload) => {
        setOddsError(null);
        setGames(Array.isArray(payload?.games) ? payload.games : []);
      })
      .catch((e) => {
        setGames([]);
        setOddsError(e instanceof Error ? e.message : "Could not load live odds");
      });
    const slate = getPublishedSlates({ sport: league })
      .then((rows) => {
        setSlateError(null);
        setSlates(rows);
      })
      .catch((e) => {
        setSlates([]);
        setSlateError(e instanceof Error ? e.message : "Could not load slates");
      });
    await Promise.all([me, bill, odds, slate]);
  }, [league]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      (async () => {
        setLoading(true);
        await load();
        if (active) setLoading(false);
      })();
      return () => {
        active = false;
      };
    }, [load]),
  );

  const currentSlate = useMemo(() => {
    return slates.find((s) => s.is_current) || slates[0] || null;
  }, [slates]);

  useEffect(() => {
    if (!currentSlate?.id) {
      setIntel(null);
      setIntelError(null);
      return;
    }
    let cancelled = false;
    getIntelligence(currentSlate.id)
      .then((payload) => {
        if (cancelled) return;
        setIntelError(null);
        setIntel(payload);
      })
      .catch((e) => {
        if (cancelled) return;
        setIntel(null);
        setIntelError(e instanceof Error ? e.message : "Intelligence unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [currentSlate?.id]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const hasAccess = billing?.has_access === true || user?.is_pro === true;
  const planLabel = displayPlanLabel(billing?.plan || user?.plan, hasAccess);
  const planCopy = lineupCopyForPlan(billing?.plan || user?.plan, hasAccess);
  const lineupLimit = lineupLimitForPlan(billing?.plan || user?.plan, hasAccess);
  const liveCount = games.filter((g) => gameStatus(g) === "LIVE").length;
  const openSlates = slates.filter((s) => s.is_current).length;
  const intelGames = Array.isArray(intel?.games) ? intel.games : [];
  const intelReady =
    Boolean(intel) &&
    !intelError &&
    intel?.empty !== true &&
    intel?.available !== false;
  const topEnv = intelGames[0];
  const displayGames = games.slice(0, 6);
  const displaySlates = slates.slice(0, 4);

  function open(route: string, params: Record<string, string>) {
    if (Object.keys(params).length) {
      router.push({ pathname: route as any, params });
      return;
    }
    router.push(route as any);
  }

  function onSportShortcut(id: string) {
    if (HOME_FEED_LEAGUES.has(id)) {
      setLeague(id);
      return;
    }
    router.push({ pathname: "/(tabs)/market-tools/live-odds" as any, params: { league: id } });
  }

  return (
    <View style={s.flex}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#c9a84c" />}
      >
        <View style={[s.topBlock, { paddingTop: Math.max(10, insets.top) }]}>
          <View style={s.header}>
            <HomeWordmark />
            <TouchableOpacity
              onPress={() => router.push("/(tabs)/profile")}
              accessibilityRole="button"
              accessibilityLabel="Account"
              style={s.accountBtn}
            >
              <Ionicons name="person-circle" size={32} color="#c9a84c" />
            </TouchableOpacity>
          </View>

          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={s.sportRow}
          >
            {SPORT_SHORTCUTS.map((sport) => {
              const on = HOME_FEED_LEAGUES.has(sport.id) && league === sport.id;
              return (
                <TouchableOpacity
                  key={sport.id}
                  style={[s.sportChip, on && s.sportChipOn]}
                  onPress={() => onSportShortcut(sport.id)}
                >
                  <Text style={on ? s.sportTextOn : s.sportText}>{sport.label}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        <ImageBackground source={STADIUM} style={s.hero} imageStyle={s.heroImg} resizeMode="cover">
          <View style={s.heroWash} />
          <View style={s.heroCopy}>
            <Text style={s.heroKicker}>SPORTBOOK ME DFS AI · SB ME</Text>
            <Text style={s.heroTitle}>DFS Intelligence.{"\n"}Live Markets.{"\n"}<Text style={s.heroTitleGold}>One AI Platform.</Text></Text>
            <Text style={s.heroSub}>Analytics, DFS optimization, and sports intelligence — not a sportsbook.</Text>
            <View style={s.heroCtas}>
              <TouchableOpacity style={s.heroCta} onPress={() => router.push("/optimizer")}>
                <Text style={s.heroCtaText}>OPEN OPTIMIZER</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={s.heroCtaGhost}
                onPress={() => router.push("/(tabs)/intelligence")}
              >
                <Text style={s.heroCtaGhostText}>SEE HOW IT WORKS</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ImageBackground>

        <View style={s.body}>
        <TouchableOpacity style={s.planCard} onPress={() => router.push("/(tabs)/subscription")}>
          <View style={s.planTop}>
            <Ionicons name="ribbon" size={16} color="#c9a84c" />
            <Text style={s.planName}>{planLabel}</Text>
            <Text style={s.planLimit}>{lineupLimit}/slate</Text>
          </View>
          <Text style={s.planCopy}>{planCopy}</Text>
        </TouchableOpacity>

        <View style={s.statusRow}>
          <View style={s.statusChip}>
            <Text style={s.statusVal}>{liveCount}</Text>
            <Text style={s.statusLbl}>Live games</Text>
          </View>
          <View style={s.statusChip}>
            <Text style={s.statusVal}>{openSlates || slates.length}</Text>
            <Text style={s.statusLbl}>{openSlates ? "Open slates" : "Listed slates"}</Text>
          </View>
          <View style={s.statusChip}>
            <Text style={s.statusVal}>{displayGames.length}</Text>
            <Text style={s.statusLbl}>{league} board</Text>
          </View>
        </View>

        <Text style={s.sectionTitle}>Quick Actions</Text>
        <View style={s.actionsGrid}>
          {ACTIONS.map((action) => (
            <TouchableOpacity
              key={action.id}
              style={s.actionCard}
              onPress={() => open(action.route, action.params)}
            >
              <Ionicons name={action.icon} size={24} color="#c9a84c" />
              <Text style={s.actionLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={s.parlayCard} onPress={() => router.push("/(tabs)/market-tools/parlay" as any)}>
          <Text style={s.parlayTitle}>BUILD YOUR PARLAY</Text>
          <Text style={s.parlayBody}>Moneylines · Spreads · Totals · Player Props</Text>
          <Text style={s.parlaySub}>55+ supported sportsbooks. Availability varies by event.</Text>
        </TouchableOpacity>

        <Text style={s.sectionTitle}>Live slates</Text>
        {loading && !refreshing ? (
          <ActivityIndicator color="#c9a84c" />
        ) : displaySlates.length > 0 ? (
          displaySlates.map((slate) => (
            <TouchableOpacity
              key={slate.id}
              style={s.slateCard}
              onPress={() =>
                router.push({
                  pathname: "/(tabs)/optimizer",
                  params: { sport: String(slate.sport || league).toLowerCase(), platform: slate.platform || "draftkings" },
                })
              }
            >
              <View style={s.slateTop}>
                <Text style={s.slateName}>{slate.slate_name}</Text>
                <Text style={s.slateFresh}>{slate.freshness || (slate.is_current ? "CURRENT" : "LISTED")}</Text>
              </View>
              <Text style={s.slateMeta}>
                {slate.sport} · {slate.platform} · {slate.player_count || 0} players · {slate.game_count || 0} games
              </Text>
            </TouchableOpacity>
          ))
        ) : (
          <Text style={s.empty}>
            {slateError || `No live ${league} slates are published right now.`}
          </Text>
        )}

        <Text style={s.sectionTitle}>SB ME Intelligence</Text>
        {intel && intelReady ? (
          <View style={s.intelCard}>
            <View style={s.intelRow}>
              <Text style={s.intelLabel}>Players scored</Text>
              <Text style={s.intelVal}>{intel.player_intelligence_count ?? intel.players?.length ?? "—"}</Text>
            </View>
            <View style={s.intelRow}>
              <Text style={s.intelLabel}>Game environments</Text>
              <Text style={s.intelVal}>{intel.game_count ?? intelGames.length ?? "—"}</Text>
            </View>
            <View style={s.intelRow}>
              <Text style={s.intelLabel}>Top environment</Text>
              <Text style={s.intelVal} numberOfLines={1}>
                {topEnv?.matchup || topEnv?.game || topEnv?.name || "None reported"}
              </Text>
            </View>
            <Text style={s.intelSource}>
              {currentSlate?.slate_name || "Current slate"}
              {intel.provider?.market_context_status
                ? ` · ${intel.provider.market_context_status}`
                : ""}
            </Text>
          </View>
        ) : (
          <Text style={s.empty}>
            {intelError && !/slate not found/i.test(intelError)
              ? intelError
              : "No intelligence summary for the current slate yet."}
          </Text>
        )}

        <View style={s.liveHead}>
          <Text style={s.sectionTitle}>Tonight's board</Text>
          <TouchableOpacity onPress={() => router.push("/(tabs)/market-tools/live-odds")}>
            <Text style={s.link}>All odds</Text>
          </TouchableOpacity>
        </View>
        {displayGames.length > 0 ? (
          displayGames.map((game, i) => {
            const status = gameStatus(game);
            return (
              <View key={game.game_id || i} style={s.gameCard}>
                <View style={s.gameTop}>
                  <Text style={[s.gameWhen, status === "LIVE" && s.live]}>{status}</Text>
                  <Text style={s.gameTeams}>{gameLabel(game)}</Text>
                </View>
                <Text style={s.gameOdds}>
                  ML {fmtOdds(game.moneyline_away)} / {fmtOdds(game.moneyline_home)}
                  {game.spread_line != null ? `  ·  Spr ${game.spread_line}` : ""}
                  {game.total_line != null ? `  ·  Tot ${game.total_line}` : ""}
                </Text>
              </View>
            );
          })
        ) : (
          <Text style={s.empty}>{oddsError || `No ${league} games on the board right now.`}</Text>
        )}
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#000000" },
  scroll: { flex: 1, backgroundColor: "#060b1a" },
  container: { paddingBottom: 36 },
  topBlock: {
    backgroundColor: "#000000",
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#c9a84c33",
  },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  accountBtn: { padding: 4 },
  sportRow: { gap: 8, paddingRight: 8, paddingVertical: 2 },
  sportChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#0a0a0a",
    borderWidth: 1,
    borderColor: "#c9a84c55",
  },
  sportChipOn: { borderColor: "#c9a84c", backgroundColor: "#c9a84c22" },
  sportText: { color: "#c9a84c", fontWeight: "700", fontSize: 12 },
  sportTextOn: { color: "#f0f6fc", fontWeight: "800", fontSize: 12 },
  hero: { justifyContent: "flex-end" },
  heroImg: { width: "100%", height: "100%" },
  heroWash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  heroCopy: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 14, gap: 5 },
  heroKicker: {
    color: "#c9a84c",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 1.4,
    textShadowColor: "rgba(0,0,0,0.8)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  heroTitle: {
    color: "#f0f6fc",
    fontSize: 22,
    fontWeight: "800",
    lineHeight: 26,
    textShadowColor: "rgba(0,0,0,0.85)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
  },
  heroTitleGold: { color: "#c9a84c", fontWeight: "800" },
  heroSub: {
    color: "#c9a84c",
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 16,
    textShadowColor: "rgba(0,0,0,0.85)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  heroCtas: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  heroCta: {
    backgroundColor: "#c9a84c",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
  },
  heroCtaText: { color: "#000000", fontWeight: "900", letterSpacing: 0.6, fontSize: 12 },
  heroCtaGhost: {
    borderWidth: 1,
    borderColor: "#c9a84c",
    backgroundColor: "rgba(0,0,0,0.35)",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
  },
  heroCtaGhostText: { color: "#c9a84c", fontWeight: "800", letterSpacing: 0.6, fontSize: 12 },
  body: { padding: 20, gap: 14, backgroundColor: "#060b1a" },
  planCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#c9a84c44",
  },
  planTop: { flexDirection: "row", alignItems: "center", gap: 8 },
  planName: { color: "#c9a84c", fontWeight: "800", fontSize: 15, flex: 1 },
  planLimit: { color: "#f0f6fc", fontSize: 12, fontWeight: "700" },
  planCopy: { color: "#94a3b8", fontSize: 12, marginTop: 6, lineHeight: 18 },
  statusRow: { flexDirection: "row", gap: 8 },
  statusChip: {
    flex: 1,
    backgroundColor: "#0a0f24",
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  statusVal: { color: "#f0f6fc", fontSize: 18, fontWeight: "800" },
  statusLbl: { color: "#64748b", fontSize: 11, marginTop: 2 },
  sectionTitle: { fontSize: 13, fontWeight: "800", color: "#c9a84c", letterSpacing: 1, textTransform: "uppercase" },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  actionCard: {
    width: "31%",
    flexGrow: 1,
    backgroundColor: "#0a0f24",
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: "#1e293b",
    minHeight: 88,
    justifyContent: "space-between",
  },
  actionLabel: { color: "#f0f6fc", fontSize: 12, fontWeight: "700", lineHeight: 16 },
  parlayCard: {
    backgroundColor: "#14110a",
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#c9a84c55",
  },
  parlayTitle: { color: "#c9a84c", fontWeight: "900", letterSpacing: 1 },
  parlayBody: { color: "#f0f6fc", marginTop: 6, fontSize: 13 },
  parlaySub: { color: "#94a3b8", marginTop: 4, fontSize: 12 },
  slateCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  slateTop: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  slateName: { color: "#f0f6fc", fontWeight: "700", flex: 1 },
  slateFresh: { color: "#c9a84c", fontSize: 11, fontWeight: "800" },
  slateMeta: { color: "#94a3b8", fontSize: 12, marginTop: 4 },
  intelCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
    gap: 10,
  },
  intelRow: { flexDirection: "row", justifyContent: "space-between", gap: 12 },
  intelLabel: { color: "#94a3b8", fontSize: 13 },
  intelVal: { color: "#f0f6fc", fontWeight: "700", fontSize: 13, flexShrink: 1, textAlign: "right" },
  intelSource: { color: "#64748b", fontSize: 11 },
  liveHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  link: { color: "#c9a84c", fontWeight: "700", fontSize: 13 },
  gameCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  gameTop: { flexDirection: "row", gap: 10, alignItems: "center" },
  gameWhen: { color: "#64748b", fontSize: 11, fontWeight: "800", width: 64 },
  live: { color: "#ef4444" },
  gameTeams: { color: "#f0f6fc", fontWeight: "700", flex: 1 },
  gameOdds: { color: "#94a3b8", fontSize: 12, marginTop: 4 },
  empty: { color: "#64748b", fontSize: 13, lineHeight: 18 },
});
