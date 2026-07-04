import type { Mission, MissionId } from "@/types/mission-control"

export interface PlanInput {
  title: string
  description: string
  priority: string
  tags?: string[]
}

export async function planMission(_input: PlanInput): Promise<Mission | null> {
  // TODO: submit goal to planner, receive decomposed mission plan
  return null
}

export async function getPlan(_missionId: MissionId): Promise<Mission | null> {
  // TODO: retrieve saved plan for a mission
  return null
}
