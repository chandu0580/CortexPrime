export interface RcaEvidencePod {
  name: string; namespace: string; status: string; restarts: number;
  oom_detected?: boolean; crashloop_detected?: boolean;
}

export interface RcaEvidenceDeployment {
  name: string; namespace: string; status: string; rollout_status: string;
}

export interface RcaEvidenceAlert {
  alert_name: string; severity: string; value?: number; labels?: Record<string, string>;
}

export interface RcaEvidenceLog {
  stream: string; error_count: number; warn_count: number; total_lines: number; log_sample?: string[];
}

export interface RcaEvidenceTrace {
  trace_id: string; service_name: string; error_spans: number; total_spans: number; duration_ms: number; p95_ms: number;
}

export interface RcaEvidenceNetwork {
  source: string; destination: string; reason: string; protocol: string; port: number; namespace: string;
}

export interface RcaHypothesis {
  hypothesis_id: string;
  pattern_id: string;
  description: string;
  root_cause: string;
  category: string;
  matching_event_count: number;
  matching_events: { source: string; type: string; name: string; status: string; timestamp: string }[];
  confidence?: number;
}

export interface RcaImpact {
  affected_services: string[];
  affected_deployments: string[];
  affected_commits: string[];
  affected_prs: string[];
  affected_builds: string[];
  affected_infrastructure: string[];
}

export interface RcaTimelineEntry {
  source: string;
  type: string;
  entity_id: string;
  name: string;
  status: string;
  timestamp: string;
  details?: Record<string, any>;
}

export interface RcaStory {
  story_id: string;
  problem: string;
  story: string;
  story_parts: string[];
  generated_at: string;
  confidence_label: string;
  confidence_score: number;
}

export interface RcaAnalysis {
  analysis_id: string;
  incident_id: string;
  problem: string;
  timestamp: string;
  time_window_hours: number;
  timeline: RcaTimelineEntry[];
  evidence: Record<string, any>;
  hypotheses: RcaHypothesis[];
  top_hypothesis: RcaHypothesis | null;
  impact: RcaImpact;
  recommendation: Record<string, any>;
  recovery_actions: string[];
  story: RcaStory;
  summary: {
    total_events_in_timeline: number;
    error_events: number;
    total_hypotheses: number;
    top_root_cause: string;
    confidence_score: number;
    confidence_label: string;
    affected_services_count: number;
    affected_deployments_count: number;
    affected_builds_count: number;
  };
  correlations: Record<string, any>;
}

export interface RcaIncident {
  incident_id: string;
  analysis_id: string;
  problem: string;
  root_cause: string;
  confidence: number;
  timestamp: string;
}

export interface RcaDashboardStats {
  total_analyses: number;
  total_incidents: number;
  top_root_causes: { cause: string; count: number }[];
  avg_confidence: number;
  recent_analyses: {
    analysis_id: string;
    problem: string;
    root_cause: string;
    confidence: number;
    timestamp: string;
  }[];
}
