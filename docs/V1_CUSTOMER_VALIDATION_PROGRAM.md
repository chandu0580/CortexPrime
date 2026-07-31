# CortexPrime v1.0 — Customer Validation Program

**Owner:** Chief Product Officer
**Status:** Active
**Start Date:** July 18, 2026
**Gate to v2.0:** All success criteria must be met before major v2 implementation begins.

---

## 1. Pilot Program — 5 Design Partners

### 1.1 Partner Profile

| Dimension | Ideal Partner |
|-----------|---------------|
| **Industry** | At least 2 of: Financial Services, Healthcare, Technology, Manufacturing |
| **Size** | 500-5,000 employees |
| **AI maturity** | Already using LLMs (any provider) in production or pilot |
| **Pain point** | Agent sprawl, governance gaps, multi-provider management |
| **Technical contact** | Dedicated AI platform engineer or architect |
| **Executive sponsor** | VP/Director of AI, Data, or Engineering |
| **Commitment** | 1 hour/week feedback call, telemetry opt-in, quarterly business review |

### 1.2 Partner Tiers

| Tier | Partners | Access Level | SLA | Term |
|------|----------|-------------|-----|------|
| **Strategic** | 2 | Full platform, roadmap influence, dedicated TAM | 4h response | 12 months |
| **Standard** | 3 | Full platform, quarterly roadmap review | 8h response | 6 months |

### 1.3 Incentives

- Free Enterprise license for 12 months (Strategic) / 6 months (Standard)
- Dedicated Slack channel with CortexPrime engineering team
- Named in public case study (opt-in)
- Early access to all v2.0 alpha features
- Co-branded press release at program conclusion

### 1.4 Onboarding Checklist

```
Week 1 — Foundation
[ ] Kickoff call: scope, goals, success criteria
[ ] Partner environment assessment (cloud, infra, compliance reqs)
[ ] CortexPrime deployment (guided Helm install or dedicated SaaS tenant)
[ ] Identity provider integration (SSO/SAML/SCIM)
[ ] Initial connector configuration (up to 3)
[ ] Admin user accounts created
[ ] Slack channel established

Week 2 — Core Setup
[ ] LLM provider configuration (1-3 providers)
[ ] Agent deployment (start with built-in agents)
[ ] Memory system validation
[ ] Mission pipeline: first end-to-end mission executed
[ ] Observability basics: health dashboard verified
[ ] Governance rules configured (RBAC, audit logging)
[ ] Secrets management integration

Week 3 — Integration
[ ] Custom connector development (if needed)
[ ] Custom agent development (if needed) via SDK
[ ] Mission pipeline customization
[ ] Knowledge graph population
[ ] Approval workflow configuration
[ ] Alert and notification setup
[ ] Backup and DR validation

Week 4 — Validation
[ ] Load testing: 10× normal mission volume
[ ] Failover testing: LLM provider failover
[ ] Recovery testing: backup restoration
[ ] Security review: audit trail verification
[ ] Performance baseline established
[ ] User acceptance testing sign-off
[ ] Go-live declaration
```

### 1.5 Weekly Feedback Cycle

| Day | Activity | Participants | Duration |
|-----|----------|-------------|----------|
| **Monday** | Async status update (Slack) | Partner PM + CortexPrime PM | 15 min |
| **Tuesday** | Usage metrics review | Partner PM + CortexPrime PM | 30 min |
| **Wednesday** | Office hours / troubleshooting | Partner team + CortexPrime eng | 1 hour |
| **Thursday** | Feature request triage | Partner PM + CortexPrime PM | 30 min |
| **Friday** | Weekly summary + next week plan | Partner PM + CortexPrime PM | 30 min |

### 1.6 Monthly Business Review

- Mission execution trends (volume, success rate, latency)
- Cost analysis (LLM spend per mission, per agent)
- User adoption (active users, missions per user)
- Feature request backlog review
- Issues and blockers (open, resolved, aging)
- Roadmap alignment check
- Partner NPS survey
- Action items for next month

### 1.7 Pilot Success Metrics

