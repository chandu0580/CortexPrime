import type { LiveKitConfig, LiveKitConnectionState } from "./types"

export interface LiveKitParticipant {
  id: string
  identity: string
  name: string
  state: string
  audioTracks: string[]
  dataTracks: string[]
}

export interface LiveKitRoom {
  name: string
  sid: string
  state: string
  participants: LiveKitParticipant[]
  createdAt: string
}

export interface LiveKitTrack {
  sid: string
  kind: string
  source: string
  publisher: string
}

const rooms = new Map<string, LiveKitRoom>()
const connections = new Map<string, LiveKitConnectionState>()
const participants = new Map<string, LiveKitParticipant[]>()

export const LiveKitManager = {
  async joinRoom(config: LiveKitConfig, roomName: string, identity: string): Promise<LiveKitRoom> {
    const connectionKey = `${roomName}:${identity}`
    connections.set(connectionKey, "connecting")

    try {
      const room: LiveKitRoom = {
        name: roomName,
        sid: `room_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
        state: "connected",
        participants: [],
        createdAt: new Date().toISOString(),
      }

      rooms.set(roomName, room)
      participants.set(roomName, [])
      connections.set(connectionKey, "connected")

      return room
    } catch (err) {
      connections.set(connectionKey, "error" as LiveKitConnectionState as LiveKitConnectionState)
      throw err
    }
  },

  async leaveRoom(roomName: string, identity: string): Promise<void> {
    const connectionKey = `${roomName}:${identity}`
    connections.delete(connectionKey)
    rooms.delete(roomName)
    participants.delete(roomName)
  },

  async getRoom(roomName: string): Promise<LiveKitRoom | null> {
    return rooms.get(roomName) ?? null
  },

  async getConnectionState(roomName: string, identity: string): Promise<LiveKitConnectionState> {
    const connectionKey = `${roomName}:${identity}`
    return connections.get(connectionKey) ?? "disconnected"
  },

  async getParticipants(roomName: string): Promise<LiveKitParticipant[]> {
    return participants.get(roomName) ?? []
  },

  async addParticipant(roomName: string, participant: LiveKitParticipant): Promise<void> {
    const roomParticipants = participants.get(roomName) ?? []
    const existingIndex = roomParticipants.findIndex((p) => p.id === participant.id)
    if (existingIndex >= 0) {
      roomParticipants[existingIndex] = participant
    } else {
      roomParticipants.push(participant)
    }
    participants.set(roomName, roomParticipants)
  },

  async removeParticipant(roomName: string, participantId: string): Promise<void> {
    const roomParticipants = participants.get(roomName) ?? []
    const filtered = roomParticipants.filter((p) => p.id !== participantId)
    participants.set(roomName, filtered)
  },

  async publishAudioTrack(roomName: string, participantId: string, trackSid: string): Promise<void> {
    const roomParticipants = participants.get(roomName) ?? []
    const participant = roomParticipants.find((p) => p.id === participantId)
    if (participant) {
      participant.audioTracks.push(trackSid)
    }
  },

  async unpublishAudioTrack(roomName: string, participantId: string, trackSid: string): Promise<void> {
    const roomParticipants = participants.get(roomName) ?? []
    const participant = roomParticipants.find((p) => p.id === participantId)
    if (participant) {
      participant.audioTracks = participant.audioTracks.filter((t) => t !== trackSid)
    }
  },

  async subscribeToTrack(roomName: string, trackSid: string): Promise<LiveKitTrack> {
    return {
      sid: trackSid,
      kind: "audio",
      source: "microphone",
      publisher: "remote",
    }
  },

  async unsubscribeFromTrack(trackSid: string): Promise<void> {
    // Cleanup subscription
    void trackSid
  },

  async reconnect(roomName: string, identity: string): Promise<boolean> {
    const connectionKey = `${roomName}:${identity}`
    connections.set(connectionKey, "reconnecting")

    try {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      connections.set(connectionKey, "connected")
      return true
    } catch {
      connections.set(connectionKey, "error" as LiveKitConnectionState)
      return false
    }
  },

  async getActiveRooms(): Promise<LiveKitRoom[]> {
    return Array.from(rooms.values()).filter((r) => r.state === "connected")
  },

  async getRoomCount(): Promise<number> {
    return rooms.size
  },

  async getParticipantCount(roomName: string): Promise<number> {
    const roomParticipants = participants.get(roomName) ?? []
    return roomParticipants.length
  },

  async cleanup(): Promise<void> {
    rooms.clear()
    connections.clear()
    participants.clear()
  },
}
