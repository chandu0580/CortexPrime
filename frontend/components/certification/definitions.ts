export interface CertificationScore {
  label: string
  score: number
  maxScore: number
  status: "passed" | "warning" | "failed"
  checks: number
  passed: number
}

export interface HealthValidationItem {
  name: string
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  latency: string
  lastChecked: string
  detail: string
}

export interface BenchmarkResult {
  name: string
  value: string
  p50: string
  p95: string
  p99: string
  samples: number
  status: "good" | "acceptable" | "poor"
}

export interface ChaosTestResult {
  id: string
  scenario: string
  description: string
  status: "passed" | "failed" | "running" | "skipped"
  duration: string
  recoveryTime: string
  impact: string
}

export interface SecurityValidationItem {
  name: string
  status: "passed" | "failed" | "warning"
  detail: string
  severity: "critical" | "high" | "medium" | "low"
}

export interface MissionCertificationResult {
  missionId: string
  name: string
  status: "certified" | "failed" | "pending"
  success: boolean
  duration: string
  stagesPassed: number
  stagesTotal: number
  hasReplay: boolean
  hasReport: boolean
  hasAudit: boolean
}

export const DEFAULT_SCORES: CertificationScore[] = [
  { label: "Platform Readiness", score: 92, maxScore: 100, status: "passed", checks: 25, passed: 23 },
  { label: "Runtime Readiness", score: 88, maxScore: 100, status: "passed", checks: 18, passed: 16 },
  { label: "Worker Readiness", score: 85, maxScore: 100, status: "passed", checks: 12, passed: 10 },
  { label: "Connector Readiness", score: 75, maxScore: 100, status: "warning", checks: 8, passed: 6 },
  { label: "Security Readiness", score: 95, maxScore: 100, status: "passed", checks: 14, passed: 13 },
  { label: "Deployment Readiness", score: 90, maxScore: 100, status: "passed", checks: 10, passed: 9 },
]

export const DEFAULT_HEALTH_ITEMS: HealthValidationItem[] = [
  { name: "Platform", status: "healthy", latency: "12ms", lastChecked: "just now", detail: "All 35 modules registered and active" },
  { name: "Runtime", status: "healthy", latency: "8ms", lastChecked: "just now", detail: "Runtime state store connected" },
  { name: "Browser Worker", status: "healthy", latency: "45ms", lastChecked: "2s ago", detail: "3 sessions active" },
  { name: "Voice Worker", status: "healthy", latency: "30ms", lastChecked: "5s ago", detail: "Idle" },
  { name: "Desktop Worker", status: "healthy", latency: "15ms", lastChecked: "3s ago", detail: "Idle" },
  { name: "Redis Memory", status: "healthy", latency: "2ms", lastChecked: "1s ago", detail: "Connected, 1.2GB used" },
  { name: "Neo4j Knowledge Graph", status: "healthy", latency: "5ms", lastChecked: "2s ago", detail: "Connected, 28K nodes" },
  { name: "PostgreSQL", status: "healthy", latency: "3ms", lastChecked: "1s ago", detail: "Connected, pgvector enabled" },
  { name: "RabbitMQ", status: "healthy", latency: "4ms", lastChecked: "2s ago", detail: "Connected, 0 queue depth" },
  { name: "Event Bus", status: "healthy", latency: "1ms", lastChecked: "1s ago", detail: "0 handlers registered" },
]

export const DEFAULT_BENCHMARKS: BenchmarkResult[] = [
  { name: "Mission Execution (avg)", value: "1.2s", p50: "0.8s", p95: "2.1s", p99: "4.5s", samples: 128, status: "good" },
  { name: "Worker Latency (avg)", value: "240ms", p50: "180ms", p95: "420ms", p99: "890ms", samples: 512, status: "good" },
  { name: "Connector Latency (avg)", value: "85ms", p50: "45ms", p95: "160ms", p99: "350ms", samples: 1024, status: "good" },
  { name: "Memory Retrieval", value: "35ms", p50: "22ms", p95: "68ms", p99: "145ms", samples: 256, status: "good" },
  { name: "Knowledge Graph Query", value: "18ms", p50: "12ms", p95: "35ms", p99: "72ms", samples: 512, status: "good" },
  { name: "API Response (avg)", value: "95ms", p50: "62ms", p95: "180ms", p99: "420ms", samples: 2048, status: "good" },
  { name: "Dashboard Load", value: "0.8s", p50: "0.6s", p95: "1.2s", p99: "2.0s", samples: 64, status: "good" },
  { name: "LLM Response (avg)", value: "1.8s", p50: "1.2s", p95: "3.5s", p99: "8.2s", samples: 256, status: "acceptable" },
]

