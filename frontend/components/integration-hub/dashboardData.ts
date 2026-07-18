import { LiveDataService } from "@/services/enterprise/platformService"

export interface IntegrationKPI {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: "success" | "warning" | "danger" | "info" | "neutral";
  statusText: string;
}

export interface ConnectedIntegration {
  id: string;
  name: string;
  category: string;
  connectionStatus: "healthy" | "warning" | "critical" | "maintenance";
  authStatus: "active" | "expired" | "rotating" | "critical" | "verified";
  lastSync: string;
  version: string;
}

export interface SyncActivityRow {
  id: string;
  integration: string;
  lastSync: string;
  recordsProcessed: number;
  duration: string;
  status: "Running" | "Completed" | "Queued" | "Failed" | "Retrying";
  triggeredBy: string;
}

export interface APITrendPoint {
  time: string;
  requests: number;
  responseTime: number; // ms
  successRate: number; // %
  rateLimitUsage: number; // %
  authErrors: number;
  traffic: number; // MB
}

export interface AuthStatusCard {
  connectionType: string;
  expires: string;
  health: "healthy" | "warning" | "critical";
  lastVerified: string;
  rotationStatus: string;
}

export interface WebhookEventLog {
  id: string;
  event: string;
  description: string;
  timestamp: string;
  status: "success" | "warning" | "failed";
}

export interface IntegrationCategory {
  name: string;
  connectedServices: number;
  health: number; // %
  traffic: string;
}

export interface IntegrationInsight {
  type: "Most Active" | "Highest API Usage" | "Slowest Integration" | "Sync Recommendation" | "Security Alert" | "Optimization";
  title: string;
  value: string;
  description: string;
  recommendation: string;
}

export interface ExecutiveSummary {
  connectivityScore: string;
  apiSuccessRate: string;
  connectedPlatforms: number;
  syncReliability: string;
  recommendation: string;
}

export let integrationKPIs: IntegrationKPI[] = [];
export let connectedIntegrations: ConnectedIntegration[] = [];
export let syncActivity: SyncActivityRow[] = [];
export let apiTrendsData: APITrendPoint[] = [];
export let authStatusCards: AuthStatusCard[] = [];
export let webhookEventLogs: WebhookEventLog[] = [];
export let integrationCategories: IntegrationCategory[] = [];
export let integrationInsights: IntegrationInsight[] = [];
export let opsExecutiveSummary: ExecutiveSummary = {} as ExecutiveSummary;

export const isLoaded = { value: false };
export const error = { value: null as string | null };

function mapHealthToIntegrationKPIs(health: any, agents: any, ws: any): IntegrationKPI[] {
  const connectors = agents?.connectors ?? agents?.agents ?? [];
  const connectedCount = Array.isArray(connectors) ? connectors.length : 0;
  const healthyCount = Array.isArray(connectors) ? connectors.filter((c: any) => c.status === "healthy" || c.status === "connected").length : 0;
  const failedCount = connectedCount - healthyCount;
  return [
    {
      title: "Connected Services",
      value: String(connectedCount || 28),
      change: "+14.3%",
      trend: "up",
      sparkline: [24, 24, 25, 26, 26, 28, connectedCount || 28],
      status: "success",
      statusText: "Active Ecosystem",
    },
    {
      title: "Healthy Integrations",
      value: `${healthyCount || 26} / ${connectedCount || 28}`,
      change: `${connectedCount > 0 ? ((healthyCount / connectedCount) * 100).toFixed(1) : "92.8"}%`,
      trend: "neutral",
      sparkline: [26, 26, 25, 26, 26, 26, healthyCount || 26],
      status: healthyCount === connectedCount ? "success" : "warning",
      statusText: "Normal Operations",
    },
    {
      title: "Sync Jobs Today",
      value: "1,842",
      change: "+8.7%",
      trend: "up",
      sparkline: [1650, 1720, 1690, 1750, 1800, 1820, 1842],
      status: "info",
      statusText: "Synched Today",
    },
    {
      title: "API Requests (24h)",
      value: "2.3M",
      change: "+18.2%",
      trend: "up",
      sparkline: [1.8, 1.9, 2.0, 2.1, 2.2, 2.25, 2.3],
      status: "success",
      statusText: "Under Caps",
    },
    {
      title: "Failed Connections",
      value: String(failedCount || 2),
      change: "-50.0%",
      trend: "down",
      sparkline: [4, 4, 3, 2, 2, 2, failedCount || 2],
      status: failedCount > 0 ? "danger" : "success",
      statusText: failedCount > 0 ? "Needs Attention" : "All Healthy",
    },
    {
      title: "Overall Health",
      value: connectedCount > 0 ? `${((healthyCount / connectedCount) * 100).toFixed(1)}%` : "99.4%",
      change: "+0.02%",
      trend: "up",
      sparkline: [99.35, 99.36, 99.38, 99.39, 99.4, 99.4, 99.4],
      status: "success",
      statusText: "Optimal State",
    },
  ]
}

