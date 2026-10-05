"use client";

import type { ReactNode } from "react";
import {
  AlertCircle,
  Calendar,
  CheckCircle,
  Database,
  FileText,
  Lock,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Tag,
  User,
} from "lucide-react";
import type { OperatorQueueItem } from "../../types/case-study";
import type { Strings } from "../../i18n";

interface OperatorCaseDossierProps {
  item: OperatorQueueItem;
  strings: Strings;
  children?: ReactNode;
}

export function OperatorCaseDossier({
  item,
  strings: s,
  children,
}: OperatorCaseDossierProps) {
  const isBlocked = item.gate_verdict === "block";

  return (
    <div className="operator-case-dossier">
      <header className="dossier-header">
        <div className="dossier-id-row">
          <div className="id-group">
            <span className="id-kicker">Expediente Oficial</span>
            <h2>{item.case_ref}</h2>
          </div>
          <span className={`status-pill pill-${item.status}`}>
            {item.status === "pending_approval"
              ? s.statusPendingApproval
              : item.status === "in_investigation"
              ? s.statusInInvestigation
              : item.status === "refused"
              ? s.statusRefusedRule
              : s.statusResolvedCase}
          </span>
        </div>

        <div className="dossier-meta-chips">
          <span className="meta-chip">
            <User size={12} /> Titular: <strong>@{item.persona}</strong>
          </span>
          <span className="meta-chip">
            <Tag size={12} /> Regla: <code>{item.reason_rule_id}</code>
          </span>
          <span className="meta-chip">
            <Calendar size={12} /> Registrado:{" "}
            <time dateTime={item.created_at}>
              {new Date(item.created_at).toLocaleString()}
            </time>
          </span>
        </div>
      </header>

      {/* Gate Block Safety Warning */}
      {isBlocked && (
        <div className="gate-block-refusal-card" role="alert">
          <div className="card-icon">
            <ShieldAlert size={20} />
          </div>
          <div className="card-body">
            <h4>{s.gateBlockNoticeTitle}</h4>
            <p>{s.gateBlockNoticeDesc}</p>
            <div className="rule-enforcement-tag">
              <Lock size={12} />
              <span>Regla aplicada: <strong>{item.reason_rule_id}</strong> (Inmutable)</span>
            </div>
          </div>
        </div>
      )}

      {/* Customer Request Section */}
      <section className="dossier-card customer-inquiry-card">
        <div className="card-header">
          <FileText size={14} />
          <h3>Consulta y Declaración del Cliente</h3>
        </div>
        <blockquote className="customer-quote">
          &ldquo;{item.customer_message}&rdquo;
        </blockquote>

      </section>

      {/* Read-Only Immutable Bank Facts */}
      <section className="dossier-card bank-facts-card">
        <div className="card-header">
          <Database size={14} />
          <h3>Evidencia Bancaria Verificada (Solo Lectura)</h3>
          <span className="immutable-badge">
            <Lock size={11} /> Inmutable
          </span>
        </div>

        <div className="facts-grid">
          <div className="fact-item">
            <span className="fact-label">Referencia de Transacción</span>
            <strong className="fact-value font-mono">
              {item.entry_reference || "Sin transacción vinculada"}
            </strong>
          </div>
          <div className="fact-item">
            <span className="fact-label">Monto Verificado</span>
            <strong className="fact-value font-mono amount-highlight">
              {item.amount ? `${item.amount} ${item.currency}` : "N/A"}
            </strong>
          </div>
          <div className="fact-item">
            <span className="fact-label">Acción Destino</span>
            <strong className="fact-value font-mono">
              {item.target_action || "Investigación general"}
            </strong>
          </div>
          <div className="fact-item">
            <span className="fact-label">Veredicto Gate</span>
            <strong className={`fact-value font-mono verdict-${item.gate_verdict || "none"}`}>
              {item.gate_verdict ? item.gate_verdict.toUpperCase() : "ESCALACIÓN HUMANA"}
            </strong>
          </div>
        </div>

        <p className="immutable-notice">
          <Scale size={12} />
          {s.auditTimelineImmutableNotice}
        </p>
      </section>

      {/* Interactive Operational Controls & Attributable Reply Slot */}
      {children}
    </div>
  );
}
