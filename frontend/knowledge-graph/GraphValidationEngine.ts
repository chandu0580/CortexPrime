import { EntityManager } from "./EntityManager"
import { RelationshipManager } from "./RelationshipManager"
import { GraphManager } from "./GraphManager"
import { GraphInferenceEngine } from "./GraphInferenceEngine"

export interface GraphValidation {
  valid: boolean
  totalEntities: number
  totalRelationships: number
  brokenLinks: string[]
  duplicateEntities: string[][]
  invalidRelationships: string[]
  cycles: number
  orphanNodes: string[]
  consistencyScore: number
  validatedAt: string
}

export const GraphValidationEngine = {
  async validate(): Promise<GraphValidation> {
    const entities = await EntityManager.getAll()
    const activeEntities = entities.filter((e) => e.status === "active")
    const relationships = await RelationshipManager.getAll()

    const brokenLinks = await this.detectBrokenLinks()
    const duplicates = await this.detectDuplicateEntities()
    const invalidRels = await this.detectInvalidRelationships()
    const cycles = await GraphInferenceEngine.detectCycles()
    const orphans = await GraphManager.findOrphanNodes()

    const totalIssues = brokenLinks.length + duplicates.length + invalidRels.length + cycles.length + orphans.length
    const totalChecks = activeEntities.length + relationships.length
    const consistencyScore = totalChecks > 0
      ? Math.round(((totalChecks - totalIssues) / Math.max(totalChecks, 1)) * 100)
      : 100

    return {
      valid: totalIssues === 0,
      totalEntities: activeEntities.length,
      totalRelationships: relationships.length,
      brokenLinks,
      duplicateEntities: duplicates,
      invalidRelationships: invalidRels,
      cycles: cycles.length,
      orphanNodes: orphans,
      consistencyScore,
      validatedAt: new Date().toISOString(),
    }
  },

  async detectBrokenLinks(): Promise<string[]> {
    const relationships = await RelationshipManager.getAll()
    const broken: string[] = []

    for (const rel of relationships) {
      const source = await EntityManager.findEntity(rel.sourceId)
      const target = await EntityManager.findEntity(rel.targetId)

      if (!source) broken.push(`Relationship ${rel.id}: source entity ${rel.sourceId} not found`)
      else if (source.status !== "active") broken.push(`Relationship ${rel.id}: source entity ${rel.sourceId} has status '${source.status}'`)

      if (!target) broken.push(`Relationship ${rel.id}: target entity ${rel.targetId} not found`)
      else if (target.status !== "active") broken.push(`Relationship ${rel.id}: target entity ${rel.targetId} has status '${target.status}'`)
    }

    return broken
  },

  async detectDuplicateEntities(): Promise<string[][]> {
    return EntityManager.findDuplicates()
  },

  async detectInvalidRelationships(): Promise<string[]> {
    const relationships = await RelationshipManager.getAll()
    const invalid: string[] = []

    for (const rel of relationships) {
      if (rel.sourceId === rel.targetId) {
        invalid.push(`Relationship ${rel.id}: self-referential (${rel.sourceId} -> ${rel.targetId})`)
      }
      if (rel.weight < 0 || rel.weight > 1) {
        invalid.push(`Relationship ${rel.id}: weight ${rel.weight} out of range [0, 1]`)
      }
      if (rel.confidence < 0 || rel.confidence > 1) {
        invalid.push(`Relationship ${rel.id}: confidence ${rel.confidence} out of range [0, 1]`)
      }
    }

    return invalid
  },

  async detectGraphInconsistencies(): Promise<string[]> {
    const nodes = await GraphManager.getAllNodes()
    const edges = await GraphManager.getAllEdges()
    const issues: string[] = []

    for (const edge of edges) {
      const sourceExists = nodes.some((n) => n.id === edge.sourceNodeId)
      const targetExists = nodes.some((n) => n.id === edge.targetNodeId)
      if (!sourceExists) issues.push(`Edge ${edge.id}: source node ${edge.sourceNodeId} missing from graph`)
      if (!targetExists) issues.push(`Edge ${edge.id}: target node ${edge.targetNodeId} missing from graph`)
    }

    return issues
  },
}
