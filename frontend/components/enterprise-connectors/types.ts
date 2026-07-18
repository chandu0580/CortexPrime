export type ConnectorStatus =
  | "connected"
  | "disconnected"
  | "healthy"
  | "needs_configuration"
  | "connection_error";

export type ConnectorId =
  | "github"
  | "jira"
  | "slack"
  | "microsoft-teams"
  | "azure-devops"
  | "servicenow"
  | "confluence"
  | "notion";

export interface ConnectorCapability {
  label: string;
}

export interface ConnectorAuthField {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "email";
  placeholder?: string;
}

export interface ConnectorPermission {
  key: string;
  label: string;
  scope: string;
}

export interface ConnectorStat {
  label: string;
  value: string;
}

export interface Connector {
  id: ConnectorId;
  name: string;
  description: string;
  status: ConnectorStatus;
  capabilities: ConnectorCapability[];
  authFields: ConnectorAuthField[];
  permissions: ConnectorPermission[];
  longDescription: string;
  operations: string[];
  stats?: ConnectorStat[];
  latency?: string | null;
  lastSync?: string | null;
  /** Backend health data */
  health?: Record<string, unknown> | null;
  /** Backend connection state */
  connectionState?: string;
  /** Has stored credentials */
  hasCredentials?: boolean;
  /** Backend latency in ms */
  latencyMs?: number | null;
}

export interface ConnectorSummaryData {
  connected: number | null;
  healthy: number | null;
  pending: number | null;
  lastSync: string | null;
  apiCallsToday?: number | null;
  avgLatency?: string | null;
  errorsToday?: number | null;
  total?: number | null;
}