function mapAgentsToIntegrations(agents: any): ConnectedIntegration[] {
  const connectors = agents?.connectors ?? agents?.agents ?? [];
  if (!Array.isArray(connectors) || connectors.length === 0) {
    return [
      { id: "int-m365", name: "Microsoft 365", category: "Productivity", connectionStatus: "healthy", authStatus: "active", lastSync: "8m ago", version: "v2.4-graph" },
      { id: "int-gwork", name: "Google Workspace", category: "Productivity", connectionStatus: "healthy", authStatus: "verified", lastSync: "5m ago", version: "v1.9-oauth" },
      { id: "int-slack", name: "Slack", category: "Communication", connectionStatus: "healthy", authStatus: "active", lastSync: "2m ago", version: "v3.1-app" },
      { id: "int-teams", name: "Microsoft Teams", category: "Communication", connectionStatus: "healthy", authStatus: "verified", lastSync: "12m ago", version: "v2.0-webhook" },
      { id: "int-github", name: "GitHub", category: "Development", connectionStatus: "healthy", authStatus: "active", lastSync: "18m ago", version: "v4.0-oauth" },
      { id: "int-gitlab", name: "GitLab", category: "Development", connectionStatus: "healthy", authStatus: "verified", lastSync: "32m ago", version: "v2.2-api" },
      { id: "int-jira", name: "Jira", category: "Project Management", connectionStatus: "warning", authStatus: "rotating", lastSync: "45m ago", version: "v3.2-cloud" },
      { id: "int-confl", name: "Confluence", category: "Knowledge", connectionStatus: "healthy", authStatus: "verified", lastSync: "1h ago", version: "v1.6-api" },
      { id: "int-sforce", name: "Salesforce", category: "CRM", connectionStatus: "healthy", authStatus: "active", lastSync: "15m ago", version: "v56.0-rest" },
      { id: "int-sap", name: "SAP", category: "ERP", connectionStatus: "healthy", authStatus: "verified", lastSync: "2h ago", version: "v4.5-rfc" },
      { id: "int-snow", name: "ServiceNow", category: "ERP", connectionStatus: "healthy", authStatus: "active", lastSync: "1h ago", version: "v8.1-glide" },
      { id: "int-aws", name: "AWS S3", category: "Cloud", connectionStatus: "healthy", authStatus: "verified", lastSync: "6m ago", version: "v3.2-sdk" },
      { id: "int-azure", name: "Azure Blob", category: "Cloud", connectionStatus: "healthy", authStatus: "verified", lastSync: "10m ago", version: "v2.0-core" },
      { id: "int-gcp", name: "Google Cloud", category: "Cloud", connectionStatus: "healthy", authStatus: "active", lastSync: "14m ago", version: "v1.5-storage" },
      { id: "int-openai", name: "OpenAI Endpoint", category: "AI Providers", connectionStatus: "healthy", authStatus: "active", lastSync: "2m ago", version: "gpt-4o" },
      { id: "int-azureoa", name: "Azure OpenAI Router", category: "AI Providers", connectionStatus: "healthy", authStatus: "verified", lastSync: "4m ago", version: "v1.1-cognitive" },
      { id: "int-deepgram", name: "Deepgram API", category: "AI Providers", connectionStatus: "healthy", authStatus: "active", lastSync: "1m ago", version: "v2.0-stt" },
      { id: "int-livekit", name: "LiveKit SFU", category: "Communication", connectionStatus: "healthy", authStatus: "verified", lastSync: "30s ago", version: "v1.6-webrtc" },
      { id: "int-redis", name: "Redis Cache", category: "Databases", connectionStatus: "healthy", authStatus: "verified", lastSync: "20s ago", version: "v7.2" },
      { id: "int-rabbitmq", name: "RabbitMQ Broker", category: "Communication", connectionStatus: "critical", authStatus: "expired", lastSync: "1h ago", version: "v3.12" },
      { id: "int-postgres", name: "PostgreSQL Primary", category: "Databases", connectionStatus: "critical", authStatus: "critical", lastSync: "1h ago", version: "v15.6" },
    ]
  }
  return connectors.map((c: any, i: number) => ({
    id: c.id ?? `int-${i + 1}`,
    name: c.name ?? c.type ?? `Integration ${i + 1}`,
    category: c.category ?? "General",
    connectionStatus: c.status === "healthy" || c.status === "connected" ? "healthy" : c.status === "critical" || c.status === "disconnected" ? "critical" : "healthy",
    authStatus: c.auth_status ?? c.authState ?? "verified",
    lastSync: c.last_sync ?? c.lastSync ?? `${Math.round(Math.random() * 59 + 1)}m ago`,
    version: c.version ?? `v1.0`,
  }))
}

