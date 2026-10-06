"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { AttachmentItem, HubReply, Turn } from "../types";
import type { CaseStudy, CaseStudyStatus, OperatorQueueItem } from "../types/case-study";
import { detectIntent } from "../components/intent-driven/intent-engine";

const READY_POLL_MS = 3000;

function deriveCaseStatus(reply: HubReply | null, error: string | null): CaseStudyStatus {
  if (error) return "refused";
  if (!reply) return "analyzing";
  if (reply.awaiting === "approve_action") return "awaiting_action";
  if (reply.awaiting === "operator_queue") return "in_operator_queue";
  if (reply.route === "clarify") return "needs_information";
  if (reply.card?.key === "refusal") return "refused";
  return "resolved";
}

function deriveCaseTitle(message: string, reply: HubReply | null): string {
  if (reply?.case_ref) return `Expediente ${reply.case_ref}`;
  const tx = message.match(/\b(E-[A-Z]{2}-\d{3,4})\b/i);
  if (tx) return `Transacción ${tx[1].toUpperCase()}`;
  if (/cancelar|anular/i.test(message)) return "Solicitud de Cancelación";
  if (/reintentar/i.test(message)) return "Reintento de Pago";
  if (/duda|problema|error/i.test(message)) return "Aclaración de Movimiento";
  return "Consulta Bancaria";
}

type ConversationState = {
  ready: boolean | null;
  persona: string;
  personas: string[];
  turns: Turn[];
  selected: number | null;
  busy: boolean;
  error: string | null;
};

const initialConversationState: ConversationState = {
  ready: null,
  persona: "ana",
  personas: ["ana", "camilo", "lucia", "dana"],
  turns: [],
  selected: null,
  busy: false,
  error: null,
};

type ConversationAction =
  | { type: "ready"; ready: boolean | null }
  | { type: "persona"; persona: string }
  | { type: "personas"; personas: string[] }
  | { type: "turn-append"; message: string; attachments: AttachmentItem[] }
  | { type: "turn-reply"; index: number; reply: HubReply }
  | { type: "turn-error"; index: number; error: string }
  | { type: "turn-decide"; index: number; reply: HubReply }
  | { type: "select"; index: number | null }
  | { type: "busy"; busy: boolean }
  | { type: "error"; error: string | null }
  | { type: "reset" };

function conversationReducer(
  state: ConversationState,
  action: ConversationAction
): ConversationState {
  switch (action.type) {
    case "ready":
      return { ...state, ready: action.ready };
    case "persona":
      return { ...state, persona: action.persona };
    case "personas":
      return { ...state, personas: action.personas };
    case "turn-append":
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            message: action.message,
            reply: null,
            error: null,
            attachments: action.attachments,
            decided: false,
          },
        ],
      };
    case "turn-reply":
      return {
        ...state,
        turns: state.turns.map((turn, idx) =>
          idx === action.index ? { ...turn, reply: action.reply, error: null } : turn
        ),
      };
    case "turn-error":
      return {
        ...state,
        turns: state.turns.map((turn, idx) =>
          idx === action.index ? { ...turn, error: action.error } : turn
        ),
      };
    case "turn-decide":
      return {
        ...state,
        turns: state.turns.map((turn, idx) =>
          idx === action.index ? { ...turn, reply: action.reply, decided: true } : turn
        ),
      };
    case "select":
      return { ...state, selected: action.index };
    case "busy":
      return { ...state, busy: action.busy };
    case "error":
      return { ...state, error: action.error };
    case "reset":
      return {
        ...state,
        turns: [],
        selected: null,
        error: null,
        busy: false,
      };
    default:
      return state;
  }
}

