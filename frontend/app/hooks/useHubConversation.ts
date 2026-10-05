"use client";

import { useCallback, useEffect, useState } from "react";
import type { AttachmentItem, HubReply, Turn } from "../types";
import type { CaseStudy, CaseStudyStatus } from "../types/case-study";
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

export function useHubConversation() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [persona, setPersona] = useState("ana");
  const [personas, setPersonas] = useState(["ana", "camilo", "lucia", "dana"]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll /ready
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const response = await fetch("/ready");
        const body = await response.json();
        if (active) setReady(Boolean(body.ready));
      } catch {
        if (active) setReady(false);
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
          setPersonas(body.personas as string[]);
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

  const send = useCallback(
    async (message: string, asPersona = persona, inputAttachments: AttachmentItem[] = []) => {
      setBusy(true);
      setError(null);

      // Append new turn and immediately capture its target index
      let targetIndex = 0;
      setTurns((prev) => {
        targetIndex = prev.length;
        return [
          ...prev,
          {
            message,
            reply: null,
            error: null,
            attachments: inputAttachments,
            decided: false,
          },
        ];
      });

      setSelected(targetIndex);

      try {
        const reply = await post("/api/hub/message", { persona: asPersona, text: message });
        setTurns((prev) =>
          prev.map((turn, idx) =>
            idx === targetIndex
              ? { ...turn, reply, error: null }
              : turn
          )
        );
        setSelected(targetIndex);
      } catch (failure) {
        const detail = failure instanceof Error ? failure.message : "El servicio no responde";
        setTurns((prev) =>
          prev.map((turn, idx) =>
            idx === targetIndex
              ? { ...turn, error: detail }
              : turn
          )
        );
        setError(detail);
      } finally {
        setBusy(false);
      }
    },
    [persona, post]
  );

  const resume = useCallback(
    async (index: number, ref: string, decision: boolean | string) => {
      setBusy(true);
      setError(null);
      try {
        const reply = await post("/api/hub/resume", { ref, decision });
        setTurns((prev) =>
          prev.map((turn, idx) =>
            idx === index
              ? { ...turn, reply, decided: true }
              : turn
          )
        );
        setSelected(index);
      } catch (failure) {
        const detail = failure instanceof Error ? failure.message : "El servicio no responde";
        setError(detail);
      } finally {
        setBusy(false);
      }
    },
    [post]
  );

  // Derived CaseStudy representations
  const caseStudies: CaseStudy[] = turns.map((turn, index) => {
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

  const selectedReply = selected !== null ? turns[selected]?.reply ?? null : null;
  const selectedCase = selected !== null ? caseStudies[selected] ?? null : null;

  return {
    ready,
    persona,
    personas,
    setPersona,
    loadPersonas,
    turns,
    caseStudies,
    selected,
    setSelected,
    selectedReply,
    selectedCase,
    busy,
    error,
    setError,
    send,
    resume,
  };
}
