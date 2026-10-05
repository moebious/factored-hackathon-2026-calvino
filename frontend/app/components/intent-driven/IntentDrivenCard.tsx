"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  CalendarDays,
  CheckSquare,
  Clock3,
  Mic,
  Palette,
  Paperclip,
  Send,
  Sparkles,
  Split,
  Search,
  RotateCcw,
  X,
  AlertTriangle,
} from "lucide-react";
import type { AttachmentItem } from "../../types";
import { decide, detectIntent, type CalmState } from "./intent-engine";
import { SplitMorph } from "./morphs/SplitMorph";
import { ChecklistMorph } from "./morphs/ChecklistMorph";
import { StatusTrackMorph } from "./morphs/StatusTrackMorph";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

type IntentDrivenCardProps = {
  text: string;
  busy: boolean;
  lang: Lang;
  attachments: AttachmentItem[];
  onTextChange: (value: string) => void;
  onSubmit: () => void;
  onAttachmentsChange: (items: AttachmentItem[]) => void;
};

export function IntentDrivenCard({
  text,
  busy,
  lang,
  attachments,
  onTextChange,
  onSubmit,
  onAttachmentsChange,
}: IntentDrivenCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const s = strings(lang);
  const observed = useMemo(() => detectIntent(text, lang), [text, lang]);
  // Commit per-keystroke observations through the calm-UI hysteresis so the
  // morph preview only switches after a repeated intent (decision 45).
  const [calm, setCalm] = useState<CalmState | null>(null);
  useEffect(() => {
    setCalm((prev) => decide(prev, observed));
  }, [observed]);
  const intent = calm?.committed ?? observed;

  const { isListening, isSupported, toggleListening } = useSpeechRecognition({
    lang: lang === "pt" ? "pt-BR" : "es-ES",
    onResult: (transcription) => {
      onTextChange(transcription);
    },
  });

  const getIcon = () => {
    switch (intent.type) {
      case "split":
        return Split;
      case "checklist":
        return CheckSquare;
      case "event":
        return CalendarDays;
      case "timer":
        return Clock3;
      case "color":
        return Palette;
      case "status_track":
        return Search;
      case "action_retry":
        return RotateCcw;
      case "action_cancel":
        return X;
      case "dispute":
        return AlertTriangle;
      default:
        return Sparkles;
    }
  };

  const Icon = getIcon();

  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    const next = Array.from(files).slice(0, 4).map((file) => ({
      id: `${file.name}-${file.lastModified}`,
      name: file.name,
      mediaType: file.type || "application/octet-stream",
      size: file.size,
      url: URL.createObjectURL(file),
      status: "ready" as const,
    }));
    onAttachmentsChange([...attachments, ...next]);
  };

  const removeAttachment = (id: string) => {
    const item = attachments.find((attachment) => attachment.id === id);
    if (item) URL.revokeObjectURL(item.url);
    onAttachmentsChange(attachments.filter((attachment) => attachment.id !== id));
  };

  return (
    <section
      className={`intent-driven-card ${intent.type !== "conversation" ? "has-intent" : ""}`}
      aria-label={s.composerAriaLabel}
    >
      <div className="composer-orbit" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <div className="composer-head">
        <span className="composer-kicker">
          <span className="live-dot" /> Calvino Intent Engine
        </span>
        <span className="composer-hint">{intent.hint}</span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          className="morph-preview"
          key={intent.type}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          <span className="morph-icon">
            <Icon size={16} />
          </span>
          <span>{intent.label}</span>
          {intent.type !== "conversation" && <span className="morph-arrow">↗</span>}
        </motion.div>
      </AnimatePresence>

      {/* Morphing interactive widgets */}
      <AnimatePresence>
        {intent.type === "split" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="morph-widget-container"
          >
            <SplitMorph
              total={Number(intent.params.total || 0)}
              people={Number(intent.params.people || 2)}
              perPerson={Number(intent.params.perPerson || 0)}
              lang={lang}
            />
          </motion.div>
        )}

        {intent.type === "checklist" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="morph-widget-container"
          >
            <ChecklistMorph items={(intent.params.items as string[]) || []} lang={lang} />
          </motion.div>
        )}

        {intent.type === "status_track" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="morph-widget-container"
          >
            <StatusTrackMorph reference={String(intent.params.reference || "")} lang={lang} />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="composer-input-row">
        <input
          ref={inputRef}
          value={text}
          onChange={(event) => onTextChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          placeholder={s.composerPlaceholder}
          maxLength={2000}
          disabled={busy}
          aria-label={s.inputPlaceholder}
        />

        <button
          className="icon-button"
          type="button"
          aria-label={s.attachLocalFile}
          disabled={busy}
          onClick={() => inputRef.current?.focus()}
        >
          <label className="file-label">
            <Paperclip size={18} aria-hidden="true" />
            <input
              type="file"
              multiple
              hidden
              disabled={busy}
              onChange={(event) => handleFiles(event.target.files)}
            />
          </label>
        </button>

        {isSupported && (
          <button
            className={`icon-button voice-button ${isListening ? "is-listening" : ""}`}
            type="button"
            aria-label={isListening ? s.stopDictation : s.startDictation}
            aria-pressed={isListening}
            disabled={busy}
            onClick={toggleListening}
          >
            <Mic size={18} aria-hidden="true" />
            {isListening && <span className="voice-pulse" aria-hidden="true" />}
          </button>
        )}

        <button
          className="send-button"
          type="button"
          aria-label={s.sendMessage}
          disabled={busy || !text.trim()}
          onClick={onSubmit}
        >
          <Send size={17} />
        </button>
      </div>

      {attachments.length > 0 && (
        <div className="attachments attachments-inline">
          {attachments.map((item) => (
            <div key={item.id} className="attachment">
              <span className="attachment-info">{item.name}</span>
              <button
                type="button"
                className="icon-button attachment-remove"
                onClick={() => removeAttachment(item.id)}
                aria-label={`${s.removeAttachment} ${item.name}`}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="composer-footnote">
        <span>{s.enterToSend}</span>
        <span className="privacy-note">{s.verifiedWithHarness}</span>
        {busy && <span className="sending-note">{s.auditingDots}</span>}
      </p>
    </section>
  );
}
