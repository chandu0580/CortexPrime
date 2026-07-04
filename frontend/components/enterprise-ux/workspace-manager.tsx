"use client";

import {
  GripVertical,
  X,
  LayoutDashboard,
  Shield,
  Users,
  Code2,
  Building2,
  Sliders,
  Activity,
  Radar,
  Cpu,
  DollarSign,
  History,
  Bell,
  UserCheck,
  Wifi,
  Lock,
  MemoryStick,
  Brain,
  ChartNoAxesCombined,
  FileText,
  Award,
  Star,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ease, variants } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

// ─── Type Definitions ────────────────────────────────────────────────────────

type WidgetId =
  | "ActivityFeed"
  | "MissionStatus"
  | "WorkerHealth"
  | "CostOverview"
  | "ReplayList"
  | "SystemAlerts"
  | "UserActivity"
  | "ConnectorStatus"
  | "SecurityEvents"
  | "MemoryUsage"
  | "KnowledgeGraph"
  | "ModelUsage"
  | "AuditLog"
  | "CertificationStatus";

type WorkspaceId = "executive" | "operations" | "engineering" | "security" | "compliance" | "custom";

interface WidgetPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Workspace {
  id: WorkspaceId;
  label: string;
  icon: string;
  description: string;
  pinnedWidgets: WidgetId[];
  layout: Record<WidgetId, WidgetPosition>;
  isFavorite: boolean;
}

interface WorkspaceContextValue {
  currentWorkspace: Workspace;
  workspaces: Workspace[];
  switchWorkspace: (id: WorkspaceId) => void;
  pinWidget: (widgetId: WidgetId) => void;
  unpinWidget: (widgetId: WidgetId) => void;
  toggleFavorite: () => void;
  saveLayout: (widgets: WidgetId[]) => void;
  resetLayout: () => void;
  isCustomWorkspace: boolean;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "cortex-workspaces";

const ALL_WIDGETS: { id: WidgetId; label: string }[] = [
  { id: "ActivityFeed", label: "Activity Feed" },
  { id: "MissionStatus", label: "Mission Status" },
  { id: "WorkerHealth", label: "Worker Health" },
  { id: "CostOverview", label: "Cost Overview" },
  { id: "ReplayList", label: "Replay List" },
  { id: "SystemAlerts", label: "System Alerts" },
  { id: "UserActivity", label: "User Activity" },
  { id: "ConnectorStatus", label: "Connector Status" },
  { id: "SecurityEvents", label: "Security Events" },
  { id: "MemoryUsage", label: "Memory Usage" },
  { id: "KnowledgeGraph", label: "Knowledge Graph" },
  { id: "ModelUsage", label: "Model Usage" },
  { id: "AuditLog", label: "Audit Log" },
  { id: "CertificationStatus", label: "Certification Status" },
];

function defaultLayout(widgets: WidgetId[]): Record<WidgetId, WidgetPosition> {
  const layout: Record<string, WidgetPosition> = {};
  widgets.forEach((id, i) => {
    layout[id] = { x: (i % 3) * 4, y: Math.floor(i / 3) * 2, w: 4, h: 2 };
  });
  return layout as Record<WidgetId, WidgetPosition>;
}

const DEFAULT_WORKSPACES: Workspace[] = [
  {
    id: "executive",
    label: "Executive",
    icon: "LayoutDashboard",
    description: "High-level business overview and KPIs",
    pinnedWidgets: ["ActivityFeed", "CostOverview", "MissionStatus", "SystemAlerts"],
    layout: defaultLayout(["ActivityFeed", "CostOverview", "MissionStatus", "SystemAlerts"]),
    isFavorite: true,
  },
  {
    id: "operations",
    label: "Operations",
    icon: "Users",
    description: "Daily operational metrics and team status",
    pinnedWidgets: ["WorkerHealth", "UserActivity", "ConnectorStatus", "MissionStatus"],
    layout: defaultLayout(["WorkerHealth", "UserActivity", "ConnectorStatus", "MissionStatus"]),
    isFavorite: false,
  },
  {
    id: "engineering",
    label: "Engineering",
    icon: "Code2",
    description: "System performance and development metrics",
    pinnedWidgets: ["MemoryUsage", "ModelUsage", "KnowledgeGraph", "WorkerHealth"],
    layout: defaultLayout(["MemoryUsage", "ModelUsage", "KnowledgeGraph", "WorkerHealth"]),
    isFavorite: false,
  },
  {
    id: "security",
    label: "Security",
    icon: "Shield",
    description: "Security events and compliance monitoring",
    pinnedWidgets: ["SecurityEvents", "AuditLog", "SystemAlerts", "CertificationStatus"],
    layout: defaultLayout(["SecurityEvents", "AuditLog", "SystemAlerts", "CertificationStatus"]),
    isFavorite: false,
  },
  {
    id: "compliance",
    label: "Compliance",
    icon: "Building2",
    description: "Regulatory compliance and certification tracking",
    pinnedWidgets: ["AuditLog", "CertificationStatus", "UserActivity", "SecurityEvents"],
    layout: defaultLayout(["AuditLog", "CertificationStatus", "UserActivity", "SecurityEvents"]),
    isFavorite: false,
  },
  {
    id: "custom",
    label: "Custom",
    icon: "Sliders",
    description: "Your personalized workspace",
    pinnedWidgets: [],
    layout: {} as Record<WidgetId, WidgetPosition>,
    isFavorite: false,
  },
];

const WIDGET_ICONS: Record<WidgetId, typeof Activity> = {
  ActivityFeed: Activity,
  MissionStatus: Radar,
  WorkerHealth: Cpu,
  CostOverview: DollarSign,
  ReplayList: History,
  SystemAlerts: Bell,
  UserActivity: UserCheck,
  ConnectorStatus: Wifi,
  SecurityEvents: Lock,
  MemoryUsage: MemoryStick,
  KnowledgeGraph: Brain,
  ModelUsage: ChartNoAxesCombined,
  AuditLog: FileText,
  CertificationStatus: Award,
};

const WORKSPACE_ICONS: Record<string, typeof LayoutDashboard> = {
  LayoutDashboard,
  Shield,
  Users,
  Code2,
  Building2,
  Sliders,
};

// ─── Store Helpers ───────────────────────────────────────────────────────────

function loadWorkspaces(): Workspace[] {
  if (typeof window === "undefined") return DEFAULT_WORKSPACES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WORKSPACES;
    return JSON.parse(raw) as Workspace[];
  } catch {
    return DEFAULT_WORKSPACES;
  }
}

