"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  CheckCircle2, Clock, XCircle, Loader2, ChevronRight,
  AlertTriangle, GitBranch, Play, Square, Eye,
} from "lucide-react"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"

export type WorkflowStatus = "pending" | "running" | "completed" | "failed" | "paused" | "approved" | "waiting_approval"

export interface WorkflowStep {
  id: string
  label: string
  description?: string
  status: WorkflowStatus
  duration?: string
  agent?: string
  output?: string
}

export interface WorkflowData {
  id: string
  name: string
  description?: string
  status: WorkflowStatus
  progress: number
  steps: WorkflowStep[]
  startedAt?: string
  completedAt?: string
  approvalRequired?: boolean
}

const statusConfig: Record<WorkflowStatus, { icon: React.ReactNode; label: string; color: string; dot: string }> = {
  pending: { icon: <Clock size={14} />, label: "Pending", color: "text-gray-400 bg-gray-100", dot: "bg-gray-400" },
  running: { icon: <Loader2 size={14} className="animate-spin" />, label: "Running", color: "text-blue-600 bg-blue-50", dot: "bg-blue-500" },
  completed: { icon: <CheckCircle2 size={14} />, label: "Completed", color: "text-[#2F9F77] bg-[#ECFBF4]", dot: "bg-[#38B88A]" },
  failed: { icon: <XCircle size={14} />, label: "Failed", color: "text-red-600 bg-red-50", dot: "bg-red-500" },
  paused: { icon: <Square size={14} />, label: "Paused", color: "text-amber-600 bg-amber-50", dot: "bg-amber-400" },
  approved: { icon: <CheckCircle2 size={14} />, label: "Approved", color: "text-[#2F9F77] bg-[#ECFBF4]", dot: "bg-[#38B88A]" },
  waiting_approval: { icon: <AlertTriangle size={14} />, label: "Needs Approval", color: "text-amber-600 bg-amber-50", dot: "bg-amber-400" },
}

