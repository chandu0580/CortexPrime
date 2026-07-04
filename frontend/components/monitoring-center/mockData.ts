export interface HealthKPICard {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: "success" | "warning" | "danger" | "info" | "neutral";
  statusText: string;
}

export interface ServiceHealthData {
  name: string;
  status: "healthy" | "warning" | "critical" | "maintenance";
  latency: string;
  uptime: string;
  version: string;
}

export interface LiveMetricRow {
  service: string;
  requestsPerSec: number;
  latency: string;
  errorRate: string; // percentage
  availability: string; // percentage
  responseTime: string;
  status: "healthy" | "warning" | "critical";
}

export interface OperationalAlert {
  id: string;
  title: string;
  description: string;
  timestamp: string; // relative
  severity: "critical" | "warning" | "info" | "resolved";
}

export interface DependencyStatusData {
  name: string;
  connection: string;
  latency: string;
  health: "healthy" | "degraded" | "offline";
  version: string;
  lastChecked: string;
}

export interface PerformanceTrendPoint {
  time: string;
  requests: number;
  latency: number; // ms
  errorRate: number; // %
  cpu: number; // %
  memory: number; // %
  network: number; // MB/s
}

export interface SystemActivityEvent {
  id: string;
  event: string;
  description: string;
  timestamp: string;
  type: "deployment" | "restart" | "scale" | "backup" | "healthcheck";
}

// ─── Section 1: KPI CARDS ──────────────────────────────────────────────────
export const platformHealthKPIs: HealthKPICard[] = [
  {
    title: "Platform Health",
    value: "Optimal",
    change: "0 Incidents",
    trend: "neutral",
    sparkline: [100, 100, 100, 100, 100, 100, 100],
    status: "success",
    statusText: "All Operational",
  },
  {
    title: "Overall Availability",
    value: "99.98%",
    change: "+0.02%",
    trend: "up",
    sparkline: [99.95, 99.96, 99.95, 99.97, 99.98, 99.98, 99.98],
    status: "success",
    statusText: "Target Met",
  },
  {
    title: "Running Services",
    value: "12 / 12",
    change: "Fully active",
    trend: "neutral",
    sparkline: [12, 12, 12, 12, 12, 12, 12],
    status: "success",
    statusText: "Healthy Runtimes",
  },
  {
    title: "Active Alerts",
    value: "1",
    change: "-75.0%",
    trend: "down",
    sparkline: [4, 4, 3, 2, 2, 1, 1],
    status: "warning",
    statusText: "1 Warning Active",
  },
  {
    title: "Average Response Time",
    value: "82 ms",
    change: "-11.4%",
    trend: "down",
    sparkline: [95, 92, 90, 86, 84, 83, 82],
    status: "success",
    statusText: "Stable Latency",
  },
  {
    title: "System Uptime",
    value: "18d 6h",
    change: "No Restarts",
    trend: "up",
    sparkline: [12, 13, 14, 15, 16, 17, 18],
    status: "success",
    statusText: "Continuous Run",
  },
];

// ─── Section 2: SYSTEM HEALTH (HERO) ─────────────────────────────────────────
export const servicesHealthData: ServiceHealthData[] = [
  { name: "API Gateway", status: "healthy", latency: "24ms", uptime: "99.99%", version: "v2.5-stable" },
  { name: "Authentication", status: "healthy", latency: "12ms", uptime: "100%", version: "v1.2-auth" },
  { name: "Runtime Engine", status: "healthy", latency: "45ms", uptime: "99.98%", version: "v4.1-pro" },
  { name: "Voice Runtime", status: "warning", latency: "185ms", uptime: "99.65%", version: "v2.4-stream" },
  { name: "Memory Service", status: "healthy", latency: "8ms", uptime: "100%", version: "v3.1-cache" },
  { name: "Research Engine", status: "healthy", latency: "145ms", uptime: "99.85%", version: "v1.8-search" },
  { name: "Browser Runtime", status: "healthy", latency: "380ms", uptime: "99.70%", version: "v3.0-browser" },
  { name: "Computer Use Runtime", status: "healthy", latency: "820ms", uptime: "99.54%", version: "v2.0-desktop" },
  { name: "Replay Engine", status: "healthy", latency: "65ms", uptime: "99.99%", version: "v1.5-replay" },
  { name: "Analytics", status: "healthy", latency: "32ms", uptime: "100%", version: "v2.1-metrics" },
  { name: "Governance", status: "healthy", latency: "18ms", uptime: "99.99%", version: "v1.9-trust" },
  { name: "Monitoring", status: "healthy", latency: "15ms", uptime: "100%", version: "v2.0-status" },
];