| Metric | Target by Month 3 | Target by Month 6 |
|--------|-------------------|-------------------|
| Active users per partner | 10+ | 25+ |
| Missions executed/day | 50+ | 200+ |
| Mission success rate | >85% | >95% |
| Connectors configured | 3+ | 5+ |
| Agents deployed | 3+ | 8+ |
| Partner NPS | >20 | >40 |
| Support tickets/week | <5 | <3 |
| Feature requests submitted | 5+ | 10+ |

---

## 2. Usage Telemetry

### 2.1 Telemetry Collection Policy

| Aspect | Policy |
|--------|--------|
| Opt-in model | Explicit consent at install/onboarding |
| What is collected | Aggregated usage metrics only (no PII, no mission content, no LLM prompts/responses) |
| What is NOT collected | Mission payloads, user identities, LLM inputs/outputs, database contents, file contents |
| Data retention | 13 months, rolling |
| Data residency | Configurable (US, EU, or on-prem only) |
| Deletion | Self-serve opt-out with 30-day data purge |
| GDPR compliance | Standard DPA, data processing agreement |
| SOC 2 | Covered under CortexPrime SOC 2 Type II |

### 2.2 Telemetry Dimensions

#### Core Usage

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| Missions created/day | Daily count, by type | Platform counter | No |
| Missions completed/day | Daily count, by status | Platform counter | No |
| Missions failed/day | Daily count, by failure mode | Platform counter | No |
| Mission duration (p50/p95/p99) | Milliseconds | Distributed tracing | No |
| Concurrent active missions | Gauge (15s interval) | Platform gauge | No |
| Missions per user | Daily, aggregated | Anonymized user ID | No |

#### Agent Usage

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| Active agents/deployment | Gauge | Platform gauge | No |
| Agent invocations/day | Count, by agent type | Platform counter | No |
| Agent execution duration | Milliseconds, p50/p95/p99 | Distributed tracing | No |
| Agent success rate | %, by agent type | Platform counter | No |
| Agent-to-agent calls | Count, by agent pair | Tracing | No |
| Custom agents deployed | Count | Platform counter | No |

#### Connector Usage

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| Active connectors | Count, by type | Platform gauge | No |
| Connector operations/day | Count, by operation (read/write/sync) | Platform counter | No |
| Connector success rate | %, by connector type | Platform counter | No |
| Connector latency | Milliseconds, p50/p95/p99 | Tracing | No |
| Objects synced/day | Count, by connector | Platform counter | No |
| Sync failures/day | Count, by connector | Platform counter | No |

#### AI Cost

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| LLM tokens in/out per day | Count, by model | Platform counter | No |
| LLM cost per day | USD, by model and agent | Computed from token counts × rate | No |
| Cost per mission | USD, p50/p95 | Computed | No |
| Cost per user | USD, monthly | Computed (anonymized) | No |
| Provider distribution | % of requests by provider | Platform counter | No |
| Model distribution | % of requests by model | Platform counter | No |
| Cache hit rate | % | Platform counter | No |

#### Failures

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| Error rate by component | %, by service | Platform counter | No |
| Error types | Count, by error class | Event log | No |
| LLM provider errors | Count, by provider and error code | Platform counter | No |
| Connector errors | Count, by connector | Platform counter | No |
| Agent failures | Count, by agent type and error | Platform counter | No |
| Crash frequency | Count/day | Process monitor | No |
| OOM events | Count/day | Process monitor | No |

#### Latency

| Metric | Granularity | Collection Method | PII? |
|--------|-------------|-------------------|------|
| API gateway latency | ms, p50/p95/p99 | Request tracing | No |
| LLM response time | ms, by provider and model | Request tracing | No |
| Memory read latency | µs, by memory type | Request tracing | No |
| Memory write latency | µs, by memory type | Request tracing | No |
| Connector response time | ms, by connector | Request tracing | No |
| End-to-end mission latency | ms, p50/p95/p99 | Distributed tracing | No |

#### User Satisfaction