function saveWorkspaces(workspaces: Workspace[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workspaces));
  } catch {}
}

// ─── Context ─────────────────────────────────────────────────────────────────

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>(loadWorkspaces);
  const [currentId, setCurrentId] = useState<WorkspaceId>("executive");

  useEffect(() => {
    saveWorkspaces(workspaces);
  }, [workspaces]);

  const currentWorkspace = useMemo(
    () => workspaces.find((w) => w.id === currentId) ?? workspaces[0],
    [workspaces, currentId],
  );

  const isCustomWorkspace = currentId === "custom";

  const updateWorkspace = useCallback(
    (id: WorkspaceId, updater: (ws: Workspace) => Workspace) => {
      setWorkspaces((prev) => prev.map((w) => (w.id === id ? updater(w) : w)));
    },
    [],
  );

  const switchWorkspace = useCallback((id: WorkspaceId) => {
    setCurrentId(id);
  }, []);

  const pinWidget = useCallback(
    (widgetId: WidgetId) => {
      updateWorkspace(currentId, (ws) => {
        if (ws.pinnedWidgets.includes(widgetId)) return ws;
        const pinned = [...ws.pinnedWidgets, widgetId];
        return {
          ...ws,
          pinnedWidgets: pinned,
          layout: { ...ws.layout, [widgetId]: { x: 0, y: pinned.length - 1, w: 4, h: 2 } },
        };
      });
    },
    [currentId, updateWorkspace],
  );

  const unpinWidget = useCallback(
    (widgetId: WidgetId) => {
      updateWorkspace(currentId, (ws) => {
        const { [widgetId]: _, ...restLayout } = ws.layout;
        return {
          ...ws,
          pinnedWidgets: ws.pinnedWidgets.filter((id) => id !== widgetId),
          layout: restLayout as Record<WidgetId, WidgetPosition>,
        };
      });
    },
    [currentId, updateWorkspace],
  );

  const toggleFavorite = useCallback(() => {
    updateWorkspace(currentId, (ws) => ({ ...ws, isFavorite: !ws.isFavorite }));
  }, [currentId, updateWorkspace]);

  const saveLayout = useCallback(
    (widgets: WidgetId[]) => {
      updateWorkspace(currentId, (ws) => {
        const existingLayout = ws.layout;
        const newLayout: Record<string, WidgetPosition> = {};
        widgets.forEach((id, i) => {
          newLayout[id] = existingLayout[id] ?? { x: (i % 3) * 4, y: Math.floor(i / 3) * 2, w: 4, h: 2 };
        });
        return { ...ws, pinnedWidgets: widgets, layout: newLayout as Record<WidgetId, WidgetPosition> };
      });
    },
    [currentId, updateWorkspace],
  );

  const resetLayout = useCallback(() => {
    const defaults = DEFAULT_WORKSPACES.find((w) => w.id === currentId);
    if (!defaults) return;
    updateWorkspace(currentId, () => ({
      ...defaults,
      isFavorite: currentWorkspace.isFavorite,
    }));
  }, [currentId, updateWorkspace, currentWorkspace.isFavorite]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      currentWorkspace,
      workspaces,
      switchWorkspace,
      pinWidget,
      unpinWidget,
      toggleFavorite,
      saveLayout,
      resetLayout,
      isCustomWorkspace,
    }),
    [
      currentWorkspace,
      workspaces,
      switchWorkspace,
      pinWidget,
      unpinWidget,
      toggleFavorite,
      saveLayout,
      resetLayout,
      isCustomWorkspace,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return ctx;
}

