"use client";

import { useState } from "react";
import {
  ArrowLeft,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { strings } from "../i18n";
import type { Lang } from "../i18n";
import { useOperatorQueue } from "../hooks/useHubConversation";

export default function OperatorConsolePage() {
  const [lang, setLang] = useState<Lang>("es");
  const s = strings(lang);

  const {
    cases,
    selectedCaseRef,
    setSelectedCaseRef,
    loading,
    error,
    actionSuccess,
    refreshCases,
    resumeCase,
  } = useOperatorQueue();

  const activeCase = cases.find((c) => c.case_ref === selectedCaseRef) || cases[0] || null;

  return (
    <div className="app-shell operator-workspace-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Calvino inicio">
          <span className="brand-symbol">
            <Sparkles size={16} />
          </span>
          Calvino
        </a>

        <nav className="view-switcher" aria-label="Navegación de producto">
          <a href="/" className="view-tab">
            <User size={13} /> {s.customerApp}
          </a>
          <a href="/console" className="view-tab active">
            <ShieldCheck size={13} /> {s.operatorWorkspace}
          </a>
        </nav>

        <div className="topbar-status operator-status">
          <span className="live-dot" /> System 3 (Human-in-the-Loop)
        </div>

        <div className="topbar-actions">
          <div className="language-switch" role="group" aria-label="Idioma">
            <button
              type="button"
              className={lang === "es" ? "active" : ""}
              onClick={() => setLang("es")}
            >
              ES
            </button>
            <button
              type="button"
              className={lang === "pt" ? "active" : ""}
              onClick={() => setLang("pt")}
            >
              PT
            </button>
          </div>

          <span className="topbar-divider" />

          <button
            type="button"
            className="refresh-btn"
            onClick={refreshCases}
            disabled={loading}
            title="Refrescar cola"
          >
            <RefreshCw size={13} className={loading ? "spin" : ""} />
          </button>

          <span className="operator-badge">
            <ShieldAlert size={13} />
            operator:demo-agent-01
          </span>
        </div>
      </header>

      <main className="operator-workspace">
        <div className="operator-header">
          <div className="operator-title-area">
            <a href="/" className="back-link">
              <ArrowLeft size={13} /> {s.customerApp}
            </a>
            <h1>{s.operatorConsoleTitle}</h1>
            <p>{s.operatorConsoleSubtitle}</p>
          </div>
          {actionSuccess && (
            <div className="success-banner" role="status">
              <ShieldCheck size={15} />
              <span>{actionSuccess}</span>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <ShieldAlert size={15} />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="operator-grid">
          <section className="queue-column" aria-label={s.queueTableTitle}>
            <div className="panel-header">
              <h2>{s.queueTableTitle}</h2>
              <span className="count-badge">{cases.length}</span>
            </div>
            {/* OperatorQueueTable rendered in next step */}
            <div className="queue-list-container">
              {cases.length === 0 ? (
                <div className="empty-queue-notice">{s.noCasesFound}</div>
              ) : (
                <ul className="queue-items">
                  {cases.map((c) => (
                    <li
                      key={c.case_ref}
                      className={`queue-item-card ${
                        c.case_ref === activeCase?.case_ref ? "selected" : ""
                      }`}
                      onClick={() => setSelectedCaseRef(c.case_ref)}
                    >
                      <div className="item-header">
                        <strong className="item-ref">{c.case_ref}</strong>
                        <span className={`status-pill pill-${c.status}`}>
                          {c.status === "pending_approval"
                            ? s.statusPendingApproval
                            : c.status === "in_investigation"
                            ? s.statusInInvestigation
                            : c.status === "refused"
                            ? s.statusRefusedRule
                            : s.statusResolvedCase}
                        </span>
                      </div>
                      <div className="item-meta">
                        <span className="persona-tag">@{c.persona}</span>
                        <span className="rule-tag">{c.reason_rule_id}</span>
                        {c.amount && (
                          <span className="amount-tag">
                            {c.amount} {c.currency}
                          </span>
                        )}
                      </div>
                      <p className="item-msg">{c.customer_message}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="dossier-column" aria-label="Detalle del caso">
            {activeCase ? (
              <div className="active-case-detail">
                <div className="detail-banner">
                  <div className="banner-meta">
                    <span className="banner-kicker">{activeCase.case_ref}</span>
                    <h3>{activeCase.customer_message}</h3>
                  </div>
                  <div className="banner-tags">
                    <span className="persona-badge">Titular: @{activeCase.persona}</span>
                    <span className="rule-badge">Regla: {activeCase.reason_rule_id}</span>
                  </div>
                </div>

                {activeCase.gate_verdict === "block" && (
                  <div className="gate-block-banner" role="alert">
                    <ShieldAlert size={18} />
                    <div>
                      <strong>{s.gateBlockNoticeTitle}</strong>
                      <p>{s.gateBlockNoticeDesc}</p>
                      <code>{activeCase.reason_rule_id}</code>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="no-case-selected">{s.selectCasePrompt}</div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