| Metric | Frequency | Collection Method | PII? |
|--------|-----------|-------------------|------|
| In-app NPS survey | Monthly | 1-question prompt in dashboard | Email (optional) |
| Feature satisfaction | Per-feature | Rating prompt after feature use | No |
| Support ticket rating | Per-ticket | CSAT survey on close | No |
| Churn risk score | Monthly | Computed from usage decline pattern | Anonymized |
| Active users (DAU/WAU/MAU) | Daily | Platform counter | Anonymized user ID |
| Session duration | Minutes, p50/p95 | Platform counter | No |
| Onboarding completion rate | %, by step | Platform counter | No |

### 2.3 Telemetry Pipeline

```
CortexPrime Deployment
        │
        ▼
  Telemetry Agent (sidecar / built-in)
        │
        ▼
  CortexPrime Observability Suite
        │
        ├──► Aggregated Metrics ──► CortexPrime Cloud (opt-in)
        │         (no PII)
        │
        ├──► Raw Metrics ──► Customer's Prometheus (local)
        │
        └──► Audit Log ──► Customer's SIEM (local)
```

---

## 3. Customer Interviews

### 3.1 Interview Cadence

| Phase | Timing | Format | Participants |
|-------|--------|--------|-------------|
| **Baseline** | Week 2 of pilot | 60-min structured interview | Partner PM + engineer + CortexPrime PM |
| **Monthly** | Every 4 weeks | 45-min check-in | Partner PM + CortexPrime PM |
| **Quarterly** | Every 12 weeks | 60-min deep dive | Partner team + CortexPrime CPO + engineering lead |
| **Exit** | End of pilot | 90-min retrospective | Full partner team + CortexPrime leadership |

### 3.2 Baseline Interview Guide

#### Opening (5 min)
- What is your role and how do you interact with CortexPrime?
- What was your primary motivation for joining this pilot?
- What is your definition of success for this engagement?

#### Pain Points (15 min)
- What AI-related challenges were you facing before CortexPrime?
  - Probe: Agent management? Cost control? Governance? Integration?
- What did you try before CortexPrime and why didn't it work?
- What is the single biggest pain point CortexPrime should solve for you?
- What keeps you up at night regarding your AI infrastructure?

#### CortexPrime Experience (15 min)
- What was your experience during onboarding?
  - Probe: Documentation quality? Deployment complexity? Time to first mission?
- What does your team like about CortexPrime so far?
- What frustrates your team about CortexPrime?
- How does CortexPrime compare to what you were using before?
- Are there any features you expected that are missing?

#### Missing Features (10 min)
- If you could add one feature to CortexPrime, what would it be?
- What integrations do you need that are not yet available?
  - Probe: Specific connectors? LLM providers? Identity providers?
- What agent capabilities do you need that are not yet built?
- What reporting or analytics are missing from the current dashboards?

#### UX & Usability (10 min)
- How intuitive did you find the CortexPrime interface?
- Were there any workflows that felt confusing or difficult to complete?
- How long did it take for your team to become productive?
- What documentation or training would have helped you move faster?
- Any specific UI elements that need improvement?

#### Business Impact (5 min)
- How has CortexPrime impacted your team's productivity so far?
- Have you identified any cost savings or efficiency gains?
- What would need to be true for you to recommend CortexPrime to a peer?

#### Closing (5 min)
- Is there anything we haven't discussed that you'd like to share?
- What would make this pilot a resounding success for you?
- Any final thoughts or advice for the CortexPrime team?

### 3.3 Monthly Check-in Guide

- What has changed in your priorities since we last spoke?
- What have you used CortexPrime for in the past month?
- What went well? What went wrong?
- Any new features you wish existed?
- Any integrations you now need that you didn't before?
- Rate your satisfaction with CortexPrime today (1-10). Why?
- What is your single most important request for the next month?

### 3.4 Quarterly Deep Dive Guide

- How has your AI strategy evolved in the past quarter?
- What new use cases are you exploring with CortexPrime?
- What use cases did you try but abandon? Why?
- How has CortexPrime affected your infrastructure costs?
- How has CortexPrime affected your team's velocity?
- What competitive products have you evaluated recently?
- What would cause you to replace CortexPrime?
- If you were CPO for a day, what would you change?

### 3.5 Exit Interview Guide

