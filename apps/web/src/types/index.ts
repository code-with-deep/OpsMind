export type InvestigationStatus =
  | "open"
  | "running"
  | "completed"
  | "unsupported"
  | "needs_clarification"
  | "insufficient_evidence"
  | "budget_exceeded"
  | "guardrail_rejected"
  | "failed"
  | "tool_demo";

export type ReviewDecision = "approved" | "rejected" | "comment";

export interface EvidenceSource {
  type: string;
  template_key?: string;
  table?: string;
  query_params?: Record<string, any>;
  doc_id?: string;
  doc_key?: string;
  title?: string;
  chunk_index?: number;
  score?: number;
  excerpt?: string;
  row_count?: number;
  sample_rows?: Array<Record<string, any>>;
}

export interface FindingEvidence {
  claim: string;
  confidence: number;
  sources: EvidenceSource[];
  assumptions: string[];
  gaps: string[];
  source_id: string;
}

export interface Finding {
  id: string;
  source_id: string;
  claim: string;
  confidence: number;
  sources: EvidenceSource[];
  assumptions: string[];
  gaps: string[];
  created_at: string;
}

export interface InvestigationEvent {
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface Review {
  id: string;
  decision: ReviewDecision;
  reviewer: string;
  notes: string | null;
  created_at: string;
}

export interface CaseSummary {
  id: string;
  title: string;
  summary: string;
  drivers: string[];
  actions: string[];
  confidence: number;
  created_at: string;
}

export interface ClaimSourceMapItem {
  claim: string;
  source_ids: string[];
}

export interface RecommendationReport {
  summary: string;
  actions: string[];
  confidence: number;
  claim_source_map: ClaimSourceMapItem[];
  status: string;
  assumptions?: string[];
  gaps?: string[];
  supported_domains?: string[];
  verification_errors?: string[];
}

export interface Hypothesis {
  summary: string;
  drivers: string[];
  confidence: number;
  supporting_source_ids: string[];
  gaps: string[];
}

export interface Critique {
  decision: "pass" | "retry" | "fail_soft";
  notes: string;
  gaps: string[];
}

export interface AuditRecord {
  question_fingerprint: string;
  question_redacted: string;
  status: InvestigationStatus;
  node_trace: string[];
  retry_count: number;
  finding_count: number;
  tool_calls_used: number;
  max_tool_calls: number;
  errors: string[];
  guardrail_flags: Record<string, any>;
  citation_verified: boolean | null;
  completed_at: string;
  audit_version: number;
}

export interface InvestigationDetail {
  id: string;
  question: string;
  status: InvestigationStatus;
  window_start: string | null;
  window_end: string | null;
  confidence: number | null;
  plan: Record<string, any> | null;
  hypothesis: Hypothesis | null;
  critique: Critique | null;
  recommendation: RecommendationReport | null;
  retry_count: number;
  audit: AuditRecord | null;
  created_at: string;
  updated_at: string;
  reviews: Review[];
  case_summary: CaseSummary | null;
  timeline: InvestigationEvent[];
  findings: Finding[];
  run?: {
    node_trace: string[];
    finding_count: number;
    errors: string[];
    retry_count: number;
  };
}

export interface InvestigationSummaryItem {
  id: string;
  question: string;
  status: InvestigationStatus;
  confidence: number | null;
  retry_count: number;
  window_start: string | null;
  window_end: string | null;
  created_at: string;
  updated_at: string;
  has_audit: boolean;
  review_count: number;
  latest_review_decision: ReviewDecision | null;
  is_approved: boolean;
}

export interface CaseSummaryItem {
  id: string;
  investigation_id: string;
  review_id: string | null;
  title: string;
  question: string;
  summary: string;
  drivers: string[];
  actions: string[];
  confidence: number;
  created_at: string;
}

export interface SqlTemplate {
  key: string;
  description: string;
  table: string;
  parameters: Record<string, string>;
}
