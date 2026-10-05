"use client";

// Local, React 18-compatible adapters for the AI Elements interaction
// patterns. The visual contracts mirror Attachments, SpeechInput and
// AudioPlayer while keeping the Calvino demo dependency-light.

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  FileText,
  Image as ImageIcon,
  Mic,
  Pause,
  Play,
  Volume2,
  X,
} from "lucide-react";
import type { AttachmentItem } from "./types";

type SpeechEvent = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => BrowserSpeechRecognition;
  webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
};

export function Attachments({
  items,
  variant = "inline",
  onRemove,
}: {
  items: AttachmentItem[];
  variant?: "grid" | "inline" | "list";
  onRemove?: (id: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className={`attachments attachments-${variant}`} aria-label="Adjuntos">
      {items.map((item) => (
        <Attachment key={item.id} item={item} onRemove={onRemove} />
      ))}
    </div>
  );
}

function Attachment({ item, onRemove }: { item: AttachmentItem; onRemove?: (id: string) => void }) {
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
          aria-label={`Quitar ${item.name}`}
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

export function SpeechInput({
  lang,
  onTranscriptionChange,
  disabled,
}: {
  lang: string;
  onTranscriptionChange: (text: string) => void;
  disabled?: boolean;
}) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);

  const toggle = () => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const speechWindow = window as SpeechWindow;
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = lang;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript ?? "";
      if (transcript) onTranscriptionChange(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  useEffect(() => () => recognitionRef.current?.stop(), []);

  const available = typeof window !== "undefined" &&
    Boolean((window as SpeechWindow).SpeechRecognition ?? (window as SpeechWindow).webkitSpeechRecognition);
  return (
    <button
      className={`icon-button voice-button ${listening ? "is-listening" : ""}`}
      type="button"
      aria-label={listening ? "Detener dictado" : "Dictar mensaje"}
      aria-pressed={listening}
      disabled={disabled || !available}
      onClick={toggle}
    >
      <Mic size={18} aria-hidden="true" />
      {listening && <span className="voice-pulse" aria-hidden="true" />}
    </button>
  );
}

export function AudioPlayer({ text }: { text: string }) {
  const [playing, setPlaying] = useState(false);
  const toggle = () => {
    if (!("speechSynthesis" in window)) return;
    if (playing) {
      window.speechSynthesis.cancel();
      setPlaying(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-ES";
    utterance.onend = () => setPlaying(false);
    window.speechSynthesis.speak(utterance);
    setPlaying(true);
  };
  return (
    <button className="audio-player" type="button" onClick={toggle} aria-label={playing ? "Detener respuesta hablada" : "Escuchar respuesta"}>
      {playing ? <Pause size={14} /> : <Play size={14} />}
      <Volume2 size={14} />
      {playing ? "Reproduciendo" : "Escuchar"}
    </button>
  );
}

export function AttachmentIcon({ item }: { item: AttachmentItem }): ReactNode {
  return item.mediaType.startsWith("image/") ? <ImageIcon size={16} /> : <FileText size={16} />;
}
