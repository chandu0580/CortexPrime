"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Building2,
  Lock,
  Cpu,
  Database,
  GitBranch,
  MessageSquare,
  Plug,
  Shield,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Copy,
  Check,
  Eye,
  EyeOff,
  Download,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, WizardContainer } from "./shared"

interface ConfigField {
  label: string
  value: string
  masked?: boolean
  description: string
}

interface ConfigStep {
  icon: typeof Building2
  title: string
  description: string
  fields: ConfigField[]
  status: "healthy" | "running" | "pending"
}

const STEPS: ConfigStep[] = [
  {
    icon: Building2,
    title: "Organization",
    description: "Configure your organization profile, domain, and subscription plan.",
    status: "healthy",
    fields: [
      { label: "Organization Name", value: "Acme Corp", description: "Your company or team name displayed across the platform." },
      { label: "Domain", value: "acme.cortexprime.io", description: "Custom domain for your CortexPrime instance." },
      { label: "Plan", value: "Enterprise", description: "Current subscription tier with full feature access." },
    ],
  },
  {
    icon: Lock,
    title: "Authentication",
    description: "Configure authentication providers, JWT settings, and SSO integration.",
    status: "healthy",
    fields: [
      { label: "JWT Secret", value: "sk-••••••••••••••••", masked: true, description: "Secret key used to sign and verify JWT tokens." },
      { label: "Token Expiry", value: "24 hours", description: "Duration before authentication tokens expire and require refresh." },
      { label: "OAuth Provider", value: "Azure AD", description: "Primary OAuth identity provider for SSO login." },
      { label: "SSO URL", value: "https://login.acme.com/saml", description: "SAML/SSO endpoint for single sign-on authentication." },
    ],
  },
  {
    icon: Cpu,
    title: "LLM Provider",
    description: "Configure AI model provider connection, API keys, and rate limits.",
    status: "healthy",
    fields: [
      { label: "Provider", value: "OpenAI", description: "AI language model provider powering agent intelligence." },
      { label: "Model", value: "GPT-4 Turbo", description: "Active model version used for agent reasoning and generation." },
      { label: "API Key", value: "sk-••••••••••••••••••••", masked: true, description: "Authentication key for the LLM provider API." },
      { label: "Rate Limit", value: "10,000 req/min", description: "Maximum API requests per minute allowed by the provider." },
    ],
  },
  {
    icon: Database,
    title: "Redis",
    description: "Configure Redis connection for caching, session management, and pub/sub messaging.",
    status: "healthy",
    fields: [
      { label: "Host", value: "redis.internal:6379", description: "Redis server hostname and port for cache and session store." },
      { label: "Port", value: "6379", description: "TCP port for Redis connections." },
      { label: "Password", value: "••••••••••••", masked: true, description: "Redis authentication password." },
      { label: "DB Index", value: "0", description: "Redis database index for data isolation." },
    ],
  },
  {
    icon: GitBranch,
    title: "Neo4j",
    description: "Configure Neo4j graph database for knowledge graph and relationship storage.",
    status: "healthy",
    fields: [
      { label: "URI", value: "bolt://neo4j.internal:7687", description: "Bolt protocol URI for Neo4j graph database connection." },
      { label: "Username", value: "neo4j", description: "Database user for authentication." },
      { label: "Password", value: "••••••••••••", masked: true, description: "Neo4j database password." },
      { label: "Database", value: "cortexprime", description: "Active database name for knowledge graph storage." },
    ],
  },
  {
    icon: MessageSquare,
    title: "RabbitMQ",
    description: "Configure RabbitMQ message broker for agent communication and task queuing.",
    status: "healthy",
    fields: [
      { label: "Host", value: "rabbit.internal:5672", description: "RabbitMQ server hostname and port." },
      { label: "Port", value: "5672", description: "AMQP protocol port for message broker." },
      { label: "VHost", value: "/cortexprime", description: "Virtual host for queue and exchange isolation." },
      { label: "Username", value: "cortexprime", description: "Message broker authentication user." },
    ],
  },
  {
    icon: Plug,
    title: "Connectors",
    description: "Configure external service connectors for tool integration and data access.",
    status: "healthy",
    fields: [
      { label: "GitHub", value: "Connected", description: "GitHub integration for code repository access." },
      { label: "Jira", value: "Connected", description: "Jira integration for issue tracking and project management." },
      { label: "Slack", value: "Connected", description: "Slack integration for notifications and collaboration." },
      { label: "Teams", value: "Connected", description: "Microsoft Teams integration for enterprise messaging." },
      { label: "ServiceNow", value: "Connected", description: "ServiceNow integration for IT service management." },
      { label: "Confluence", value: "Connected", description: "Confluence integration for knowledge base access." },
      { label: "Notion", value: "Connected", description: "Notion integration for workspace and documentation." },
      { label: "Azure DevOps", value: "Connected", description: "Azure DevOps integration for CI/CD pipelines." },
    ],
  },
  {
    icon: Shield,
    title: "Security",
    description: "Configure access control, auditing, and security policies.",
    status: "healthy",
    fields: [
      { label: "RBAC", value: "Enabled", description: "Role-Based Access Control for user permission management." },
      { label: "ABAC", value: "Enabled", description: "Attribute-Based Access Control for fine-grained policy enforcement." },
      { label: "Audit Level", value: "Detailed", description: "Verbosity level for security audit logging." },
      { label: "Session Timeout", value: "30 minutes", description: "Maximum idle time before automatic session termination." },
    ],
  },
]

