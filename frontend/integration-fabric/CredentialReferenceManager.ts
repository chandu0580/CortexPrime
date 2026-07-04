import type { CredentialReference } from "./types"
import { generateId } from "./shared"

const credentials = new Map<string, CredentialReference>()

export const CredentialReferenceManager = {
  async registerReference(
    name: string,
    connectorId: string,
    type: string,
    reference: string,
    endpointId: string | null = null,
    expiresAt: string | null = null,
  ): Promise<CredentialReference> {
    if (Array.from(credentials.values()).some((c) => c.name === name && c.connectorId === connectorId && c.revokedAt === null)) {
      throw new Error(`Credential reference already exists: ${name}`)
    }
    const id = generateId("cred")
    const ref: CredentialReference = {
      id,
      name,
      connectorId,
      endpointId,
      type,
      reference,
      expiresAt,
      createdAt: new Date().toISOString(),
      rotatedAt: null,
      revokedAt: null,
      valid: true,
    }
    credentials.set(id, ref)
    return ref
  },

  async rotateReference(credentialId: string, newReference: string): Promise<CredentialReference> {
    const ref = credentials.get(credentialId)
    if (!ref) throw new Error(`Credential reference not found: ${credentialId}`)
    const updated: CredentialReference = {
      ...ref,
      reference: newReference,
      rotatedAt: new Date().toISOString(),
      valid: true,
    }
    credentials.set(credentialId, updated)
    return updated
  },

  async revokeReference(credentialId: string): Promise<CredentialReference> {
    const ref = credentials.get(credentialId)
    if (!ref) throw new Error(`Credential reference not found: ${credentialId}`)
    const updated: CredentialReference = {
      ...ref,
      revokedAt: new Date().toISOString(),
      valid: false,
    }
    credentials.set(credentialId, updated)
    return updated
  },

  async validateReference(credentialId: string): Promise<{ valid: boolean; reason: string }> {
    const ref = credentials.get(credentialId)
    if (!ref) return { valid: false, reason: "Credential reference not found" }
    if (ref.revokedAt) return { valid: false, reason: "Credential reference has been revoked" }
    if (ref.expiresAt && new Date(ref.expiresAt) < new Date()) return { valid: false, reason: "Credential reference has expired" }
    if (!ref.valid) return { valid: false, reason: "Credential reference is marked invalid" }
    return { valid: true, reason: "Credential reference is valid" }
  },

  async getReference(credentialId: string): Promise<CredentialReference | null> {
    return credentials.get(credentialId) ?? null
  },

  async listReferences(connectorId?: string): Promise<CredentialReference[]> {
    let result = Array.from(credentials.values())
    if (connectorId) result = result.filter((c) => c.connectorId === connectorId)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async credentialCount(): Promise<number> {
    return credentials.size
  },
}
