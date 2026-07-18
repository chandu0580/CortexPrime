import { api } from "@/services/api";

export interface ConnectorHealthDetail {
  status: string;
  connector: string;
  name: string;
  authenticated: boolean;
  authentication_type: string;
  latency_ms: number | null;
  version: string | null;
  rate_limits: Record<string, unknown> | null;
  last_sync: string | null;
  available_operations: string[];
  connection_state: string;
  capabilities: string[];
}

export interface ConnectorSummary {
  type: string;
  name: string;
  description: string;
  status: string;
  health: Record<string, unknown>;
  authentication_type: string;
  capabilities: string[];
  operations: string[];
  connection_state: string;
  has_credentials: boolean;
  last_validation: string | null;
  latency_ms: number | null;
  auth_fields?: Array<{
    key: string;
    label: string;
    type: string;
    placeholder?: string;
  }>;
  permissions?: Array<{
    key: string;
    label: string;
    scope: string;
  }>;
  long_description?: string;
}

export interface ConnectorListResponse {
  connectors: ConnectorSummary[];
  total: number;
}

export interface ConnectorTestResponse {
  success: boolean;
  message: string;
  latency_ms: number;
}

export interface ConnectorConnectResponse {
  success: boolean;
  status: string;
  health?: Record<string, unknown>;
  message: string;
  latency_ms: number;
}

export interface ConnectorDisconnectResponse {
  success: boolean;
  message: string;
}

export interface ConnectorRefreshResponse {
  success: boolean;
  health: Record<string, unknown>;
}

export interface ConnectorActivityEvent {
  id: string;
  connector_name: string;
  connector_type: string;
  operation: string;
  resource: string | null;
  resource_id: string | null;
  status: string;
  initiated_by: string | null;
  duration_ms: number | null;
  created_at: string;
  message: string | null;
  metadata: Record<string, unknown> | null;
}

export interface ConnectorActivityResponse {
  activities: ConnectorActivityEvent[];
  total: number;
  page: number;
  page_size: number;
}

export async function listConnectors(): Promise<ConnectorListResponse> {
  return api.get<ConnectorListResponse>("/api/connectors");
}

export async function getConnectorDetail(connectorType: string): Promise<ConnectorSummary> {
  return api.get<ConnectorSummary>(`/api/connectors/${connectorType}`);
}

export async function testConnector(
  connectorType: string,
  credentials: Record<string, string>,
): Promise<ConnectorTestResponse> {
  return api.post<ConnectorTestResponse>(`/api/connectors/${connectorType}/test`, { credentials });
}

export async function connectConnector(
  connectorType: string,
  credentials: Record<string, string>,
): Promise<ConnectorConnectResponse> {
  return api.post<ConnectorConnectResponse>(`/api/connectors/${connectorType}/connect`, { credentials });
}

export async function disconnectConnector(
  connectorType: string,
): Promise<ConnectorDisconnectResponse> {
  return api.post<ConnectorDisconnectResponse>(`/api/connectors/${connectorType}/disconnect`);
}

export async function refreshConnector(
  connectorType: string,
): Promise<ConnectorRefreshResponse> {
  return api.post<ConnectorRefreshResponse>(`/api/connectors/${connectorType}/refresh`);
}

export async function getConnectorHealth(
  connectorType: string,
): Promise<ConnectorHealthDetail> {
  return api.get<ConnectorHealthDetail>(`/api/connectors/${connectorType}/health`);
}

export async function getConnectorActivity(
  connectorType: string,
  page = 1,
  pageSize = 50,
): Promise<ConnectorActivityResponse> {
  return api.get<ConnectorActivityResponse>(
    `/api/connectors/activity?connector_type=${connectorType}&page=${page}&page_size=${pageSize}`,
  );
}
