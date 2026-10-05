"use client";

import type { CaseStudy } from "../../types/case-study";
import { CaseStatusBadge } from "./CaseStatusBadge";
import { ChainOfThought } from "../ai-elements/ChainOfThought";
import { OperatorQueuePanel } from "./OperatorQueuePanel";
import { CardView } from "../../cards";
import { Sparkles, ShieldCheck, ArrowRight } from "lucide-react";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

export function CaseDossier({
  caseStudy,
  lang = "es",
  disabled,
  onConfirmAction,
  onDenyAction,
  onResumeOperator,
}: {
  caseStudy: CaseStudy | null;
  lang?: Lang;
  disabled?: boolean;
  onConfirmAction?: (ref: string) => void;
  onDenyAction?: (ref: string) => void;
  onResumeOperator?: (ref: string, decision: string) => void;
}) {
  const s = strings(lang);

  if (!caseStudy) {
    return (
      <aside className="case-dossier empty" aria-label={s.dossierAriaLabel}>
        <div className="empty-dossier-state">
          <Sparkles size={24} className="text-mint" />
          <h3>{s.emptyDossierTitle}</h3>
          <p>{s.emptyDossierSubtitle}</p>
        </div>
      </aside>
    );
  }

  const { title, status, intent, input, cards, evidence, pendingAction, trace, finalResponse } = caseStudy;

  return (
    <aside className="case-dossier" aria-label={`${s.dossier}: ${title}`}>
      <div className="dossier-header">
        <div className="dossier-meta">
          <span className="dossier-kicker">{s.officialDossier} · {caseStudy.id}</span>
          <h2>{title}</h2>
        </div>
        <CaseStatusBadge status={status} lang={lang} />
      </div>

      {/* Customer prompt / Intent detected */}
      <div className="dossier-section dossier-prompt">
        <span className="section-label">{s.customerRequest}</span>
        <blockquote className="prompt-text">“{input.rawText}”</blockquote>
        {intent.type !== "conversation" && (
          <div className="detected-intent-badge">
            <span className="intent-type">{s.intentLabel}: <strong>{intent.label}</strong></span>
            <span className="intent-hint">{intent.hint}</span>
          </div>
        )}
      </div>

      {/* Verified final reply */}
      {finalResponse && (
        <div className="dossier-section dossier-reply">
          <div className="verified-heading">
            <ShieldCheck size={16} className="text-mint" />
            <span className="section-label">{s.verifiedFinding}</span>
          </div>
          <p className="reply-body">{finalResponse}</p>
        </div>
      )}

      {/* Official Catalog Cards */}
      {cards.length > 0 && (
        <div className="dossier-section dossier-cards">
          <span className="section-label">{s.structuredEvidence}</span>
          {cards.map((card, idx) => (
            <CardView
              key={`${card.key}-${idx}`}
              card={card}
              lang={lang}
              decided={Boolean(pendingAction?.decided)}
              disabled={disabled}
              onConfirm={() => pendingAction?.ref && onConfirmAction?.(pendingAction.ref)}
              onDeny={() => pendingAction?.ref && onDenyAction?.(pendingAction.ref)}
            />
          ))}
        </div>
      )}

      {/* Operator queue panel if pending */}
      {pendingAction?.type === "operator_queue" && pendingAction.ref && (
        <div className="dossier-section dossier-operator">
          <OperatorQueuePanel
            caseRef={caseStudy.id.startsWith("CASE-") ? caseStudy.id : null}
            awaitingRef={pendingAction.ref}
            decided={pendingAction.decided}
            disabled={disabled}
            lang={lang}
            onResume={(ref, decision) => onResumeOperator?.(ref, decision)}
          />
        </div>
      )}

      {/* Chain of Thought / Harness Steps */}
      <div className="dossier-section dossier-trace">
        <ChainOfThought steps={trace} lang={lang} />
      </div>

      {/* Route & Security metadata */}
      {evidence.route && (
        <div className="dossier-footer">
          <span className="route-pill">
            {s.assignedRoute}: <strong>{evidence.route}</strong>
          </span>
          {evidence.escalated && (
            <span className="escalated-pill">{s.humanInterventionActive}</span>
          )}
        </div>
      )}
    </aside>
  );
}