function StatusBadge({ status }: { status: WorkflowStatus }) {
  const cfg = statusConfig[status]
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold", cfg.color)}>
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

function StepNode({ step, isLast }: { step: WorkflowStep; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = statusConfig[step.status]

  const isActive = step.status === "running" || step.status === "waiting_approval"

  return (
    <div className="relative">
      <div className="flex items-start gap-3">
        {/* Connector line + dot */}
        <div className="flex flex-col items-center">
          <div className={cn(
            "flex h-7 w-7 items-center justify-center rounded-full border-2 transition-all",
            step.status === "completed" || step.status === "approved"
              ? "border-[#38B88A] bg-[#ECFBF4]"
              : isActive
                ? "border-[#38B88A] bg-[#38B88A]"
                : "border-[#E5E7EB] bg-white"
          )}>
            {step.status === "completed" || step.status === "approved" ? (
              <CheckCircle2 size={12} className="text-[#2F9F77]" />
            ) : isActive ? (
              <Loader2 size={12} className="text-white animate-spin" />
            ) : (
              <div className="h-2 w-2 rounded-full bg-[#D1D5DB]" />
            )}
          </div>
          {!isLast && (
            <div className={cn(
              "w-0.5 h-8",
              step.status === "completed" || step.status === "approved" ? "bg-[#38B88A]" : "bg-[#E5E7EB]"
            )} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 pb-6 min-w-0">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => step.output && setExpanded(!expanded)}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className={cn(
                "text-[0.82rem] font-semibold truncate",
                step.status === "completed" || step.status === "approved" ? "text-[#2F9F77]" :
                isActive ? "text-[#111827]" : "text-[#6B7280]"
              )}>
                {step.label}
              </span>
              {step.agent && (
                <span className="text-[0.6rem] text-[#9CA3AF] bg-gray-100 rounded px-1.5 py-0.5">
                  {step.agent}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {step.duration && (
                <span className="text-[0.65rem] text-[#9CA3AF]">{step.duration}</span>
              )}
              {step.status === "waiting_approval" && (
                <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[9px] font-bold text-amber-600">
                  <Eye size={10} />
                  APPROVAL
                </span>
              )}
              <StatusBadge status={step.status} />
              {step.output && (
                <ChevronRight size={12} className={cn(
                  "text-gray-300 transition-transform",
                  expanded && "rotate-90"
                )} />
              )}
            </div>
          </div>

          {step.description && (
            <p className="text-[0.7rem] text-[#9CA3AF] mt-0.5">{step.description}</p>
          )}

          <AnimatePresence>
            {expanded && step.output && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: dur.fast }}
                className="mt-2 overflow-hidden"
              >
                <div className="rounded-[8px] bg-[#F9FAFB] border border-[#E8EDF3] p-3">
                  <pre className="text-[0.68rem] text-[#374151] whitespace-pre-wrap font-mono">{step.output}</pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

export function WorkflowVisualizer({ workflow }: { workflow: WorkflowData }) {
  const cfg = statusConfig[workflow.status]
  const [showAll, setShowAll] = useState(false)
  const displaySteps = showAll ? workflow.steps : workflow.steps.slice(0, 5)
  const hasMore = workflow.steps.length > 5

  return (
    <div className="rounded-[16px] border border-[#E8EDF3] bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[#E8EDF3]">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <GitBranch size={16} className="text-[#38B88A] shrink-0" />
              <h3 className="text-[0.9rem] font-bold text-[#111827] truncate">{workflow.name}</h3>
              <StatusBadge status={workflow.status} />
            </div>
            {workflow.description && (
              <p className="text-[0.72rem] text-[#6B7280] mt-0.5">{workflow.description}</p>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${workflow.progress}%` }}
              transition={{ duration: dur.medium, ease: ease.out }}
              className={cn(
                "h-full rounded-full",
                workflow.status === "failed" ? "bg-red-400" : "bg-[#38B88A]"
              )}
            />
          </div>
          <span className="text-[0.72rem] font-bold text-[#374151] shrink-0">{workflow.progress}%</span>
          {workflow.startedAt && (
            <span className="text-[0.65rem] text-[#9CA3AF] shrink-0">
              {new Date(workflow.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>

        {/* Approval badge */}
        {workflow.approvalRequired && workflow.status !== "approved" && (
          <div className="mt-3 flex items-center gap-2 rounded-[10px] bg-amber-50 border border-amber-200 px-4 py-2.5">
            <AlertTriangle size={14} className="text-amber-500 shrink-0" />
            <div className="flex-1">
              <p className="text-[0.72rem] font-bold text-amber-700">Approval Required</p>
              <p className="text-[0.65rem] text-amber-600">This workflow needs executive approval to proceed</p>
            </div>
            <button className="rounded-[8px] bg-amber-500 px-3 py-1.5 text-[0.65rem] font-bold text-white hover:bg-amber-600 transition-colors">
              Review
            </button>
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="px-5 py-4">
        <p className="text-[0.68rem] font-bold text-[#9CA3AF] uppercase tracking-wider mb-3">
          Steps ({workflow.steps.length})
        </p>
        <div className="space-y-1">
          {displaySteps.map((step, i) => (
            <StepNode key={step.id} step={step} isLast={i === workflow.steps.length - 1} />
          ))}
        </div>

        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="mt-2 text-[0.72rem] font-semibold text-[#38B88A] hover:text-[#2F9F77] transition-colors"
          >
            {showAll ? "Show less" : `Show ${workflow.steps.length - 5} more steps`}
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-[#E8EDF3] flex items-center justify-between">
        <div className="flex items-center gap-3 text-[0.65rem] text-[#9CA3AF]">
          {workflow.startedAt && <span>Started {new Date(workflow.startedAt).toLocaleString()}</span>}
          {workflow.completedAt && <span>· Completed {new Date(workflow.completedAt).toLocaleString()}</span>}
        </div>
        <div className="flex items-center gap-2">
          {workflow.status === "running" && (
            <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2.5 py-1 text-[0.65rem] font-semibold text-[#6B7280] hover:bg-gray-50 transition-colors">
              <Square size={10} />
              Pause
            </button>
          )}
          <button className="flex items-center gap-1 rounded-[8px] bg-[#38B88A] px-2.5 py-1 text-[0.65rem] font-bold text-white hover:bg-[#2F9F77] transition-colors">
            <Eye size={10} />
            View Details
          </button>
        </div>
      </div>
    </div>
  )
}

export function WorkflowList({ workflows }: { workflows: WorkflowData[] }) {
  if (workflows.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <GitBranch size={32} className="text-gray-200 mb-3" />
        <p className="text-[0.9rem] font-bold text-[#6B7280]">No workflows</p>
        <p className="text-[0.78rem] text-[#9CA3AF] mt-1">Execute a mission or workflow to see it here</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {workflows.map((wf) => (
        <WorkflowVisualizer key={wf.id} workflow={wf} />
      ))}
    </div>
  )
}
