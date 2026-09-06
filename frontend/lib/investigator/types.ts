/**
 * Response types, mirroring `backend/api/product/schemas.py` field for field.
 *
 * Nothing is renamed on the way in. A field called `retrieved_at` on the server
 * is called `retrieved_at` here, because the moment a UI type renames
 * `recorded_at` to `timestamp` the distinction between when the world was and
 * when CortexPrime found out has been thrown away in a place nobody will look.
 */

export interface SourceLineage {
    source_kind: string
    source_ref: string
    /** null means UNKNOWN origin — which is not the same as a distinct origin. */
    origin_id: string | null
    relation: string | null
    origin_known: boolean
}

export interface EvidenceRef {
    observation_id: string
    subject_ref: string
    predicate: string
    value: string | null
    /** returned_data / returned_empty / unavailable / not_configured. */
    status: string | null
    source_ref: string | null
    source_kind: string | null
    authority_tier: string | null
    lineage: SourceLineage | null
    /** WHEN THE WORLD WAS OBSERVED. */
    observed_at: string | null
    /** WHEN CORTEXPRIME LEARNED IT. */
    retrieved_at: string | null
    execution_ref: string | null
    trace_ref: string | null
    /** false when the reference could not be resolved — shown, never dropped. */
    resolved: boolean
}

export interface Freshness {
    state: string
    age_seconds: number | null
    horizon_seconds: number | null
    reason: string
}

export interface AuthorityAlternative {
    value: string | null
    source_ref: string | null
    tier: string | null
    observation_ref: string | null
}

export interface Authority {
    status: string
    reason: string
    source_ref: string | null
    source_kind: string | null
    tier: string | null
    alternatives: AuthorityAlternative[]
}

export interface Corroboration {
    /** independent / correlated / indeterminate / single / contradicted. */
    level: string
    independent_sources: string[]
    independent_origins: string[]
    lineage: SourceLineage[]
    correlated_count: number
    supporting_count: number
    contradicting_count: number
    reason: string
}

export interface Hypothesis {
    hypothesis_id: string
    statement: string
    subject_ref: string | null
    status: string
    temporal_fit: string | null
    evidence_for: string[]
    evidence_against: string[]
    missing_evidence: string[]
    contradiction_refs: string[]
    lineage_origins: string[]
    authority: string | null
    created_by: string | null
    unresolved_reason: string | null
    would_support: string | null
    would_contradict: string | null
    discriminates_from: string[]
}

export interface InvestigationSummary {
    investigation_ref: string
    status: string
    incident_ref: string | null
    subject_ref: string | null
    /** Platform-set A0–A4. Displayed; never editable. */
    autonomy_level: string | null
    conclusion_kind: string | null
    opened_at: string | null
    last_event_at: string | null
    is_terminal: boolean
}

export interface InvestigationList {
    items: InvestigationSummary[]
    count: number
    limit: number
    state: string
    note: string
}

export interface InvestigationDetail {
    investigation_ref: string
    status: string
    incident_ref: string | null
    subject_ref: string | null
    autonomy_level: string | null
    opened_at: string | null
    last_event_at: string | null
    conclusion_kind: string | null
    hypotheses: Hypothesis[]
    evidence: EvidenceRef[]
    residual_uncertainty: string[]
    supported: string[]
    eliminated: string[]
    still_open: string[]
    /** A supported hypothesis is not a verified one. */
    assurance_verified: boolean
    verification_refs: string[]
    steps_taken: number
    reads_taken: number
    read_at: string | null
}

export interface TimelineEvent {
    seq: number
    event_kind: string
    from_status: string | null
    to_status: string
    autonomy_level: string | null
    /** A ledger time — when CortexPrime committed the event. */
    recorded_at: string | null
    detail: string | null
}

export interface Timeline {
    investigation_ref: string
    events: TimelineEvent[]
    count: number
    note: string
}

export interface WorldState {
    subject_ref: string
    predicate: string
    epistemic_status: string
    value: string | null
    queried_valid_at: string | null
    as_known_at: string | null
    observed_at: string | null
    read_at: string | null
    freshness: Freshness
    authority: Authority
    corroboration: Corroboration | null
    evidence: EvidenceRef[]
    evidence_count: number
}

