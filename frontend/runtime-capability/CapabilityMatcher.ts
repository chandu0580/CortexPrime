import type { CapabilityRequirement, CapabilityMatch, CapabilityDescriptor } from "./types"

export const CapabilityMatcher = {
  async match(requirement: CapabilityRequirement, descriptor: CapabilityDescriptor): Promise<CapabilityMatch> {
    const matchedFeatures: string[] = []
    const unmatchedFeatures: string[] = []

    for (const feature of requirement.requiredFeatures) {
      if (descriptor.features.some((f) => f.toLowerCase() === feature.toLowerCase())) {
        matchedFeatures.push(feature)
      } else {
        unmatchedFeatures.push(feature)
      }
    }

    const precision = matchedFeatures.length === requirement.requiredFeatures.length && requirement.requiredFeatures.length > 0
      ? "exact"
      : matchedFeatures.length > 0
        ? "partial"
        : requirement.requiredFeatures.length === 0
          ? "exact"
          : "none"

    const versionCompare = compareVersions(
      requirement.minVersion,
      descriptor.version,
    )

    const versionCompatible = versionCompare !== "incompatible"
    const versionMatch = versionCompare

    const crossTrainPrecision: "exact" | "partial" | "cross_train" | "none" =
      precision === "none" && descriptor.capability !== requirement.requiredCapability
        ? "cross_train"
        : precision

    return {
      descriptorId: descriptor.id,
      workerId: "",
      precision: crossTrainPrecision,
      matchedFeatures,
      unmatchedFeatures,
      versionCompatible,
      versionMatch,
    }
  },
}

function compareVersions(required: string, available: string): "exact" | "major" | "minor" | "incompatible" {
  const reqParts = required.split(".").map(Number)
  const availParts = available.split(".").map(Number)

  if (reqParts.length === 0 || availParts.length === 0) return "incompatible"

  if (reqParts[0] !== availParts[0]) return "incompatible"
  if (reqParts[1] !== availParts[1]) return "major"
  if (reqParts[2] !== availParts[2]) return "minor"
  return "exact"
}