const slideVariants = {
  enter: (direction: number) => ({ x: direction > 0 ? 300 : -300, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({ x: direction > 0 ? -300 : 300, opacity: 0 }),
}

function ConfigFieldRow({ field }: { field: ConfigField }) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div className="flex items-start gap-4 py-2.5 border-b border-[#E8EDF3] last:border-b-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-[#111827]">{field.label}</span>
          {field.masked && (
            <button
              onClick={() => setRevealed(!revealed)}
              className="p-0.5 rounded text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
            >
              {revealed ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
            </button>
          )}
        </div>
        <p className="text-xs text-[#6B7280] mt-0.5">{field.description}</p>
      </div>
      <div className="shrink-0 min-w-[140px] text-right">
        <span className="text-sm font-semibold text-[#111827] font-mono">
          {field.masked && !revealed ? field.value : field.value}
        </span>
      </div>
    </div>
  )
}

export function ConfigurationWizardPanel() {
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(0)
  const [completed, setCompleted] = useState(false)

  const current = STEPS[step]
  const Icon = current.icon
  const total = STEPS.length
  const progress = ((step + 1) / total) * 100

  const goNext = () => {
    if (step < total - 1) {
      setDirection(1)
      setStep((s) => s + 1)
    } else {
      setCompleted(true)
    }
  }

  const goBack = () => {
    if (step > 0) {
      setDirection(-1)
      setStep((s) => s - 1)
    }
  }

  const handleExportJson = () => {
    const config = STEPS.reduce<Record<string, Record<string, string>>>((acc, section) => {
      acc[section.title] = section.fields.reduce<Record<string, string>>((fields, f) => {
        fields[f.label] = f.value
        return fields
      }, {})
      return acc
    }, {})
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "cortexprime-configuration.json"
    a.click()
    URL.revokeObjectURL(url)
  }

  if (completed) {
    return (
      <WizardContainer>
        <div className="p-8 text-center space-y-6">
          <div className="flex justify-center">
            <div className="w-20 h-20 rounded-full bg-[#E8F5EE] flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10 text-[#38B88A]" />
            </div>
          </div>
          <div>
            <h3 className="text-xl font-bold text-[#111827] mb-2">Configuration Complete</h3>
            <p className="text-sm text-[#6B7280] max-w-md mx-auto">
              All 8 configuration sections have been reviewed. Your environment is fully configured and ready for deployment validation.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-w-lg mx-auto">
            {STEPS.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-[#111827] bg-[#F4F7FA] rounded-xl px-2.5 py-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#38B88A] shrink-0" />
                {s.title}
              </div>
            ))}
          </div>
          <div className="flex justify-center">
            <button
              onClick={handleExportJson}
              className="flex items-center gap-2 px-5 py-2.5 rounded-[18px] text-sm font-medium bg-[#38B88A] text-white hover:bg-[#2F9F77] transition-colors duration-150"
            >
              <Download className="w-4 h-4" />
              Export Configuration as JSON
            </button>
          </div>
        </div>
      </WizardContainer>
    )
  }

  return (
    <WizardContainer>
      {/* Progress */}
      <div className="px-6 pt-6 pb-2">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold text-[#111827]">Environment Configuration</h2>
          <span className="text-xs font-medium text-[#38B88A]">{Math.round(progress)}%</span>
        </div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#6B7280]">
            Step {step + 1} of {total} — {current.title}
          </span>
          <StatusBadge tone={current.status} label={current.status === "healthy" ? "Configured" : "Pending"} />
        </div>
        <div className="w-full h-1.5 bg-[#E8EDF3] rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-[#38B88A]"
            initial={false}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="px-6 pb-6">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={step}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="space-y-5 pt-4"
          >
            {/* Section Header */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#E8F5EE] flex items-center justify-center shrink-0">
                <Icon className="w-6 h-6 text-[#38B88A]" />
              </div>
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-[#111827]">{current.title}</h3>
                <p className="text-sm text-[#6B7280] mt-1">{current.description}</p>
              </div>
            </div>

            {/* Config Fields */}
            <div className="border border-[#E8EDF3] rounded-[18px] divide-y divide-[#E8EDF3]">
              {current.fields.map((field) => (
                <div key={field.label} className="px-4">
                  <ConfigFieldRow field={field} />
                </div>
              ))}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-[#E8EDF3] bg-[#F4F7FA]">
        <div>
          {step > 0 && (
            <button
              onClick={goBack}
              className="flex items-center gap-1.5 px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-white hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          )}
        </div>
        <button
          onClick={goNext}
          className="flex items-center gap-1.5 px-5 py-2 rounded-[18px] text-sm font-medium bg-[#38B88A] text-white hover:bg-[#2F9F77] transition-colors duration-150"
        >
          {step < total - 1 ? (
            <>
              Next
              <ArrowRight className="w-4 h-4" />
            </>
          ) : (
            <>
              Complete
              <CheckCircle2 className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </WizardContainer>
  )
}