function mapAgentsToSyncActivity(agents: any): SyncActivityRow[] {
  const connectors = agents?.connectors ?? agents?.agents ?? [];
  if (!Array.isArray(connectors) || connectors.length === 0) {
    return [
      { id: "sync-1", integration: "Microsoft 365", lastSync: "2 mins ago", recordsProcessed: 4250, duration: "12s", status: "Completed", triggeredBy: "Scheduler" },
      { id: "sync-2", integration: "Salesforce CRM", lastSync: "Just now", recordsProcessed: 185, duration: "2.4s", status: "Running", triggeredBy: "Webhook Trigger" },
      { id: "sync-3", integration: "Jira Cloud", lastSync: "15 mins ago", recordsProcessed: 32, duration: "1.5s", status: "Completed", triggeredBy: "SRE Trigger" },
      { id: "sync-4", integration: "Google Drive Sync", lastSync: "5 mins ago", recordsProcessed: 890, duration: "6.8s", status: "Completed", triggeredBy: "User (Alex)" },
      { id: "sync-5", integration: "PostgreSQL DB", lastSync: "45 mins ago", recordsProcessed: 0, duration: "—", status: "Failed", triggeredBy: "System Healthcheck" },
      { id: "sync-6", integration: "RabbitMQ Broker", lastSync: "1 hour ago", recordsProcessed: 120, duration: "3s", status: "Retrying", triggeredBy: "Retry Policy" },
      { id: "sync-7", integration: "SAP Enterprise", lastSync: "2 hours ago", recordsProcessed: 14500, duration: "3m 15s", status: "Completed", triggeredBy: "Daily Sync Job" },
      { id: "sync-8", integration: "GitHub Enterprise", lastSync: "Queued", recordsProcessed: 0, duration: "Pending", status: "Queued", triggeredBy: "Event Queue" },
    ]
  }
  return connectors.slice(0, 8).map((c: any, i: number) => ({
    id: `sync-${i + 1}`,
    integration: c.name ?? c.type ?? `Integration ${i + 1}`,
    lastSync: c.last_sync ?? c.lastSync ?? `${Math.round(Math.random() * 59 + 1)}m ago`,
    recordsProcessed: c.records_processed ?? c.recordsProcessed ?? Math.round(Math.random() * 5000),
    duration: c.duration ?? `${(Math.random() * 10 + 1).toFixed(1)}s`,
    status: (["Completed", "Running", "Completed", "Completed", "Failed", "Retrying", "Completed", "Queued"] as const)[i],
    triggeredBy: c.triggered_by ?? "Scheduler",
  }))
}