// ─── WorkspaceSwitcher ───────────────────────────────────────────────────────

export function WorkspaceSwitcher() {
  const { workspaces, currentWorkspace, switchWorkspace } = useWorkspace();

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      {workspaces.map((ws) => {
        const IconComponent = WORKSPACE_ICONS[ws.icon] ?? LayoutDashboard;
        const isActive = ws.id === currentWorkspace.id;
        return (
          <motion.button
            key={ws.id}
            onClick={() => switchWorkspace(ws.id)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.96 }}
            transition={{ duration: 0.2, ease: ease.out }}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-[18px] border px-4 py-2.5 text-sm font-medium transition-colors duration-200",
              isActive
                ? "border-[#38B88A] bg-[#38B88A] text-white shadow-[0_4px_12px_rgba(56,184,138,0.2)]"
                : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB] hover:bg-[#F9FAFB]",
            )}
            title={ws.description}
          >
            <IconComponent className="h-4 w-4" />
            <span>{ws.label}</span>
            {ws.isFavorite && (
              <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
            )}
          </motion.button>
        );
      })}
    </div>
  );
}

// ─── WidgetCard ──────────────────────────────────────────────────────────────

export function WidgetCard({
  widgetId,
  onClose,
  children,
  className,
}: {
  widgetId: WidgetId;
  onClose?: () => void;
  children?: ReactNode;
  className?: string;
}) {
  const widgetDef = ALL_WIDGETS.find((w) => w.id === widgetId);
  const IconComponent = WIDGET_ICONS[widgetId] ?? Activity;

  return (
    <motion.div
      layout
      initial="hidden"
      animate="visible"
      exit="exit"
      variants={variants.fadeUp}
      className={cn(
        "flex flex-col rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_4px_12px_rgba(148,163,184,0.08)]",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-[#E8EDF3] px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#111827]">
          <GripVertical className="h-4 w-4 cursor-grab text-[#9CA3AF]" />
          <IconComponent className="h-4 w-4 text-[#38B88A]" />
          <span>{widgetDef?.label ?? widgetId}</span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded-full text-[#9CA3AF] transition-colors hover:bg-[#F3F4F6] hover:text-[#EF4444]"
            aria-label={`Remove ${widgetDef?.label ?? widgetId}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="flex-1 p-4">{children}</div>
    </motion.div>
  );
}

// ─── WidgetGrid ──────────────────────────────────────────────────────────────

export function WidgetGrid({ className }: { className?: string }) {
  const { currentWorkspace, unpinWidget, pinWidget } = useWorkspace();
  const { pinnedWidgets } = currentWorkspace;

  if (pinnedWidgets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-[18px] border-2 border-dashed border-[#E8EDF3] p-12 text-center">
        <LayoutDashboard className="h-10 w-10 text-[#9CA3AF]" />
        <p className="text-lg font-semibold text-[#6B7280]">No widgets pinned</p>
        <p className="max-w-sm text-sm text-[#9CA3AF]">
          Pin widgets to this workspace from the available list below to build your dashboard.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
        className,
      )}
    >
      <AnimatePresence mode="popLayout">
        {pinnedWidgets.map((id) => (
          <WidgetCard key={id} widgetId={id} onClose={() => unpinWidget(id)}>
            <div className="flex h-full items-center justify-center text-sm text-[#9CA3AF]">
              Widget content placeholder
            </div>
          </WidgetCard>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ─── AvailableWidgetsPanel ───────────────────────────────────────────────────

export function AvailableWidgetsPanel() {
  const { currentWorkspace, pinWidget } = useWorkspace();
  const available = ALL_WIDGETS.filter(
    (w) => !currentWorkspace.pinnedWidgets.includes(w.id),
  );

  if (available.length === 0) {
    return (
      <p className="text-sm text-[#9CA3AF]">All widgets are pinned to this workspace.</p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {available.map((w) => {
        const IconComponent = WIDGET_ICONS[w.id] ?? Activity;
        return (
          <motion.button
            key={w.id}
            onClick={() => pinWidget(w.id)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-xs font-medium text-[#374151] transition-colors hover:border-[#38B88A] hover:text-[#38B88A]"
          >
            <IconComponent className="h-3.5 w-3.5" />
            {w.label}
          </motion.button>
        );
      })}
    </div>
  );
}