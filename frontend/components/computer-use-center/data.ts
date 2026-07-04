import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  Bot,
  Brain,
  Camera,
  CheckCircle2,
  Clock3,
  Columns3,
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Globe,
  HardDriveUpload,
  Home,
  Mail,
  Mic,
  Monitor,
  Puzzle,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SquareTerminal,
  Target,
  TrendingUp,
  Upload,
  UserCheck,
  Users,
  Workflow,
  Zap,
} from "lucide-react";

export type ComputerUseTone =
  | "running"
  | "completed"
  | "queued"
  | "paused"
  | "waiting"
  | "reviewing"
  | "warning"
  | "failed"
  | "info";

export type Metric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: ComputerUseTone;
  icon: LucideIcon;
  data: number[];
};

export type Session = {
  id: string;
  os: string;
  agent: string;
  task: string;
  status: ComputerUseTone;
  started: string;
  progress: number;
  thumbnail: "excel" | "browser" | "deck" | "ledger" | "crm" | "hr";
};

export type ActionCard = {
  label: string;
  detail: string;
  icon: LucideIcon;
};

export type UsageItem = {
  label: string;
  value: string;
  trend: string;
  icon: LucideIcon;
};

export type ActivityItem = {
  label: string;
  time: string;
  tone: ComputerUseTone;
  icon: LucideIcon;
};

export type TimelineItem = {
  action: string;
  application: string;
  timestamp: string;
  duration: string;
  tone: ComputerUseTone;
  icon: LucideIcon;
};

export type AppCard = {
  name: string;
  windows: string;
  cpu: string;
  status: ComputerUseTone;
  icon: LucideIcon;
};

export type ApprovalItem = {
  action: string;
  agent: string;
  application: string;
  risk: "Low" | "Medium" | "High";
  requested: string;
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Missions", href: "/missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain },
  { label: "Research", href: "/workspace", icon: Search },
  { label: "Computer Use", href: "/operator", icon: Monitor, active: true },
  { label: "Browser", href: "/operator", icon: Globe },
  { label: "Replay", href: "/replay", icon: Archive },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Activity },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const metrics: Metric[] = [
  { label: "Active Sessions", value: "8", trend: "+14.3%", status: "Running", tone: "running", icon: Monitor, data: [4, 4, 5, 6, 5, 6, 7, 7, 8] },
  { label: "Running Automations", value: "21", trend: "+11.2%", status: "Executing", tone: "running", icon: Workflow, data: [9, 11, 12, 13, 14, 16, 18, 19, 21] },
  { label: "Tasks Completed", value: "156", trend: "+18.7%", status: "Completed", tone: "completed", icon: CheckCircle2, data: [102, 110, 118, 124, 129, 138, 144, 150, 156] },
  { label: "Approval Requests", value: "4", trend: "-22%", status: "Review", tone: "reviewing", icon: UserCheck, data: [7, 6, 6, 5, 5, 5, 4, 4, 4] },
  { label: "Avg. Task Time", value: "02:41", trend: "-8.4%", status: "Faster", tone: "info", icon: Clock3, data: [4.4, 4.1, 3.8, 3.5, 3.2, 3.0, 2.9, 2.8, 2.7] },
  { label: "Success Rate", value: "94.6%", trend: "+3.2%", status: "Trusted", tone: "running", icon: TrendingUp, data: [83, 86, 88, 89, 90, 92, 92.8, 93.7, 94.6] },
];

export const sessions: Session[] = [
  { id: "#7821", os: "Windows 11", agent: "Data Analyst", task: "Generate sales report", status: "running", started: "10:32 AM", progress: 67, thumbnail: "excel" },
  { id: "#7819", os: "Windows 11", agent: "Research Agent", task: "Collect competitor data", status: "running", started: "10:28 AM", progress: 42, thumbnail: "browser" },
  { id: "#7818", os: "macOS Sonoma", agent: "Marketing Agent", task: "Create campaign deck", status: "running", started: "10:21 AM", progress: 51, thumbnail: "deck" },
  { id: "#7817", os: "Windows 11", agent: "Finance Agent", task: "Reconcile transactions", status: "completed", started: "09:47 AM", progress: 100, thumbnail: "ledger" },
  { id: "#7816", os: "Windows 11", agent: "Support Agent", task: "Update customer records", status: "running", started: "09:35 AM", progress: 38, thumbnail: "crm" },
  { id: "#7815", os: "macOS Sonoma", agent: "HR Agent", task: "Process employee data", status: "completed", started: "09:12 AM", progress: 100, thumbnail: "hr" },
];

export const actionCards: ActionCard[] = [
  { label: "New Computer Task", detail: "Start a new automation", icon: Monitor },
  { label: "Upload File", detail: "Upload document or data", icon: Upload },
  { label: "Schedule Task", detail: "Run tasks on a schedule", icon: Clock3 },
  { label: "Manage Environments", detail: "Manage OS environments", icon: Columns3 },
];

export const usageOverview: UsageItem[] = [
  { label: "Compute Time", value: "32h 45m", trend: "+16.2%", icon: Clock3 },
  { label: "Tasks Executed", value: "342", trend: "+12.1%", icon: Workflow },
  { label: "Screens Captured", value: "2,148", trend: "+18.7%", icon: Camera },
  { label: "Data Processed", value: "15.6 GB", trend: "+9.3%", icon: Database },
];