export const DEFAULT_CHAOS_TESTS: ChaosTestResult[] = [
  { id: "chaos-redis", scenario: "Redis Failure", description: "Simulate Redis connection loss and verify graceful degradation", status: "passed", duration: "15s", recoveryTime: "2.3s", impact: "In-memory fallback activated" },
  { id: "chaos-neo4j", scenario: "Neo4j Failure", description: "Simulate Neo4j connection loss and verify graceful degradation", status: "passed", duration: "12s", recoveryTime: "1.8s", impact: "Knowledge graph queries suspended" },
  { id: "chaos-worker", scenario: "Worker Restart", description: "Force worker restart and verify session recovery", status: "passed", duration: "8s", recoveryTime: "3.5s", impact: "Worker reconnected with session restored" },
  { id: "chaos-connector", scenario: "Connector Failure", description: "Simulate RabbitMQ disconnection and verify reconnection", status: "passed", duration: "10s", recoveryTime: "4.1s", impact: "Orchestration bus queued messages" },
  { id: "chaos-mission", scenario: "Mission Recovery", description: "Kill active mission mid-execution and verify recovery", status: "passed", duration: "20s", recoveryTime: "5.2s", impact: "Mission recovered from Redis state" },
]

export const DEFAULT_SECURITY_ITEMS: SecurityValidationItem[] = [
  { name: "RBAC Enforcement", status: "passed", detail: "All 6 roles have correct permission boundaries", severity: "high" },
  { name: "ABAC Rules", status: "passed", detail: "Attribute-based rules enforced for production deployments", severity: "high" },
  { name: "Approval Workflows", status: "passed", detail: "Multi-level approvals enforced for HIGH+ risk missions", severity: "critical" },
  { name: "Break-Glass Access", status: "passed", detail: "Emergency override logs to audit with full trace", severity: "critical" },
  { name: "API Key Management", status: "passed", detail: "SHA-256 hashed keys, rotation supported, IP whitelisting", severity: "high" },
  { name: "Secrets Management", status: "warning", detail: "Vault integration configured but 2 secrets use env fallback", severity: "medium" },
  { name: "Audit Logging", status: "passed", detail: "All auth events and authorization decisions recorded", severity: "high" },
  { name: "Token Validation", status: "passed", detail: "JWT with Redis blacklist, auto-revocation on logout", severity: "critical" },
  { name: "Rate Limiting", status: "passed", detail: "Redis-backed sliding window, per-route limits active", severity: "medium" },
  { name: "Session Management", status: "passed", detail: "Refresh token rotation with automatic expiry", severity: "high" },
]

export const DEFAULT_MISSION_CERTIFICATIONS: MissionCertificationResult[] = [
  { missionId: "enterprise.software_release", name: "Software Release", status: "certified", success: true, duration: "1.2s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.incident_response", name: "Incident Response", status: "certified", success: true, duration: "1.8s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.executive_research", name: "Executive Research", status: "certified", success: true, duration: "0.9s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.compliance_audit", name: "Compliance Audit", status: "certified", success: true, duration: "1.5s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.security_investigation", name: "Security Investigation", status: "certified", success: true, duration: "2.1s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.disaster_recovery", name: "Disaster Recovery", status: "pending", success: false, duration: "-", stagesPassed: 0, stagesTotal: 8, hasReplay: false, hasReport: false, hasAudit: false },
  { missionId: "enterprise.infrastructure_deployment", name: "Infrastructure Deployment", status: "certified", success: true, duration: "1.4s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.knowledge_discovery", name: "Knowledge Discovery", status: "certified", success: true, duration: "0.7s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.customer_escalation", name: "Customer Escalation", status: "certified", success: true, duration: "1.1s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
  { missionId: "enterprise.change_management", name: "Change Management", status: "certified", success: true, duration: "1.3s", stagesPassed: 8, stagesTotal: 8, hasReplay: true, hasReport: true, hasAudit: true },
]