"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getMissions } from "@/services/mission-control"
import type { MissionsFilter } from "@/services/mission-control"

export function useMissionList(filter?: MissionsFilter) {
    return useQuery({
        queryKey: [...queryKeys.missionControl.missions(), filter].filter(Boolean),
        queryFn: () => getMissions(filter),
    })
}
