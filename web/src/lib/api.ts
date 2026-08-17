import { getApiBaseUrl } from "./api-base-url";

const API_BASE_URL = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const TOKEN_KEY = "sbme_dfs_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export interface ApiResponse<T> {
  status: string;
  data: T;
  metadata: {
    data_source: 'live' | 'cached';
    last_updated: string;
    api_version: string;
    environment: string;
  };
}

export interface PlayerProjection {
  id: number;
  name: string;
  team: string;
  slate_id: number;
  player_id: number;
  salary: number;
  roster_position: string;
  projected_fp: number;
  ceiling: number;
  floor: number;
  ownership: number;
  leverage: number;
  value: number;
}

export interface LineupResponse {
  total_salary: number;
  projected_score: number;
  players: PlayerProjection[];
}

export interface AdminSummary {
  mrr: string;
  active_subscribers: string;
  churn_rate: string;
  trial_conversions: string;
  mrr_trend: string;
  subs_trend: string;
}

export interface PerformanceStats {
  total_roi: string;
  win_rate: string;
  ave_error: string;
  accuracy: Record<string, number>;
}

export interface SportMatchup {
  time: string;
  home_team: string;
  away_team: string;
  is_live?: boolean;
  odds: Array<{ val: string; price: string }>;
}

export interface SystemStatus {
  provider_name: string;
  is_healthy: boolean;
  last_sync_time: string;
  last_sync_result: string;
  data_source_mode: string;
}

export interface SubscriptionStatus {
  plan: string;
  status: string;
  next_billing: string | null;
  is_canceled?: boolean;
  has_access: boolean;
}

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };
  // Attach auth token if available
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error ${res.status}: ${errorBody}`);
  }
  return await res.json();
}

/** DFS API */
export async function fetchProjections(slateId: number = 1): Promise<ApiResponse<PlayerProjection[]>> {
  return apiFetch<PlayerProjection[]>(`/projections/${slateId}`);
}

export async function runOptimizer(slateId: number = 1, settings: any): Promise<ApiResponse<LineupResponse[]>> {
  return apiFetch<LineupResponse[]>(`/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      slate_id: slateId,
      settings: settings
    })
  });
}

/** Admin API */
export async function fetchAdminSummary(): Promise<ApiResponse<AdminSummary>> {
  return apiFetch<AdminSummary>(`/admin/summary`);
}

export async function fetchRevenueTrends(): Promise<ApiResponse<number[]>> {
  return apiFetch<number[]>(`/admin/revenue-trends`);
}

export async function fetchAdminEvents(): Promise<ApiResponse<any[]>> {
  return apiFetch<any[]>(`/admin/events`);
}

export async function fetchPlanDistribution(): Promise<ApiResponse<Record<string, number>>> {
  return apiFetch<Record<string, number>>(`/admin/distribution`);
}

/** Stats/Performance API */
export async function fetchPerformanceStats(): Promise<ApiResponse<PerformanceStats>> {
  return apiFetch<PerformanceStats>(`/stats/performance`);
}

/** Sports API */
export async function fetchSportsLobby(sport: string = "NFL"): Promise<ApiResponse<SportMatchup[]>> {
  return apiFetch<SportMatchup[]>(`/sports/lobby?sport=${sport}`);
}

/** Health/System API */
export async function fetchSystemStatus(): Promise<ApiResponse<SystemStatus[]>> {
  return apiFetch<SystemStatus[]>(`/admin/health`); // Implemented in admin.py
}

export async function triggerManualSync(): Promise<ApiResponse<{ task_id: string, status: string }>> {
  return apiFetch<{ task_id: string, status: string }>(`/admin/sync/trigger`, {
    method: "POST"
  });
}

/** Billing API */
export async function fetchSubscriptionStatus(): Promise<ApiResponse<SubscriptionStatus>> {
  return apiFetch<SubscriptionStatus>(`/billing/status`);
}

