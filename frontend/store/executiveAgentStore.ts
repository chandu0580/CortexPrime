import { create } from "zustand"
import { executiveAgent, type ExecutiveAgentState } from "@/services/intelligence/executiveAgent"

interface ExecutiveAgentStore extends ExecutiveAgentState {
  startAgent: () => void
  stopAgent: () => void
  markRead: (id: string) => void
  dismissNotification: (id: string) => void
  dismissSuggestion: (id: string) => void
}

export const useExecutiveAgentStore = create<ExecutiveAgentStore>((set, get) => {
  const sync = (state: ExecutiveAgentState) => set({ ...state })

  return {
    notifications: [],
    suggestions: [],
    missionPreparations: [],
    timeline: [],
    conversationContext: null,
    lastMonitoredAt: null,
    monitoring: false,

    startAgent: () => {
      if (get().monitoring) return
      executiveAgent.subscribe(sync)
      executiveAgent.startMonitoring()
    },

    stopAgent: () => {
      executiveAgent.stopMonitoring()
    },

    markRead: (id: string) => {
      executiveAgent.markRead(id)
      set({ notifications: executiveAgent.getNotifications() })
    },

    dismissNotification: (id: string) => {
      executiveAgent.dismissNotification(id)
      set({ notifications: executiveAgent.getNotifications() })
    },

    dismissSuggestion: (id: string) => {
      executiveAgent.dismissSuggestion(id)
      set({ suggestions: executiveAgent.getSuggestions() })
    },
  }
})