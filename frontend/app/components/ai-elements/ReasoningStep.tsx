"use client";

import { Check, AlertCircle, ShieldAlert, Cpu } from "lucide-react";
import type { TraceStep } from "../../types";
import { resolveRule, resolveStage, resolveVerdict, percent } from "../../vocabulary";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

// Helper for formatting percentage
const formatPercent = (v: number) => `${(v * 100).toFixed(1)}%`;

export function ReasoningStep({
  step,
  isLatest,
  lang = "es",
}: {
  step: TraceStep;
  isLatest: boolean;
  lang?: Lang;
}) {
  const s = strings(lang);
  const stageName = resolveStage(step.stage, lang);
  const ruleMeta = resolveRule(step.rule_id, lang);
  const verdictMeta = resolveVerdict(step.verdict, lang);
  const threshold = typeof step.summary?.threshold === "number" ? step.summary.threshold : null;

  const getToneIcon = () => {
    switch (verdictMeta.tone) {
      case "danger":
        return <ShieldAlert size={14} className="text-coral" />;
      case "warn":
        return <AlertCircle size={14} className="text-coral" />;
      case "ok":
        return <Check size={14} className="text-mint" />;
      default:
        return <Cpu size={14} className="text-dim" />;
    }
  };

  return (
    <article className={`reasoning-step tone-${verdictMeta.tone} ${isLatest ? "is-latest" : ""}`}>
      <div className="reasoning-header">
        <span className="reasoning-icon">{getToneIcon()}</span>
        <div className="reasoning-titles">
          <strong>{stageName}</strong>
          {step.rule_id && (
            <span className="reasoning-rule-badge">
              <code>{step.rule_id}</code> · {ruleMeta.label}
            </span>
          )}
        </div>
        <span className={`verdict-pill tone-${verdictMeta.tone}`}>
          {verdictMeta.label}
        </span>
      </div>

      {ruleMeta.description && (
        <p className="reasoning-description">{ruleMeta.description}</p>
      )}

      {/* Calibrated Scores with threshold comparison */}
      {Object.keys(step.scores).length > 0 && (
        <div className="reasoning-scores">
          <span className="scores-title">{s.calibratedScores}</span>
          <div className="scores-grid">
            {Object.entries(step.scores).map(([metric, value]) => {
              const exceedsThreshold = threshold !== null && value >= threshold;
              const metricLabel = s.scoreMetrics?.[metric] || metric.replace(/_/g, " ");
              const isDangerMetric = metric === "injection" && value > 0.05;
              const isConfidenceMetric = metric === "confidence";
              return (
                <div key={metric} className="score-row">
                  <div className="score-meta">
                    <span className="metric-name" title={metric}>
                      {metricLabel}
                    </span>
                    <span className={`metric-val ${isDangerMetric ? "text-coral font-bold" : ""}`}>
                      {formatPercent(value)}
                    </span>
                  </div>
                  <div className="score-bar-track">
                    <div
                      className={`score-bar-fill ${
                        isDangerMetric
                          ? "threshold-alert"
                          : exceedsThreshold
                          ? "threshold-ok"
                          : isConfidenceMetric
                          ? "confidence-fill"
                          : ""
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
                    />
                    {threshold !== null && (
                      <div
                        className="score-threshold-line"
                        style={{ left: `${Math.min(100, Math.max(0, threshold * 100))}%` }}
                        title={`${s.threshold}: ${formatPercent(threshold)}`}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Facts summary */}
      {Object.keys(step.summary).length > 0 && (
        <div className="reasoning-summary">
          {Object.entries(step.summary).map(([k, v]) => (
            <span key={k} className="summary-chip">
              <span className="summary-key">{k}:</span>
              <span className="summary-val">{String(v)}</span>
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
