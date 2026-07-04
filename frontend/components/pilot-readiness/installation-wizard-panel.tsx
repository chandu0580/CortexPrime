"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Container,
  Box,
  Ship,
  ShieldOff,
  ArrowLeft,
  ArrowRight,
  Check,
  Copy,
  ExternalLink,
  CheckCircle2,
  Terminal,
} from "lucide-react"
import Link from "next/link"

import { cn } from "@/utils/cn"
import { StatusBadge, SetupCard, WizardContainer } from "./shared"

const STEPS = [
  {
    icon: Container,
    title: "Docker Compose",
    description: "Deploy CortexPrime using Docker Compose for local development, testing, and single-server production environments.",
    code: `# Pull the latest images
docker pull cortexprime/api:latest
docker pull cortexprime/worker:latest
docker pull cortexprime/ui:latest

# Start all services
docker compose up -d

# Verify deployment
docker compose ps`,
    codeLanguage: "bash",
    codeLabel: "docker-compose.yml",
    codeSnippet: `version: "3.8"
services:
  api:
    image: cortexprime/api:latest
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://redis:6379
      - NEO4J_URL=bolt://neo4j:7687
  worker:
    image: cortexprime/worker:latest
    depends_on:
      - api
  ui:
    image: cortexprime/ui:latest
    ports:
      - "3000:3000"`,
    prerequisites: ["Docker Engine 24+", "Docker Compose v2+", "4 GB RAM minimum", "10 GB free disk space"],
    summary: "Docker Compose deployment configured",
  },
  {
    icon: Box,
    title: "Kubernetes",
    description: "Deploy CortexPrime on any Kubernetes cluster using kubectl for production-grade orchestration and auto-scaling.",
    code: `# Create namespace
kubectl create namespace cortexprime

# Apply core manifests
kubectl apply -f https://cortexprime.io/deploy/k8s/namespace.yaml
kubectl apply -f https://cortexprime.io/deploy/k8s/configmap.yaml
kubectl apply -f https://cortexprime.io/deploy/k8s/secrets.yaml

# Deploy services
kubectl apply -f https://cortexprime.io/deploy/k8s/api-deployment.yaml
kubectl apply -f https://cortexprime.io/deploy/k8s/worker-deployment.yaml
kubectl apply -f https://cortexprime.io/deploy/k8s/ui-deployment.yaml

# Verify
kubectl get pods -n cortexprime`,
    codeLanguage: "bash",
    codeLabel: "deployment.yaml",
    codeSnippet: `apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortexprime-api
  namespace: cortexprime
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cortexprime-api
  template:
    metadata:
      labels:
        app: cortexprime-api
    spec:
      containers:
      - name: api
        image: cortexprime/api:latest
        ports:
        - containerPort: 8080`,
    prerequisites: ["Kubernetes cluster 1.28+", "kubectl configured", "8 GB RAM minimum (3 nodes)", "Persistent volumes for databases"],
    summary: "Kubernetes deployment configured",
  },
  {
    icon: Ship,
    title: "Helm",
    description: "Install CortexPrime using Helm charts for customizable, repeatable deployments with version management.",
    code: `# Add Helm repository
helm repo add cortexprime https://helm.cortexprime.io/stable
helm repo update

# Install with custom values
helm install cortexprime cortexprime/cortexprime \\
  --namespace cortexprime \\
  --create-namespace \\
  --set global.environment=production \\
  --set api.replicas=3 \\
  --set worker.replicas=5 \\
  --set persistence.enabled=true

# Verify installation
helm list -n cortexprime
kubectl get all -n cortexprime`,
    codeLanguage: "bash",
    codeLabel: "values.yaml",
    codeSnippet: `global:
  environment: production
  logLevel: info

api:
  replicas: 3
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"

worker:
  replicas: 5
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"

persistence:
  enabled: true
  storageClass: standard`,
    prerequisites: ["Helm 3.12+", "Kubernetes cluster 1.28+", "Tiller removed (Helm 3 only)", "StorageClass configured"],
    summary: "Helm chart deployed",
  },
  {
    icon: ShieldOff,
    title: "Air-Gapped Installation",
    description: "Deploy CortexPrime in air-gapped or offline environments with no internet access using pre-packaged artifacts.",
    code: `# On internet-connected machine:
docker pull cortexprime/api:latest
docker pull cortexprime/worker:latest
docker pull cortexprime/ui:latest
docker pull cortexprime/redis:7
docker pull cortexprime/neo4j:5

# Save images to tarball
docker save cortexprime/api:latest \\
  cortexprime/worker:latest \\
  cortexprime/ui:latest \\
  cortexprime/redis:7 \\
  cortexprime/neo4j:5 \\
  -o cortexprime-images.tar

# Transfer tar to air-gapped machine, then:
docker load -i cortexprime-images.tar

# Verify all images loaded
docker images | grep cortexprime`,
    codeLanguage: "bash",
    codeLabel: "Offline Verification",
    codeSnippet: `# Verify all images present
for img in api worker ui redis neo4j; do
  docker image inspect cortexprime/$img:latest > /dev/null 2>&1 \\
    && echo "✅ $img loaded" \\
    || echo "❌ $img missing"
done

# Check disk space
df -h /var/lib/docker

# Start services offline
docker compose -f docker-compose.airgap.yml up -d`,
    prerequisites: ["Docker Engine 24+", "Air-gapped network isolated", "Pre-packaged image tarball (approx 8 GB)", "USB or physical media transfer option"],
    summary: "Air-gapped deployment prepared",
  },
]

