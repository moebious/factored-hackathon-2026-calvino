"use client";

// The minimal demo frontend (TSD-003): a warm-up screen that polls /ready
// until the backend's Laya is loaded, then one form that sends a short
// customer message to /api/demo/decide and shows the glass box: the verdict,
// the rule that fired, the calibrated scores and the per-question
// probabilities (decision 10). The customer app (T-205) replaces this page.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type DemoAnswer = {
  chosen_option: string;
  confidence: number;
  probabilities: Record<string, number>;
};

type DemoDecision = {
  decision_id: string;
  route: string;
  human_action: string;
  rule_id: string;
  policy_version: string;
  scores: Record<string, number>;
  answers: Record<string, DemoAnswer>;
};

// A cold Space can take a while even with baked weights (in-memory preload);
// polling every 3 s keeps the warm-up screen honest without hammering it.
const READY_POLL_MS = 3000;

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function Home() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [text, setText] = useState("Mi transferencia sigue pendiente desde ayer.");
  const [passcode, setPasscode] = useState("");
  const [decision, setDecision] = useState<DemoDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const response = await fetch("/ready");
        const body = await response.json();
        if (active) setReady(Boolean(body.ready));
      } catch {
        if (active) setReady(false);
      }
    };
    poll();
    const timer = setInterval(poll, READY_POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const decide = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const response = await fetch("/api/demo/decide", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-calvino-passcode": passcode,
          },
          body: JSON.stringify({ text }),
        });
        const body = await response.json();
        if (response.ok) {
          setDecision(body as DemoDecision);
        } else {
          setDecision(null);
          setError(typeof body.detail === "string" ? body.detail : `failed (${response.status})`);
        }
      } catch {
        setDecision(null);
        setError("the demo backend is unreachable");
      } finally {
        setBusy(false);
      }
    },
    [passcode, text],
  );

  if (ready !== true) {
    return (
      <main>
        <h1>Calvino</h1>
        <p>
          {ready === null
            ? "Checking the backend…"
            : "Warming up: loading the Laya model. A cold start can take a minute."}
        </p>
      </main>
    );
  }

  return (
    <main>
      <h1>Calvino demo</h1>
      <p>
        One short customer message → calibrated Laya probabilities → a deterministic policy
        verdict. Nothing on this screen is free-form generation.
      </p>

      <form onSubmit={decide}>
        <label>
          Customer message
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={3}
            maxLength={2000}
            required
          />
        </label>
        <label>
          Demo passcode
          <input
            type="password"
            value={passcode}
            onChange={(event) => setPasscode(event.target.value)}
            autoComplete="off"
            required
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Deciding…" : "Decide"}
        </button>
      </form>

      {error !== null && <p role="alert">{error}</p>}

      {decision !== null && (
        <section aria-label="decision">
          <h2>Verdict</h2>
          <dl>
            <dt>Route</dt>
            <dd>{decision.route}</dd>
            <dt>Human action</dt>
            <dd>{decision.human_action}</dd>
            <dt>Rule fired</dt>
            <dd>
              <code>{decision.rule_id}</code>
            </dd>
            <dt>Policy version</dt>
            <dd>{decision.policy_version}</dd>
            <dt>Decision id</dt>
            <dd>
              <code>{decision.decision_id}</code>
            </dd>
          </dl>

          <h2>Scores the policy read</h2>
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(decision.scores).map(([name, value]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{percent(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>Laya answers</h2>
          {Object.entries(decision.answers).map(([questionId, answer]) => (
            <article key={questionId}>
              <h3>{questionId}</h3>
              <p>
                Chosen: <strong>{answer.chosen_option}</strong> (confidence{" "}
                {percent(answer.confidence)})
              </p>
              <ul>
                {Object.entries(answer.probabilities).map(([option, probability]) => (
                  <li key={option}>
                    {option}: {percent(probability)}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
