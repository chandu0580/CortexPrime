"use client";

import {
  GripVertical,
  X,
  Settings2,
  Maximize2,
  Plus,
  RotateCcw,
  Download,
  Upload,
  Save,
  Undo2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ease, variants } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

// ─── Type Definitions ────────────────────────────────────────────────────────

type WidgetType =
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

interface GridPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface WidgetSettings {
  title: string;
  refreshInterval: number;
  displayOptions: Record<string, string | boolean | number>;
}

interface DashboardWidget {
  id: string;
  type: WidgetType;
  title: string;
  grid: GridPosition;
  settings: WidgetSettings;
}

interface DashboardContextValue {
  widgets: DashboardWidget[];
  isEditing: boolean;
  setEditing: (editing: boolean) => void;
  addWidget: (type: WidgetType) => void;
  removeWidget: (id: string) => void;
  updateWidgetPosition: (id: string, grid: GridPosition) => void;
  updateWidgetSettings: (id: string, settings: Partial<WidgetSettings>) => void;
  resetLayout: () => void;
  exportLayout: () => string;
  importLayout: (json: string) => void;
  saveLayout: () => void;
  restoreDefaults: () => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "cortex-dashboard-layout";

const COLUMNS = 12;
const CELL_W = 80;
const CELL_H = 80;
const GAP = 12;

const WIDGET_LABELS: Record<WidgetType, string> = {
  ActivityFeed: "Activity Feed",
  MissionStatus: "Mission Status",
  WorkerHealth: "Worker Health",
  CostOverview: "Cost Overview",
  ReplayList: "Replay List",
  SystemAlerts: "System Alerts",
  UserActivity: "User Activity",
  ConnectorStatus: "Connector Status",
  SecurityEvents: "Security Events",
  MemoryUsage: "Memory Usage",
  KnowledgeGraph: "Knowledge Graph",
  ModelUsage: "Model Usage",
  AuditLog: "Audit Log",
  CertificationStatus: "Certification Status",
};

const DEFAULT_SETTINGS: WidgetSettings = {
  title: "",
  refreshInterval: 30000,
  displayOptions: {},
};

function makeDefaultWidget(type: WidgetType, index: number): DashboardWidget {
  return {
    id: `${type}-${index}-${Date.now()}`,
    type,
    title: WIDGET_LABELS[type],
    grid: { x: (index % 3) * 4, y: Math.floor(index / 3) * 3, w: 4, h: 3 },
    settings: { ...DEFAULT_SETTINGS, title: WIDGET_LABELS[type] },
  };
}

const DEFAULT_WIDGETS: DashboardWidget[] = (
  [
    "ActivityFeed",
    "MissionStatus",
    "WorkerHealth",
    "CostOverview",
    "SystemAlerts",
    "MemoryUsage",
  ] as WidgetType[]
).map(makeDefaultWidget);

// ─── Store Helpers ───────────────────────────────────────────────────────────

function loadLayout(): DashboardWidget[] {
  if (typeof window === "undefined") return DEFAULT_WIDGETS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WIDGETS;
    return JSON.parse(raw) as DashboardWidget[];
  } catch {
    return DEFAULT_WIDGETS;
  }
}

function saveLayoutToStorage(widgets: DashboardWidget[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widgets));
  } catch {}
}

// ─── Context ─────────────────────────────────────────────────────────────────

