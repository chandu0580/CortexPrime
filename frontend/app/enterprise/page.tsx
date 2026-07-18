"use client"

import { motion } from "framer-motion"
import { useMissions } from "@/hooks/queries/useMissions"
import { useAgents } from "@/hooks/queries/useAgents"
import { useHealthStatus } from "@/hooks/queries/useAgents"
import { Target, Bot, CheckCircle, AlertTriangle, Activity } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/enterprise/ui"
import MissionCard from "./dashboard/MissionCard"
import StatsCard from "./dashboard/StatsCard"
import ActivityFeed from "./dashboard/ActivityFeed"

const container = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } }
const item = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }

export default function EnterpriseDashboard() {
  const { data: missionsData } = useMissions()
  const { data: agentsData } = useAgents()
  const { data: health } = useHealthStatus()
  const missions = missionsData?.missions ?? []
  const agents = agentsData?.agents ?? []

  const activeMissions = missions.filter((m) => m.status === "running")
  const completedMissions = missions.filter((m) => m.status === "completed")
  const failedMissions = missions.filter((m) => m.status === "failed")

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6 max-w-7xl">
      <motion.div variants={item}>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Executive Dashboard</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">
          Real-time overview of autonomous operations
        </p>
      </motion.div>

      <motion.div variants={item} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard icon={Target} label="Active Missions" value={activeMissions.length} color="accent" />
        <StatsCard icon={Bot} label="Available Agents" value={agents.length} color="info" />
        <StatsCard icon={CheckCircle} label="Completed" value={completedMissions.length} color="success" />
        <StatsCard icon={AlertTriangle} label="Failed" value={failedMissions.length} color="danger" />
      </motion.div>

      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Missions</CardTitle>
              <Activity className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {missions.slice(0, 5).map((m) => (
                <MissionCard key={m.mission_id} mission={m} />
              ))}
              {missions.length === 0 && (
                <p className="type-body-sm text-[var(--text-muted)] text-center py-6">
                  No missions yet. Start one from Mission Center.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <ActivityFeed missions={missions} agents={agents} health={health} />
      </motion.div>
    </motion.div>
  )
}
