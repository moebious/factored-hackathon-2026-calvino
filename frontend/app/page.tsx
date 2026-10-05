"use client";

// The premium demo shell. Calvino owns the verified workflow; Shapeshift
// owns the first-second interaction and adapts gracefully when media APIs are
// unavailable.

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, ChevronRight, PanelRight, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { Attachments, AudioPlayer, ChainOfThought } from "./ai-elements";
import { CardView } from "./cards";
import { GlassBox } from "./glassbox";
import { strings } from "./i18n";
import type { Lang } from "./i18n";
import { ShapeshiftComposer } from "./shapeshift";
import { SCENARIOS, scenarioLabel } from "./scenarios";
import type { AttachmentItem, HubReply, Turn } from "./types";

const READY_POLL_MS = 3000;

export default function Home() {
  const [lang, setLang] = useState<Lang>("es");
  const [ready, setReady] = useState<boolean | null>(null);
  const [persona, setPersona] = useState("ana");
  const [personas, setPersonas] = useState(["ana", "camilo", "lucia", "dana"]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [operatorDecision, setOperatorDecision] = useState("");
  const [traceOpen, setTraceOpen] = useState(false);

  const s = strings(lang);

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

  useEffect(() => {
    if (window.innerWidth > 900) setTraceOpen(true);
  }, []);

  const post = useCallback(async (path: string, body: unknown): Promise<HubReply> => {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `failed (${response.status})`);
    return payload as HubReply;
  }, []);

  const send = useCallback(async (message: string, asPersona: string, inputAttachments = attachments) => {
    setBusy(true);
    setError(null);
    const turnIndex = turns.length;
    setTurns((previous) => [...previous, { message, reply: null, error: null, attachments: inputAttachments, decided: false }]);
    setText("");
    setAttachments([]);
    try {
      const reply = await post("/api/hub/message", { persona: asPersona, text: message });
      setTurns((previous) => {
        const next = [...previous];
        next[turnIndex] = { message, reply, error: null, attachments: inputAttachments, decided: false };
        return next;
      });
      setSelected(turnIndex);
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : s.unreachable;
      setTurns((previous) => {
        const next = [...previous];
        next[turnIndex] = { message, reply: null, error: detail, attachments: inputAttachments, decided: false };
        return next;
      });
      setError(detail);
    } finally {
      setBusy(false);
    }
  }, [attachments, post, s.unreachable, turns.length]);

  const resume = useCallback(async (index: number, ref: string, decision: boolean | string) => {
    setBusy(true);
    setError(null);
    try {
      const reply = await post("/api/hub/resume", { ref, decision });
      setTurns((previous) => previous.map((turn, turnIndex) => turnIndex === index ? { ...turn, reply, decided: true } : turn));
      setSelected(index);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : s.unreachable);
    } finally {
      setBusy(false);
    }
  }, [post, s.unreachable]);

  const loadPersonas = useCallback(async () => {
    try {
      const response = await fetch("/api/hub/personas");
      if (response.ok) {
        const body = await response.json();
        if (Array.isArray(body.personas) && body.personas.length > 0) setPersonas(body.personas as string[]);
      }
    } catch {
      setError(s.unreachable);
    }
  }, [s.unreachable]);

  const selectedReply = selected !== null ? (turns[selected]?.reply ?? null) : null;

  if (ready !== true) {
    return (
      <main className="warmup-screen">
        <div className="warmup-orb" />
        <span className="brand-mark"><Sparkles size={18} /> Calvino</span>
        <h1>La banca que<br /><em>piensa contigo.</em></h1>
        <p>{ready === null ? s.warmupChecking : s.warmupLoading}</p>
        <div className="loading-line"><span /></div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Calvino inicio"><span className="brand-symbol"><Sparkles size={16} /></span>Calvino</a>
        <div className="topbar-status"><span className="live-dot" /> Sistema protegido <ShieldCheck size={15} /></div>
        <div className="topbar-actions">
          <div className="language-switch" role="group" aria-label="Idioma">
            <button type="button" className={lang === "es" ? "active" : ""} onClick={() => setLang("es")}>ES</button>
            <button type="button" className={lang === "pt" ? "active" : ""} onClick={() => setLang("pt")}>PT</button>
          </div>
          <span className="topbar-divider" />
          <label className="persona-select">
            <span>Perfil</span>
            <select value={persona} onChange={(event) => setPersona(event.target.value)} onFocus={loadPersonas}>
              {personas.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
        </div>
      </header>

      <main className="workspace">
        <section className="hero-column">
          <div className="hero-intro">
            <div className="hero-overline"><span className="overline-rule" /> Tu espacio de decisión</div>
            <h1>Hazlo simple.<br /><span>Hazlo seguro.</span></h1>
            <p>Una conversación que se adapta a lo que necesitas. Cada respuesta tiene evidencia detrás.</p>
          </div>

          <nav className="scenario-strip" aria-label={s.scenarios}>
            <div className="section-label"><span>Prueba una ruta</span><small>Demo guiada</small></div>
            <div className="scenario-scroll">
              {SCENARIOS.map((scenario, index) => (
                <button key={scenario.id} type="button" className="scenario-chip" disabled={busy} onClick={() => {
                  setPersona(scenario.persona);
                  void send(scenario.message, scenario.persona);
                }}>
                  <span>{scenarioLabel(lang, scenario).split(" · ")[0]}</span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          </nav>

          <section className="conversation-stage" aria-label="Conversación">
            {turns.length === 0 && (
              <div className="empty-stage">
                <div className="empty-glyph"><Sparkles size={22} /></div>
                <p>Tu siguiente decisión empieza aquí.</p>
                <span>Escribe una pregunta o elige una ruta de demo.</span>
              </div>
            )}
            <ol className="turns">
              <AnimatePresence initial={false}>
                {turns.map((turn, index) => (
                  <motion.li key={`${turn.message}-${index}`} className="turn" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
                    <div className="message customer-message">
                      <span className="message-label">Tú <span>ahora</span></span>
                      <p>{turn.message}</p>
                      {turn.attachments && <Attachments items={turn.attachments} variant="grid" />}
                    </div>
                    {turn.error && <div className="message error-message" role="alert"><span className="message-label">Calvino</span><p>{turn.error}</p></div>}
                    {turn.reply && (
                      <div className={`message assistant-message ${selected === index ? "is-selected" : ""}`} onClick={() => setSelected(index)} onKeyDown={(event) => event.key === "Enter" && setSelected(index)} role="button" tabIndex={0} aria-pressed={selected === index}>
                        <div className="assistant-heading"><span className="assistant-avatar"><Sparkles size={14} /></span><span className="message-label">Calvino <span>respuesta verificada</span></span><ArrowUpRight size={15} /></div>
                        {turn.reply.reply && <p>{turn.reply.reply}</p>}
                        <CardView card={turn.reply.card} lang={lang} decided={turn.decided} disabled={busy} onConfirm={() => turn.reply?.awaiting_ref && void resume(index, turn.reply.awaiting_ref, true)} onDeny={() => turn.reply?.awaiting_ref && void resume(index, turn.reply.awaiting_ref, false)} />
                        <div className="assistant-tools"><AudioPlayer text={turn.reply.reply} /><button type="button" className="trace-link" onClick={(event) => { event.stopPropagation(); setSelected(index); setTraceOpen(true); }}>Ver evidencia <ArrowUpRight size={13} /></button></div>
                        {turn.reply.awaiting === "operator_queue" && turn.reply.awaiting_ref && !turn.decided && (
                          <div className="operator-resume">
                            <input value={operatorDecision} onChange={(event) => setOperatorDecision(event.target.value)} placeholder={s.operatorDecision} />
                            <button type="button" disabled={busy || !operatorDecision.trim()} onClick={() => void resume(index, turn.reply?.awaiting_ref ?? "", operatorDecision.trim())}>{s.operatorResume}</button>
                          </div>
                        )}
                      </div>
                    )}
                    {turn.reply === null && !turn.error && <div className="message assistant-message pending-message"><span className="assistant-avatar"><Sparkles size={14} /></span><span>Calvino está revisando la evidencia<span className="typing-dots"> · · ·</span></span></div>}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ol>
          </section>
          {error && <p className="error-banner" role="alert">{error}<button type="button" onClick={() => setError(null)}><RotateCcw size={14} /> Cerrar</button></p>}
          <ShapeshiftComposer text={text} busy={busy} lang={lang} attachments={attachments} onTextChange={setText} onAttachmentsChange={setAttachments} onSubmit={() => { if (text.trim() && !busy) void send(text.trim(), persona); }} />
        </section>

        <aside className={`evidence-rail ${traceOpen ? "is-open" : ""}`}>
          <div className="rail-header"><div><span className="eyebrow">Vista de control</span><h2>Evidencia</h2></div><button className="icon-button rail-close" type="button" aria-label="Cerrar evidencia" onClick={() => setTraceOpen(false)}><PanelRight size={17} /></button></div>
          <div className="rail-summary"><span className="verified-icon"><ShieldCheck size={17} /></span><div><strong>{selectedReply ? "Respuesta trazable" : "Listo para empezar"}</strong><p>{selectedReply ? "Basada en datos verificados" : "La evidencia aparecerá aquí"}</p></div></div>
          <ChainOfThought steps={selectedReply?.trace ?? []} open={traceOpen} onOpenChange={setTraceOpen} />
          <GlassBox reply={selectedReply} lang={lang} />
        </aside>
        {!traceOpen && <button className="open-rail" type="button" onClick={() => setTraceOpen(true)}><PanelRight size={17} /> Evidencia</button>}
      </main>
    </div>
  );
}
