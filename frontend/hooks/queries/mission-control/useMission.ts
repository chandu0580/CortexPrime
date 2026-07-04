"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getMission } from "@/services/mission-control"
import type { MissionId } from "@/types/mission-control"

export function useMission(id: MissionId | null) {
    return useQuery({
        queryKey: queryKeys.missionControl.mission(id ?? ""),
        queryFn: () => getMission(id!),
        enabled: id != null,
    })
}
