"use client";

// The customer app (TSD-010, decision 10): one screen with the persona
// selector, the conversation, the FR-7 card under each Calvino reply, the
// scenario buttons for every demo use case, the ES / PT chrome toggle and
// the glass-box panel for the selected turn. The UI is a verdict: every
// card comes from the hub's fixed catalog, filled only from verified data.
// A parked approve_action turn shows confirm / deny buttons bound to that
// exact action; a parked operator_queue turn offers the operator's resume.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { CardView } from "./cards";
import { GlassBox } from "./glassbox";
import { strings } from "./i18n";
import type { Lang } from "./i18n";
import { SCENARIOS, scenarioLabel } from "./scenarios";
import type { HubReply, Turn } from "./types";
import { useVoiceInput } from "./voice";

// A cold Space can take a while even with baked weights (in-memory preload);
// polling every 3 s keeps the warm-up screen honest without hammering it.
const READY_POLL_MS = 3000;

const PASSCODE_HEADER = "x-calvino-passcode";

export default function Home() {
  const [lang, setLang] = useState<Lang>("es");
  const [ready, setReady] = useState<boolean | null>(null);
  const [passcode, setPasscode] = useState("");
  const [persona, setPersona] = useState("ana");
  const [personas, setPersonas] = useState<string[]>(["ana", "camilo", "lucia", "dana"]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [operatorDecision, setOperatorDecision] = useState("");

  const s = strings(lang);

  const appendTranscript = useCallback((transcript: string) => {
    setText((previous) => (previous.length > 0 ? `${previous} ${transcript}` : transcript));
  }, []);

  const voice = useVoiceInput({
    lang: lang === "pt" ? "pt-BR" : "es-ES",
    onFinalText: appendTranscript,
  });
  const listening = voice.status === "listening";

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

  const post = useCallback(
    async (path: string, body: unknown): Promise<HubReply> => {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", [PASSCODE_HEADER]: passcode },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string" ? payload.detail : `failed (${response.status})`,
        );
      }
      return payload as HubReply;
    },
    [passcode],
  );

  const send = useCallback(
    async (message: string, asPersona: string) => {
      setBusy(true);
      setError(null);
      setTurns((previous) => [...previous, { message, reply: null, error: null, decided: false }]);
      try {
        const reply = await post("/api/hub/message", { persona: asPersona, text: message });
        setTurns((previous) => {
          const next = [...previous];
          next[next.length - 1] = { message, reply, error: null, decided: false };
          return next;
        });
        setSelected(turns.length); // the reply about to land
      } catch (failure) {
        const detail = failure instanceof Error ? failure.message : s.unreachable;
        setTurns((previous) => {
          const next = [...previous];
          next[next.length - 1] = { message, reply: null, error: detail, decided: false };
          return next;
        });
        setError(detail);
      } finally {
        setBusy(false);
      }
    },
    [post, s.unreachable, turns.length],
  );

  const resume = useCallback(
    async (index: number, ref: string, decision: boolean | string) => {
      setBusy(true);
      setError(null);
      try {
        const reply = await post("/api/hub/resume", { ref, decision });
        setTurns((previous) => {
          const next = [...previous];
          const turn = next[index];
          next[index] = { ...turn, reply, decided: true };
          return next;
        });
        setSelected(index);
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : s.unreachable);
      } finally {
        setBusy(false);
      }
    },
    [post, s.unreachable],
  );

  const loadPersonas = useCallback(async () => {
    try {
      const response = await fetch("/api/hub/personas", {
        headers: { [PASSCODE_HEADER]: passcode },
      });
      if (response.ok) {
        const body = await response.json();
        if (Array.isArray(body.personas) && body.personas.length > 0) {
          setPersonas(body.personas as string[]);
        }
      }
    } catch {
      // The built-in demo names stay; the selector works either way.
    }
  }, [passcode]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const message = text.trim();
    if (message.length === 0 || busy) return;
    setText("");
    void send(message, persona);
  };

  const onScenario = (index: number) => {
    if (busy) return;
    const scenario = SCENARIOS[index];
    setPersona(scenario.persona);
    void send(scenario.message, scenario.persona);
  };

  if (ready !== true) {
    return (
      <main className="warmup">
        <h1>{s.title}</h1>
        <p>{ready === null ? s.warmupChecking : s.warmupLoading}</p>
      </main>
    );
  }

  const selectedReply = selected !== null ? (turns[selected]?.reply ?? null) : null;

  return (
    <div className="layout">
      <header className="topbar">
        <h1>{s.title}</h1>
        <p className="tagline">{s.tagline}</p>
        <div className="controls">
          <label>
            {s.persona}
            <select
              value={persona}
              onChange={(event) => setPersona(event.target.value)}
              onFocus={loadPersonas}
            >
              {personas.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {s.passcode}
            <input
              type="password"
              value={passcode}
              onChange={(event) => setPasscode(event.target.value)}
              onBlur={loadPersonas}
              autoComplete="off"
            />
          </label>
          <div className="lang-toggle" role="group" aria-label="ES / PT">
            <button
              type="button"
              className={lang === "es" ? "active" : "secondary"}
              onClick={() => setLang("es")}
            >
              ES
            </button>
            <button
              type="button"
              className={lang === "pt" ? "active" : "secondary"}
              onClick={() => setLang("pt")}
            >
              PT
            </button>
          </div>
        </div>
      </header>

      <main className="conversation">
        <nav className="scenarios" aria-label={s.scenarios}>
          <h2>{s.scenarios}</h2>
          <div className="scenario-buttons">
            {SCENARIOS.map((scenario, index) => (
              <button
                key={scenario.id}
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => onScenario(index)}
              >
                {scenarioLabel(lang, scenario)}
              </button>
            ))}
          </div>
        </nav>

        <ol className="turns">
          {turns.map((turn, index) => (
            <li key={index} className="turn">
              <div className="bubble customer">
                <span className="who">{s.you}</span>
                <p>{turn.message}</p>
              </div>
              {turn.error !== null && (
                <div className="bubble calvino" role="alert">
                  <span className="who">{s.calvino}</span>
                  <p>{turn.error}</p>
                </div>
              )}
              {turn.reply !== null && (
                <div
                  className={`bubble calvino${selected === index ? " selected" : ""}`}
                  onClick={() => setSelected(index)}
                  onKeyDown={(event) => event.key === "Enter" && setSelected(index)}
                  role="button"
                  tabIndex={0}
                  aria-pressed={selected === index}
                >
                  <span className="who">{s.calvino}</span>
                  {turn.reply.reply.length > 0 && <p>{turn.reply.reply}</p>}
                  <CardView
                    card={turn.reply.card}
                    lang={lang}
                    decided={turn.decided}
                    disabled={busy}
                    onConfirm={() =>
                      turn.reply?.awaiting_ref !== null &&
                      void resume(index, turn.reply?.awaiting_ref ?? "", true)
                    }
                    onDeny={() =>
                      turn.reply?.awaiting_ref !== null &&
                      void resume(index, turn.reply?.awaiting_ref ?? "", false)
                    }
                  />
                  {turn.reply.awaiting === "operator_queue" &&
                    turn.reply.awaiting_ref !== null &&
                    !turn.decided && (
                      <div className="operator-resume">
                        <input
                          value={operatorDecision}
                          onChange={(event) => setOperatorDecision(event.target.value)}
                          placeholder={s.operatorDecision}
                        />
                        <button
                          type="button"
                          disabled={busy || operatorDecision.trim().length === 0}
                          onClick={() =>
                            void resume(
                              index,
                              turn.reply?.awaiting_ref ?? "",
                              operatorDecision.trim(),
                            )
                          }
                        >
                          {s.operatorResume}
                        </button>
                      </div>
                    )}
                </div>
              )}
              {turn.reply === null && turn.error === null && (
                <div className="bubble calvino pending">
                  <span className="who">{s.calvino}</span>
                  <p>{s.sending}</p>
                </div>
              )}
            </li>
          ))}
        </ol>

        {error !== null && <p role="alert">{error}</p>}

        <form onSubmit={onSubmit} className="composer">
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={s.inputPlaceholder}
            maxLength={2000}
            disabled={busy}
            aria-label={s.inputPlaceholder}
          />
          {voice.supported ? (
            listening ? (
              <button type="button" onClick={voice.stop} aria-label={s.voiceStop}>
                {s.voiceStop}
              </button>
            ) : (
              <button
                type="button"
                className="secondary"
                onClick={voice.start}
                disabled={busy}
                aria-label={s.voiceStart}
              >
                {s.voiceStart}
              </button>
            )
          ) : null}
          <button type="submit" disabled={busy || text.trim().length === 0}>
            {busy ? s.sending : s.send}
          </button>
        </form>
        {listening && (
          <p role="status">
            {s.voiceListening}
            {voice.interim.length > 0 && ` ${voice.interim}`}
          </p>
        )}
        {!voice.supported && <p className="muted">{s.voiceNotSupported}</p>}
        {voice.status === "denied" && <p role="alert">{s.voiceDenied}</p>}
        {voice.status === "error" && <p role="alert">{s.voiceError}</p>}
      </main>

      <GlassBox reply={selectedReply} lang={lang} />
    </div>
  );
}
