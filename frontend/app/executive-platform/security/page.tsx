"use client"

import { useLiveData, DataWidget, type AsyncResult } from "@/services/enterprise/liveHooks"
import { LiveDataService } from "@/services/enterprise/platformService"
import { GlassCard, StatusBadge } from "@/components/executive-platform/shared"
import { Lock, Users, Shield, Key, Building2, Eye, Activity } from "lucide-react"

export default function LiveSecurityCenter() {
  const users = useLiveData((s) => LiveDataService.getUsers(s), [], 30000)
  const roles = useLiveData((s) => LiveDataService.getRoles(s), [], 30000)
  const groups = useLiveData((s) => LiveDataService.getGroups(s), [], 30000)
  const orgs = useLiveData((s) => LiveDataService.getOrganizations(s), [], 30000)
  const apiKeys = useLiveData((s) => LiveDataService.getApiKeys(undefined, s), [], 30000)
  const secrets = useLiveData((s) => LiveDataService.getSecrets(s), [], 30000)

  const sections = [
    { icon: Users, label: "Users", result: users, key: "users" },
    { icon: Building2, label: "Organizations", result: orgs, key: "organizations" },
    { icon: Shield, label: "Groups", result: groups, key: "groups" },
    { icon: Key, label: "Roles", result: roles, key: "roles" },
    { icon: Activity, label: "API Keys", result: apiKeys, key: "api_keys" },
    { icon: Eye, label: "Secrets", result: secrets, key: "secrets" },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Lock className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Security Center</h1>
          <p className="text-xs text-white/40 mt-0.5">Live identity, access, and secrets management</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {sections.map((section) => (
          <GlassCard key={section.label}>
            <div className="flex items-center gap-2 mb-2">
              <section.icon className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-white/60">{section.label}</span>
            </div>
            <DataWidget result={section.result as AsyncResult<Record<string, unknown>>} skeletonLines={1} emptyMessage="0">
              {(data) => {
                const items = (data as Record<string, unknown>)[section.key] as Record<string, unknown>[] || []
                return <div className="text-xl font-semibold text-white/90">{items.length}</div>
              }}
            </DataWidget>
          </GlassCard>
        ))}
      </div>

      <GlassCard>
        <h2 className="text-sm font-medium text-white/60 mb-3">Active Users</h2>
        <DataWidget result={users} skeletonLines={3} emptyMessage="No users found">
          {(data) => {
            const items = (data as Record<string, unknown>).users as Record<string, unknown>[] || []
            if (items.length === 0) return <div className="text-sm text-white/20 py-4 text-center">No users registered</div>
            return (
              <div className="space-y-1">
                {items.map((u: Record<string, unknown>, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg border border-white/5 text-sm">
                    <Users className="w-4 h-4 text-white/30" />
                    <span className="text-white/70">{String(u.display_name || u.username || u.user_id)}</span>
                    <span className="text-xs text-white/30">{String(u.email || "")}</span>
                    <div className="ml-auto flex items-center gap-1.5">
                      {(u.role_ids as string[] || []).map((r: string) => <StatusBadge key={r} status="healthy" label={r} />)}
                      {u.is_active === false && <span className="text-[10px] text-red-400">Inactive</span>}
                    </div>
                  </div>
                ))}
              </div>
            )
          }}
        </DataWidget>
      </GlassCard>
    </div>
  )
}