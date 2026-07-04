import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const SlackCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "slack-workspaces",
    name: "slack.workspaces",
    description: "Manage Slack workspaces",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "slack-channels",
    name: "slack.channels",
    description: "Manage Slack channels",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "slack-messaging",
    name: "slack.messaging",
    description: "Send and manage Slack messages",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "slack-notifications",
    name: "slack.notifications",
    description: "Dispatch Slack notifications",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "slack-workflows",
    name: "slack.workflows",
    description: "Manage Slack workflows",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "slack-permissions",
    name: "slack.permissions",
    description: "Evaluate Slack permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const SlackCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...SlackCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return SlackCapabilityDefinitions.find((d) => d.name === name)
  },
}