// ─── Section 4: LIVE SYSTEM METRICS ──────────────────────────────────────────
export const liveSystemMetrics: LiveMetricRow[] = [
  { service: "API Services", requestsPerSec: 245, latency: "24 ms", errorRate: "0.04%", availability: "99.99%", responseTime: "28 ms", status: "healthy" },
  { service: "Voice Services", requestsPerSec: 42, latency: "185 ms", errorRate: "1.25%", availability: "99.65%", responseTime: "210 ms", status: "warning" },
  { service: "Memory Indexer", requestsPerSec: 185, latency: "8 ms", errorRate: "0.00%", availability: "100.0%", responseTime: "10 ms", status: "healthy" },
  { service: "Research Broker", requestsPerSec: 18, latency: "145 ms", errorRate: "0.20%", availability: "99.85%", responseTime: "165 ms", status: "healthy" },
  { service: "Browser Crawler", requestsPerSec: 11, latency: "380 ms", errorRate: "0.45%", availability: "99.70%", responseTime: "420 ms", status: "healthy" },
  { service: "Computer Use CLI", requestsPerSec: 4, latency: "820 ms", errorRate: "0.85%", availability: "99.54%", responseTime: "910 ms", status: "healthy" },
  { service: "Replay Logger", requestsPerSec: 125, latency: "65 ms", errorRate: "0.01%", availability: "99.99%", responseTime: "72 ms", status: "healthy" },
  { service: "Supervisor Agent", requestsPerSec: 85, latency: "14 ms", errorRate: "0.00%", availability: "100.0%", responseTime: "16 ms", status: "healthy" },
];

// ─── Section 5: ALERTS CENTER ───────────────────────────────────────────────
export const operationalAlerts: OperationalAlert[] = [
  {
    id: "alert-1",
    title: "Voice Runtime Restarted",
    description: "Voice Streamer container restarted automatically after a transient Socket Hang Up error. Service recovered in 4.2s.",
    timestamp: "12 mins ago",
    severity: "warning",
  },
  {
    id: "alert-2",
    title: "High Memory Usage Alert",
    description: "Node worker memory consumption rose above 86% threshold on host cluster node-cortex-03.",
    timestamp: "45 mins ago",
    severity: "resolved",
  },
  {
    id: "alert-3",
    title: "Redis Reconnected",
    description: "System successfully re-established broker link with redis caching cluster after 120ms ping timeout.",
    timestamp: "2 hours ago",
    severity: "info",
  },
  {
    id: "alert-4",
    title: "RabbitMQ Queue Full Warning",
    description: "Memory task execution queue depth surpassed 1,000 requests. Scaling agents to clear lag.",
    timestamp: "4 hours ago",
    severity: "warning",
  },
  {
    id: "alert-5",
    title: "API Gateway Latency Warning",
    description: "Gateway response average peaked at 180ms during active research agent scan burst.",
    timestamp: "8 hours ago",
    severity: "resolved",
  },
  {
    id: "alert-6",
    title: "Database Disk Storage Alert",
    description: "Postgres disk utilization index reached 82% on primary storage block. Initiated cleanup.",
    timestamp: "1 day ago",
    severity: "warning",
  },
];

// ─── Section 6: DEPENDENCY STATUS ────────────────────────────────────────────
export const dependenciesStatus: DependencyStatusData[] = [
  { name: "PostgreSQL", connection: "Connected", latency: "2.4ms", health: "healthy", version: "v15.6-aws", lastChecked: "1 min ago" },
  { name: "Redis", connection: "Connected", latency: "0.8ms", health: "healthy", version: "v7.2-cluster", lastChecked: "2 mins ago" },
  { name: "RabbitMQ", connection: "Connected", latency: "1.5ms", health: "healthy", version: "v3.12-broker", lastChecked: "1 min ago" },
  { name: "LiveKit SFU", connection: "Connected", latency: "42ms", health: "healthy", version: "v1.6-webrtc", lastChecked: "30s ago" },
  { name: "Deepgram API", connection: "Connected", latency: "125ms", health: "healthy", version: "v2.0-stt", lastChecked: "1 min ago" },
  { name: "OpenAI Endpoint", connection: "Connected", latency: "180ms", health: "healthy", version: "gpt-4o-2024-05-13", lastChecked: "3 mins ago" },
  { name: "Azure OpenAI Router", connection: "Connected", latency: "165ms", health: "healthy", version: "gpt-35-turbo-16k", lastChecked: "2 mins ago" },
  { name: "AWS S3 Storage", connection: "Connected", latency: "8.5ms", health: "healthy", version: "s3-bucket-us-east-1", lastChecked: "5 mins ago" },
];