- Overall, would you recommend CortexPrime? (0-10, followed by why)
- Did CortexPrime meet the goals we set at the beginning of the pilot?
- What was the most valuable outcome from using CortexPrime?
- What was the biggest disappointment?
- Would you be willing to become a paying customer? At what price point?
- What would need to change for you to expand CortexPrime across your organization?
- What would make CortexPrime a must-have rather than a nice-to-have?
- Any final advice?

### 3.6 Interview Tracking

| Field | Format |
|-------|--------|
| Partner name | Text |
| Date | ISO 8601 |
| Interview type | Baseline / Monthly / Quarterly / Exit |
| Participants | List of names + roles |
| Key pain points | Bullet list |
| Feature requests | List with priority (partner-rated) |
| Top integrations requested | List |
| UX issues | Bullet list |
| NPS score | 0-10 |
| Overall sentiment | Positive / Neutral / Negative |
| Action items | Bullet list with owners |
| Raw notes | Link to internal doc |

---

## 4. Analytics Dashboard

### 4.1 Daily Dashboard

**Purpose:** Spot anomalies and regressions immediately.

| Section | Metric | Alert Threshold |
|---------|--------|-----------------|
| **Health** | Mission success rate | <90% |
| | API error rate | >5% |
| | P99 latency | >5s |
| | Active users (today) | <50% of 7-day avg |
| **Usage** | Missions executed (today) | <50% of 7-day avg |
| | Agents invoked (today) | <50% of 7-day avg |
| | Tokens consumed (today) | >2× 7-day avg |
| **Cost** | Daily LLM cost | >2× 7-day avg |
| | Cost per mission | >$0.50 |
| **Failures** | Error count by type | Any new error type |
| | Top 5 error sources | — |
| | Unhandled exceptions | >0 |
| **Adoption** | New users (today) | — |
| | New agents deployed (today) | — |
| | New connectors configured (today) | — |

### 4.2 Weekly Dashboard

**Purpose:** Track trends, identify growth patterns and emerging issues.

| Section | Metrics | Visualization |
|---------|---------|---------------|
| **Usage Trends** | Missions/day (7-day rolling avg) | Line chart |
| | Active users/day (7-day rolling avg) | Line chart |
| | Agent invocations/day (7-day rolling avg) | Stacked bar by agent type |
| | Connector operations/day (7-day rolling avg) | Stacked bar by connector |
| **Reliability** | Mission success rate (daily) | Sparkline |
| | Error rate by component (daily) | Stacked area |
| | P50/P95/P99 mission duration (daily) | Multi-line chart |
| | LLM provider failover events | Event timeline |
| **Cost** | Weekly LLM cost by provider | Pie chart |
| | Weekly LLM cost by agent | Bar chart |
| | Cost per mission trend | Line chart |
| | Cost projection (next 4 weeks) | Forecast line |
| **Adoption** | DAU/WAU/MAU | 3-number metric card |
| | Missions per user (weekly) | Histogram |
| | Connectors added this week | Count card |
| | Custom agents deployed | Count card |
| **Feedback** | Support tickets opened/closed | Waterfall chart |
| | Feature requests submitted | Count card |
| | Top 5 feature requests | Ranked list |
| | Partner NPS (if surveyed) | Score card |

### 4.3 Monthly Dashboard

**Purpose:** Business review, executive reporting, strategic decisions.

| Section | Metrics | Comparison |
|---------|---------|------------|
| **Executive Summary** | Total active users (MAU) | MoM change |
| | Total missions executed (month) | MoM change |
| | Overall mission success rate | MoM change |
| | Total LLM cost (month) | MoM change |
| | Gross retention rate | MoM change |
| | Net revenue retention (if paying) | MoM change |
| **Adoption Depth** | Power users (>50 missions/month) | Count + % change |
| | Active agents/deployment | Avg + distribution |
| | Active connectors/deployment | Avg + distribution |
| | Feature adoption rate | % of available features used |
| | Onboarding completion rate | Funnel conversion |
| **Reliability** | Uptime (SaaS tenants) | % |
| | P99 mission duration | ms |
| | Blocker bugs opened/closed | Count |
| | Mean time to resolve (P1) | Hours |
| **Cost Efficiency** | Cost per mission trend | 3-month line |
| | Cost per active user | $ |
| | LLM cost as % of total | % |
| | Cost savings from caching | $ |
| **Satisfaction** | In-app NPS score | Score + trend |
| | Support CSAT score | Score + trend |
| | Feature satisfaction scores | By feature, radar chart |
| | Churn risk list | High/Medium/Low |
| **Feedback Summary** | Feature requests by theme | Grouped bar |
| | Top 10 requested integrations | Ranked list |
| | Top 5 UX issues | Ranked list |
| | Customer verbatims (anonymized) | Key quotes |

