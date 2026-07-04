"use client"

import { useState } from "react"
import {
  Users,
  Play,
  Square,
  Activity,
  Clock,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Zap,
  Sliders,
  Timer,
} from "lucide-react"
import { StatusBadge, KpiCard, SectionHeader } from "./shared"

interface ScenarioPreset {
  name: string
  users: number
  missions: number
  workers: number
  connectors: number
  duration: number
}

const presets: ScenarioPreset[] = [
  { name: "Light Load", users: 50, missions: 5, workers: 2, connectors: 1, duration: 30 },
  { name: "Medium Load", users: 500, missions: 20, workers: 10, connectors: 5, duration: 60 },
  { name: "Heavy Load", users: 2000, missions: 50, workers: 25, connectors: 10, duration: 120 },
  { name: "Enterprise Peak", users: 5000, missions: 100, workers: 50, connectors: 20, duration: 300 },
]

const durations = [
  { label: "30s", value: 30 },
  { label: "60s", value: 60 },
  { label: "120s", value: 120 },
  { label: "300s", value: 300 },
  { label: "600s", value: 600 },
]

const latencyHistogram = [
  { bucket: "<50ms", count: 1420 },
  { bucket: "100ms", count: 890 },
  { bucket: "200ms", count: 520 },
  { bucket: "500ms", count: 210 },
  { bucket: "1000ms", count: 85 },
  { bucket: "2000ms+", count: 23 },
]

const maxHistoCount = Math.max(...latencyHistogram.map((h) => h.count))

export default function LoadTestingPanel() {
  const [users, setUsers] = useState(100)
  const [missions, setMissions] = useState(10)
  const [workers, setWorkers] = useState(5)
  const [connectors, setConnectors] = useState(3)
  const [duration, setDuration] = useState(60)
  const [isRunning, setIsRunning] = useState(false)
  const [hasResults, setHasResults] = useState(false)

  const applyPreset = (p: ScenarioPreset) => {
    setUsers(p.users)
    setMissions(p.missions)
    setWorkers(p.workers)
    setConnectors(p.connectors)
    setDuration(p.duration)
  }

  const runTest = () => {
    setIsRunning(true)
    setHasResults(false)
    setTimeout(() => {
      setIsRunning(false)
      setHasResults(true)
    }, 2500)
  }

  const stopTest = () => {
    setIsRunning(false)
    setHasResults(true)
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Load Testing" subtitle="Configure and run load tests against the system" />

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
        <SectionHeader title="Scenario Configuration" />

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
              Concurrent Users: {users}
            </label>
            <input
              type="range"
              min={10}
              max={5000}
              value={users}
              onChange={(e) => setUsers(Number(e.target.value))}
              className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>10</span>
              <span>5,000</span>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
              Concurrent Missions: {missions}
            </label>
            <input
              type="range"
              min={1}
              max={100}
              value={missions}
              onChange={(e) => setMissions(Number(e.target.value))}
              className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>1</span>
              <span>100</span>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
              Concurrent Workers: {workers}
            </label>
            <input
              type="range"
              min={1}
              max={50}
              value={workers}
              onChange={(e) => setWorkers(Number(e.target.value))}
              className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>1</span>
              <span>50</span>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">
              Concurrent Connectors: {connectors}
            </label>
            <input
              type="range"
              min={1}
              max={20}
              value={connectors}
              onChange={(e) => setConnectors(Number(e.target.value))}
              className="w-full h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-[#38B88A]"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>1</span>
              <span>20</span>
            </div>
          </div>
        </div>

        <div className="mb-6">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Duration</label>
          <div className="flex gap-2">
            {durations.map((d) => (
              <button
                key={d.value}
                onClick={() => setDuration(d.value)}
                className={`px-4 py-2 text-sm font-medium rounded-xl border transition-colors ${
                  duration === d.value
                    ? "border-[#38B88A] bg-emerald-50 text-[#38B88A]"
                    : "border-[#E8EDF3] text-gray-600 hover:border-gray-300"
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 mb-6">
          {isRunning ? (
            <button
              onClick={stopTest}
              className="px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <Square size={16} /> Stop Test
            </button>
          ) : (
            <button
              onClick={runTest}
              className="px-6 py-2.5 bg-[#38B88A] hover:bg-emerald-600 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2"
            >
              <Play size={16} /> Run Test
            </button>
          )}
          {isRunning && (
            <span className="text-sm text-amber-600 font-medium flex items-center gap-1.5">
              <Activity size={14} className="animate-pulse" /> Test in progress...
            </span>
          )}
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Scenario Presets</label>
          <div className="grid grid-cols-4 gap-3">
            {presets.map((p) => (
              <button
                key={p.name}
                onClick={() => applyPreset(p)}
                className="p-3 rounded-xl border border-[#E8EDF3] hover:border-[#38B88A] hover:bg-emerald-50/30 text-left transition-colors"
              >
                <span className="text-sm font-semibold text-gray-900 block">{p.name}</span>
                <span className="text-xs text-gray-400">{p.users} users · {p.duration}s</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {(hasResults || isRunning) && (
        <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-5 shadow-sm">
          <SectionHeader
            title="Test Results"
            subtitle={isRunning ? "Collecting data..." : "Load test completed"}
            action={
              <StatusBadge status={isRunning ? "injecting" : "passed"} label={isRunning ? "Running" : "Completed"} />
            }
          />

          <div className="grid grid-cols-4 gap-4 mb-6">
            <KpiCard title="TPS" value="245" icon={<Zap size={16} />} />
            <KpiCard title="Avg Latency" value="342ms" icon={<Clock size={16} />} />
            <KpiCard title="P99 Latency" value="1,240ms" icon={<AlertTriangle size={16} />} />
            <KpiCard title="Failure Rate" value="0.12%" icon={<BarChart3 size={16} />} />
          </div>

          <div className="mb-6">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Latency Distribution</h4>
            <div className="flex items-end gap-3 h-28">
              {latencyHistogram.map((h) => (
                <div key={h.bucket} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-lg transition-all duration-500"
                    style={{
                      height: `${(h.count / maxHistoCount) * 100}%`,
                      backgroundColor: h.bucket === "2000ms+" ? "#EF4444" : "#38B88A",
                      opacity: 0.8,
                    }}
                  />
                  <span className="text-[10px] text-gray-400">{h.bucket}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-50 border border-emerald-200">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={20} className="text-emerald-600" />
              <div>
                <span className="text-sm font-semibold text-emerald-800">Recovery</span>
                <p className="text-xs text-emerald-600">All systems recovered in 3.2s</p>
              </div>
            </div>
            <StatusBadge status="healthy" label="All Systems OK" />
          </div>
        </div>
      )}
    </div>
  )
}