export async function createCheckout(plan: string): Promise<ApiResponse<{ url: string }>> {
  return apiFetch<{ url: string }>(`/billing/checkout`, {
    method: "POST",
    body: JSON.stringify({ plan }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function createPortal(): Promise<ApiResponse<{ url: string }>> {
  return apiFetch<{ url: string }>(`/billing/portal`);
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL.slice(0, -'/api'.length)}/health`);
    return res.ok;
  } catch (error) {
    return false;
  }
}


// ── Authentication API ──────────────────────────────────────

export interface AuthTokens {
  access_token: string;
  token_type: string;
  plan: string;
  email: string;
  role: string;
}

export async function register(email: string, password: string): Promise<AuthTokens> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail || "Registration failed");
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthTokens> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Invalid credentials" }));
    throw new Error(err.detail || "Invalid credentials");
  }
  return res.json();
}

export async function fetchCurrentUser(): Promise<ApiResponse<any>> {
  return apiFetch<any>("/auth/me", {
    headers: { Authorization: `Bearer ${getStoredToken()}` },
  });
}

// ── Native DFS Slate API ──────────────────────────────────────

export interface DFSSlateSummary {
  id: number;
  platform: string;
  sport: string;
  slate_name: string;
  start_time: string | null;
  slate_date: string | null;
  is_current: boolean;
  player_count: number;
  status: string;
  data_source: string;
}

export interface DFSSlatePlayer {
  player_id: string;
  name: string;
  team: string;
  opponent: string | null;
  position: string;
  eligible_positions: string[];
  salary: number;
  game_info: string | null;
  mapping_status: string;
}

export interface DFSSlateDetail {
  id: number;
  platform: string;
  sport: string;
  slate_name: string;
  start_time: string | null;
  player_count: number;
  data_source: string;
  players: DFSSlatePlayer[];
}

export async function fetchDFSSlates(platform?: string, sport?: string): Promise<ApiResponse<DFSSlateSummary[]>> {
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (sport) params.set("sport", sport);
  const qs = params.toString();
  return apiFetch<DFSSlateSummary[]>(`/dfs/slates${qs ? `?${qs}` : ""}`);
}

export async function fetchDFSSlate(slateId: number): Promise<ApiResponse<DFSSlateDetail>> {
  return apiFetch<DFSSlateDetail>(`/dfs/slates/${slateId}`);
}

// ── Lineup History API ──────────────────────────────────────

export interface LineupHistoryEntry {
  id: number;
  sport: string;
  platform: string;
  slate_id: number;
  strategy: string;
  lineup_count: number;
  player_count: number;
  total_salary: number;
  projected_score: number;
  data_mode: string;
  created_at: string;
  lineups: LineupHistoryLineup[];
}

export interface LineupHistoryLineup {
  total_salary: number;
  projected_score: number;
  remaining_salary: number;
  players: LineupHistoryPlayer[];
}

export interface LineupHistoryPlayer {
  id: number;
  name: string;
  team: string;
  roster_slot: string;
  salary: number;
  projected_fp: number;
}

export async function fetchLineupHistory(): Promise<ApiResponse<LineupHistoryEntry[]>> {
  return apiFetch<LineupHistoryEntry[]>("/lineups/history");
}

// ── Intelligence API ──────────────────────────────────────

export interface IntelligenceSlatePlayer {
  id: number;
  player_name: string;
  team: string;
  position: string;
  salary: number;
  projected_fp: number | null;
  fantasy_market_line: number | null;
  edge_pct: number | null;
  props_count: number;
}

export async function fetchSlateIntelligence(slateId: number): Promise<ApiResponse<any>> {
  return apiFetch<any>(`/intelligence/slate/${slateId}`);
}

// ── SB ME Data Hub / Sims / Top Stacks API ──────────────────────

export interface CanonicalPlayer {
  id: string;
  name: string;
  position: string;
  roster_position: string;
  salary: number;
  team: string;
  opponent: string | null;
  eligible_positions: string[];
  projected_fp: number;
  projection_source: string;
  projection_confidence: number;
  value: number;
  sbme_ownership_pct: number | null;
  leverage: number | null;
  ceiling: number | null;
  floor: number | null;
  mapping_status: string;
}

export async function fetchDataHubSlate(slateId: number, platform: string): Promise<ApiResponse<{ players: CanonicalPlayer[]; metadata: any }>> {
  return apiFetch<any>(`/data-hub/slate?slate_id=${slateId}&platform=${platform}`);
}

export interface SimPlayer {
  id: string;
  name: string;
  position: string;
  team: string;
  salary: number;
  sim_score: number;
  optimal_pct: number;
  top1_pct: number;
  ownership_pct: number;
  leverage: number;
}

export interface SimLineupResult {
  lineup_index: number;
  sim_score: number;
  cash_pct: number | null;
  win_pct: number | null;
  sim_roi: number | null;
  players: any[];
}

export async function runSims(body: { slate_id: number; platform: string; n_sims: number; lineups?: any[] }): Promise<ApiResponse<{ players: SimPlayer[]; lineups: SimLineupResult[] | null; metadata: any }>> {
  return apiFetch<any>(`/sims/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface StackPlayer {
  id: string;
  name: string;
  position: string;
  salary: number;
  projected_fp: number;
  ownership_pct: number | null;
  leverage: number | null;
}

export interface TopStack {
  team: string;
  opponent: string;
  stack_size: number;
  implied_total: number | null;
  sb_projection: number;
  stack_ownership: number;
  optimal_stack_pct: number | null;
  leverage: number;
  value: number;
  rating: string;
  salary: number;
  players: StackPlayer[];
}

export async function fetchTopStacks(slateId: number, platform: string): Promise<ApiResponse<{ stacks: TopStack[]; metadata: any }>> {
  return apiFetch<any>(`/top-stacks?slate_id=${slateId}&platform=${platform}`);
}