### 4.4 Dashboard Tooling

- **Primary:** CortexPrime Observability Suite (dogfood our own product)
- **Backup:** Grafana + Prometheus (for internal use)
- **Export:** PDF monthly report for executive distribution
- **Alerting:** PagerDuty for P0/P1, Slack for P2, email digest for P3
- **Access:** CPO, Product team, Engineering leadership, CEO

---

## 5. Product Prioritization Framework

### 5.1 Feedback Intake Pipeline

```
Customer Feedback
    │
    ▼
┌──────────────────────────────────────────────────┐
│              Feedback Intake                      │
│  Source: Interviews, Telemetry, Support, NPS      │
│  Owner: Product Manager (weekly triage)           │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│           Feedback Classification                 │
│  Type: Bug / Feature / Integration / UX / Other   │
│  Severity: Blocker / Major / Minor / Enhancement  │
│  Frequency: Single / Multiple / Systematic        │
│  Impact: Low / Medium / High / Critical           │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│           Prioritization Board                    │
│  Convert to P0 / P1 / P2 / Backlog               │
│  Weekly review: CPO + Eng Lead + PM               │
└──────────────────────────────────────────────────┘
```

### 5.2 Prioritization Criteria

Each item is scored on four dimensions:

| Dimension | Weight | 1 (Low) | 2 (Medium) | 3 (High) | 4 (Critical) |
|-----------|--------|---------|------------|-----------|--------------|
| **Customer Impact** | 40% | 1 customer affected | 2-3 customers | 4-5 customers | All customers OR >50% revenue |
| **Business Impact** | 25% | Nice-to-have | Efficiency gain | New revenue opportunity | Competitive necessity |
| **Engineering Effort** | 20% | >4 weeks | 2-4 weeks | 1-2 weeks | <1 week |
| **Risk** | 15% | High complexity/unknown | Medium complexity | Known, moderate complexity | Simple, well-understood |

**Priority Score = (Customer Impact × 0.4) + (Business Impact × 0.25) + ((5 - Effort) × 0.20) + ((5 - Risk) × 0.15)**

### 5.3 Priority Definitions

| Priority | Score Range | Response | Action |
|----------|-------------|----------|--------|
| **P0** | 4.0-5.0 | Immediate | Assigned to current sprint. Blocking issue or critical customer need. CPO notified. |
| **P1** | 3.0-3.9 | This quarter | Committed to roadmap. Assigned to upcoming sprint. |
| **P2** | 2.0-2.9 | Next quarter | Reviewed quarterly. May be deprioritized. |
| **Backlog** | <2.0 | Future | Logged for future consideration. Reviewed quarterly for promotion. |

### 5.4 Special Designations

| Designation | Definition | Treatment |
|-------------|-----------|-----------|
| **Quick Win** | P1+ impact, <1 week effort | Fast-tracked into current sprint |
| **Strategic Bet** | High business impact, long effort | CPO decision, dedicated track |
| **Integration Request** | New connector/API | Aggregated quarterly, batch release |
| **UX Debt** | Repeated usability friction | Design sprint every 6 weeks |
| **Tech Debt** | Internal quality issue | 20% of each sprint allocated |
| **Customer Blocker** | Customer cannot proceed | Automatic P0 |

### 5.5 Feedback-to-Roadmap Flow

```
Week 1-4: Collect
  Interviews, telemetry, support tickets, NPS

Week 4: Triage
  PM classifies all new feedback
  Identify P0 candidates immediately

Month 1: Review
  CPO + Eng Lead + PM review all P1+ items
  Update roadmap commitments
  Communicate decisions to partners

Quarter: Publish
  Update public roadmap
  Send quarterly update to all partners
  Review P2 and Backlog for promotion
```

