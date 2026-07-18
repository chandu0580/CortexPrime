import type { LucideIcon } from "lucide-react";

export type StatusTone = "running" | "healthy" | "warning" | "critical" | "idle" | "info" | "completed";

export type SidebarItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  active?: boolean;
};

export type KpiMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: StatusTone;
  icon: LucideIcon;
  data: number[];
};

export type Mission = {
  name: string;
  agent: string;
  status: StatusTone;
  startTime: string;
  progress: number;
};

export type Agent = {
  name: string;
  version: string;
  runtime: string;
  status: StatusTone;
  health: number;
  icon: LucideIcon;
};

export type SystemMetric = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
  data: number[];
};

export type Alert = {
  message: string;
  time: string;
  severity: StatusTone;
};

export type QuickAction = {
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
};

export type HealthSignal = {
  label: string;
  value: number;
  status: string;
};

export type ActivityItem = {
  title: string;
  detail: string;
  time: string;
  icon: LucideIcon;
  tone: StatusTone;
};


