import type { ForecastDataset, TrendPoint, ForecastState } from "./types"
import { generateId } from "./shared"

const datasets = new Map<string, ForecastDataset>()

export const ForecastPreparationEngine = {
  async prepareDataset(name: string, metricName: string, points: TrendPoint[], parameters: Record<string, unknown> = {}): Promise<ForecastDataset> {
    const dataset: ForecastDataset = {
      id: generateId("fds"),
      name,
      metricName,
      timeSeries: points,
      state: "preparing",
      normalized: false,
      parameters,
      createdAt: new Date().toISOString(),
    }
    datasets.set(dataset.id, dataset)
    return dataset
  },

  async buildTimeSeries(metricName: string, values: { timestamp: string; value: number }[]): Promise<TrendPoint[]> {
    return values.map((v) => ({
      timestamp: v.timestamp,
      value: v.value,
      label: new Date(v.timestamp).toISOString().split("T")[0],
    }))
  },

  async normalizeData(points: TrendPoint[]): Promise<TrendPoint[]> {
    const values = points.map((p) => p.value)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min

    if (range === 0) return points.map((p) => ({ ...p, value: 0 }))

    return points.map((p) => ({
      ...p,
      value: Number(((p.value - min) / range).toFixed(4)),
    }))
  },

  async validateForecastInput(datasetId: string): Promise<{ valid: boolean; errors: string[] }> {
    const dataset = datasets.get(datasetId)
    if (!dataset) return { valid: false, errors: ["Dataset not found"] }
    const errors: string[] = []
    if (dataset.timeSeries.length === 0) errors.push("Time series is empty")
    if (!dataset.metricName) errors.push("Metric name is required")
    if (!dataset.name) errors.push("Dataset name is required")
    const allNumbers = dataset.timeSeries.every((p) => typeof p.value === "number" && !isNaN(p.value))
    if (!allNumbers) errors.push("Time series contains non-numeric values")
    return { valid: errors.length === 0, errors }
  },

  async markReady(datasetId: string): Promise<ForecastDataset> {
    const dataset = datasets.get(datasetId)
    if (!dataset) throw new Error(`Dataset not found: ${datasetId}`)
    const updated: ForecastDataset = { ...dataset, state: "ready", normalized: true }
    datasets.set(datasetId, updated)
    return updated
  },

  async markFailed(datasetId: string): Promise<ForecastDataset> {
    const dataset = datasets.get(datasetId)
    if (!dataset) throw new Error(`Dataset not found: ${datasetId}`)
    const updated: ForecastDataset = { ...dataset, state: "failed" }
    datasets.set(datasetId, updated)
    return updated
  },

  async getDataset(id: string): Promise<ForecastDataset | null> {
    return datasets.get(id) ?? null
  },

  async listDatasets(metricName?: string): Promise<ForecastDataset[]> {
    let result = Array.from(datasets.values())
    if (metricName) result = result.filter((d) => d.metricName === metricName)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async datasetCount(): Promise<number> {
    return datasets.size
  },
}
