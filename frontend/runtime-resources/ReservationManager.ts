import type { ResourceReservation } from "./types"
import { generateId } from "./shared"

const reservations = new Map<string, ResourceReservation>()

export const ReservationManager = {
  async createReservation(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    startAt: string,
    endAt: string,
  ): Promise<ResourceReservation> {
    const reservation: ResourceReservation = {
      id: generateId("reservation"),
      poolId,
      workerId,
      sessionId,
      amount,
      startAt,
      endAt,
      confirmed: false,
      createdAt: new Date().toISOString(),
    }
    reservations.set(reservation.id, reservation)
    return reservation
  },

  async getReservation(id: string): Promise<ResourceReservation | null> {
    return reservations.get(id) ?? null
  },

  async confirmReservation(id: string): Promise<ResourceReservation> {
    const reservation = reservations.get(id)
    if (!reservation) throw new Error(`Reservation not found: ${id}`)
    const updated: ResourceReservation = { ...reservation, confirmed: true }
    reservations.set(id, updated)
    return updated
  },

  async cancelReservation(id: string): Promise<void> {
    reservations.delete(id)
  },

  async getSessionReservations(sessionId: string): Promise<ResourceReservation[]> {
    return Array.from(reservations.values()).filter((r) => r.sessionId === sessionId)
  },

  async getPendingReservations(): Promise<ResourceReservation[]> {
    return Array.from(reservations.values()).filter((r) => !r.confirmed)
  },

  async getUpcomingReservations(): Promise<ResourceReservation[]> {
    const now = new Date()
    return Array.from(reservations.values()).filter((r) => new Date(r.startAt) > now)
  },

  async getActiveReservationCount(): Promise<number> {
    return reservations.size
  },
}
