// Local voice input (commit 1): Web Speech API wrapped in a small hook.
// No audio leaves the browser. Final transcripts feed the existing composer
// text for manual correction before send. The backend still receives only
// {persona, text} through the unchanged hub contract.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type SpeechRecognitionResultItem = {
  transcript: string;
  isFinal: boolean;
};

type SpeechRecognitionResult = {
  isFinal: boolean;
  [index: number]: SpeechRecognitionResultItem;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResult>;
};

type SpeechRecognitionErrorLike = {
  error: string;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type WindowWithSpeech = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

export type VoiceStatus = "idle" | "listening" | "denied" | "error";

export function isVoiceSupported(): boolean {
  if (typeof window === "undefined") return false;
  const candidate = window as WindowWithSpeech;
  return Boolean(candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition);
}

export function useVoiceInput(options: {
  lang: string;
  onFinalText: (text: string) => void;
}) {
  const { lang, onFinalText } = options;
  const [supported] = useState<boolean>(() => isVoiceSupported());
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [interim, setInterim] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const callbackRef = useRef(onFinalText);
  callbackRef.current = onFinalText;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    if (typeof window === "undefined") return;
    const candidate = window as WindowWithSpeech;
    const Recognition = candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition;
    if (!Recognition) {
      setStatus("error");
      return;
    }
    try {
      recognitionRef.current?.abort();
    } catch {
      // A previous instance may already be gone; start fresh below.
    }
    const recognition = new Recognition();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const first = result[0];
        if (!first) continue;
        if (result.isFinal) {
          const finalText = first.transcript.trim();
          if (finalText.length > 0) callbackRef.current(finalText);
        } else {
          interimText += first.transcript;
        }
      }
      setInterim(interimText.trim());
    };
    recognition.onerror = (event: SpeechRecognitionErrorLike) => {
      setInterim("");
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setStatus("denied");
      } else {
        setStatus("error");
      }
    };
    recognition.onend = () => {
      setInterim("");
      setStatus((previous) => (previous === "listening" ? "idle" : previous));
    };
    recognitionRef.current = recognition;
    setInterim("");
    setStatus("listening");
    try {
      recognition.start();
    } catch {
      setStatus("error");
    }
  }, [lang]);

  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.abort();
      } catch {
        // Cleanup only; a torn-down recognizer needs no error surface.
      }
      recognitionRef.current = null;
    };
  }, []);

  return { supported, status, interim, start, stop };
}