### 5.6 Feedback Sources Weighting

| Source | Weight in Scoring | Notes |
|--------|-------------------|-------|
| Design partner interview | 3× | Deepest context |
| Telemetry signal | 2× | Data-backed, not anecdotal |
| Support ticket analysis | 2× | Indicates friction |
| NPS verbatim | 1.5× | Structured sentiment |
| Sales inquiry | 1× | Market demand signal |
| Internal team | 0.5× | Bias-adjusted |
| Community / open source | 0.5× | Broader signal, less context |

---

## 6. Success Criteria — Gate to v2.0

### 6.1 The Gate

**CortexPrime v2.0 major implementation (new architecture, SaaS, marketplace, multi-language SDKs, fleet management) MUST NOT begin until ALL success criteria below are met.**

Minor v1.x releases (bug fixes, security patches, small feature additions, connector additions) may continue during validation.

### 6.2 Adoption Criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **Active users (MAU)** | 100 | 250 | 500+ |
| **Enterprise customers (paying)** | 20 | 50 | 100+ |
| **Design partners completed program** | 5 | 5 | 10+ |
| **Daily active users / Monthly active users** | >30% | >40% | >50% |
| **Missions executed per active user per month** | >20 | >50 | >100 |

### 6.3 Usage Criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **Missions executed (cumulative)** | 100,000 | 500,000 | 1,000,000+ |
| **Missions executed per day (sustained 30-day avg)** | >1,000 | >5,000 | >10,000 |
| **Mission success rate (30-day rolling)** | >90% | >95% | >99% |
| **Custom agents deployed (cumulative)** | >10 | >25 | >50+ |
| **Connectors configured (cumulative)** | >20 | >50 | >100 |
| **Active agents per deployment (avg)** | >3 | >5 | >10 |

### 6.4 Quality Criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **NPS (in-app, 30-day rolling)** | >20 | >40 | >50 |
| **Net retention (monthly)** | >90% | >95% | >98% |
| **P1 incidents per month** | <3 | <1 | 0 |
| **P99 mission latency (sustained)** | <10s | <5s | <2s |
| **API uptime (SaaS, trailing 30 days)** | >99.5% | >99.9% | >99.95% |
| **Support ticket CSAT** | >80% | >90% | >95% |
| **Onboarding completion rate** | >70% | >85% | >95% |

### 6.5 Business Criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **Paying customers** | 20 | 50 | 100+ |
| **Net revenue retention** | >90% | >100% | >120% |
| **Average deal size (annual)** | $15,000 | $25,000 | $50,000+ |
| **Sales-qualified leads per month** | >10 | >25 | >50 |
| **Customers willing to provide case study** | >3 | >5 | >10 |
| **Customer references for sales** | >5 | >10 | >20 |

### 6.6 Product-Market Fit Criteria

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **"Would you be very disappointed without CortexPrime?" (% yes)** | >30% | >40% | >50% |
| **Customers who expanded license (node/seat increase)** | >5 | >10 | >20 |
| **Customers who went from pilot to paid** | >80% | >90% | >100% |
| **Feature request-to-implementation cycle** | <90 days | <60 days | <30 days |
| **Top 10 feature requests all from different customers** | Yes | Yes | Yes |

### 6.7 Leading Indicators (Track, but not gates)

| Indicator | Why It Matters |
|-----------|---------------|
| Community GitHub stars growth rate | Developer interest leading indicator |
| SDK downloads (PyPI + npm) | Developer adoption leading indicator |
| Docs site traffic | Evaluation activity leading indicator |
| Unprompted inbound inquiries | Brand awareness leading indicator |
| Partner referral rate | Satisfaction leading indicator |
| Time to first value (onboarding → first mission) | Friction leading indicator |
| Feature adoption depth (% of features used) | Stickiness leading indicator |

### 6.8 Go/No-Go Decision Process

