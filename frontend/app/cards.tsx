// The FR-7 card catalog: one component per key the hub can emit, rendered
// only from the payload the hub verified. An unknown key renders a named
// fallback card (the key plus the raw payload), never a crash and never a
// guessed field: a field the payload lacks is left out, not invented.

import type { ReactNode } from "react";
import { actionLabel, strings } from "./i18n";
import type { Lang } from "./i18n";
import type { Card } from "./types";

const text = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="card-field">
      <span className="card-label">{label}</span>
      <span className="card-value">{value}</span>
    </div>
  );
}

function CardShell({
  title,
  tone,
  children,
}: {
  title: string;
  tone?: "info" | "warn" | "ok";
  children: ReactNode;
}) {
  return (
    <section className={`card${tone ? ` card-${tone}` : ""}`} aria-label={title}>
      <h3>{title}</h3>
      <div className="card-body">{children}</div>
    </section>
  );
}

function PaymentStatusCard({ lang, payload }: { lang: Lang; payload: Record<string, unknown> }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardPaymentStatus}>
      <Field
        label={s.amount}
        value={`${text(payload.amount) ?? "—"} ${text(payload.currency) ?? ""}`}
      />
      <Field label={s.status} value={<span className="badge">{text(payload.status) ?? "—"}</span>} />
      {text(payload.booking_date) !== null && (
        <Field label={s.date} value={text(payload.booking_date)} />
      )}
      {text(payload.remittance_information) !== null && (
        <Field label={s.merchant} value={text(payload.remittance_information)} />
      )}
      {text(payload.entry_reference) !== null && (
        <Field label={s.reference} value={<code>{text(payload.entry_reference)}</code>} />
      )}
    </CardShell>
  );
}

function ProblemTransactionsCard({
  lang,
  payload,
}: {
  lang: Lang;
  payload: Record<string, unknown>;
}) {
  const s = strings(lang);
  const entries = Array.isArray(payload.entries) ? (payload.entries as Record<string, unknown>[]) : [];
  return (
    <CardShell title={s.cardProblemTransactions}>
      {entries.map((entry, index) => (
        <Field
          key={text(entry.entry_reference) ?? index}
          label={text(entry.entry_reference) ?? "—"}
          value={`${text(entry.amount) ?? "—"} ${text(entry.currency) ?? ""} · ${
            text(entry.status) ?? "—"
          }${text(entry.booking_date) ? ` · ${text(entry.booking_date)}` : ""}`}
        />
      ))}
    </CardShell>
  );
}

// The confirm button is bound to that exact action (UC-5): the resume call
// carries the awaiting_ref the hub parked, and the buttons disappear once
// the decision went out. ``disabled`` covers the in-flight resume, so a
// fast double click never fires two resumes.
function ActionConfirmationCard({
  lang,
  payload,
  decided,
  disabled,
  onConfirm,
  onDeny,
}: {
  lang: Lang;
  payload: Record<string, unknown>;
  decided: boolean;
  disabled?: boolean;
  onConfirm: () => void;
  onDeny: () => void;
}) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardActionConfirmation} tone="warn">
      <Field label={s.action} value={actionLabel(lang, payload.action)} />
      <Field
        label={s.amount}
        value={`${text(payload.amount) ?? "—"} ${text(payload.currency) ?? ""}`}
      />
      {text(payload.entry_reference) !== null && (
        <Field label={s.reference} value={<code>{text(payload.entry_reference)}</code>} />
      )}
      <div className="card-actions">
        {decided ? (
          <span className="card-decided">{s.decided}</span>
        ) : (
          <>
            <button type="button" disabled={disabled} onClick={onConfirm}>
              {s.confirm}
            </button>
            <button type="button" className="secondary" disabled={disabled} onClick={onDeny}>
              {s.deny}
            </button>
          </>
        )}
      </div>
    </CardShell>
  );
}

function ActionResultCard({ lang, payload }: { lang: Lang; payload: Record<string, unknown> }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardActionResult} tone="ok">
      <Field label={s.action} value={actionLabel(lang, payload.action)} />
      {text(payload.entry_reference) !== null && (
        <Field label={s.reference} value={<code>{text(payload.entry_reference)}</code>} />
      )}
      {text(payload.status) !== null && (
        <Field label={s.status} value={<span className="badge">{text(payload.status)}</span>} />
      )}
    </CardShell>
  );
}

function CaseOpenedCard({ lang, payload }: { lang: Lang; payload: Record<string, unknown> }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardCaseOpened} tone="info">
      <Field label={s.caseRef} value={<code>{text(payload.case_ref) ?? "—"}</code>} />
    </CardShell>
  );
}

function CaseStatusCard({ lang, payload }: { lang: Lang; payload: Record<string, unknown> }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardCaseStatus}>
      <Field label={s.caseRef} value={<code>{text(payload.case_ref) ?? "—"}</code>} />
      <Field label={s.status} value={<span className="badge">{text(payload.status) ?? "—"}</span>} />
      {text(payload.next_step) !== null && (
        <Field label={s.nextStep} value={text(payload.next_step)} />
      )}
    </CardShell>
  );
}

function HumanPathCard({ lang }: { lang: Lang }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardHumanPath} tone="info">
      <p>{s.cardHumanPathText}</p>
    </CardShell>
  );
}

function RefusalCard({ lang, payload }: { lang: Lang; payload: Record<string, unknown> }) {
  const s = strings(lang);
  return (
    <CardShell title={s.cardRefusal} tone="warn">
      <Field label={s.rule} value={<code>{text(payload.rule) ?? "—"}</code>} />
    </CardShell>
  );
}

// The named fallback: an unknown key shows the key and the raw payload, so
// a catalog drift is visible instead of silently dropped.
function FallbackCard({ lang, card }: { lang: Lang; card: Card }) {
  const s = strings(lang);
  return (
    <CardShell title={`${s.cardUnknown}: ${card.key}`} tone="warn">
      <pre>{JSON.stringify(card.payload, null, 2)}</pre>
    </CardShell>
  );
}

export function CardView({
  card,
  lang,
  decided,
  disabled,
  onConfirm,
  onDeny,
}: {
  card: Card | null;
  lang: Lang;
  decided: boolean;
  disabled?: boolean;
  onConfirm: () => void;
  onDeny: () => void;
}) {
  if (card === null) return null;
  switch (card.key) {
    case "payment_status":
      return <PaymentStatusCard lang={lang} payload={card.payload} />;
    case "problem_transactions":
      return <ProblemTransactionsCard lang={lang} payload={card.payload} />;
    case "action_confirmation":
      return (
        <ActionConfirmationCard
          lang={lang}
          payload={card.payload}
          decided={decided}
          disabled={disabled}
          onConfirm={onConfirm}
          onDeny={onDeny}
        />
      );
    case "action_result":
      return <ActionResultCard lang={lang} payload={card.payload} />;
    case "case_opened":
      return <CaseOpenedCard lang={lang} payload={card.payload} />;
    case "case_status":
      return <CaseStatusCard lang={lang} payload={card.payload} />;
    case "human_path":
      return <HumanPathCard lang={lang} />;
    case "refusal":
      return <RefusalCard lang={lang} payload={card.payload} />;
    default:
      return <FallbackCard lang={lang} card={card} />;
  }
}