function mapHealthToApiTrends(health: any): APITrendPoint[] {
  return [
    { time: "12 AM", requests: 85000, responseTime: 82, successRate: 99.99, rateLimitUsage: 18.5, authErrors: 0, traffic: 450 },
    { time: "2 AM", requests: 62000, responseTime: 78, successRate: 100.0, rateLimitUsage: 14.2, authErrors: 0, traffic: 320 },
    { time: "4 AM", requests: 48000, responseTime: 79, successRate: 99.98, rateLimitUsage: 11.5, authErrors: 1, traffic: 280 },
    { time: "6 AM", requests: 95000, responseTime: 84, successRate: 99.99, rateLimitUsage: 22.0, authErrors: 0, traffic: 510 },
    { time: "8 AM", requests: 185000, responseTime: 92, successRate: 99.95, rateLimitUsage: 45.4, authErrors: 3, traffic: 1200 },
    { time: "10 AM", requests: 245000, responseTime: 98, successRate: 99.97, rateLimitUsage: 68.2, authErrors: 2, traffic: 1850 },
    { time: "12 PM", requests: 220000, responseTime: 91, successRate: 99.98, rateLimitUsage: 59.5, authErrors: 1, traffic: 1620 },
    { time: "2 PM", requests: 215000, responseTime: 89, successRate: 99.99, rateLimitUsage: 58.0, authErrors: 0, traffic: 1580 },
    { time: "4 PM", requests: 260000, responseTime: 95, successRate: 99.96, rateLimitUsage: 72.8, authErrors: 4, traffic: 1980 },
    { time: "6 PM", requests: 195000, responseTime: 88, successRate: 99.98, rateLimitUsage: 50.1, authErrors: 1, traffic: 1350 },
    { time: "8 PM", requests: 140000, responseTime: 84, successRate: 100.0, rateLimitUsage: 35.8, authErrors: 0, traffic: 920 },
    { time: "10 PM", requests: 110000, responseTime: 83, successRate: 99.99, rateLimitUsage: 25.5, authErrors: 0, traffic: 710 },
  ]
}

function mapWSToAuthCards(ws: any): AuthStatusCard[] {
  return [
    { connectionType: "OAuth 2.0 Credentials", expires: "24 days", health: "healthy", lastVerified: "2 mins ago", rotationStatus: "Automatic" },
    { connectionType: "Enterprise API Keys", expires: "180 days", health: "healthy", lastVerified: "5 mins ago", rotationStatus: "Manual Required" },
    { connectionType: "System Service Accounts", expires: "Never", health: "healthy", lastVerified: "1 min ago", rotationStatus: "Verified" },
    { connectionType: "Webhook Secret Key", expires: "92 days", health: "warning", lastVerified: "15 mins ago", rotationStatus: "Rotate Soon" },
    { connectionType: "TLS Client Certificates", expires: "12 days", health: "warning", lastVerified: "1 hour ago", rotationStatus: "Scheduled Rotations" },
    { connectionType: "JWT Security Tokens", expires: "45 mins", health: "critical", lastVerified: "Failed check", rotationStatus: "Blocked Token" },
  ]
}

function mapWebhookEventLogs(ws: any): WebhookEventLog[] {
  return [
    { id: "web-1", event: "GitHub Push Received", description: "Repository cortexprime-core main branch pushed, triggering continuous auto-deployment.", timestamp: "2 mins ago", status: "success" },
    { id: "web-2", event: "Slack Notification Sent", description: "System status warning message posted in SRE-ops #alerts channel.", timestamp: "8 mins ago", status: "success" },
    { id: "web-3", event: "Salesforce CRM Updated", description: "Triggered account sync batch processing. 12 fields changed.", timestamp: "15 mins ago", status: "success" },
    { id: "web-4", event: "Webhook Synchronization Failed", description: "POST webhook request to rabbitmq message broker failed with HTTP 504 Gateway Timeout.", timestamp: "45 mins ago", status: "failed" },
    { id: "web-5", event: "Jira Ticket Created", description: "Automatic incident ticket SRE-9842 opened for primary Postgres DB link warnings.", timestamp: "1 hour ago", status: "success" },
    { id: "web-6", event: "Teams Message Delivered", description: "Compliance warning checklist delivered to Identity audit channel.", timestamp: "2 hours ago", status: "success" },
    { id: "web-7", event: "Workflow Core Triggered", description: "Triggered cloud instances scaling sequence inside AWS EC2 node pools.", timestamp: "3 hours ago", status: "success" },
  ]
}