const DashboardBuilderContext = createContext<DashboardContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function DashboardBuilderProvider({ children }: { children: ReactNode }) {
  const [widgets, setWidgets] = useState<DashboardWidget[]>(loadLayout);
  const [isEditing, setEditing] = useState(false);

  useEffect(() => {
    if (!isEditing) saveLayoutToStorage(widgets);
  }, [widgets, isEditing]);

  const addWidget = useCallback((type: WidgetType) => {
    setWidgets((prev) => [...prev, makeDefaultWidget(type, prev.length)]);
  }, []);

  const removeWidget = useCallback((id: string) => {
    setWidgets((prev) => prev.filter((w) => w.id !== id));
  }, []);

  const updateWidgetPosition = useCallback((id: string, grid: GridPosition) => {
    setWidgets((prev) =>
      prev.map((w) => (w.id === id ? { ...w, grid } : w)),
    );
  }, []);

  const updateWidgetSettings = useCallback(
    (id: string, partial: Partial<WidgetSettings>) => {
      setWidgets((prev) =>
        prev.map((w) =>
          w.id === id ? { ...w, settings: { ...w.settings, ...partial } } : w,
        ),
      );
    },
    [],
  );

  const resetLayout = useCallback(() => {
    setWidgets(DEFAULT_WIDGETS.map((w) => ({ ...w, id: `${w.type}-${Date.now()}-${Math.random()}` })));
  }, []);

  const exportLayout = useCallback((): string => {
    return JSON.stringify(widgets, null, 2);
  }, [widgets]);

  const importLayout = useCallback((json: string) => {
    try {
      const parsed = JSON.parse(json) as DashboardWidget[];
      if (Array.isArray(parsed)) setWidgets(parsed);
    } catch {}
  }, []);

  const saveLayout = useCallback(() => {
    saveLayoutToStorage(widgets);
  }, [widgets]);

  const restoreDefaults = useCallback(() => {
    setWidgets(DEFAULT_WIDGETS.map((w) => ({ ...w, id: `${w.type}-${Date.now()}-${Math.random()}` })));
    saveLayoutToStorage(DEFAULT_WIDGETS);
  }, []);

  const value = useMemo<DashboardContextValue>(
    () => ({
      widgets,
      isEditing,
      setEditing,
      addWidget,
      removeWidget,
      updateWidgetPosition,
      updateWidgetSettings,
      resetLayout,
      exportLayout,
      importLayout,
      saveLayout,
      restoreDefaults,
    }),
    [
      widgets,
      isEditing,
      setEditing,
      addWidget,
      removeWidget,
      updateWidgetPosition,
      updateWidgetSettings,
      resetLayout,
      exportLayout,
      importLayout,
      saveLayout,
      restoreDefaults,
    ],
  );

  return (
    <DashboardBuilderContext.Provider value={value}>
      {children}
    </DashboardBuilderContext.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useDashboardBuilder(): DashboardContextValue {
  const ctx = useContext(DashboardBuilderContext);
  if (!ctx) throw new Error("useDashboardBuilder must be used within a DashboardBuilderProvider");
  return ctx;
}

// ─── Utility: grid snap ──────────────────────────────────────────────────────

function snapToGrid(px: number, colOrRow: number, maxCols = COLUMNS): number {
  const snapped = Math.round(px / (CELL_W + GAP));
  return Math.max(0, Math.min(snapped, maxCols - colOrRow));
}

function pxToGridPos(pxX: number, pxY: number, w: number, h: number): GridPosition {
  return {
    x: snapToGrid(pxX, w),
    y: snapToGrid(pxY, h, 100),
    w,
    h,
  };
}

// ─── DashboardToolbar ────────────────────────────────────────────────────────

export function DashboardToolbar() {
  const {
    isEditing,
    setEditing,
    addWidget,
    resetLayout,
    exportLayout,
    importLayout,
    saveLayout,
  } = useDashboardBuilder();
  const [importText, setImportText] = useState("");
  const [showImport, setShowImport] = useState(false);

  const handleExport = () => {
    const json = exportLayout();
    navigator.clipboard.writeText(json).catch(() => {});
  };

  const handleImport = () => {
    importLayout(importText);
    setShowImport(false);
    setImportText("");
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[18px] border border-[#E8EDF3] bg-white px-4 py-3 shadow-[0_4px_12px_rgba(148,163,184,0.06)]">
      <motion.button
        onClick={() => setEditing(!isEditing)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.97 }}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-[18px] border px-4 py-2 text-sm font-medium transition-colors",
          isEditing
            ? "border-[#38B88A] bg-[#38B88A] text-white"
            : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
        )}
      >
        <Settings2 className="h-4 w-4" />
        {isEditing ? "Save Dashboard" : "Customize Dashboard"}
      </motion.button>

      {isEditing && (
        <>
          <motion.button
            onClick={() => addWidget("ActivityFeed")}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm font-medium text-[#374151] transition-colors hover:border-[#38B88A] hover:text-[#38B88A]"
          >
            <Plus className="h-4 w-4" />
            Add Widget
          </motion.button>

          <motion.button
            onClick={resetLayout}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm font-medium text-[#374151] transition-colors hover:border-[#EF4444] hover:text-[#EF4444]"
          >
            <RotateCcw className="h-4 w-4" />
            Reset Layout
          </motion.button>

          <div className="ml-auto flex items-center gap-2">
            <motion.button
              onClick={handleExport}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm font-medium text-[#374151] transition-colors hover:border-[#38B88A] hover:text-[#38B88A]"
              title="Copy layout JSON to clipboard"
            >
              <Download className="h-4 w-4" />
              Export Layout
            </motion.button>

            <motion.button
              onClick={() => setShowImport(!showImport)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm font-medium text-[#374151] transition-colors hover:border-[#38B88A] hover:text-[#38B88A]"
            >
              <Upload className="h-4 w-4" />
              Import Layout
            </motion.button>

            <motion.button
              onClick={saveLayout}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-1.5 rounded-[18px] border border-[#38B88A] bg-[#38B88A] px-3 py-2 text-sm font-medium text-white"
            >
              <Save className="h-4 w-4" />
              Save
            </motion.button>
          </div>
        </>
      )}

      {showImport && (
        <div className="flex w-full items-center gap-2">
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="Paste layout JSON here..."
            rows={3}
            className="flex-1 rounded-[12px] border border-[#E8EDF3] bg-white p-2 text-xs font-mono text-[#374151] outline-none focus:border-[#38B88A] focus:ring-1 focus:ring-[#38B88A]"
          />
          <motion.button
            onClick={handleImport}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-1 rounded-[18px] border border-[#38B88A] bg-[#38B88A] px-3 py-2 text-sm font-medium text-white"
          >
            Apply
          </motion.button>
        </div>
      )}
    </div>
  );
}

// ─── SaveLayoutButton ────────────────────────────────────────────────────────

export function SaveLayoutButton({ className }: { className?: string }) {
  const { saveLayout } = useDashboardBuilder();
  return (
    <motion.button
      onClick={saveLayout}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[18px] border border-[#38B88A] bg-[#38B88A] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#2F9F77]",
        className,
      )}
    >
      <Save className="h-4 w-4" />
      Save Layout
    </motion.button>
  );
}

// ─── RestoreDefaultsButton ───────────────────────────────────────────────────

export function RestoreDefaultsButton({ className }: { className?: string }) {
  const { restoreDefaults } = useDashboardBuilder();
  return (
    <motion.button
      onClick={restoreDefaults}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[18px] border border-[#E8EDF3] bg-white px-4 py-2 text-sm font-medium text-[#374151] transition-colors hover:border-[#EF4444] hover:text-[#EF4444]",
        className,
      )}
    >
      <Undo2 className="h-4 w-4" />
      Restore Defaults
    </motion.button>
  );
}

// ─── AddWidgetPanel ──────────────────────────────────────────────────────────

const ALL_TYPES: WidgetType[] = [
  "ActivityFeed",
  "MissionStatus",
  "WorkerHealth",
  "CostOverview",
  "ReplayList",
  "SystemAlerts",
  "UserActivity",
  "ConnectorStatus",
  "SecurityEvents",
  "MemoryUsage",
  "KnowledgeGraph",
  "ModelUsage",
  "AuditLog",
  "CertificationStatus",
];

export function AddWidgetPanel({ className }: { className?: string }) {
  const { addWidget } = useDashboardBuilder();

  return (
    <div className={cn("rounded-[18px] border border-[#E8EDF3] bg-white p-4", className)}>
      <h3 className="mb-3 text-sm font-semibold text-[#111827]">Available Widgets</h3>
      <div className="space-y-1">
        {ALL_TYPES.map((type) => (
          <motion.button
            key={type}
            onClick={() => addWidget(type)}
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.97 }}
            className="flex w-full items-center justify-between rounded-[12px] px-3 py-2 text-left text-sm text-[#374151] transition-colors hover:bg-[#F9FAFB]"
          >
            <span>{WIDGET_LABELS[type]}</span>
            <span className="inline-flex items-center gap-1 rounded-full border border-[#E8EDF3] px-2 py-0.5 text-xs font-medium text-[#38B88A]">
              <Plus className="h-3 w-3" />
              Add
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

// ─── WidgetSettingsModal ─────────────────────────────────────────────────────

export function WidgetSettingsModal({
  widgetId,
  onClose,
}: {
  widgetId: string | null;
  onClose: () => void;
}) {
  const { widgets, updateWidgetSettings } = useDashboardBuilder();
  const widget = widgets.find((w) => w.id === widgetId);

  if (!widget) return null;

  return (
    <AnimatePresence>
      {widgetId && (
        <motion.div
          key="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ duration: 0.2, ease: ease.out }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-[18px] border border-[#E8EDF3] bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.15)]"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[#111827]">Widget Settings</h2>
              <button
                onClick={onClose}
                className="flex h-7 w-7 items-center justify-center rounded-full text-[#9CA3AF] transition-colors hover:bg-[#F3F4F6] hover:text-[#111827]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-[#6B7280]">Title</label>
                <input
                  value={widget.settings.title}
                  onChange={(e) =>
                    updateWidgetSettings(widget.id, { title: e.target.value })
                  }
                  className="w-full rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm text-[#374151] outline-none focus:border-[#38B88A] focus:ring-1 focus:ring-[#38B88A]"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[#6B7280]">
                  Refresh Interval (ms)
                </label>
                <input
                  type="number"
                  value={widget.settings.refreshInterval}
                  onChange={(e) =>
                    updateWidgetSettings(widget.id, {
                      refreshInterval: parseInt(e.target.value, 10) || 30000,
                    })
                  }
                  min={1000}
                  step={1000}
                  className="w-full rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-sm text-[#374151] outline-none focus:border-[#38B88A] focus:ring-1 focus:ring-[#38B88A]"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[#6B7280]">
                  Display Options (JSON)
                </label>
                <textarea
                  value={JSON.stringify(widget.settings.displayOptions, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      updateWidgetSettings(widget.id, { displayOptions: parsed });
                    } catch {}
                  }}
                  rows={4}
                  className="w-full rounded-[12px] border border-[#E8EDF3] bg-white p-3 text-xs font-mono text-[#374151] outline-none focus:border-[#38B88A] focus:ring-1 focus:ring-[#38B88A]"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <motion.button
                onClick={onClose}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                className="rounded-[18px] border border-[#38B88A] bg-[#38B88A] px-6 py-2 text-sm font-medium text-white"
              >
                Done
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── Draggable Widget ────────────────────────────────────────────────────────

function DraggableWidget({
  widget,
  onRemove,
  onPositionChange,
  onSettingsOpen,
}: {
  widget: DashboardWidget;
  onRemove: () => void;
  onPositionChange: (grid: GridPosition) => void;
  onSettingsOpen: () => void;
}) {
  const dragRef = useRef<{
    startX: number;
    startY: number;
    origGrid: GridPosition;
    dragging: boolean;
  }>({ startX: 0, startY: 0, origGrid: widget.grid, dragging: false });

  const [isDragging, setIsDragging] = useState(false);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origGrid: { ...widget.grid },
      dragging: true,
    };
    setIsDragging(true);

    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current.dragging) return;
      const dx = ev.clientX - dragRef.current.startX;
      const dy = ev.clientY - dragRef.current.startY;
      setOffset({ x: dx, y: dy });
    };

    const handleMouseUp = () => {
      if (dragRef.current.dragging) {
        const dx = offset.x;
        const dy = offset.y;
        const snapped = pxToGridPos(
          dragRef.current.origGrid.x * (CELL_W + GAP) + dx,
          dragRef.current.origGrid.y * (CELL_H + GAP) + dy,
          widget.grid.w,
          widget.grid.h,
        );
        onPositionChange(snapped);
      }
      dragRef.current.dragging = false;
      setIsDragging(false);
      setOffset({ x: 0, y: 0 });
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const style: React.CSSProperties = {
    position: "absolute",
    left: widget.grid.x * (CELL_W + GAP),
    top: widget.grid.y * (CELL_H + GAP),
    width: widget.grid.w * CELL_W + (widget.grid.w - 1) * GAP,
    height: widget.grid.h * CELL_H + (widget.grid.h - 1) * GAP,
  };

  const dragStyle: React.CSSProperties = isDragging
    ? {
        transform: `translate(${offset.x}px, ${offset.y}px)`,
        zIndex: 50,
        boxShadow: "0 18px 50px rgba(15,23,42,0.15)",
      }
    : {};

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      style={{ ...style, ...dragStyle }}
      className={cn(
        "rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_4px_12px_rgba(148,163,184,0.08)] transition-shadow",
        isDragging && "cursor-grabbing",
      )}
    >
      <div
        className="flex items-center justify-between border-b border-[#E8EDF3] px-3 py-2"
        onMouseDown={handleMouseDown}
        style={{ cursor: "grab" }}
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-[#111827]">
          <GripVertical className="h-4 w-4 text-[#9CA3AF]" />
          <span>{widget.settings.title || widget.title}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onSettingsOpen}
            className="flex h-6 w-6 items-center justify-center rounded-full text-[#9CA3AF] transition-colors hover:bg-[#F3F4F6] hover:text-[#38B88A]"
            aria-label="Settings"
          >
            <Settings2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onRemove}
            className="flex h-6 w-6 items-center justify-center rounded-full text-[#9CA3AF] transition-colors hover:bg-[#F3F4F6] hover:text-[#EF4444]"
            aria-label={`Remove ${widget.title}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="flex h-[calc(100%-40px)] items-center justify-center p-4 text-sm text-[#9CA3AF]">
        {widget.type} content
      </div>
    </motion.div>
  );
}

// ─── Read-only Widget ────────────────────────────────────────────────────────

function ReadOnlyWidget({ widget }: { widget: DashboardWidget }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_4px_12px_rgba(148,163,184,0.08)]"
    >
      <div className="border-b border-[#E8EDF3] px-4 py-3">
        <span className="text-sm font-semibold text-[#111827]">
          {widget.settings.title || widget.title}
        </span>
      </div>
      <div className="flex h-[calc(100%-44px)] items-center justify-center p-4 text-sm text-[#9CA3AF]">
        {widget.type} content
      </div>
    </motion.div>
  );
}

// ─── DashboardBuilder ────────────────────────────────────────────────────────

export function DashboardBuilder({ className }: { className?: string }) {
  const {
    widgets,
    isEditing,
    updateWidgetPosition,
    removeWidget,
    addWidget,
    setEditing,
  } = useDashboardBuilder();
  const [settingsWidgetId, setSettingsWidgetId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const gridWidth = COLUMNS * CELL_W + (COLUMNS - 1) * GAP;

  const maxY = useMemo(
    () =>
      widgets.reduce((max, w) => Math.max(max, w.grid.y + w.grid.h), 0),
    [widgets],
  );

  return (
    <div className={cn("space-y-4", className)}>
      <DashboardToolbar />

      {isEditing && (
        <div className="flex gap-4">
          <AddWidgetPanel className="w-56 shrink-0" />
          <div className="flex-1">
            <div
              ref={containerRef}
              className="relative"
              style={{
                width: gridWidth,
                height: (maxY + 3) * (CELL_H + GAP) + 20,
              }}
            >
              <AnimatePresence mode="popLayout">
                {widgets.map((w) => (
                  <DraggableWidget
                    key={w.id}
                    widget={w}
                    onRemove={() => removeWidget(w.id)}
                    onPositionChange={(grid) => updateWidgetPosition(w.id, grid)}
                    onSettingsOpen={() => setSettingsWidgetId(w.id)}
                  />
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      )}

      {!isEditing && (
        <div
          className="relative"
          style={{
            width: gridWidth,
            height: (maxY + 3) * (CELL_H + GAP) + 20,
          }}
        >
          <AnimatePresence mode="popLayout">
            {widgets.map((w) => (
              <div
                key={w.id}
                className="absolute"
                style={{
                  left: w.grid.x * (CELL_W + GAP),
                  top: w.grid.y * (CELL_H + GAP),
                  width: w.grid.w * CELL_W + (w.grid.w - 1) * GAP,
                  height: w.grid.h * CELL_H + (w.grid.h - 1) * GAP,
                }}
              >
                <ReadOnlyWidget widget={w} />
              </div>
            ))}
          </AnimatePresence>
        </div>
      )}

      <WidgetSettingsModal
        widgetId={settingsWidgetId}
        onClose={() => setSettingsWidgetId(null)}
      />
    </div>
  );
}