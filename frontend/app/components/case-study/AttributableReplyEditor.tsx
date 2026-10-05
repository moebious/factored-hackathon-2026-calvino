"use client";

import { useEffect, useState } from "react";
import {
  Edit3,
  FileCheck,
  History,
  Lock,
  RefreshCw,
  Send,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import type { OperatorQueueItem } from "../../types/case-study";
import type { Strings } from "../../i18n";

interface AttributableReplyEditorProps {
  item: OperatorQueueItem;
  strings: Strings;
  onSendReply: (reply: string) => Promise<void>;
  loading: boolean;
}

export function AttributableReplyEditor({
  item,
  strings: s,
  onSendReply,
  loading,
}: AttributableReplyEditorProps) {
  const defaultDraft = `Estimado/a titular (@${item.persona}): Hemos revisado su expediente ${item.case_ref}. ${
    item.target_action === "retry_payment"
      ? "Su reintento de pago ha sido procesado con autorización del equipo de operaciones."
      : item.reason_rule_id === "TOOL-NOT-OWNER"
      ? "Por motivos de seguridad y titularidad de cuenta, esta solicitud no puede ser ejecutada directamente."
      : "Un especialista del banco ha verificado la información de su transferencia y continuará la investigación."
  }`;

  const [editedText, setEditedText] = useState(defaultDraft);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    setEditedText(defaultDraft);
    setSubmitted(false);
  }, [item.case_ref, defaultDraft]);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editedText.trim() || loading || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSendReply(editedText);
      setSubmitted(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="attributable-reply-editor-card" onSubmit={handleSubmit}>
      <div className="editor-header">
        <div className="header-title">
          <Edit3 size={15} />
          <h4>{s.replyEditorTitle}</h4>
        </div>
        <div className="operator-signature">
          <UserCheck size={12} />
          <span>{s.replyEditorSignature} <strong>operator:demo-agent-01</strong></span>
        </div>
      </div>

      <div className="draft-comparison-grid">
        <div className="draft-pane original-draft">
          <span className="pane-label">
            <Lock size={10} /> {s.replyEditorOriginalDraft}
          </span>
          <div className="pane-content font-mono">{defaultDraft}</div>
        </div>

        <div className="draft-pane editable-draft">
          <span className="pane-label">
            <Edit3 size={10} /> {s.replyEditorEditedDraft}
          </span>
          <textarea
            className="editor-textarea"
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            placeholder={s.replyEditorPlaceholder}
            rows={4}
            disabled={loading || isSubmitting || item.status === "resolved"}
          />
        </div>
      </div>

      <div className="editor-footer">
        <div className="audit-provenance-note">
          <ShieldCheck size={13} />
          <span>{s.replyEditorProvenance}</span>
        </div>

        <button
          type="submit"
          className="btn-send-reply"
          disabled={loading || isSubmitting || !editedText.trim() || item.status === "resolved"}
        >
          {isSubmitting ? (
            <>
              <RefreshCw size={13} className="spin" /> {s.replyEditorSending}
            </>
          ) : submitted ? (
            <>
              <FileCheck size={14} /> {s.replySentSuccess}
            </>
          ) : (
            <>
              <Send size={13} /> {s.replyEditorSend}
            </>
          )}
        </button>
      </div>
    </form>
  );
}
