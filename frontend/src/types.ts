// Mirrors backend/headmaster/api/main.py response models.

export interface CritiqueSummary {
  target_agent: string;
  status: "APPROVED" | "REJECTED";
  zero_shot_detected: boolean;
  rejection_codes: string[];
  rejection_categories: string[];
}

export interface TaskStatus {
  task_id: string;
  state: string;
  running: boolean;
  failure_reason: string | null;
  artifact_id: string | null;
  artifact_path: string | null;
  supplied_asset_ids: string[];
  reused_asset_ids: string[];
  critiques: CritiqueSummary[];
}

export interface CreateTaskRequest {
  text: string;
  harness?: string;
  orchestra?: string;
  needs_human_approval: boolean;
}

export interface CreateTaskResponse {
  task_id: string;
  state: string;
}

export interface ApprovalTicket {
  ticket_id: string;
  task_id: string;
  kind: "publish" | "budget_overrun" | "phase_gate";
  reason: string;
  details: Record<string, unknown>;
}

export interface ArtifactResponse {
  artifact_id: string;
  content_hash: string;
  format: string;
  content: string;
}

export interface EventRecord {
  specversion: string;
  id: string;
  source: string;
  type: string;
  time: string;
  subject: string | null;
  data: Record<string, unknown>;
}

export interface Metrics {
  total_tasks: number;
  completed: number;
  failed: number;
  task_success_rate: number;
  critiques_approved: number;
  critiques_rejected: number;
  zero_shot_detections: number;
  evidence_coverage: number;
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  est_cost_usd: number;
}
