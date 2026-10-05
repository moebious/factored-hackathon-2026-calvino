"use client";

// The hero composer. It keeps Shapeshift's core promise, one input that
// changes shape with intent, while Calvino remains authoritative for actions.

import { AnimatePresence, motion } from "motion/react";
import { CalendarDays, CheckSquare, Clock3, Palette, Paperclip, Send, Sparkles, Split, X } from "lucide-react";
import { useMemo, useRef } from "react";
import { Attachments, SpeechInput } from "./ai-elements";
import type { AttachmentItem } from "./types";

type ComposerProps = {
  text: string;
  busy: boolean;
  lang: string;
  attachments: AttachmentItem[];
  onTextChange: (value: string) => void;
  onSubmit: () => void;
  onAttachmentsChange: (items: AttachmentItem[]) => void;
};

const morphs = [
  { match: /split|divide|entre/i, label: "split", icon: Split, hint: "Divide un importe entre personas" },
  { match: /todo|comprar|lista|check/i, label: "checklist", icon: CheckSquare, hint: "Convierte ideas en pasos" },
  { match: /mañana|viernes|cita|reunión|evento/i, label: "event", icon: CalendarDays, hint: "Prepara un evento con fecha" },
  { match: /minutos|timer|temporizador/i, label: "timer", icon: Clock3, hint: "Inicia un temporizador" },
  { match: /color|#[0-9a-f]{3,8}/i, label: "color", icon: Palette, hint: "Explora un color" },
];

export function ShapeshiftComposer({
  text,
  busy,
  lang,
  attachments,
  onTextChange,
  onSubmit,
  onAttachmentsChange,
}: ComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const intent = useMemo(() => morphs.find((item) => item.match.test(text)), [text]);
  const Icon = intent?.icon ?? Sparkles;

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

  const remove = (id: string) => {
    const item = attachments.find((attachment) => attachment.id === id);
    if (item) URL.revokeObjectURL(item.url);
    onAttachmentsChange(attachments.filter((attachment) => attachment.id !== id));
  };

  return (
    <section className={`shapeshift-composer ${intent ? "has-intent" : ""}`} aria-label="Composer principal">
      <div className="composer-orbit" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="composer-head">
        <span className="composer-kicker"><span className="live-dot" /> Calvino studio</span>
        <span className="composer-hint">{intent?.hint ?? "Escribe, habla o adjunta. Yo encuentro la forma."}</span>
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          className="morph-preview"
          key={intent?.label ?? "note"}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          <span className="morph-icon"><Icon size={17} /></span>
          <span>{intent ? `Modo ${intent.label}` : "Modo conversación"}</span>
          {intent && <span className="morph-arrow">↗</span>}
        </motion.div>
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
          placeholder="¿Qué necesitas resolver hoy?"
          maxLength={2000}
          disabled={busy}
          aria-label="Mensaje para Calvino"
        />
        <button className="icon-button" type="button" aria-label="Adjuntar archivo" disabled={busy} onClick={() => inputRef.current?.focus()}>
          <label className="file-label">
            <Paperclip size={18} aria-hidden="true" />
            <input type="file" multiple hidden disabled={busy} onChange={(event) => handleFiles(event.target.files)} />
          </label>
        </button>
        <SpeechInput lang={lang === "pt" ? "pt-BR" : "es-ES"} disabled={busy} onTranscriptionChange={(value) => onTextChange(`${text}${text ? " " : ""}${value}`)} />
        <button className="send-button" type="button" aria-label="Enviar mensaje" disabled={busy || !text.trim()} onClick={onSubmit}>
          <Send size={17} />
        </button>
      </div>
      <Attachments items={attachments} onRemove={remove} />
      <p className="composer-footnote">
        <span>Enter para enviar</span>
        <span className="privacy-note">Los adjuntos se quedan en este dispositivo</span>
        {busy && <span className="sending-note">Calvino está pensando…</span>}
      </p>
    </section>
  );
}