```
Step 1: Monthly Check (CPO)
  └─ Track all metrics against minimums
  └─ Flag if >80% of minimums are met for 2 consecutive months

Step 2: Quarterly Review (CPO + CEO + Leadership)
  └─ Full criteria assessment
  └─ Review leading indicators
  └─ Customer verbatim review
  └─ Competitive landscape update

Step 3: Go Decision
  └─ ALL minimum criteria met AND sustained for 2 months
  └─ >50% of target criteria met
  └─ No unmitigated competitive threats requiring acceleration
  └─ Board approval (if applicable)

Step 4: No-Go Triggers
  └─ Any single minimum criterion missed
  └─ NPS < 20 for 2 consecutive months
  └─ Net retention < 85% for 2 consecutive months
  └─ P1 incidents increasing trend over 3 months
  └─ >2 design partners churning early

Step 5: If No-Go
  └─ Identify root causes for missed criteria
  └─ Develop remediation plan (max 3 months)
  └─ Re-assess after remediation
  └─ Do NOT begin v2.0 implementation
```

### 6.9 What the Gate Protects

Beginning v2.0 before product-market fit is confirmed risks:

- Building features nobody needs (waste)
- Scaling a broken model (multiplied waste)
- Missing critical feedback because team is heads-down on v2.0
- Running out of runway before finding PMF
- Building a marketplace with no supply or demand
- SaaS infrastructure costs with no revenue to offset

### 6.10 What IS Allowed During Validation

- Bug fixes and security patches
- Connector additions (low effort, high value)
- Small UX improvements based on feedback
- Documentation improvements
- Performance optimization
- SDK documentation and examples
- Community engagement
- Sales and marketing
- Pilot program operations
- Telemetry infrastructure

### 6.11 What Is NOT Allowed During Validation

- Multi-region deployment architecture
- SaaS multi-tenant infrastructure
- Marketplace platform
- New SDK languages
- Fleet management / edge agents
- Memory federation
- White-label / embedded platform
- Major refactoring
- New enterprise modules

---

*Discipline over ambition. Validate before scale.*

---

## Appendix A: Partner Agreement Template

```
CORTEXPRIME DESIGN PARTNER AGREEMENT

Partner Name: __________________________________
Contact: _______________________________________
Tier: Strategic / Standard
Term: ___ months (renewable)
Start Date: ____________________________________

COMMITMENTS

CortexPrime provides:
  - Free Enterprise license for term
  - Dedicated Slack channel with engineering
  - Named TAM (Strategic only)
  - Early access to v2.0 features
  - Quarterly roadmap review

Partner provides:
  - 1 hour/week feedback call (minimum)
  - Telemetry opt-in (anonymized, aggregated)
  - Quarterly business review participation
  - Case study participation (opt-in)
  - NPS survey response (monthly)

SUCCESS CRITERIA (to be defined jointly)

1. ______________________________________________
2. ______________________________________________
3. ______________________________________________

SIGNATURES

_________________________          _______________
CortexPrime CPO                       Date

_________________________          _______________
Partner Representative               Date
```

## Appendix B: NPS Survey Template

```
Subject: How likely are you to recommend CortexPrime?

Question 1 (required):
How likely are you to recommend CortexPrime to a colleague?
0 (Not at all likely) — 10 (Extremely likely)

Question 2 (required):
What is the primary reason for your score?

Question 3 (optional):
What is the single most important thing we could do to improve CortexPrime?

Question 4 (optional):
Which feature do you find most valuable?

Question 5 (optional):
Is there any feature you expected that CortexPrime does not have?
```

## Appendix C: Weekly Feedback Log Template

```
PARTNER: _________________________  WEEK STARTING: _______________

USAGE HIGHLIGHTS
  Missions executed: ___
  Active users: ___
  Mission success rate: ___%
  New agents deployed: ___
  New connectors configured: ___

WINS (what went well)
  - 
  - 
  - 

BLOCKERS (what needs immediate attention)
  - 
  - 
  - 

FEATURE REQUESTS
  1. [P0/P1/P2] __________________________________
  2. [P0/P1/P2] __________________________________
  3. [P0/P1/P2] __________________________________

BUGS / ISSUES
  1. [Severity] __________________________________
  2. [Severity] __________________________________

GENERAL FEEDBACK
  ________________________________________________
  ________________________________________________

NEXT WEEK GOALS
  1. __________________________________
  2. __________________________________
  3. __________________________________
```
