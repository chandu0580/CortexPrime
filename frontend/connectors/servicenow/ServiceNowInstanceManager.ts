import { ServiceNowInstance } from "./types"
import { ServiceNowAuth } from "./ServiceNowAuth"
import { ServiceNowClient } from "./ServiceNowClient"

export const ServiceNowInstanceManager = {
  async validateInstance(): Promise<boolean> {
    const result = await ServiceNowClient.get("/table/sys_user?sysparm_limit=1")
    return result.success
  },

  async getInstance(): Promise<ServiceNowInstance | null> {
    const inst = await ServiceNowAuth.getInstance()
    if (!inst) return null
    return { id: inst, name: inst, url: `https://${inst}.service-now.com`, version: "", description: "", archived: false, createdAt: "", updatedAt: "" }
  },

  async listInstances(): Promise<ServiceNowInstance[]> {
    const inst = await this.getInstance()
    return inst ? [inst] : []
  },
}