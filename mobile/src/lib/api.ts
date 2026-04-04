const API_BASE_URL = "http://localhost:8000/api";

export interface ApiResponse<T> {
  status: string;
  data: T;
  metadata: {
    data_source: 'live' | 'cached' | 'demo';
    last_updated: string;
    api_version: string;
    environment: string;
  };
}

export interface PlayerProjection {
  id: number;
  name: string;
  team: string;
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
  is_boosted?: boolean;
  odds: Array<{ val: string; price: string }>;
}

export interface SystemStatus {
  provider_name: string;
  is_healthy: boolean;
  last_sync_time: string;
  last_sync_result: string;
  data_source_mode: string;
}

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return await res.json();
}

export async function fetchProjections(slateId: number = 1): Promise<ApiResponse<PlayerProjection[]>> {
  return apiFetch<PlayerProjection[]>(`/projections/${slateId}`);
}

export async function fetchAdminSummary(): Promise<ApiResponse<AdminSummary>> {
  return apiFetch<AdminSummary>(`/admin/summary`);
}

export async function fetchPerformanceStats(): Promise<ApiResponse<PerformanceStats>> {
  return apiFetch<PerformanceStats>(`/stats/performance`);
}

export async function fetchSportsLobby(sport: string = "NFL"): Promise<ApiResponse<SportMatchup[]>> {
  return apiFetch<SportMatchup[]>(`/sports/lobby?sport=${sport}`);
}

export async function fetchSystemStatus(): Promise<ApiResponse<SystemStatus[]>> {
  return apiFetch<SystemStatus[]>(`/admin/health`);
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