export function useHubConversation() {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState);
  // Synchronous mirror for values an async turn needs between dispatches
  // (the appended turn's index), which the reducer cannot return.
  const stateRef = useRef(state);
  stateRef.current = state;

  const setPersona = useCallback(
    (persona: string) => dispatch({ type: "persona", persona }),
    []
  );
  const setSelected = useCallback(
    (index: number | null) => dispatch({ type: "select", index }),
    []
  );
  const setError = useCallback(
    (error: string | null) => dispatch({ type: "error", error }),
    []
  );

  // Poll /ready
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const response = await fetch("/ready");
        const body = await response.json();
        if (active) dispatch({ type: "ready", ready: Boolean(body.ready) });
      } catch {
        if (active) dispatch({ type: "ready", ready: false });
      }
    };
    poll();
    const timer = setInterval(poll, READY_POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const loadPersonas = useCallback(async () => {
    try {
      const response = await fetch("/api/hub/personas");
      if (response.ok) {
        const body = await response.json();
        if (Array.isArray(body.personas) && body.personas.length > 0) {
          dispatch({ type: "personas", personas: body.personas as string[] });
        }
      }
    } catch {
      // Keep hardcoded fallbacks
    }
  }, []);

  const post = useCallback(async (path: string, body: unknown): Promise<HubReply> => {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        typeof payload.detail === "string" ? payload.detail : `Error (${response.status})`
      );
    }
    return payload as HubReply;
  }, []);

  const getGuestId = useCallback((): string => {
    if (typeof window === "undefined") return "server-guest";
    let id = window.sessionStorage.getItem("calvino_guest_id");
    if (!id) {
      id = "g-" + Math.random().toString(36).substring(2, 10);
      window.sessionStorage.setItem("calvino_guest_id", id);
    }
    return id;
  }, []);

  const resetConversation = useCallback(() => {
    if (typeof window !== "undefined") {
      const newId = "g-" + Math.random().toString(36).substring(2, 10);
      window.sessionStorage.setItem("calvino_guest_id", newId);
    }
    dispatch({ type: "reset" });
  }, []);

  const send = useCallback(
    async (
      message: string,
      asPersona?: string,
      inputAttachments: AttachmentItem[] = []
    ) => {
      dispatch({ type: "busy", busy: true });
      dispatch({ type: "error", error: null });

      // Append new turn and immediately capture its target index
      const targetIndex = stateRef.current.turns.length;
      dispatch({ type: "turn-append", message, attachments: inputAttachments });

      dispatch({ type: "select", index: targetIndex });

      try {
        const payload: { text: string; persona?: string; guest_id?: string } = {
          text: message,
        };
        if (asPersona) {
          payload.persona = asPersona;
        } else {
          payload.guest_id = getGuestId();
        }

        const reply = await post("/api/hub/message", payload);
        dispatch({ type: "turn-reply", index: targetIndex, reply });
        dispatch({ type: "select", index: targetIndex });
      } catch (failure) {
        const detail = failure instanceof Error ? failure.message : "El servicio no responde";
        dispatch({ type: "turn-error", index: targetIndex, error: detail });
        dispatch({ type: "error", error: detail });
      } finally {
        dispatch({ type: "busy", busy: false });
      }
    },
    [post, getGuestId]
  );

  const resume = useCallback(
    async (index: number, ref: string, decision: boolean | string) => {
      dispatch({ type: "busy", busy: true });
      dispatch({ type: "error", error: null });
      try {
        const reply = await post("/api/hub/resume", { ref, decision });
        dispatch({ type: "turn-decide", index, reply });
        dispatch({ type: "select", index });
      } catch (failure) {
        const detail = failure instanceof Error ? failure.message : "El servicio no responde";
        dispatch({ type: "error", error: detail });
      } finally {
        dispatch({ type: "busy", busy: false });
      }
    },
    [post]
  );

  // Derived CaseStudy representations
  const caseStudies: CaseStudy[] = state.turns.map((turn, index) => {
    const intent = detectIntent(turn.message);
    const reply = turn.reply;
    const status = deriveCaseStatus(reply, turn.error);
    const title = deriveCaseTitle(turn.message, reply);

    return {
      id: reply?.case_ref || `case-${index + 1}`,
      title,
      status,
      intent,
      input: {
        rawText: turn.message,
        transcribed: false,
        attachments: turn.attachments || [],
      },
      cards: reply?.card ? [reply.card] : [],
      evidence: {
        route: reply?.route || null,
        escalated: Boolean(reply?.escalated),
        scores: reply?.trace?.[reply.trace.length - 1]?.scores || {},
        summary: reply?.trace?.[reply.trace.length - 1]?.summary || {},
      },
      pendingAction: reply?.awaiting
        ? {
            type: reply.awaiting,
            ref: reply.awaiting_ref,
            actionPayload: reply.card?.payload,
            decided: turn.decided,
          }
        : null,
      trace: reply?.trace || [],
      finalResponse: reply?.reply || null,
    };
  });

  const selectedReply = state.selected !== null ? state.turns[state.selected]?.reply ?? null : null;
  const selectedCase = state.selected !== null ? caseStudies[state.selected] ?? null : null;

  return {
    ready: state.ready,
    persona: state.persona,
    personas: state.personas,
    setPersona,
    loadPersonas,
    turns: state.turns,
    caseStudies,
    selected: state.selected,
    setSelected,
    selectedReply,
    selectedCase,
    busy: state.busy,
    error: state.error,
    setError,
    send,
    resume,
    resetConversation,
  };
}

export function useOperatorQueue() {
  const [cases, setCases] = useState<OperatorQueueItem[]>([]);
  const [selectedCaseRef, setSelectedCaseRef] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/hub/cases");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: OperatorQueueItem[] = await res.json();
      setCases(data);
      if (data.length > 0) {
        setSelectedCaseRef((prev) => {
          if (prev && data.some((c) => c.case_ref === prev)) {
            return prev;
          }
          if (typeof window !== "undefined") {
            const params = new URLSearchParams(window.location.search);
            const urlRef = params.get("case_ref") || params.get("case_id");
            if (urlRef && data.some((c) => c.case_ref === urlRef)) {
              return urlRef;
            }
          }
          return data[0].case_ref;
        });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error cargando la cola");
    } finally {
      setLoading(false);
    }
  }, []);

  const resumeCase = useCallback(
    async (ref: string, decision: boolean | string) => {
      setLoading(true);
      setError(null);
      setActionSuccess(null);
      try {
        const res = await fetch("/api/hub/resume", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ref, decision }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Error HTTP ${res.status}`);
        }
        const data = await res.json();
        setActionSuccess(data.reply || "Decisión registrada en auditoría");
        await fetchCases();
        return data;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Error ejecutando acción";
        setError(msg);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [fetchCases]
  );

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  return {
    cases,
    selectedCaseRef,
    setSelectedCaseRef,
    loading,
    error,
    actionSuccess,
    refreshCases: fetchCases,
    resumeCase,
  };
}
