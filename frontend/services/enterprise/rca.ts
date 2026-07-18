import { api } from '@/services/api';
import type {
  RcaAnalysis,
  RcaIncident,
  RcaDashboardStats,
  RcaTimelineEntry,
  RcaHypothesis,
  RcaImpact,
} from '@/types/rca';

const BASE = '/api/rca';

export const enterpriseRcaApi = {
  // ---- Analysis ----
  runAnalysis: (params?: { incident_id?: string; problem?: string; hours_back?: number }) =>
    api.post<RcaAnalysis>(`${BASE}/analyze`, params || {}),

  listAnalyses: (limit = 50) =>
    api.get<{ analyses: RcaAnalysis[] }>(`${BASE}/analyses`, { params: { limit } }),

  getAnalysis: (analysisId: string) =>
    api.get<RcaAnalysis>(`${BASE}/analyses/${analysisId}`),

  // ---- Incidents ----
  listIncidents: (limit = 50) =>
    api.get<{ incidents: RcaIncident[] }>(`${BASE}/incidents`, { params: { limit } }),

  getIncident: (incidentId: string) =>
    api.get<RcaIncident>(`${BASE}/incidents/${incidentId}`),

  // ---- Dashboard ----
  getDashboard: () =>
    api.get<RcaDashboardStats>(`${BASE}/dashboard`),

  // ---- Timeline ----
  buildTimeline: (hoursBack = 24) =>
    api.post<{ timeline: RcaTimelineEntry[] }>(`${BASE}/timeline/build`, null, { params: { hours_back: hoursBack } }),

  // ---- Hypotheses ----
  buildHypotheses: (timeline: RcaTimelineEntry[]) =>
    api.post<{ hypotheses: RcaHypothesis[] }>(`${BASE}/hypotheses/build`, timeline),

  rankHypotheses: (hypotheses: RcaHypothesis[], timeline: RcaTimelineEntry[]) =>
    api.post<{ ranked: RcaHypothesis[] }>(`${BASE}/hypotheses/rank`, { hypotheses, timeline }),

  // ---- Impact ----
  analyzeImpact: (timeline: RcaTimelineEntry[]) =>
    api.post<{ impact: RcaImpact }>(`${BASE}/impact/analyze`, timeline),

  // ---- Story ----
  generateStory: (data: {
    problem: string;
    timeline: RcaTimelineEntry[];
    top_hypothesis?: RcaHypothesis | null;
    impact?: RcaImpact;
    confidence?: number;
    evidence_summary?: Record<string, any>;
  }) => api.post<{ story: any }>(`${BASE}/story/generate`, data),

  // ---- Correlations ----
  correlateByTime: (events: RcaTimelineEntry[], timeWindowSeconds = 300) =>
    api.post(`${BASE}/correlate/time`, events, { params: { time_window_seconds: timeWindowSeconds } }),

  correlateByEntity: (events: RcaTimelineEntry[]) =>
    api.post(`${BASE}/correlate/entity`, events),

  // ---- Evidence ----
  collectEvidence: () =>
    api.get(`${BASE}/evidence/collect`),

  // ---- Events ----
  listEvents: () =>
    api.get<{ events: Record<string, string> }>(`${BASE}/events`),
};
