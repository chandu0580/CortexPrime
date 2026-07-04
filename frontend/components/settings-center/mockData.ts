export interface OrgSettings {
  name: string;
  logo: string;
  workspaceId: string;
  region: string;
  timezone: string;
  language: string;
  description: string;
}

export interface UserRecord {
  id: string;
  name: string;
  email: string;
  role: "Enterprise Admin" | "SRE Engineer" | "Compliance Auditor" | "Developer";
  status: "Active" | "Deactivated";
  lastLogin: string;
}

export interface SecuritySettings {
  ssoEnabled: boolean;
  oauthEnabled: boolean;
  mfaEnabled: boolean;
  sessionTimeout: number; // minutes
  passwordPolicy: "Standard" | "Strict" | "Custom";
  deviceTrust: boolean;
  apiAuthentication: boolean;
  auditLogging: boolean;
}

export interface AIModelConfig {
  id: string;
  name: string;
  provider: string;
  status: "healthy" | "degraded" | "offline";
  isDefault: boolean;
  contextWindow: string;
  temperature: number; // 0 to 1
}

export interface VoiceConfig {
  provider: string;
  status: "healthy" | "offline";
  inputDevice: string;
  outputDevice: string;
  model: string;
  noiseSuppression: boolean;
  streaming: boolean;
  language: string;
}

export interface MemoryConfig {
  embeddingModel: string;
  vectorDb: string;
  retentionPolicy: string;
  knowledgeSources: number;
  memorySizeGb: number;
  autoIndexing: boolean;
}

export interface ConnectedIntegrationPreference {
  id: string;
  name: string;
  status: "connected" | "disconnected";
}

export interface NotificationSettings {
  email: boolean;
  slack: boolean;
  teams: boolean;
  pushNotifications: boolean;
  incidentAlerts: boolean;
  missionUpdates: boolean;
  governanceAlerts: boolean;
  securityAlerts: boolean;
}

export interface APIKeyRow {
  id: string;
  name: string;
  type: string;
  created: string;
  expires: string;
  status: "Active" | "Expired" | "Revoked";
}

export interface AppearanceSettings {
  theme: "Light" | "Dark" | "System";
  compactMode: boolean;
  animations: boolean;
  density: "Compact" | "Cozy" | "Roomy";
  sidebarWidth: number; // px
  fontSize: number; // px
  accentColor: string;
}

export interface SystemInfo {
  version: string;
  buildNumber: string;
  license: string;
  environment: string;
  deploymentType: string;
  dbVersion: string;
  redisVersion: string;
  rabbitmqVersion: string;
}

// ─── Default Organization Configuration ────────────────────────────────────
export const defaultOrgSettings: OrgSettings = {
  name: "CortexPrime Inc.",
  logo: "CortexPrime Logo",
  workspaceId: "wrk-cortex-prime-prod-098",
  region: "US East (N. Virginia)",
  timezone: "Asia/Kolkata (GMT+05:30)",
  language: "English (US)",
  description: "Enterprise Production Workspace for AI-driven operation analysis, security audit scoping, and workflow synchronization.",
};

// ─── Users List ────────────────────────────────────────────────────────────
export const initialUsers: UserRecord[] = [
  { id: "usr-1", name: "Alex Morgan", email: "alex.morgan@cortexprime.ai", role: "Enterprise Admin", status: "Active", lastLogin: "Just now" },
  { id: "usr-2", name: "Jane Doe", email: "jane.doe@cortexprime.ai", role: "SRE Engineer", status: "Active", lastLogin: "10 mins ago" },
  { id: "usr-3", name: "Sarah Connor", email: "sarah.connor@cortexprime.ai", role: "Compliance Auditor", status: "Active", lastLogin: "1 hour ago" },
  { id: "usr-4", name: "John Connor", email: "john.connor@cortexprime.ai", role: "Developer", status: "Active", lastLogin: "Yesterday" },
  { id: "usr-5", name: "Miles Dyson", email: "miles.dyson@cortexprime.ai", role: "Developer", status: "Deactivated", lastLogin: "3 days ago" },
];

// ─── Security Settings ──────────────────────────────────────────────────────
export const defaultSecuritySettings: SecuritySettings = {
  ssoEnabled: true,
  oauthEnabled: true,
  mfaEnabled: true,
  sessionTimeout: 30,
  passwordPolicy: "Strict",
  deviceTrust: true,
  apiAuthentication: true,
  auditLogging: true,
};

