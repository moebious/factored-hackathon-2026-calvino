// Shared types of the customer app (TSD-010): the JSON the hub endpoints
// return, mirrored field for field. The UI renders only these shapes; an
// unknown card key falls back to a named fallback card, never a crash.

export type TraceStep = {
  stage: string;
  rule_id: string | null;
  verdict: string;
  scores: Record<string, number>;
  summary: Record<string, string | number | boolean | null>;
};

export type Card = {
  key: string;
  payload: Record<string, unknown>;
};

export type AttachmentItem = {
  id: string;
  name: string;
  mediaType: string;
  size: number;
  url: string;
  status: "ready" | "failed";
  error?: string;
};

export type HubReply = {
  reply: string;
  card: Card | null;
  escalated: boolean;
  route: string;
  awaiting: "approve_action" | "operator_queue" | string | null;
  awaiting_ref: string | null;
  case_ref: string | null;
  trace: TraceStep[];
};

// One exchange in the conversation: the customer's text and, once answered,
// Calvino's full reply (the card, the trace and the parked-turn fields).
export type Turn = {
  message: string;
  reply: HubReply | null;
  error: string | null;
  attachments?: AttachmentItem[];
  // Set once the customer confirmed or denied a parked action, so the
  // buttons of an answered action_confirmation card are not offered twice.
  decided: boolean;
};

export const percent = (value: number): string => `${(value * 100).toFixed(1)}%`;
