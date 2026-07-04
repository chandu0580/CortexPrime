# CortexPrime v1.0.0 GA — User Guide

> **Version:** 1.0.0 GA  
> **Last Updated:** July 2026

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Executive Platform](#2-executive-platform)
3. [Mission Control](#3-mission-control)
4. [Replay Center](#4-replay-center)
5. [Developer Portal](#5-developer-portal)
6. [Workspaces](#6-workspaces)
7. [Notifications](#7-notifications)
8. [Keyboard Shortcuts](#8-keyboard-shortcuts)
9. [Preferences](#9-preferences)
10. [Dashboard Customization](#10-dashboard-customization)
11. [Frequently Asked Questions](#11-frequently-asked-questions)

---

## 1. Getting Started

### Logging In

1. Navigate to your organization's CortexPrime URL (e.g., `https://cortexprime.example.com`).
2. Enter your credentials (username/email and password) provided by your administrator.
3. Click **Sign In**.
4. If Single Sign-On (SSO) is enabled, you will be redirected to your identity provider.

### Navigating the Interface

The CortexPrime interface is organized into three primary zones:

- **Left Sidebar** — Workspace switcher, primary navigation, and quick-access tools.
- **Main Content Area** — The active workspace panel where all work occurs.
- **Top Bar** — Search, notifications, workspace selector, user menu, and preferences.

### Understanding the Workspace

CortexPrime provides five workspaces, each tailored to a specific role:

| Workspace | Purpose |
|-----------|---------|
| **Executive** | High-level command center, runtime status, agent monitoring |
| **Operations** | Mission creation, execution, and monitoring |
| **Engineering** | API exploration, SDK examples, code playground |
| **Security** | User management, API keys, role configuration |
| **Compliance** | Governance policies, approval workflows, audit trails |

---

## 2. Executive Platform

### Using the Command Center

The Executive Command Center provides a real-time overview of your CortexPrime deployment.

- **System Health** — CPU, memory, and throughput metrics for all runtimes.
- **Active Agents** — Cards showing each running agent, its status, and recent activity.
- **Mission Queue** — Pending, active, and completed missions with priority indicators.
- **Alert Feed** — Real-time stream of system events and notifications.

### Viewing Runtime Status

Navigate to **Executive > Runtime Status** to see:

- Runtime version and uptime
- Connected agent count
- Memory utilization trend
- Request throughput (requests/sec)
- Error rate and average latency

### Monitoring Agents

The Agent Monitor displays:

- Agent name, type, and version
- Current status (Idle, Running, Error, Offline)
- Active mission association
- Resource consumption (CPU, memory)
- Last heartbeat timestamp

Click any agent card to drill into its detailed view, which includes a live log stream and performance charts.

---

## 3. Mission Control

### Creating Missions

1. Navigate to **Operations > Missions**.
2. Click **New Mission**.
3. Configure the mission:
   - **Name** — A descriptive mission name.
   - **Description** — Optional context or goals.
   - **Objectives** — One or more objectives the mission will execute.
   - **Priority** — Low, Normal, High, or Critical.
   - **Agents** — Select which agents to assign.
   - **Timeout** — Maximum execution time.
4. Click **Create Mission**.

### Executing Objectives

Objectives are individual tasks within a mission. Each objective can be:

- A pre-built **template** (e.g., data analysis, report generation)
- A **custom prompt** written in natural language
- A **workflow** referencing an external pipeline

To execute:

1. Open a mission.
2. Click **Run** on any objective or **Run All** for the entire mission.
3. Monitor real-time output in the Objective Results panel.

### Monitoring Progress

The Mission Monitor provides:

- **Progress Bar** — Percentage complete per objective.
- **Status Icons** — Pending, Running, Succeeded, Failed, Cancelled.
- **Log Stream** — Live logs for each running objective.
- **Timeline** — Visual execution timeline showing start/end times.

### Viewing Results

Once a mission completes:

- **Summary** — Overall success/failure, duration, agent count.
- **Objective Results** — Expand each objective to see its output, metadata, and any generated artifacts.
- **Export** — Download results as JSON, CSV, or PDF.

---

## 4. Replay Center

### Accessing Replay Data

1. Navigate to **Operations > Replay Center**.
2. Browse the mission history list. Use filters for date range, status, agent, or mission name.
3. Click any mission to open its replay.

### Playing Back Missions

The replay player offers standard playback controls:

- **Play / Pause** — Start or pause the replay.
- **Step Forward / Backward** — Move one event at a time.
- **Speed Control** — 0.5x, 1x, 2x, 4x, 8x speed.
- **Timeline Scrubber** — Drag to any point in the mission's execution.

During playback, you see:

- Agent state changes in real time
- Decision points and branching
- Memory reads and writes
- Communication between agents

### Analyzing Decisions

The Decision Analysis panel highlights every decision made during a mission:

- **Decision ID** — Unique identifier.
- **Timestamp** — When the decision was made.
- **Agent** — Which agent made it.
- **Input** — Context and data available at the time.
- **Output** — The chosen action.
- **Confidence Score** — Model confidence percentage.
- **Alternatives** — Other options that were considered.

### Exporting Reports

From any replay, click **Export** to generate:

- **Summary Report (PDF)** — Executive summary with key decisions and outcomes.
- **Detailed Log (JSON)** — Complete event log for programmatic analysis.
- **Execution Graph (PNG/SVG)** — Visual representation of the mission execution flow.
- **Decision Report (CSV)** — All decisions in tabular format.

---

## 5. Developer Portal

### Using the API Explorer

1. Navigate to **Engineering > API Explorer**.
2. Select an endpoint from the sidebar.
3. Fill in request parameters, headers, and body.
4. Click **Send** to execute the request.
5. View the response body, headers, and status code.

The API Explorer automatically includes your authentication token and supports all HTTP methods.

### Using the WebSocket Explorer

1. Navigate to **Engineering > WebSocket Explorer**.
2. Enter the WebSocket URL (pre-populated with defaults).
3. Click **Connect**.
4. Subscribe to event types using the subscription panel.
5. View real-time events in the message log.

### Code Playground

The Code Playground lets you write and test Python, JavaScript, or Go code against live CortexPrime APIs:

- **Editor** — Syntax-highlighted code editor with autocompletion.
- **Libraries** — Pre-loaded SDK client libraries.
- **Output** — Real-time stdout/stderr and response display.
- **Templates** — Quick-start templates for common tasks.

### SDK Examples

Pre-built examples are available for:

- Python: `pip install cortexprime-sdk`
- JavaScript/TypeScript: `npm install cortexprime-sdk`
- Go: `go get github.com/cortexprime/sdk-go`

Each example demonstrates authentication, mission creation, and data retrieval.

---

## 6. Workspaces

Switch between workspaces using the left sidebar or the **Ctrl+1** through **Ctrl+5** shortcuts.

### Executive (Ctrl+1)
Command center, runtime dashboard, agent monitoring, system alerts.

### Operations (Ctrl+2)
Mission creation, execution monitoring, replay center, results export.

### Engineering (Ctrl+3)
API Explorer, WebSocket Explorer, Code Playground, SDK documentation.

### Security (Ctrl+4)
User management, role configuration, API key generation, secrets vault.

### Compliance (Ctrl+5)
Governance policies, approval workflows, audit logs, emergency stop.

---

## 7. Notifications

### Notification Types

| Type | Icon | Description |
|------|------|-------------|
| Mission Complete | ✅ | A mission has finished execution |
| Mission Failed | ❌ | A mission encountered an error |
| Agent Offline | ⚠️ | An agent has stopped responding |
| Approval Required | 🔔 | A governance approval is pending |
| System Alert | 🚨 | Critical system event detected |
| Security Event | 🔒 | Authentication or access change |

### Managing Preferences

1. Click your avatar in the top bar > **Notification Preferences**.
2. Toggle notification types on or off.
3. Choose delivery channels:
   - **In-App** — Bell icon badge and toast messages.
   - **Email** — Digest or immediate emails.
   - **Webhook** — POST to a custom URL.

### Priority Levels

| Level | Color | Behavior |
|-------|-------|----------|
| Critical | Red | Persistent alert, sound, email immediately |
| High | Orange | Toast notification, email within 5 min |
| Normal | Blue | Silent badge update, digest email |
| Low | Gray | Badge only, no email |

---

## 8. Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open Command Palette |
| `Ctrl+1` | Switch to Executive workspace |
| `Ctrl+2` | Switch to Operations workspace |
| `Ctrl+3` | Switch to Engineering workspace |
| `Ctrl+4` | Switch to Security workspace |
| `Ctrl+5` | Switch to Compliance workspace |
| `Ctrl+,` | Open Preferences |
| `Ctrl+Shift+N` | Open Notifications panel |
| `Ctrl+Shift+F` | Global search |
| `Ctrl+Shift+E` | Export current view |
| `Ctrl+?` | Show keyboard shortcuts help |
| `Esc` | Close current panel / dismiss modal |

### Navigation

| Shortcut | Action |
|----------|--------|
| `Ctrl+B` | Toggle left sidebar |
| `Ctrl+Shift+B` | Toggle right sidebar |
| `Alt+Left` | Go back in navigation history |
| `Alt+Right` | Go forward in navigation history |
| `Ctrl+Up` | Scroll to top of page |
| `Ctrl+Down` | Scroll to bottom of page |

### Mission Control

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New mission |
| `Ctrl+Shift+R` | Run selected mission |
| `Ctrl+Shift+S` | Stop running mission |
| `Ctrl+Shift+E` | Export mission results |
| `Ctrl+Shift+D` | Duplicate mission |

### Replay Controls

| Shortcut | Action |
|----------|--------|
| `Space` | Play / Pause replay |
| `Left` | Step backward |
| `Right` | Step forward |
| `Shift+Left` | Jump to previous decision point |
| `Shift+Right` | Jump to next decision point |
| `Ctrl+Left` | Jump to start of replay |
| `Ctrl+Right` | Jump to end of replay |
| `+` / `-` | Increase / decrease playback speed |
| `R` | Reset replay to beginning |

### Editing & Code Playground

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save current document |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+Shift+Enter` | Run code in playground |
| `Ctrl+L` | Clear output console |
| `Ctrl+Space` | Trigger autocomplete |

---

## 9. Preferences

### Accessing Preferences

Click your avatar in the top bar and select **Preferences**, or press **Ctrl+,**.

### Language

Select from supported languages:

- English (default)
- Spanish
- French
- German
- Japanese
- Chinese (Simplified)
- Korean

### Timezone

Choose your local timezone. All timestamps across the UI will adjust accordingly.

### Date Format

| Format | Example |
|--------|---------|
| `YYYY-MM-DD` | 2026-07-04 |
| `MM/DD/YYYY` | 07/04/2026 |
| `DD/MM/YYYY` | 04/07/2026 |
| `DD.MM.YYYY` | 04.07.2026 |

### Time Format

- 12-hour (AM/PM)
- 24-hour

### Notification Preferences

Configure which notification types trigger:
- In-app toast messages
- Sound alerts
- Badge counters
- Email digests (immediate, hourly, daily, or off)

### Theme Settings

- **Light** — Default light theme.
- **Dark** — Dark theme for low-light environments.
- **System** — Follow your operating system setting.
- **High Contrast** — Accessibility-optimized theme.
- **Custom** — Customize accent color, background, and font scale.

---

## 10. Dashboard Customization

### Adding Widgets

1. Enter **Edit Mode** by clicking the pencil icon or pressing `Ctrl+Shift+E`.
2. Click **+ Add Widget**.
3. Browse the widget gallery:
   - System Health gauge
   - Active Agents list
   - Mission throughput chart
   - Recent missions table
   - Alert feed
   - Resource utilization sparkline
   - Custom metric widget
4. Drag the widget to your desired position.
5. Click **Save Layout**.

### Removing Widgets

In Edit Mode, click the **×** icon in the top-right corner of any widget to remove it.

### Saving Layouts

- **Save** — Overwrites the current layout.
- **Save As** — Name and save multiple layouts for different contexts (e.g., "Daily Standup", "Incident Response").
- **Reset to Default** — Restore the factory layout.

### Importing / Exporting Layouts

- **Export** — Downloads your layout as a JSON file for sharing or backup.
- **Import** — Upload a previously exported layout JSON file.

---

## 11. Frequently Asked Questions

### 1. How do I reset my password?

Click **Forgot Password?** on the login page. You will receive a password reset link at your registered email address. If you are already logged in, go to **Preferences > Security > Change Password**.

### 2. Can I be logged in on multiple devices simultaneously?

Yes. CortexPrime supports concurrent sessions. You can be logged in on multiple browser tabs, desktop, and mobile devices at the same time.

### 3. How do I invite new users to my organization?

Go to **Security > Users > Invite User**. Enter the user's email address and select their role. An invitation email will be sent automatically.

### 4. What are the different user roles?

- **Admin** — Full access to all features, settings, and user management.
- **Developer** — Access to Engineering workspace, API keys, and SDK tools.
- **Operator** — Access to Operations workspace, missions, and replay.
- **Viewer** — Read-only access to dashboards and reports.
- **Compliance Officer** — Access to Compliance workspace, governance, and audit logs.

### 5. How long is mission data retained?

Mission execution data is retained for 90 days by default. Enterprise customers can configure retention policies up to 365 days. Exported reports are stored indefinitely in your account.

### 6. Can I schedule recurring missions?

Yes. When creating a mission, set the **Schedule** option to **Recurring** and choose a frequency (hourly, daily, weekly, monthly) and an optional end date.

### 7. How do I generate an API key?

Go to **Engineering > API Keys** (or **Security > API Keys** for Admin users). Click **Generate Key**, give it a name, select permissions, and copy the key immediately — it will not be shown again.

### 8. What happens when an agent goes offline?

If an agent stops sending heartbeats, an **Agent Offline** notification is triggered. The agent's missions are paused. Once the agent reconnects, missions can be resumed from the last checkpoint or restarted.

### 9. Is there a mobile app?

Yes. CortexPrime offers native mobile apps for iOS and Android. They provide read-only access to dashboards, mission status, and notifications. Full mission creation and management is available on desktop.

### 10. How do I export an audit log?

Go to **Compliance > Audit Log**. Use the date range and event type filters to narrow results, then click **Export** to download as CSV or JSON.

### 11. Can I customize the Command Palette?

Yes. The Command Palette (`Ctrl+K`) supports custom commands added via the **Developer Portal > Custom Commands** section. You can register commands that trigger API calls, run scripts, or navigate to specific views.

### 12. What browsers are supported?

- Google Chrome (latest 2 major versions)
- Mozilla Firefox (latest 2 major versions)
- Microsoft Edge (latest 2 major versions)
- Safari (latest 2 major versions)