export interface Verification {
    verification_id: string
    /** supported / unsupported / insufficient_evidence. */
    verdict: string
    subject_ref: string
    procedure_ref: string | null
    verifier_ref: string | null
    /** Independence is proven by this differing from the producer's path. */
    verifier_reasoning_path: string | null
    rationale: string | null
    verified_at: string | null
    evidence_refs: string[]
}

export interface AssuranceList {
    investigation_ref: string
    items: Verification[]
    count: number
    note: string
}


// ---------------------------------------------------------------------
// Remediation and approval (Phase 10.3)
// ---------------------------------------------------------------------

export interface RemediationProposal {
    investigation_ref: string
    capability_ref: string
    capability_version: number
    capability_digest: string
    operation: string
    provider: string
    tenant_id: string
    principal_id: string
    environment: string
    namespace: string
    workload: string
    parameters: Record<string, unknown>
    side_effect_class: string
    effect_semantics: string | null
    code_trust: string
    isolation_tier: string
    reversible: boolean
    blast_radius: string
    approval_required: boolean
    /** Platform-set. Displayed; there is no route that could change it. */
    autonomy_ceiling: string
    /** ADR-090. Binds the approval to this exact action. */
    approval_digest: string
    evidence_refs: string[]
    diagnosis: string | null
}

export interface Approval {
    approval_id: string
    investigation_ref: string | null
    capability_ref: string
    capability_digest: string
    operation: string
    environment: string
    namespace: string
    workload: string
    parameters: Record<string, unknown>
    approval_digest: string
    /** pending / granted / denied / withdrawn. Not success or failure. */
    state: string
    requested_by: string
    decided_by: string | null
    justification: string | null
    requested_at: string | null
    decided_at: string | null
    expires_at: string | null
    expired: boolean
    consumed_by_execution: string | null
}

export interface ApprovalList {
    items: Approval[]
    count: number
    limit: number
}

export interface RemediationOutcome {
    execution_ref: string
    approval_id: string
    subject_ref: string
    action_requested: boolean
    action_approved: boolean
    execution_started: boolean
    world_status: string | null
    world_value: string | null
    world_observed_at: string | null
    assurance_verdicts: string[]
    read_at: string | null
    note: string | null
}

// ---------------------------------------------------------------------
// The approval queue (Phase 10.4)
// ---------------------------------------------------------------------

export interface ApprovalQueueItem {
    approval_id: string
    investigation_ref: string | null
    incident_ref: string | null
    requested_by: string
    decided_by: string | null
    requested_at: string | null
    decided_at: string | null
    expires_at: string | null

    capability_ref: string
    capability_version: number
    capability_digest: string
    operation: string
    provider: string | null
    environment: string
    namespace: string
    workload: string
    parameters: Record<string, unknown>

    /** ADR-090. Binds this approval to this exact action. */
    approval_digest: string
    /** Null on purpose — see action_digest_note. */
    action_digest: string | null
    action_digest_note: string

    side_effect_class: string | null
    effect_semantics: string | null
    code_trust: string | null
    isolation_tier: string | null
    reversible: boolean
    /** low / medium / high / critical, from the platform's own derivation. */
    risk: string
    blast_radius: string

    autonomy_ceiling: string
    autonomy_requested: string | null
    /** Null unless an AutonomyDecision was recorded. Never computed here. */
    autonomy_allowed: string | null
    autonomy_note: string

    assurance_status: string
    assurance_note: string
    verification_refs: string[]
    evidence_count: number
    evidence_refs: string[]

    state: string
    /** True while a decision can still be taken by ANYONE. About the approval. */
    actionable: boolean
    /**
     * True only when the approval is actionable AND the authenticated caller
     * holds approver authority in this tenant.
     *
     * Presentation only. The decision route re-resolves the same authority from
     * the same store and enforces it, so flipping this in a browser changes what
     * a button looks like and nothing else.
     */
    can_approve: boolean
    /** Why the caller may or may not decide — a stable code, not prose. */
    authority_reason: string
    expired: boolean
    consumed_by_execution: string | null
    justification: string | null
}

export interface ApprovalQueue {
    items: ApprovalQueueItem[]
    count: number
    actionable_count: number
    limit: number
    ordering: string
    filters: Record<string, unknown>
    /** Whether this caller holds approver authority at all. Server-resolved. */
    viewer_can_approve: boolean
    viewer_authority_reason: string
    note: string
}
