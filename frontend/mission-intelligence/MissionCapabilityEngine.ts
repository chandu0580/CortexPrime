import type { MissionAnalysis } from "@/types/intelligence"
import type { MissionCapability } from "./types"

function generateId(): string {
  return `cap-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

const capabilityCatalog: Record<string, { description: string; alternatives: string[] }> = {
  "Data Analysis": {
    description: "Extract insights and patterns from structured and unstructured data",
    alternatives: ["Business Intelligence", "Statistical Analysis", "Reporting"],
  },
  "Process Automation": {
    description: "Automate repetitive workflows and business processes",
    alternatives: ["Workflow Orchestration", "RPA"],
  },
  "Knowledge Retrieval": {
    description: "Search, retrieve, and synthesize information from knowledge bases",
    alternatives: ["Semantic Search", "Document Intelligence"],
  },
  "Conversational AI": {
    description: "Natural language interaction and dialogue management",
    alternatives: ["Chat Interface", "Voice Assistant"],
  },
  "Monitoring & Alerting": {
    description: "Real-time system monitoring and automated alerting",
    alternatives: ["Observability Platform", "Incident Detection"],
  },
  "Task Execution": {
    description: "Autonomous execution of defined tasks and workflows",
    alternatives: ["Scripted Automation", "Job Scheduler"],
  },
  "Research & Analysis": {
    description: "Systematic research and analysis of topics and domains",
    alternatives: ["Market Research", "Competitive Analysis"],
  },
  "Document Processing": {
    description: "Extract, classify, and process documents at scale",
    alternatives: ["OCR Pipeline", "Document Understanding"],
  },
}

export const MissionCapabilityEngine = {
  async recommendCapabilities(analysis: MissionAnalysis): Promise<MissionCapability[]> {
    const capabilities: MissionCapability[] = []

    for (const suggested of analysis.preview.suggestedCapabilities) {
      const catalog = capabilityCatalog[suggested]
      if (catalog) {
        capabilities.push({
          id: `cap-${generateId()}`,
          name: suggested,
          description: catalog.description,
          required: true,
          confidence: 0.85,
          alternatives: catalog.alternatives,
        })
      } else {
        capabilities.push({
          id: `cap-${generateId()}`,
          name: suggested,
          description: `Enterprise capability for ${suggested.toLowerCase()}`,
          required: true,
          confidence: 0.7,
          alternatives: [],
        })
      }
    }

    capabilities.push({
      id: `cap-${generateId()}`,
      name: "Project Governance",
      description: "Structured oversight, reporting, and decision management",
      required: true,
      confidence: 0.9,
      alternatives: ["Agile Coaching", "PMO Support"],
    })

    capabilities.push({
      id: `cap-${generateId()}`,
      name: "Quality Assurance",
      description: "Systematic validation and verification of deliverables",
      required: false,
      confidence: 0.75,
      alternatives: ["Automated Testing", "Manual Review"],
    })

    return capabilities
  },
}
