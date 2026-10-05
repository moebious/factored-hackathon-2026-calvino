import type { AttachmentItem, Card, TraceStep } from "../types";

export type CaseStudyStatus =
  | "draft"              // User is actively typing/dictating in the intent-driven card
  | "analyzing"          // Message sent to backend; harness and policy rules evaluating
  | "needs_information"  // Backend returned CLARIFY route (e.g. choose problem payment)
  | "awaiting_action"    // Action parked for customer approval (Gate ASK; approve_action)
  | "in_operator_queue"  // Escalated to human operator (open_investigation; operator_queue)
  | "resolved"           // Settled with verified evidence and card
  | "refused";           // Blocked by banking policy rule (Gate BLOCK)

export type DetectedIntentType =
  | "split"
  | "checklist"
  | "event"
  | "timer"
  | "color"
  | "status_track"
  | "action_retry"
  | "action_cancel"
  | "dispute"
  | "conversation";

export type DetectedIntent = {
  type: DetectedIntentType;
  label: string;
  hint: string;
  confidence: number;
  params: Record<string, unknown>;
};

export type CaseStudy = {
  id: string;                     // Backend case_ref or turn timestamp id
  title: string;                  // Dynamic summary title
  status: CaseStudyStatus;        // Investigation lifecycle state
  intent: DetectedIntent;         // Local intent detected by IntentEngine
  input: {
    rawText: string;              // What the customer typed or dictated
    transcribed: boolean;         // True if generated via SpeechRecognition
    attachments: AttachmentItem[];// Local files attached to the case
  };
  cards: Card[];                  // Official catalog cards accumulated in this case
  evidence: {
    route: string | null;         // "agents" | "clarify" | "human" | "out_of_scope"
    escalated: boolean;           // True if human involved
    scores: Record<string, number>; // Calibrated Laya scores
    summary: Record<string, unknown>; // Audited facts (amount, threshold, etc.)
  };
  pendingAction: {
    type: "approve_action" | "operator_queue" | string | null;
    ref: string | null;           // awaiting_ref to resume with /api/hub/resume
    actionPayload?: Record<string, unknown>; // Parameters of action to confirm
    decided: boolean;             // Prevents duplicate confirmations
  } | null;
  trace: TraceStep[];             // Full audited harness decision steps
  finalResponse: string | null;   // Grounded, verified reply from Calvino
};

export type OperatorQueueItem = {
  case_ref: string;
  persona: string;
  status: "pending_approval" | "in_investigation" | "refused" | "resolved";
  reason_rule_id: string;
  created_at: string;
  customer_message: string;
  entry_reference: string | null;
  amount: string | null;
  currency: string | null;
  target_action: "cancel_payment" | "retry_payment" | "open_investigation" | null;
  awaiting_ref: string | null;
  gate_verdict: string | null;
};