const slideVariants = {
  enter: (direction: number) => ({ x: direction > 0 ? 300 : -300, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({ x: direction > 0 ? -300 : 300, opacity: 0 }),
}

function CodeBlock({ code, language, label }: { code: string; language?: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-[18px] overflow-hidden border border-[#E8EDF3]">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1F2937] border-b border-[#374151]">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-[#9CA3AF]" />
          <span className="text-xs text-[#9CA3AF] font-mono">{language || label || "bash"}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-[#9CA3AF] hover:text-white transition-colors duration-150"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-[#38B88A]" />
              <span className="text-[#38B88A]">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy commands</span>
            </>
          )}
        </button>
      </div>
      <pre className="bg-[#111827] text-[#E5E7EB] p-4 overflow-x-auto text-sm font-mono leading-relaxed max-h-52 overflow-y-auto">
        <code>{code}</code>
      </pre>
    </div>
  )
}

export function InstallationWizardPanel() {
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(0)
  const [completed, setCompleted] = useState(false)

  const current = STEPS[step]
  const Icon = current.icon
  const total = STEPS.length

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

  const progress = ((step + 1) / total) * 100

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
            <h3 className="text-xl font-bold text-[#111827] mb-2">Installation Complete</h3>
            <p className="text-sm text-[#6B7280] max-w-md mx-auto">
              All deployment methods have been reviewed. Your CortexPrime installation is ready for configuration.
            </p>
          </div>
          <div className="flex flex-col items-center gap-3">
            <div className="grid grid-cols-2 gap-3 w-full max-w-sm">
              {STEPS.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[#111827] bg-[#F4F7FA] rounded-xl px-3 py-2">
                  <CheckCircle2 className="w-4 h-4 text-[#38B88A] shrink-0" />
                  {s.title}
                </div>
              ))}
            </div>
          </div>
          <CodeBlock
            code={`# Quick verification
docker compose ps
# or
kubectl get pods -n cortexprime
# or
helm list -n cortexprime

# Check API health
curl http://localhost:8080/health`}
            language="bash"
            label="Quick Verification Commands"
          />
          <div className="pt-2">
            <Link
              href="/developer-portal/deployment-guide"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[#38B88A] hover:text-[#2F9F77] transition-colors duration-150"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open Deployment Guide
            </Link>
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
          <h2 className="text-lg font-bold text-[#111827]">Installation Wizard</h2>
          <span className="text-xs font-medium text-[#38B88A]">{Math.round(progress)}%</span>
        </div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#6B7280]">
            Step {step + 1} of {total} — {current.title}
          </span>
          <StatusBadge tone={step === total - 1 ? "healthy" : "running"} label={step === total - 1 ? "Final Step" : "In Progress"} />
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
            {/* Method Header */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#E8F5EE] flex items-center justify-center shrink-0">
                <Icon className="w-6 h-6 text-[#38B88A]" />
              </div>
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-[#111827]">{current.title}</h3>
                <p className="text-sm text-[#6B7280] mt-1">{current.description}</p>
              </div>
            </div>

            {/* Code Block */}
            <CodeBlock code={current.code} language={current.codeLanguage} />

            {/* YAML Snippet */}
            <div>
              <h4 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-2">Example {current.codeLabel}</h4>
              <CodeBlock code={current.codeSnippet} language="yaml" label={current.codeLabel} />
            </div>

            {/* Prerequisites */}
            <div>
              <h4 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-2">Prerequisites</h4>
              <div className="space-y-1">
                {current.prerequisites.map((prereq) => (
                  <div key={prereq} className="flex items-center gap-2 text-sm text-[#6B7280]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#38B88A] shrink-0" />
                    {prereq}
                  </div>
                ))}
              </div>
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