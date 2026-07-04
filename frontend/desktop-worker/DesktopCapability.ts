import type { PlatformCapability, PlatformCapabilityType } from "@/platform/contracts"
import type { DesktopActionType, DesktopCapabilityConfig } from "./types"

const DEFAULT_DESKTOP_CAPABILITY_CONFIG: DesktopCapabilityConfig = {
  id: "desktop.capability",
  name: "Desktop Capability",
  type: "desktop",
  version: "1.0.0",
  features: [],
  enabled: true,
  supportedActions: [
    "mouse_move", "mouse_click", "mouse_double_click", "mouse_right_click",
    "mouse_drag", "mouse_drop", "mouse_scroll",
    "keyboard_type", "keyboard_combination", "keyboard_shortcut", "keyboard_hotkey",
    "keyboard_paste", "keyboard_copy",
    "window_list", "window_focus", "window_minimize", "window_maximize",
    "window_restore", "window_close",
    "desktop_screenshot", "descreen_info", "desktop_monitor_info",
    "clipboard_read", "clipboard_write", "clipboard_clear",
    "file_create", "file_move", "file_rename", "file_copy", "file_delete",
    "file_upload", "file_download", "file_search",
    "dialog_open", "dialog_save", "dialog_file_picker",
    "app_launch", "app_apply", "app_list", "app_activate",
  ],
  maxSessions: 3,
  supportsScreenshots: true,
  supportsFileOperations: true,
  supportsClipboard: true,
  supportsDialogs: true,
  supportsApplications: true,
}

export class DesktopCapability {
  private readonly config: DesktopCapabilityConfig

  constructor(config?: Partial<DesktopCapabilityConfig>) {
    this.config = { ...DEFAULT_DESKTOP_CAPABILITY_CONFIG, ...config }
  }

  getId(): string { return this.config.id }
  getName(): string { return this.config.name }
  getMaxSessions(): number { return this.config.maxSessions }
  getSupportedActions(): DesktopActionType[] { return [...this.config.supportedActions] }
  isEnabled(): boolean { return this.config.enabled }
  setEnabled(enabled: boolean): void { this.config.enabled = enabled }
  supportsScreenshots(): boolean { return this.config.supportsScreenshots }
  supportsFileOperations(): boolean { return this.config.supportsFileOperations }
  supportsClipboard(): boolean { return this.config.supportsClipboard }
  supportsDialogs(): boolean { return this.config.supportsDialogs }
  supportsApplications(): boolean { return this.config.supportsApplications }

  supportsAction(action: DesktopActionType): boolean {
    return this.config.supportedActions.includes(action)
  }

  toPlatformCapability(): PlatformCapability {
    return {
      id: this.config.id,
      name: this.config.name,
      type: this.config.type as PlatformCapabilityType,
      version: this.config.version,
      features: [...this.config.features],
      enabled: this.config.enabled,
    }
  }

  static createDefault(): DesktopCapability {
    return new DesktopCapability()
  }
}