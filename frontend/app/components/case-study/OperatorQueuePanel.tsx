"use client";

import { useState } from "react";
import { UserCheck, Clock, Send } from "lucide-react";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

export function OperatorQueuePanel({
  caseRef,
  awaitingRef,
  decided,
  disabled,
  lang = "es",
  onResume,
}: {
  caseRef: string | null;
  awaitingRef: string | null;
  decided: boolean;
  disabled?: boolean;
  lang?: Lang;
  onResume: (ref: string, decision: string) => void;
}) {
  const [decisionText, setDecisionText] = useState("");
  const s = strings(lang);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!decisionText.trim() || disabled || !awaitingRef) return;
    onResume(awaitingRef, decisionText.trim());
  };

  return (
    <section className="operator-queue-card" aria-label={s.operatorQueueTitle}>
      <div className="operator-queue-header">
        <span className="queue-icon"><Clock size={16} /></span>
        <div className="queue-meta">
          <strong>{s.operatorQueueTitle}</strong>
          {caseRef && <span>{s.bankReference}: <code>{caseRef}</code></span>}
        </div>
        <span className="queue-badge">{s.humanAttentionBadge}</span>
      </div>

      <p className="queue-description">
        {s.operatorQueueDescription}
      </p>

      {decided ? (
        <div className="operator-decided-banner">
          <UserCheck size={14} />
          <span>{s.operatorDecidedText}</span>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="operator-resolution-form">
          <label htmlFor={`operator-input-${caseRef}`} className="sr-only">
            {s.issueVerdict}
          </label>
          <input
            id={`operator-input-${caseRef}`}
            type="text"
            value={decisionText}
            onChange={(e) => setDecisionText(e.target.value)}
            placeholder={s.operatorPlaceholder}
            maxLength={200}
            disabled={disabled}
          />
          <button
            type="submit"
            className="operator-submit-btn"
            disabled={disabled || !decisionText.trim()}
          >
            <Send size={14} />
            <span>{s.issueVerdict}</span>
          </button>
        </form>
      )}
    </section>
  );
}
