export interface MonitoringKPI {
  title: string;
  value: string;
  change: string;
  isPositive: boolean;
  vsText: string;
  sparkline: number[];
  color: string;
  icon: "uptime" | "response" | "agents" | "tasks" | "load";
}

export interface SystemOverviewPoint {
  time: string;
  cpu: number;
  memory: number;
  disk: number;
  network: number;
}

export interface SystemHealthComponent {
  name: string;
  status: "Healthy" | "Degraded" | "Down";
  health: number;
  details: string;
}

export interface MonitoringAlert {
  title: string;
  description: string;
  risk: "High" | "Medium" | "Low" | "Info";
  time: string;
}

export interface ResourceGauge {
  label: string;
  percentage: number;
  color: string;
  peak: string;
}

export interface TopProcess {
  name: string;
  cpu: string;
  memory: string;
  status: "Running" | "Stopped";
}

export interface LiveEventLog {
  timestamp: string;
  message: string;
  tag: "Success" | "Info" | "Resolved" | "Warning" | "Error";
}

export const monitoringKPIs: MonitoringKPI[] = [
  {
    title: "System Uptime",
    value: "99.98%",
    change: "↑ 0.02%",
    isPositive: true,
    vsText: "vs last 24 hours",
    sparkline: [99.95, 99.96, 99.96, 99.97, 99.97, 99.98, 99.98],
    color: "#38B88A",
    icon: "uptime",
  },
  {
    title: "Avg Response Time",
    value: "1.24s",
    change: "↑ 8.4%",
    isPositive: true,
    vsText: "vs last 24 hours",
    sparkline: [1.12, 1.15, 1.18, 1.20, 1.22, 1.23, 1.24],
    color: "#38B88A",
    icon: "response",
  },
  {
    title: "Active Agents",
    value: "36",
    change: "↑ 12.5%",
    isPositive: true,
    vsText: "vs last 24 hours",
    sparkline: [32, 32, 33, 34, 34, 35, 36],
    color: "#38B88A",
    icon: "agents",
  },
  {
    title: "Tasks Executed",
    value: "8,742",
    change: "↑ 15.3%",
    isPositive: true,
    vsText: "vs last 24 hours",
    sparkline: [7500, 7800, 8000, 8200, 8400, 8500, 8742],
    color: "#EF4444", // red warning color matching screenshot
    icon: "tasks",
  },
  {
    title: "System Load",
    value: "42%",
    change: "↑ 5.6%",
    isPositive: true,
    vsText: "vs last 24 hours",
    sparkline: [38, 39, 40, 39, 41, 40, 42],
    color: "#38B88A",
    icon: "load",
  },
];

export const systemOverviewPoints: SystemOverviewPoint[] = [
  { time: "12 AM", cpu: 38, memory: 30, disk: 25, network: 10 },
  { time: "3 AM", cpu: 42, memory: 32, disk: 26, network: 11 },
  { time: "6 AM", cpu: 38, memory: 30, disk: 27, network: 10 },
  { time: "9 AM", cpu: 40, memory: 32, disk: 28, network: 12 },
  { time: "12 PM", cpu: 62, memory: 38, disk: 30, network: 8 },
  { time: "3 PM", cpu: 50, memory: 37, disk: 31, network: 13 },
  { time: "6 PM", cpu: 48, memory: 38, disk: 32, network: 11 },
  { time: "9 PM", cpu: 42, memory: 35, disk: 28, network: 12 },
];

export const systemHealthComponents: SystemHealthComponent[] = [
  { name: "API Services", status: "Healthy", health: 99.9, details: "All services running" },
  { name: "Database", status: "Healthy", health: 99.8, details: "Primary active" },
  { name: "Cache", status: "Healthy", health: 100, details: "Hit rate: 98.3%" },
  { name: "Storage", status: "Healthy", health: 99.7, details: "2.1 TB / 10 TB used" },
  { name: "Message Queue", status: "Healthy", health: 99.9, details: "Queue depth: 120" },
  { name: "Agent Runtime", status: "Healthy", health: 99.6, details: "36 agents active" },
  { name: "Search Service", status: "Healthy", health: 99.8, details: "Index status: OK" },
  { name: "File Processing", status: "Healthy", health: 99.5, details: "All workers active" },
];

export const SREAlerts: MonitoringAlert[] = [
  {
    title: "High memory usage detected",
    description: "Memory usage is above 85% on server-02",
    risk: "High",
    time: "2m ago",
  },
  {
    title: "Increased response time",
    description: "API response time is above 2s",
    risk: "Medium",
    time: "15m ago",
  },
  {
    title: "New agent deployed",
    description: "Research Agent v2.1.0 deployed successfully",
    risk: "Info",
    time: "1h ago",
  },
  {
    title: "Disk space running low",
    description: "Disk usage is above 80% on server-03",
    risk: "Medium",
    time: "2h ago",
  },
  {
    title: "Backup completed",
    description: "Daily backup completed successfully",
    risk: "Info",
    time: "3h ago",
  },
];

export const resourceGauges: ResourceGauge[] = [
  { label: "CPU Usage", percentage: 42, color: "#38B88A", peak: "Peak: 68%" },
  { label: "Memory Usage", percentage: 63, color: "#3B82F6", peak: "Peak: 85%" },
  { label: "Disk Usage", percentage: 57, color: "#F59E0B", peak: "Peak: 72%" },
];

export const topProcesses: TopProcess[] = [
  { name: "agent-runtime", cpu: "18.4%", memory: "2.1 GB", status: "Running" },
  { name: "api-gateway", cpu: "12.7%", memory: "1.8 GB", status: "Running" },
  { name: "data-processor", cpu: "9.3%", memory: "1.2 GB", status: "Running" },
  { name: "search-service", cpu: "7.8%", memory: "1.1 GB", status: "Running" },
];

export const liveEvents: LiveEventLog[] = [
  {
    timestamp: "May 12, 2024 10:30:45 AM",
    message: "Agent Research Agent completed task #7821",
    tag: "Success",
  },
  {
    timestamp: "May 12, 2024 10:28:12 AM",
    message: "Database backup initiated",
    tag: "Info",
  },
  {
    timestamp: "May 12, 2024 10:25:33 AM",
    message: "High memory usage alert resolved",
    tag: "Resolved",
  },
  {
    timestamp: "May 12, 2024 10:22:11 AM",
    message: "New user login: Sarah Chen",
    tag: "Info",
  },
  {
    timestamp: "May 12, 2024 10:18:45 AM",
    message: "System configuration updated",
    tag: "Info",
  },
];
