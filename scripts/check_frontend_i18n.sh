#!/usr/bin/env bash
# FR-13 chrome-parity guard (frontend audit E2/E3).
#
# Fails on:
#  1. hardcoded Spanish literals in runtime TSX (every visible string must
#     come from strings(lang) in frontend/app/i18n.ts);
#  2. raw trace fields rendered outside the vocabulary resolvers
#     (stage/verdict must go through resolveStage/resolveRule/resolveVerdict);
#  3. resurrected dead code (the intent-driven-card composer, GlassBox, the
#     legacy ChainOfThought's SpeechInput).
#
# Documented exceptions (not failures):
#  - frontend/app/i18n.ts: the translation tables themselves;
#  - frontend/app/layout.tsx: static page metadata, which cannot follow the
#    client-side ES/PT toggle;
#  - AttributableReplyEditor default drafts: hub reply content, which the hub
#    (not the chrome toggle) owns by design (i18n.ts header).
#
# Wired into `npm run lint`, so it runs on every frontend check.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0

accent_hits=$(grep -rn "[áéíóúñ¿¡]" "$ROOT/frontend/app" --include="*.tsx" \
  | grep -v "frontend/app/i18n.ts" \
  | grep -v "frontend/app/layout.tsx" \
  | grep -v "reintento de pago ha sido procesado" \
  | grep -v "información de su transferencia" \
  | grep -v "titularidad de cuenta" || true)
if [ -n "$accent_hits" ]; then
  echo "FR-13: hardcoded Spanish literals outside strings(lang):"
  echo "$accent_hits"
  fail=1
fi

raw_hits=$(grep -rn "step\.stage}\|{step\.verdict}" "$ROOT/frontend/app" --include="*.tsx" | grep -v "key=" || true)
if [ -n "$raw_hits" ]; then
  echo "E3: raw trace fields rendered outside the vocabulary resolvers:"
  echo "$raw_hits"
  fail=1
fi

dead_hits=$(grep -rn "SpeechInput\|GlassBox\|from.*intent-driven-card" "$ROOT/frontend/app" --include="*.tsx" || true)
if [ -n "$dead_hits" ]; then
  echo "E1: resurrected dead frontend code:"
  echo "$dead_hits"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "frontend i18n guard: clean"
fi
exit "$fail"