// ─── Section 3 & 7: INFRASTRUCTURE & PERFORMANCE TRENDS ──────────────────────
export const performanceTrendsData: PerformanceTrendPoint[] = [
  { time: "12 AM", requests: 120, latency: 78, errorRate: 0.01, cpu: 42, memory: 58, network: 8.4 },
  { time: "2 AM", requests: 95, latency: 74, errorRate: 0.00, cpu: 35, memory: 56, network: 6.2 },
  { time: "4 AM", requests: 88, latency: 76, errorRate: 0.02, cpu: 32, memory: 56, network: 5.8 },
  { time: "6 AM", requests: 145, latency: 82, errorRate: 0.05, cpu: 48, memory: 61, network: 11.2 },
  { time: "8 AM", requests: 220, latency: 90, errorRate: 0.08, cpu: 65, memory: 68, network: 18.5 },
  { time: "10 AM", requests: 260, latency: 95, errorRate: 0.04, cpu: 74, memory: 72, network: 22.4 },
  { time: "12 PM", requests: 245, latency: 88, errorRate: 0.03, cpu: 71, memory: 74, network: 20.8 },
  { time: "2 PM", requests: 250, latency: 85, errorRate: 0.02, cpu: 70, memory: 75, network: 21.2 },
  { time: "4 PM", requests: 280, latency: 92, errorRate: 0.06, cpu: 78, memory: 78, network: 24.5 },
  { time: "6 PM", requests: 235, latency: 84, errorRate: 0.03, cpu: 66, memory: 76, network: 19.4 },
  { time: "8 PM", requests: 190, latency: 80, errorRate: 0.01, cpu: 52, memory: 70, network: 14.8 },
  { time: "10 PM", requests: 155, latency: 79, errorRate: 0.01, cpu: 45, memory: 65, network: 10.6 },
];

// ─── Section 8: RECENT SYSTEM EVENTS ─────────────────────────────────────────
export const systemActivityEvents: SystemActivityEvent[] = [
  {
    id: "evt-1",
    event: "Deployment Completed Successfully",
    description: "CortexPrime core agent engine version 4.1-pro rolled out successfully to the production kubernetes cluster. Zero downtime.",
    timestamp: "10 mins ago",
    type: "deployment",
  },
  {
    id: "evt-2",
    event: "Voice Service restarted",
    description: "Voice-processing node pod container-v2 restarted under memory constraints override rules.",
    timestamp: "1 hour ago",
    type: "restart",
  },
  {
    id: "evt-3",
    event: "Database Backup Completed",
    description: "Incremental snapshot backup successfully written to secure AWS S3 bucket. Size: 1.4 TB.",
    timestamp: "3 hours ago",
    type: "backup",
  },
  {
    id: "evt-4",
    event: "SRE Scaling Triggered",
    description: "Added 4 worker nodes to task supervisor clusters in response to increased prompt volume.",
    timestamp: "6 hours ago",
    type: "scale",
  },
  {
    id: "evt-5",
    event: "Subsystem Health Check Passed",
    description: "Deep health verification scanned 12 microservices and 8 connection interfaces. 0 errors.",
    timestamp: "12 hours ago",
    type: "healthcheck",
  },
];

// ─── Section 9: SRE INSIGHTS ─────────────────────────────────────────────────
export interface ExecutiveOpsSummary {
  healthScore: string;
  incidentCount: string;
  avgRecoveryTime: string;
  availability: string;
  recommendation: string;
}

export const opsSummary: ExecutiveOpsSummary = {
  healthScore: "98.6 / 100",
  incidentCount: "0 Active",
  avgRecoveryTime: "4.2s (Auto)",
  availability: "99.98%",
  recommendation: "Increase the memory limit allocated to host voice-streamers from 2GB to 4GB.",
};
