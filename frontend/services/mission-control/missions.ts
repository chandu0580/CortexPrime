import type { Mission, MissionId, MissionSummary } from "@/types/mission-control"

export interface MissionsFilter {
  status?: string
  priority?: string
  search?: string
  page?: number
  limit?: number
}

export async function getMissions(_filter?: MissionsFilter): Promise<MissionSummary[]> {
  // TODO: fetch from runtime service, normalize into MissionSummary[]
  return []
}

export async function getMission(id: MissionId): Promise<Mission | null> {
  // TODO: fetch from runtime service, normalize into Mission
  return null
}
