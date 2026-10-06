"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowUpRight,
  ChevronRight,
  PanelRight,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { Attachments, AudioPlayer } from "./ai-elements";
import { CardView } from "./cards";
import { strings } from "./i18n";
import type { Lang } from "./i18n";
import { IntentDrivenCard } from "./components/intent-driven/IntentDrivenCard";
import { CaseDossier } from "./components/case-study/CaseDossier";
import { useHubConversation } from "./hooks/useHubConversation";
import { SCENARIOS, scenarioLabel } from "./scenarios";
import type { AttachmentItem } from "./types";

export default function Home() {
  const [lang, setLang] = useState<Lang>("es");
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [traceOpen, setTraceOpen] = useState(false);

  const {
    ready,
    turns,
    selected,
    setSelected,
    selectedCase,
    busy,
    error,
    setError,
    send,
    resume,
    resetConversation,
  } = useHubConversation();

  const s = strings(lang);

  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth > 900) {
      setTraceOpen(true);
    }
  }, []);

  // Reactive Human-in-the-Loop Intercept: Automatically open evidence rail when an action requires human intervention
  useEffect(() => {
    if (selectedCase?.pendingAction && !selectedCase.pendingAction.decided) {
      setTraceOpen(true);
    }
  }, [selectedCase?.pendingAction]);

  const handleSend = () => {
    if (text.trim() && !busy) {
      const msg = text.trim();
      const currentAttachments = [...attachments];
      setText("");
      setAttachments([]);
      void send(msg, undefined, currentAttachments);
    }
  };

  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (ready !== true) {
      const interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [ready]);

  if (ready !== true) {
    return (
      <main className="warmup-screen">
        <div className="warmup-orb" />
        <span className="brand-mark">
          <Sparkles size={18} /> Calvino
        </span>
        <h1>
          {s.warmupHeadline1}
          <br />
          <em>{s.warmupHeadline2}</em>
        </h1>
        <p>{ready === null ? s.warmupChecking : s.warmupLoading}</p>
        <div className="warmup-meta-pill">
          <code>{s.warmupCheckpoint}</code>
          <span>•</span>
          <span>{elapsedSeconds}s {s.warmupSecondsElapsed}</span>
        </div>
        <div className="loading-line">
          <span />
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label={s.brandHomeAria}>
          <span className="brand-symbol">
            <Sparkles size={16} />
          </span>
          Calvino
        </a>
        <nav className="view-switcher" aria-label={s.productNavAria}>
          <a href="/" className="view-tab active">
            <User size={13} /> {s.customerApp}
          </a>
          <a href="/console" className="view-tab">
            <ShieldCheck size={13} /> {s.operatorWorkspace}
          </a>
        </nav>
        <div className="topbar-status">
          <span className="live-dot" /> {s.systemProtected} <ShieldCheck size={15} />
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
            className="session-reset-btn"
            onClick={resetConversation}
            title={s.newSession}
          >
            <RotateCcw size={13} />
            <span>{s.newSession}</span>
          </button>
          <div className="sandbox-badge">
            <Sparkles size={13} className="text-mint" />
            <span>{s.sandboxSession}</span>
          </div>
        </div>
      </header>

      <main className="workspace">
        <section className="hero-column">
          <div className="hero-intro">
            <div className="hero-overline">
              <span className="overline-rule" /> {s.investigationTitle}
            </div>
            <h1>
              {s.heroHeadline1}
              <br />
              <span>{s.heroHeadline2}</span>
            </h1>
            <p>{s.heroDescription}</p>
          </div>

          <nav className="scenario-strip" aria-label={s.scenarios}>
            <div className="section-label">
              <span>{s.tryRoute}</span>
              <small>{s.guidedScenariosTitle || s.guidedDemo}</small>
            </div>
            <div className="scenario-scroll">
              {SCENARIOS.map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  className="scenario-chip"
                  disabled={busy}
                  onClick={() => {
                    void send(scenario.message, scenario.persona);
                  }}
                >
                  <span>{scenarioLabel(lang, scenario).split(" · ")[0]}</span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          </nav>

          <section className="conversation-stage" aria-label={s.conversation}>
            {turns.length === 0 && (
              <div className="empty-stage">
                <div className="empty-glyph">
                  <Sparkles size={22} />
                </div>
                <p>{s.emptyStageTitle}</p>
                <span>{s.emptyStageSubtitle}</span>
              </div>
            )}

            <ol className="turns">
              <AnimatePresence initial={false}>
                {turns.map((turn, index) => (
                  <motion.li
                    key={`${turn.message}-${index}`}
                    className="turn"
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35 }}
                  >
                    {/* Customer Turn */}
                    <div className="message customer-message">
                      <span className="message-label">
                        {s.you} <span>{s.now}</span>
                      </span>
                      <p>{turn.message}</p>
                      {turn.attachments && turn.attachments.length > 0 && (
                        <Attachments items={turn.attachments} variant="grid" lang={lang} />
                      )}
                    </div>

                    {/* Error Bubble */}
                    {turn.error && (
                      <div className="message error-message" role="alert">
                        <span className="message-label">Calvino</span>
                        <p>{turn.error}</p>
                      </div>
                    )}

                    {/* Calvino Verified Turn */}
                    {turn.reply && (
                      <div
                        className={`message assistant-message ${
                          selected === index ? "is-selected" : ""
                        }`}
                        onClick={() => setSelected(index)}
                        onKeyDown={(event) => event.key === "Enter" && setSelected(index)}
                        role="button"
                        tabIndex={0}
                        aria-pressed={selected === index}
                      >
                        <div className="assistant-heading">
                          <span className="assistant-avatar">
                            <Sparkles size={14} />
                          </span>
                          <span className="message-label">
                            Calvino <span>{s.verifiedResponse}</span>
                          </span>
                          <ArrowUpRight size={15} />
                        </div>

                        {turn.reply.reply && <p>{turn.reply.reply}</p>}

                        <CardView
                          card={turn.reply.card}
                          lang={lang}
                          decided={turn.decided}
                          disabled={busy}
                          onConfirm={() =>
                            turn.reply?.awaiting_ref &&
                            void resume(index, turn.reply.awaiting_ref, true)
                          }
                          onDeny={() =>
                            turn.reply?.awaiting_ref &&
                            void resume(index, turn.reply.awaiting_ref, false)
                          }
                        />

                        <div className="assistant-tools">
                          {turn.reply.reply && <AudioPlayer text={turn.reply.reply} lang={lang} />}
                          <button
                            type="button"
                            className="trace-link"
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelected(index);
                              setTraceOpen(true);
                            }}
                          >
                            {s.viewDossier} <ArrowUpRight size={13} />
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Pending State */}
                    {turn.reply === null && !turn.error && (
                      <div className="message assistant-message pending-message">
                        <span className="assistant-avatar">
                          <Sparkles size={14} />
                        </span>
                        <span>
                          {s.auditingEvidence}
                          <span className="typing-dots"> · · ·</span>
                        </span>
                      </div>
                    )}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ol>
          </section>

          {error && (
            <p className="error-banner" role="alert">
              {error}
              <button type="button" onClick={() => setError(null)}>
                <RotateCcw size={14} /> {s.close}
              </button>
            </p>
          )}

          {/* Morphing Intent-Driven Composer */}
          <IntentDrivenCard
            text={text}
            busy={busy}
            lang={lang}
            attachments={attachments}
            onTextChange={setText}
            onAttachmentsChange={setAttachments}
            onSubmit={handleSend}
          />
        </section>

        {/* Evidence & Case Dossier Rail */}
        <aside className={`evidence-rail ${traceOpen ? "is-open" : ""}`}>
          <div className="rail-header">
            <div>
              <span className="eyebrow">{s.controlView}</span>
              <h2>{s.dossier}</h2>
            </div>
            <button
              className="icon-button rail-close"
              type="button"
              aria-label={s.closeDossier}
              onClick={() => setTraceOpen(false)}
            >
              <PanelRight size={17} />
            </button>
          </div>

          <CaseDossier
            caseStudy={selectedCase}
            lang={lang}
            disabled={busy}
            onConfirmAction={(ref) => selected !== null && void resume(selected, ref, true)}
            onDenyAction={(ref) => selected !== null && void resume(selected, ref, false)}
            onResumeOperator={(ref, decision) =>
              selected !== null && void resume(selected, ref, decision)
            }
          />
        </aside>

        {!traceOpen && (
          <button
            className="open-rail"
            type="button"
            onClick={() => setTraceOpen(true)}
          >
            <PanelRight size={17} /> {s.dossier}
          </button>
        )}
      </main>
    </div>
  );
}
