import { TeamMeeting, MeetingStatus } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiMeeting(api: Record<string, unknown>, teamId: string): TeamMeeting {
  return {
    id: String(api.id),
    teamId,
    channelId: String(api.channelId ?? ""),
    organizerId: (() => {
      try {
        const participants = api.participants as Record<string, unknown>[] | undefined
        if (!participants) return ""
        const organizer = participants.find((p) => (p.role as string) === "organizer")
        const identity = organizer?.identity as Record<string, unknown> | undefined
        const user = identity?.user as Record<string, unknown> | undefined
        return String(user?.id ?? organizer?.userId ?? "")
      } catch { return "" }
    })(),
    subject: String(api.subject ?? ""),
    description: String(api.description ?? ""),
    status: (api.status as string ?? "scheduled").toLowerCase() as MeetingStatus,
    startTime: String(api.startDateTime ?? ""),
    endTime: api.endDateTime as string ?? null,
    participants: [],
    recording: null,
    joinUrl: String(api.joinUrl ?? api.joinWebUrl ?? ""),
    createdAt: String(api.creationDateTime ?? api.createdDateTime ?? ""),
    updatedAt: String(api.lastModifiedDateTime ?? ""),
  }
}

export const TeamsMeetingManager = {
  async scheduleMeeting(subject: string, description: string = "", startTime: string, endTime: string): Promise<TeamMeeting | null> {
    const userId = "me"
    const body = { subject, description, startDateTime: startTime, endDateTime: endTime }
    const result = await TeamsClient.post<Record<string, unknown>>(`/users/${userId}/onlineMeetings`, body)
    if (result.success && result.data) return mapApiMeeting(result.data, "")
    return null
  },

  async getMeeting(meetingId: string): Promise<TeamMeeting | null> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/users/me/onlineMeetings/${meetingId}`)
    if (result.success && result.data) return mapApiMeeting(result.data, "")
    return null
  },

  async listMeetings(): Promise<TeamMeeting[]> {
    const result = await TeamsClient.get<Record<string, unknown>>("/users/me/onlineMeetings?$top=100")
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((m) => mapApiMeeting(m, ""))
    }
    return []
  },

  async endMeeting(meetingId: string): Promise<boolean> {
    const result = await TeamsClient.delete(`/users/me/onlineMeetings/${meetingId}`)
    return result.success
  },
}