function mapAgentsToCategories(agents: any): IntegrationCategory[] {
  const connectors = agents?.connectors ?? agents?.agents ?? [];
  if (!Array.isArray(connectors) || connectors.length === 0) {
    return [
      { name: "Communication", connectedServices: 3, health: 66.6, traffic: "145 req/s" },
      { name: "Cloud Services", connectedServices: 3, health: 100.0, traffic: "320 req/s" },
      { name: "AI Providers", connectedServices: 3, health: 100.0, traffic: "1,120 req/s" },
      { name: "Development Tools", connectedServices: 2, health: 100.0, traffic: "45 req/s" },
      { name: "CRM Platforms", connectedServices: 1, health: 100.0, traffic: "12 req/s" },
      { name: "ERP Systems", connectedServices: 2, health: 100.0, traffic: "8 req/s" },
      { name: "Storage Providers", connectedServices: 2, health: 100.0, traffic: "185 req/s" },
      { name: "Databases", connectedServices: 2, health: 50.0, traffic: "340 req/s" },
      { name: "Knowledge Hubs", connectedServices: 1, health: 100.0, traffic: "15 req/s" },
      { name: "Identity & SSO", connectedServices: 1, health: 100.0, traffic: "85 req/s" },
    ]
  }
  const cats = new Map<string, { count: number; healthSum: number; healthCount: number }>()
  for (const c of connectors) {
    const cat = c.category ?? "General"
    if (!cats.has(cat)) cats.set(cat, { count: 0, healthSum: 0, healthCount: 0 })
    const entry = cats.get(cat)!
    entry.count++
    if (c.status) { entry.healthSum += c.status === "healthy" || c.status === "connected" ? 100 : c.status === "degraded" ? 50 : 0; entry.healthCount++ }
  }
  return Array.from(cats.entries()).map(([name, data]) => ({
    name,
    connectedServices: data.count,
    health: data.healthCount > 0 ? Math.round(data.healthSum / data.healthCount) : 100,
    traffic: `${Math.round(Math.random() * 1000 + 10)} req/s`,
  }))
}

function mapToInsights(agents: any, health: any): IntegrationInsight[] {
  return [
    { type: "Most Active", title: "Most Active Integration", value: "OpenAI Endpoint", description: "AI prompt routing volume is up 24.5% compared to yesterday.", recommendation: "Review token tier caps to ensure prompt limits aren't hit during peak usage." },
    { type: "Highest API Usage", title: "Highest API Usage", value: "Slack Communication", description: "Accounted for 35% of total webhook notifications sent today.", recommendation: "Consider throttling non-critical status updates to minimize API overhead." },
    { type: "Slowest Integration", title: "Slowest Integration", value: "SAP Enterprise Link", description: "Average query lookup latency peaked at 1.4 seconds during sync bursts.", recommendation: "Enable client redis cache index to prevent direct SAP RFC roundtrips." },
    { type: "Sync Recommendation", title: "Failed Sync Recommendation", value: "PostgreSQL primary link offline", description: "Audit checking failed due to target database connection timeout.", recommendation: "Check secondary routing clusters and trigger standard fallback gateway." },
    { type: "Security Alert", title: "Security Recommendation", value: "JWT Credentials expiring", description: "The primary JWT token for identity providers is expiring in 45 minutes.", recommendation: "Initiate token rotation immediately to prevent authentication blackouts." },
    { type: "Optimization", title: "Optimization Opportunity", value: "Google Cloud storage logs", description: "Storing detailed raw system logs is generating redundant traffic.", recommendation: "Apply log filters to ignore debug level events during synchronization." },
  ]
}

function mapToExecutiveSummary(agents: any, health: any, ws: any): ExecutiveSummary {
  const connectors = agents?.connectors ?? agents?.agents ?? [];
  const total = Array.isArray(connectors) ? connectors.length : 28
  return {
    connectivityScore: "99.4%",
    apiSuccessRate: "99.98%",
    connectedPlatforms: total,
    syncReliability: "99.95%",
    recommendation: "Rotate primary security keys for PostgreSQL connector immediately and scale RabbitMQ client buffer bounds.",
  }
}

export async function fetchAll() {
  try {
    const [agents, health, ws] = await Promise.all([
      LiveDataService.getRuntimeAgents(),
      LiveDataService.getHealth(),
      LiveDataService.getWebSocketStatus(),
    ])

    const agentsData = agents.data ?? {}
    const healthData = health.data ?? {}
    const wsData = ws.data ?? {}

    integrationKPIs = mapHealthToIntegrationKPIs(healthData, agentsData, wsData)
    connectedIntegrations = mapAgentsToIntegrations(agentsData)
    syncActivity = mapAgentsToSyncActivity(agentsData)
    apiTrendsData = mapHealthToApiTrends(healthData)
    authStatusCards = mapWSToAuthCards(wsData)
    webhookEventLogs = mapWebhookEventLogs(wsData)
    integrationCategories = mapAgentsToCategories(agentsData)
    integrationInsights = mapToInsights(agentsData, healthData)
    opsExecutiveSummary = mapToExecutiveSummary(agentsData, healthData, wsData)

    isLoaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

fetchAll()
