"use client";

// Local, React 18-compatible adapters for the AI Elements interaction
// patterns. The visual contracts mirror Attachments and AudioPlayer while
// keeping the Calvino demo dependency-light. Voice dictation in the live
// composer uses the useSpeechRecognition hook with a Mic button instead.

import { useState } from "react";
import {
  FileText,
  Pause,
  Play,
  Volume2,
  X,
} from "lucide-react";
import type { AttachmentItem } from "./types";
import { strings, type Lang } from "./i18n";

export function Attachments({
  items,
  variant = "inline",
  onRemove,
  lang,
}: {
  items: AttachmentItem[];
  variant?: "grid" | "inline" | "list";
  onRemove?: (id: string) => void;
  lang: Lang;
}) {
  if (items.length === 0) return null;
  return (
    <div className={`attachments attachments-${variant}`} aria-label={strings(lang).attachmentsAria}>
      {items.map((item) => (
        <Attachment key={item.id} item={item} onRemove={onRemove} lang={lang} />
      ))}
    </div>
  );
}

function Attachment({ item, onRemove, lang }: { item: AttachmentItem; onRemove?: (id: string) => void; lang: Lang }) {
  const image = item.mediaType.startsWith("image/");
  return (
    <article className={`attachment ${item.status === "failed" ? "attachment-failed" : ""}`}>
      <div className="attachment-preview">
        {image ? (
          // Blob URLs are local previews and cannot use Next image optimization.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={item.url} alt="" />
        ) : <FileText size={18} aria-hidden="true" />}
      </div>
      <div className="attachment-info">
        <strong>{item.name}</strong>
        <span>
          {item.status === "failed" ? item.error : `${formatBytes(item.size)} · local`}
        </span>
      </div>
      {onRemove && (
        <button
          className="icon-button attachment-remove"
          type="button"
          aria-label={`${strings(lang).removeAttachment} ${item.name}`}
          onClick={() => onRemove(item.id)}
        >
          <X size={15} aria-hidden="true" />
        </button>
      )}
    </article>
  );
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function AudioPlayer({ text, lang }: { text: string; lang: Lang }) {
  const [playing, setPlaying] = useState(false);
  const s = strings(lang);
  const toggle = () => {
    if (!("speechSynthesis" in window)) return;
    if (playing) {
      window.speechSynthesis.cancel();
      setPlaying(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "pt" ? "pt-BR" : "es-ES";
    utterance.onend = () => setPlaying(false);
    window.speechSynthesis.speak(utterance);
    setPlaying(true);
  };
  return (
    <button className="audio-player" type="button" onClick={toggle} aria-label={playing ? s.audioStopAria : s.audioListenAria}>
      {playing ? <Pause size={14} /> : <Play size={14} />}
      <Volume2 size={14} />
      {playing ? s.audioPlaying : s.audioListen}
    </button>
  );
}
