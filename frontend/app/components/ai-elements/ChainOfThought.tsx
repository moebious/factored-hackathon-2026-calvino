"use client";

import { useState } from "react";
import { ChevronDown, Search, ShieldCheck } from "lucide-react";
import type { TraceStep } from "../../types";
import { ReasoningStep } from "./ReasoningStep";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

export function ChainOfThought({
  steps,
  open: controlledOpen,
  onOpenChange,
  lang = "es",
}: {
  steps: TraceStep[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  lang?: Lang;
}) {
  const [internalOpen, setInternalOpen] = useState(true);
  const isOpen = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const s = strings(lang);

  const toggle = () => {
    if (onOpenChange) onOpenChange(!isOpen);
    else setInternalOpen(!isOpen);
  };

  return (
    <section className="chain-of-thought-panel" aria-label={s.traceEvidence}>
      <button
        className="chain-trigger-button"
        type="button"
        aria-expanded={isOpen}
        onClick={toggle}
      >
        <div className="chain-title-row">
          <ShieldCheck size={16} className="text-mint" />
          <span className="chain-heading">
            {s.traceEvidence} ({steps.length} {steps.length === 1 ? s.traceStep : s.traceSteps})
          </span>
        </div>
        <ChevronDown
          size={16}
          className={`chain-chevron-icon ${isOpen ? "is-open" : ""}`}
        />
      </button>

      {isOpen && (
        <div className="chain-steps-container">
          {steps.length === 0 ? (
            <div className="empty-trace-state">
              <Search size={18} className="text-dim" />
              <p>{s.emptyTraceState}</p>
            </div>
          ) : (
            steps.map((step, index) => (
              <div
                key={`${step.stage}-${index}`}
                className="trace-step-reveal"
                style={{ animationDelay: `${Math.min(index, 8) * 70}ms` }}
              >
                <ReasoningStep
                  step={step}
                  isLatest={index === steps.length - 1}
                  lang={lang}
                />
              </div>
            ))
          )}
        </div>
      )}
    </section>
  );
}
