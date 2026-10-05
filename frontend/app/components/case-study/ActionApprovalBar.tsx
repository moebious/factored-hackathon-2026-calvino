"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Lock,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { OperatorQueueItem } from "../../types/case-study";
import type { Strings } from "../../i18n";

interface ActionApprovalBarProps {
  item: OperatorQueueItem;
  strings: Strings;
  onApprove: () => Promise<void>;
  onDeny: () => Promise<void>;
  loading: boolean;
}

export function ActionApprovalBar({
  item,
  strings: s,
  onApprove,
  onDeny,
  loading,
}: ActionApprovalBarProps) {
  const isBlocked = item.gate_verdict === "block" || item.status === "refused";
  const isResolved = item.status === "resolved";
  const [submittingAction, setSubmittingAction] = useState<"approve" | "deny" | null>(null);

  const handleApprove = async () => {
    if (isBlocked || isResolved || loading) return;
    setSubmittingAction("approve");
    try {
      await onApprove();
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleDeny = async () => {
    if (isBlocked || isResolved || loading) return;
    setSubmittingAction("deny");
    try {
      await onDeny();
    } finally {
      setSubmittingAction(null);
    }
  };

  return (
    <div className="action-approval-bar-card">
      <div className="approval-bar-header">
        <div className="title-group">
          <ShieldCheck size={16} className="approval-icon" />
          <div>
            <h4>Control de Ejecución Regulada</h4>
            <span className="subtitle">
              {item.target_action ? `Acción: ${item.target_action}` : "Revisión manual requerida"}
            </span>
          </div>
        </div>

        <div className="verdict-tag">
          {item.gate_verdict === "ask" && (
            <span className="gate-ask-badge">Zona Gris (Gate ASK)</span>
          )}
          {item.gate_verdict === "block" && (
            <span className="gate-block-badge">
              <Lock size={10} /> Gate BLOCK
            </span>
          )}
        </div>
      </div>

      {isBlocked ? (
        <div className="approval-blocked-notice" role="alert">
          <ShieldAlert size={16} />
          <div className="notice-content">
            <strong>Botones de aprobación deshabilitados por diseño</strong>
            <p>
              La política de seguridad bancaria vetó esta acción (<code>{item.reason_rule_id}</code>).
              Un operador humano no tiene autoridad para anular un bloqueo del Gate (Decisión 37).
            </p>
          </div>
        </div>
      ) : isResolved ? (
        <div className="approval-resolved-notice">
          <CheckCircle2 size={16} />
          <span>Acción ejecutada y asentada en el registro de auditoría.</span>
        </div>
      ) : (
        <div className="approval-actions-row">
          <button
            type="button"
            className="btn-approve"
            onClick={handleApprove}
            disabled={loading || submittingAction !== null}
            title={s.actionApprove}
          >
            {submittingAction === "approve" ? (
              <>
                <RefreshCw size={13} className="spin" /> {s.actionApproving}
              </>
            ) : (
              <>
                <CheckCircle2 size={14} /> {s.actionApprove}
              </>
            )}
          </button>

          <button
            type="button"
            className="btn-deny"
            onClick={handleDeny}
            disabled={loading || submittingAction !== null}
            title={s.actionDeny}
          >
            {submittingAction === "deny" ? (
              <>
                <RefreshCw size={13} className="spin" /> {s.actionDenying}
              </>
            ) : (
              <>
                <XCircle size={14} /> {s.actionDeny}
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