// ─── AI Models List ─────────────────────────────────────────────────────────
export const defaultAIModels: AIModelConfig[] = [
  { id: "model-gpt5", name: "GPT-5 (Preview)", provider: "OpenAI Endpoint", status: "healthy", isDefault: true, contextWindow: "128k tokens", temperature: 0.7 },
  { id: "model-azureoa", name: "Azure GPT-4o", provider: "Azure OpenAI Router", status: "healthy", isDefault: false, contextWindow: "128k tokens", temperature: 0.4 },
  { id: "model-claude3", name: "Claude 3.5 Sonnet", provider: "Anthropic API", status: "healthy", isDefault: false, contextWindow: "200k tokens", temperature: 0.5 },
  { id: "model-gemini15", name: "Gemini 1.5 Pro", provider: "Google AI API", status: "degraded", isDefault: false, contextWindow: "1M tokens", temperature: 0.6 },
  { id: "model-local", name: "Llama-3-70B-Local", provider: "On-Premise Server", status: "offline", isDefault: false, contextWindow: "8k tokens", temperature: 0.2 },
];

// ─── Voice Configurations ───────────────────────────────────────────────────
export const defaultVoiceSettings: VoiceConfig = {
  provider: "Deepgram API",
  status: "healthy",
  inputDevice: "Built-in Microphone (Array)",
  outputDevice: "Default Speaker (High Def Audio)",
  model: "nova-2-general",
  noiseSuppression: true,
  streaming: true,
  language: "en-US (English - United States)",
};

// ─── Memory Settings ────────────────────────────────────────────────────────
export const defaultMemorySettings: MemoryConfig = {
  embeddingModel: "text-embedding-3-small (OpenAI)",
  vectorDb: "ChromaDB (Cluster)",
  retentionPolicy: "Keep forever (Indefinite)",
  knowledgeSources: 14,
  memorySizeGb: 256,
  autoIndexing: true,
};

// ─── Connected Integrations preferences ─────────────────────────────────────
export const defaultIntegrationPreferences: ConnectedIntegrationPreference[] = [
  { id: "pref-ms", name: "Microsoft 365", status: "connected" },
  { id: "pref-slack", name: "Slack", status: "connected" },
  { id: "pref-github", name: "GitHub", status: "connected" },
  { id: "pref-jira", name: "Jira", status: "connected" },
  { id: "pref-sforce", name: "Salesforce", status: "connected" },
  { id: "pref-aws", name: "AWS Services", status: "connected" },
  { id: "pref-azure", name: "Azure Cloud", status: "connected" },
  { id: "pref-google", name: "Google Cloud", status: "disconnected" },
];

// ─── Notification Configs ───────────────────────────────────────────────────
export const defaultNotificationSettings: NotificationSettings = {
  email: true,
  slack: true,
  teams: false,
  pushNotifications: true,
  incidentAlerts: true,
  missionUpdates: false,
  governanceAlerts: true,
  securityAlerts: true,
};

// ─── API Keys Log ───────────────────────────────────────────────────────────
export const initialApiKeys: APIKeyRow[] = [
  { id: "key-1", name: "Production SRE Key", type: "System Access", created: "May 12, 2024", expires: "Nov 12, 2024", status: "Active" },
  { id: "key-2", name: "Local Agent Sync", type: "Developer Access", created: "Jun 1, 2024", expires: "Dec 1, 2024", status: "Active" },
  { id: "key-3", name: "Legacy Webhook Access", type: "ReadOnly Link", created: "Jan 15, 2024", expires: "Jul 15, 2024", status: "Expired" },
  { id: "key-4", name: "Temp Analytics Fetcher", type: "System Access", created: "Feb 10, 2024", expires: "Never", status: "Revoked" },
];

// ─── Appearance Preferences ─────────────────────────────────────────────────
export const defaultAppearanceSettings: AppearanceSettings = {
  theme: "System",
  compactMode: false,
  animations: true,
  density: "Cozy",
  sidebarWidth: 208,
  fontSize: 13,
  accentColor: "#38B88A",
};

// ─── System Information ──────────────────────────────────────────────────────
export const defaultSystemInfo: SystemInfo = {
  version: "CortexPrime v4.1-pro",
  buildNumber: "4.1.20240626.8942",
  license: "Enterprise Perpetual License",
  environment: "Production Cluster",
  deploymentType: "Self-Hosted (Kubernetes)",
  dbVersion: "PostgreSQL v15.6",
  redisVersion: "Redis v7.2-cluster",
  rabbitmqVersion: "RabbitMQ v3.12",
};