export const recentActivity: ActivityItem[] = [
  { label: "Data Analyst started session #7821", time: "2m ago", tone: "running", icon: Monitor },
  { label: "Research Agent completed task", time: "8m ago", tone: "completed", icon: CheckCircle2 },
  { label: "Screenshot captured - session #7819", time: "11m ago", tone: "info", icon: Camera },
  { label: "Finance Agent completed task", time: "25m ago", tone: "completed", icon: FileSpreadsheet },
  { label: "Marketing Agent started session #7818", time: "32m ago", tone: "running", icon: Workflow },
];

export const taskCategories = [
  { label: "Data and Reports", value: 42, color: "#38B88A" },
  { label: "Research", value: 38, color: "#3B82F6" },
  { label: "Data Entry", value: 28, color: "#8B5CF6" },
  { label: "Analysis", value: 24, color: "#F59E0B" },
  { label: "Other", value: 24, color: "#CBD5E1" },
];

export const successRateSeries = [
  { day: "May 6", value: 68 },
  { day: "May 8", value: 84 },
  { day: "May 10", value: 71 },
  { day: "May 12", value: 77 },
  { day: "May 14", value: 88 },
  { day: "May 16", value: 74 },
  { day: "May 18", value: 81 },
  { day: "May 20", value: 86 },
  { day: "May 22", value: 73 },
  { day: "May 24", value: 90 },
  { day: "May 26", value: 76 },
  { day: "May 28", value: 69 },
  { day: "May 30", value: 92 },
  { day: "May 31", value: 84 },
  { day: "Jun 1", value: 89 },
];

export const currentTask = {
  title: "Quarterly Revenue Performance Report",
  agent: "Data Analyst Agent",
  step: "Preparing spreadsheet summary and chart exports",
  eta: "01:24 min",
  confidence: "93%",
  progress: 58,
  status: "Executing",
};

export const timeline: TimelineItem[] = [
  { action: "Opened Chrome", application: "Chrome", timestamp: "10:21:03", duration: "2s", tone: "completed", icon: Globe },
  { action: "Clicked Search", application: "Chrome", timestamp: "10:21:08", duration: "1s", tone: "completed", icon: Search },
  { action: "Typed Query", application: "Chrome", timestamp: "10:21:11", duration: "4s", tone: "completed", icon: FileText },
  { action: "Opened Excel", application: "Excel", timestamp: "10:22:02", duration: "3s", tone: "completed", icon: FileSpreadsheet },
  { action: "Downloaded Report", application: "Chrome", timestamp: "10:24:17", duration: "6s", tone: "running", icon: Download },
  { action: "Generated PDF", application: "Excel", timestamp: "10:28:52", duration: "9s", tone: "running", icon: FileText },
  { action: "Uploaded File", application: "Salesforce", timestamp: "10:30:11", duration: "5s", tone: "reviewing", icon: HardDriveUpload },
  { action: "Completed Task", application: "Workspace", timestamp: "Pending", duration: "--", tone: "queued", icon: CheckCircle2 },
];

export const applications: AppCard[] = [
  { name: "Chrome", windows: "3 windows", cpu: "22%", status: "running", icon: Globe },
  { name: "Excel", windows: "2 windows", cpu: "31%", status: "running", icon: FileSpreadsheet },
  { name: "Word", windows: "1 window", cpu: "12%", status: "running", icon: FileText },
  { name: "Outlook", windows: "2 windows", cpu: "18%", status: "paused", icon: Mail },
  { name: "Slack", windows: "1 window", cpu: "7%", status: "running", icon: Send },
  { name: "Teams", windows: "1 window", cpu: "9%", status: "running", icon: Users },
  { name: "PowerPoint", windows: "1 window", cpu: "14%", status: "queued", icon: FileText },
  { name: "File Explorer", windows: "2 windows", cpu: "11%", status: "running", icon: FolderOpen },
  { name: "Terminal", windows: "1 window", cpu: "19%", status: "running", icon: SquareTerminal },
  { name: "SAP", windows: "1 window", cpu: "15%", status: "reviewing", icon: Database },
  { name: "Salesforce", windows: "2 windows", cpu: "24%", status: "running", icon: Database },
];

export const approvalQueue: ApprovalItem[] = [
  { action: "Delete file from finance share", agent: "Finance Agent", application: "File Explorer", risk: "High", requested: "2m ago" },
  { action: "Send quarterly summary email", agent: "Marketing Agent", application: "Outlook", risk: "Medium", requested: "6m ago" },
  { action: "Upload signed contract", agent: "Support Agent", application: "Salesforce", risk: "Medium", requested: "11m ago" },
  { action: "Execute reconciliation script", agent: "Finance Agent", application: "Terminal", risk: "High", requested: "18m ago" },
  { action: "Modify spreadsheet formula", agent: "Data Analyst", application: "Excel", risk: "Low", requested: "24m ago" },
];

export const analyticsCards = [
  { label: "Automation Success Rate", value: "94.6%", trend: "+3.2%", data: [82, 84, 88, 87, 90, 92, 94, 94.6] },
  { label: "Average Runtime", value: "2m 41s", trend: "-8.4%", data: [4.1, 3.8, 3.6, 3.3, 3.1, 2.9, 2.8, 2.7] },
  { label: "Actions Per Minute", value: "18.2", trend: "+5.6%", data: [10, 12, 13, 14, 15, 16, 17, 18.2] },
  { label: "Approval Rate", value: "96%", trend: "+1.4%", data: [90, 91, 92, 92, 93, 95, 95, 96] },
];

export const aiInsight =
  "Today, CortexPrime completed 184 autonomous desktop tasks across 12 enterprise applications with a 99.2% success rate. Manual approval was required for only 4 high-risk actions.";
