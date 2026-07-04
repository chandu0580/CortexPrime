import { TestStatus, type ConnectorEventResult } from "./types"

export const ConnectorEventValidator = {
  async validateEventNaming(events: string[]): Promise<{ valid: boolean; invalidNames: string[] }> {
    const invalidNames = events.filter((e) => !e.match(/^[a-z]+\.[a-z]+(\.[a-z]+)*$/))
    return { valid: invalidNames.length === 0, invalidNames }
  },

  async validateEventCategory(events: string[], validCategories: string[]): Promise<{ valid: boolean; invalidCategories: string[] }> {
    const invalidCategories = events.filter((e) => {
      const category = e.split(".")[0]
      return !validCategories.includes(category)
    })
    return { valid: invalidCategories.length === 0, invalidCategories }
  },

  async validate(
    events: string[],
    validCategories: string[],
  ): Promise<ConnectorEventResult> {
    const errors: string[] = []
    const namingResult = await this.validateEventNaming(events)
    if (!namingResult.valid) errors.push(`invalid event names: ${namingResult.invalidNames.join(", ")}`)

    const categoryResult = await this.validateEventCategory(events, validCategories)
    if (!categoryResult.valid) errors.push(`invalid event categories: ${categoryResult.invalidCategories.join(", ")}`)

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      eventNamingValid: namingResult.valid,
      eventPublishingSupported: events.length > 0,
      eventCategoryValid: categoryResult.valid,
      payloadConsistent: namingResult.valid,
      eventsPublished: events,
      status,
      errors,
    }
  },
}