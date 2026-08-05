# 3 — Project Installation Procedure

**Project:** CortexPrime — AI-Native Enterprise Operations Intelligence Platform
**Reg. No:** 24BMMCA023  **Name:** Chandu S

---

## Purpose

This document is the index for the installation package. It tells an evaluator
what is included, what order to read it in, and what to expect once the project
is running.

---

## Contents of this submission

| # | Document | Format | What it covers |
|---|---|---|---|
| **3.1** | Supporting Software | PDF / Word | Every piece of software required, with versions and where to obtain it |
| **3.2** | User ID and Passwords | *(submitted separately)* | Login credentials for the running system |
| **3.3** | Readme | **Word file** | Step-by-step instructions to install and run the project |

**Read them in this order: 3.1 → 3.3 → 3.2.**

Install the software first, follow the Readme to set the project up, then use
the credentials sheet to log in.

---

## What the project is

CortexPrime is a DevOps operations platform. It monitors a running software
system, detects real production problems, explains the root cause with
supporting evidence, and proposes or applies a fix — with every risky action
gated behind human approval.

It is not a monitoring dashboard. The distinguishing behaviour is the complete
loop:

> **detect a real problem → explain why it happened → recommend or take the fix
> → verify it worked**

Ten detectors are implemented, each following that loop end to end:

| # | Detector | Detects | Proposed fix |
|---|---|---|---|
| 1 | Deploy regression | Error-rate or latency spike after a deployment | Roll back to last known-good |
| 2 | Docker container health | Crash-loops, OOM kills | Restart the container |
| 3 | Credential expiry | Tokens and certificates nearing expiry | Alert with renewal steps |
| 4 | Vulnerability | Dependabot security alerts | Automated dependency-bump PR |
| 5 | Branch protection | Missing reviews or CI checks | Enable minimum protection |
| 6 | LLM cost anomaly | Provider spend spike | Temporarily disable the provider |
| 7 | Flaky test | Intermittently failing tests | Quarantine and report |
| 8 | Alert correlation | Duplicate alerts across sources | Deduplicate into one incident |
| 9–10 | Additional infrastructure detectors | — | — |

---

## Architecture at a glance

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16, React 19, Tailwind CSS |
| **Backend** | Python 3.13, FastAPI, async SQLAlchemy |
| **Database** | PostgreSQL 16 with the pgvector extension |
| **Cache / messaging** | Redis 7.2 |
| **Integrations** | Docker, GitHub, GitLab, Jira, Prometheus |
| **AI** | OpenAI, Anthropic, Google, Azure OpenAI (pluggable) |

The codebase is approximately **157,000 lines** across **698 Python modules**,
with around **3,000 automated tests**.

---

## Installation summary

The full procedure is in **3.3 — Readme**. In outline:

1. Install Python 3.13, Node.js 20, and Docker Desktop
2. Create a Python virtual environment and install dependencies
3. Install frontend dependencies with `npm install`
4. Copy `.env.example` to `.env` and fill in five required settings
5. Generate a login password hash
6. Start PostgreSQL and Redis via Docker
7. Create the database tables with Alembic
8. Start the backend, then the frontend, in two terminals
9. Open `http://localhost:3000` and log in

**Estimated time: 15–20 minutes on a machine with the prerequisites installed.**

---

## What the evaluator will see

| Address | Purpose |
|---|---|
| `http://localhost:3000` | The application — Executive Dashboard with all ten detector panels |
| `http://localhost:8000/docs` | Interactive API documentation for every endpoint |
| `http://localhost:8000/health` | Service health check |

The Readme includes an optional demonstration: creating a deliberately
crash-looping Docker container so the container-health detector can be seen
firing on real data rather than sample output.

---

## Notes for the evaluator

**The project works against real systems, not simulated data.** The Docker
detector reads the actual Docker daemon on the machine; the Jira integration
files real tickets when configured. Detectors that need an external service
(Jira, GitHub, Prometheus) show a clear "not configured" state rather than
failing, so the project runs fully without any external account.

**AI provider keys are optional.** The platform starts and every detector runs
without them. They enable the natural-language root-cause explanations only.

**Approval gating is active by default.** Any fix classified above low risk
waits for human approval in the Approval Center before executing. This is
deliberate and is a core part of the design.
