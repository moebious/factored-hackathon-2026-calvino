// The glass-box panel (FR-12): the selected turn's decision trace, exactly
// as the harness logged it — stage, rule, verdict, the classifier's scores
// and each record's summary. The panel reads only HubReply.trace, so it can
// never show data the harness did not log.

import { strings } from "./i18n";
import type { Lang } from "./i18n";
import { percent } from "./types";
import type { HubReply } from "./types";

export function GlassBox({ reply, lang }: { reply: HubReply | null; lang: Lang }) {
  const s = strings(lang);
  if (reply === null) {
    return (
      <aside className="glassbox" aria-label={s.glassBox}>
        <h2>{s.glassBox}</h2>
        <p className="muted">{s.glassBoxEmpty}</p>
      </aside>
    );
  }
  return (
    <aside className="glassbox" aria-label={s.glassBox}>
      <h2>{s.glassBox}</h2>
      <p className="glassbox-meta">
        {s.route}: <strong>{reply.route}</strong>
        {reply.escalated && (
          <>
            {" · "}
            <strong>{s.escalated}</strong>
          </>
        )}
        {reply.case_ref !== null && (
          <>
            {" · "}
            {s.caseRef}: <code>{reply.case_ref}</code>
          </>
        )}
      </p>
      {reply.trace.map((step, index) => (
        <article key={`${step.stage}-${index}`} className="trace-step">
          <h3>
            {step.stage}
            {step.rule_id !== null && <code> · {step.rule_id}</code>}
          </h3>
          <p>
            {s.verdict}: <strong>{step.verdict}</strong>
          </p>
          {Object.keys(step.scores).length > 0 && (
            <>
              <h4>{s.scores}</h4>
              <ul>
                {Object.entries(step.scores).map(([name, value]) => (
                  <li key={name}>
                    {name}: {percent(value)}
                  </li>
                ))}
              </ul>
            </>
          )}
          {Object.keys(step.summary).length > 0 && (
            <>
              <h4>{s.summary}</h4>
              <ul>
                {Object.entries(step.summary).map(([name, value]) => (
                  <li key={name}>
                    {name}: {String(value)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </article>
      ))}
    </aside>
  );
}
