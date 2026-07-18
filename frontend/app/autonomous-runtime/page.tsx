"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useTriggerPolicies,
  useTriggerHistory,
  useTriggerStats,
  useCreateTriggerPolicy,
  useDeleteTriggerPolicy,
  useUpdateTriggerPolicy,
  useSimulateTrigger,
  useTriggerSources,
} from "@/hooks/queries/enterprise/useEnterpriseTriggers"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Eye,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  Target,
  Trash2,
  XCircle,
} from "lucide-react"
import type { TriggerPolicy } from "@/types/triggers"
import { TRIGGER_SOURCES } from "@/types/triggers"

const PRIORITY_COLORS: Record<string, string> = {
  critical: "text-red-500 bg-red-50",
  high: "text-orange-500 bg-orange-50",
  medium: "text-amber-500 bg-amber-50",
  low: "text-blue-500 bg-blue-50",
}

const STATUS_COLORS: Record<string, string> = {
  matched: "text-[#38B88A] bg-[#F0FDF4]",
  suppressed: "text-orange-500 bg-orange-50",
  error: "text-red-500 bg-red-50",
  generated: "text-blue-500 bg-blue-50",
}

function PolicyForm({ onSubmit, initial }: { onSubmit: (data: any) => void; initial?: TriggerPolicy }) {
  const [name, setName] = useState(initial?.name ?? "")
  const [source, setSource] = useState(initial?.source ?? "")
  const [eventPattern, setEventPattern] = useState(initial?.event_pattern ?? "")
  const [template, setTemplate] = useState(initial?.mission_template ?? "software_release")
  const [priority, setPriority] = useState(initial?.priority ?? "medium")
  const [cooldown, setCooldown] = useState(initial?.cooldown_seconds ?? 300)
  const [enabled, setEnabled] = useState(initial?.enabled ?? true)

  return (
    <div className="space-y-3">
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Policy name"
        className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
      <div className="flex gap-2">
        <select value={source} onChange={e => setSource(e.target.value)}
          className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
          <option value="">Any source</option>
          {TRIGGER_SOURCES.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <input value={eventPattern} onChange={e => setEventPattern(e.target.value)} placeholder="Event pattern"
          className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
      </div>
      <div className="flex gap-2">
        <select value={template} onChange={e => setTemplate(e.target.value)}
          className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
          <option value="software_release">Software Release</option>
          <option value="incident_response">Incident Response</option>
          <option value="deployment">Deployment</option>
          <option value="security_review">Security Review</option>
          <option value="patch">Patch</option>
          <option value="infrastructure">Infrastructure</option>
        </select>
        <select value={priority} onChange={e => setPriority(e.target.value)}
          className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
          {["critical", "high", "medium", "low"].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-[0.65rem] text-[#6B7280]">
          <input type="number" value={cooldown} onChange={e => setCooldown(Number(e.target.value))}
            className="w-20 rounded-lg border border-[#E8EDF3] px-2 py-1.5 text-[0.72rem] outline-none" />
          Cooldown (s)
        </label>
        <label className="flex items-center gap-1.5 text-[0.65rem] text-[#6B7280]">
          <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)}
            className="rounded border-[#D1D5DB]" />
          Enabled
        </label>
      </div>
      <button onClick={() => onSubmit({ name, source, event_pattern: eventPattern, mission_template: template, priority, cooldown_seconds: cooldown, enabled })}
        disabled={!name}
        className="w-full rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
        {initial ? "Update Policy" : "Create Policy"}
      </button>
    </div>
  )
}

export default function AutonomousRuntimeCenter() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [simSource, setSimSource] = useState("github")
  const [simEvent, setSimEvent] = useState("push")
  const [simPayload, setSimPayload] = useState("{}")
  const [simResult, setSimResult] = useState<any>(null)

  const { data: policies } = useTriggerPolicies()
  const { data: history } = useTriggerHistory()
  const { data: stats } = useTriggerStats()
  const { data: sources } = useTriggerSources()
  const createMutation = useCreateTriggerPolicy()
  const updateMutation = useUpdateTriggerPolicy()
  const deleteMutation = useDeleteTriggerPolicy()
  const simulateMutation = useSimulateTrigger()

  const handleCreate = async (data: any) => {
    try {
      await createMutation.mutateAsync(data)
      setShowCreate(false)
    } catch (err) { console.error(err) }
  }

  const handleUpdate = async (data: any) => {
    if (!editingId) return
    try {
      await updateMutation.mutateAsync({ id: editingId, payload: data })
      setEditingId(null)
    } catch (err) { console.error(err) }
  }

  const handleDelete = async (id: string) => {
    try { await deleteMutation.mutateAsync(id) } catch (err) { console.error(err) }
  }

  const handleSimulate = async () => {
    setSimResult(null)
    try {
      const payload = JSON.parse(simPayload)
      const result = await simulateMutation.mutateAsync({ source: simSource, event_type: simEvent, payload })
      setSimResult(result)
    } catch (err) {
      setSimResult({ error: String(err) })
    }
  }

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: BarChart3 },
    { id: "policies", label: "Policies", icon: Radio },
    { id: "history", label: "History", icon: Clock },
    { id: "simulate", label: "Simulate", icon: Target },
  ]

  return (
    <CortexShell title="Autonomous Runtime" subtitle="Continuously observe events and auto-generate engineering missions">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">

        {/* ── Dashboard ── */}
        {activeTab === "dashboard" && (
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: Radio, label: "Policies", value: (stats as any)?.total_policies ?? policies?.length ?? "-", color: "bg-blue-500" },
                { icon: CheckCircle2, label: "Active", value: (stats as any)?.active_policies ?? "-", color: "bg-[#38B88A]" },
                { icon: Target, label: "Missions Generated", value: (stats as any)?.total_missions_generated ?? "-", color: "bg-purple-500" },
                { icon: Clock, label: "Events Processed", value: (stats as any)?.total_events_processed ?? "-", color: "bg-amber-500" },
              ].map((stat, i) => {
                const Icon = stat.icon
                return (
                  <motion.div key={i} variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg p-2.5 ${stat.color}`}><Icon className="h-4 w-4 text-white" /></div>
                      <div>
                        <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                        <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>

            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Active Trigger Policies</h3>
              {policies && policies.filter(p => p.enabled).length > 0 ? (
                <div className="space-y-2">
                  {policies.filter(p => p.enabled).slice(0, 5).map(p => (
                    <div key={p.policy_id} className="flex items-center justify-between rounded-lg border border-[#E8EDF3] px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Radio className="h-3.5 w-3.5 text-[#38B88A]" />
                        <span className="text-[0.65rem] font-medium text-[#111827]">{p.name}</span>
                        <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{p.source || "any"}</span>
                      </div>
                      <span className={`rounded px-1.5 py-0.5 text-[0.5rem] font-medium ${PRIORITY_COLORS[p.priority] || PRIORITY_COLORS.medium}`}>
                        {p.priority}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center py-8 text-[#9CA3AF]">
                  <Radio className="mb-2 h-8 w-8 opacity-30" />
                  <p className="text-xs">No active trigger policies.</p>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Recent Trigger Events</h3>
              {history?.history && history.history.length > 0 ? (
                <div className="space-y-2">
                  {history.history.slice(-5).reverse().map(e => (
                    <div key={e.entry_id} className="flex items-center justify-between rounded-lg border border-[#E8EDF3] px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block h-2 w-2 rounded-full ${e.status === "matched" || e.status === "generated" ? "bg-[#38B88A]" : e.status === "suppressed" ? "bg-orange-400" : "bg-red-400"}`} />
                        <span className="text-[0.6rem] font-medium text-[#111827]">{e.source}.{e.event_type}</span>
                        {e.policy_name && <span className="text-[0.5rem] text-[#9CA3AF]">→ {e.policy_name}</span>}
                      </div>
                      <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${STATUS_COLORS[e.status] || "text-gray-500 bg-gray-100"}`}>
                        {e.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center py-8 text-[#9CA3AF]">
                  <Clock className="mb-2 h-8 w-8 opacity-30" />
                  <p className="text-xs">No trigger events recorded yet.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ── Policies ── */}
        {activeTab === "policies" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex justify-end">
              <button onClick={() => { setShowCreate(!showCreate); setEditingId(null) }}
                className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
                <Plus className="h-3.5 w-3.5" /> {showCreate ? "Cancel" : "New Policy"}
              </button>
            </div>

            {showCreate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Trigger Policy</h3>
                <PolicyForm onSubmit={handleCreate} />
              </div>
            )}

            <div className="space-y-2">
              {policies?.map(p => (
                <div key={p.policy_id} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  {editingId === p.policy_id ? (
                    <div>
                      <h3 className="mb-3 text-sm font-bold text-[#111827]">Edit Policy</h3>
                      <PolicyForm onSubmit={handleUpdate} initial={p} />
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`inline-block h-2 w-2 rounded-full ${p.enabled ? "bg-[#38B88A]" : "bg-gray-300"}`} />
                          <h3 className="text-[0.82rem] font-bold text-[#111827]">{p.name}</h3>
                          <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${PRIORITY_COLORS[p.priority] || PRIORITY_COLORS.medium}`}>
                            {p.priority}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[0.6rem] text-[#6B7280]">{p.description || p.event_pattern || p.source || "No description"}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[0.5rem] text-[#9CA3AF]">
                          {p.source && <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5">{p.source}</span>}
                          {p.event_pattern && <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5">{p.event_pattern}</span>}
                          <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5">{p.mission_template}</span>
                          <span>{p.cooldown_seconds}s cooldown</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <button onClick={() => { setEditingId(p.policy_id); setShowCreate(false) }}
                          className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F4F7FA]">
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => {
                          handleUpdate({ id: p.policy_id, payload: { enabled: !p.enabled } } as any)
                        }}
                          className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F4F7FA]">
                          <RefreshCw className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => handleDelete(p.policy_id)}
                          className="rounded-lg p-1.5 text-red-400 hover:bg-red-50">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {(!policies || policies.length === 0) && (
                <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                  <Radio className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">No trigger policies configured. Create one to get started.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ── History ── */}
        {activeTab === "history" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {history?.history && history.history.length > 0 ? (
              history.history.slice().reverse().map(e => (
                <div key={e.entry_id} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block h-2 w-2 rounded-full ${e.status === "matched" || e.status === "generated" ? "bg-[#38B88A]" : e.status === "suppressed" ? "bg-orange-400" : "bg-red-400"}`} />
                        <span className="text-[0.72rem] font-medium text-[#111827]">{e.source}.{e.event_type}</span>
                        <span className={`rounded px-1.5 py-0.5 text-[0.45rem] font-medium ${STATUS_COLORS[e.status] || "text-gray-500 bg-gray-100"}`}>
                          {e.status}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[0.5rem] text-[#6B7280]">
                        {e.policy_name && <span>Policy: {e.policy_name}</span>}
                        {e.mission_id && <span>Mission: {e.mission_id}</span>}
                        {e.error && <span className="text-red-500">Error: {e.error}</span>}
                      </div>
                    </div>
                    <span className="shrink-0 text-[0.45rem] text-[#9CA3AF]">{new Date(e.timestamp).toLocaleString()}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Clock className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No trigger events recorded yet.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Simulate ── */}
        {activeTab === "simulate" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Simulate Trigger Event</h3>
              <div className="flex flex-wrap gap-3">
                <select value={simSource} onChange={e => setSimSource(e.target.value)}
                  className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                  {TRIGGER_SOURCES.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                </select>
                <input value={simEvent} onChange={e => setSimEvent(e.target.value)} placeholder="Event type (e.g. push)"
                  className="min-w-[120px] rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                <textarea value={simPayload} onChange={e => setSimPayload(e.target.value)} placeholder='Event payload JSON'
                  className="min-h-[80px] flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.72rem] outline-none font-mono" />
              </div>
              <button onClick={handleSimulate} disabled={simulateMutation.isPending}
                className="mt-3 flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                {simulateMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Target className="h-3.5 w-3.5" />}
                Simulate
              </button>
            </div>

            {simResult && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-5">
                <h3 className="mb-2 text-sm font-bold text-[#111827]">Simulation Result</h3>
                {simResult.error ? (
                  <div className="flex items-center gap-2 text-red-500">
                    <XCircle className="h-4 w-4" />
                    <span className="text-[0.72rem]">{simResult.error}</span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {(simResult.matched_policies ?? []).length > 0 ? (
                      <div>
                        <p className="mb-1 text-[0.65rem] font-medium text-[#38B88A]">Matched {simResult.matched_policies.length} policy(ies)</p>
                        {(simResult.matched_policies as any[]).map((mp: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-[0.65rem]">
                            <CheckCircle2 className="h-3.5 w-3.5 text-[#38B88A]" />
                            <span className="font-medium text-[#111827]">{mp.policy_name}</span>
                            <span className="text-[#6B7280]">({mp.source || "any"} / {mp.mission_template})</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-[#6B7280]">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="text-[0.72rem]">No policies matched this event.</span>
                      </div>
                    )}
                    <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-white p-3 text-[0.6rem] text-[#6B7280] font-mono">
                      {JSON.stringify(simResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
