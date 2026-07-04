import type { PlatformCapability } from "@/platform/contracts"
import type { BrowserBrowserType, BrowserActionType, BrowserExtractionFormat } from "./types"

export interface BrowserCapabilityConfig extends PlatformCapability {
  browserType: BrowserBrowserType
  maxSessions: number
  supportedActions: BrowserActionType[]
  supportedExtractionFormats: BrowserExtractionFormat[]
}

const DEFAULT_BROWSER_CAPABILITY_CONFIG: BrowserCapabilityConfig = {
  id: "browser.capability",
  name: "Browser Capability",
  type: "browser",
  version: "1.0.0",
  features: [],
  enabled: true,
  browserType: "chromium",
  maxSessions: 5,
  supportedActions: [
    "navigate", "click", "doubleClick", "hover", "focus", "blur",
    "fill", "type", "press", "check", "uncheck", "select",
    "dragAndDrop", "scroll", "upload", "download", "extract",
    "screenshot", "evaluate", "wait", "back", "forward", "reload",
    "close", "pdf", "cookie_read", "cookie_write", "cookie_clear",
  ],
  supportedExtractionFormats: [
    "text", "html", "attribute", "table", "json", "markdown",
    "screenshot", "links", "images", "forms",
  ],
}

export class BrowserCapability {
  private readonly config: BrowserCapabilityConfig

  constructor(config?: Partial<BrowserCapabilityConfig>) {
    this.config = { ...DEFAULT_BROWSER_CAPABILITY_CONFIG, ...config }
  }

  getId(): string {
    return this.config.id
  }

  getName(): string {
    return this.config.name
  }

  getBrowserType(): BrowserBrowserType {
    return this.config.browserType
  }

  getMaxSessions(): number {
    return this.config.maxSessions
  }

  getSupportedActions(): BrowserActionType[] {
    return [...this.config.supportedActions]
  }

  getSupportedExtractionFormats(): BrowserExtractionFormat[] {
    return [...this.config.supportedExtractionFormats]
  }

  isEnabled(): boolean {
    return this.config.enabled
  }

  setEnabled(enabled: boolean): void {
    this.config.enabled = enabled
  }

  supportsAction(action: BrowserActionType): boolean {
    return this.config.supportedActions.includes(action)
  }

  supportsExtractionFormat(format: BrowserExtractionFormat): boolean {
    return this.config.supportedExtractionFormats.includes(format)
  }

  supportsFeature(feature: string): boolean {
    return this.config.features.includes(feature)
  }

  toPlatformCapability(): PlatformCapability {
    return {
      id: this.config.id,
      name: this.config.name,
      type: this.config.type,
      version: this.config.version,
      features: [...this.config.features],
      enabled: this.config.enabled,
    }
  }

  static createChromium(overrides?: Partial<BrowserCapabilityConfig>): BrowserCapability {
    return new BrowserCapability({ ...overrides, browserType: "chromium", id: "browser.capability.chromium", name: "Chromium Browser Capability" })
  }

  static createFirefox(overrides?: Partial<BrowserCapabilityConfig>): BrowserCapability {
    return new BrowserCapability({ ...overrides, browserType: "firefox", id: "browser.capability.firefox", name: "Firefox Browser Capability" })
  }

  static createWebKit(overrides?: Partial<BrowserCapabilityConfig>): BrowserCapability {
    return new BrowserCapability({ ...overrides, browserType: "webkit", id: "browser.capability.webkit", name: "WebKit Browser Capability" })
  }

  static createDefault(): BrowserCapability {
    return new BrowserCapability()
  }
}
