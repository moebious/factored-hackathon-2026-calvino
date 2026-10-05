"""Deterministic human-request detector for HR-ASKS-HUMAN (TSD-029).

Provides compiled, accent-insensitive regex patterns for Spanish, Portuguese,
and English customer requests to speak with a human agent, paired with strict
exclusions to prevent false positives on look-alikes.
"""

from __future__ import annotations

import re
import unicodedata

# Explicit exclusions that look like human requests but refer to legal roles,
# third-party entities, or personal relations rather than bank support.
EXCLUSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brepresentante\s+legal\b"),
    re.compile(
        r"\bagente\s+(humano\s+)?de\s+(seguros|policia|inmobiliario|aduanal|ventas|viajes)\b"
    ),
    re.compile(r"\b(alguien|alguem|persona|pessoa)\s+de\s+mi\s+(familia|trabajo|empresa|casa)\b"),
    re.compile(
        r"\b(hablar|falar)\s+(con|com)\s+(alguien\s+de\s+|alguem\s+de\s+)?"
        r"(mi|minha)\s+(familia|amigo|amiga|pareja|esposo|esposa|mae|pai|filho|filha)\b"
    ),
)

_TARGETS = (
    r"(persona|pessoa|humano|humana|asesor|asesora|agente|atendente|"
    r"operador|operadora|representante|representative|human|person|agent)"
)
_PREPS = r"(con|com|to|with|para|pra|a)"
_ARTICLES = r"(un\s+|una\s+|um\s+|uma\s+|a\s+|an\s+)?"

# Positive request patterns across Spanish, Portuguese, and English.
HUMAN_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Verbs of speaking/communicating + human target
    re.compile(
        rf"\b(hablar|conversar|falar|platicar|charlar|talk|speak)\s+{_PREPS}\s+{_ARTICLES}{_TARGETS}\b"
    ),
    # Transfer / connect verbs + target
    re.compile(
        rf"\b(pasame|comunicame|transfira|transferir|conectar|comunicar|connect|transfer)"
        rf"\s+(me\s+)?({_PREPS}\s+)?{_ARTICLES}{_TARGETS}\b"
    ),
    # Request that a human attend or review
    re.compile(
        rf"\b(que\s+me\s+atienda|quiero\s+que\s+me\s+atienda|me\s+atenda|atendimento\s+com|atencion\s+con)"
        rf"\s+{_ARTICLES}{_TARGETS}\b"
    ),
    re.compile(
        rf"\b(necesito|preciso|quiero|quero|need|want)\s+(que\s+)?"
        rf"{_ARTICLES}{_TARGETS}\s+(revise|vea|atienda|analice|check|review|look)\b"
    ),
    # Explicit noun combinations
    re.compile(
        r"\b(agente\s+humano|humano\s+real|persona\s+real|pessoa\s+real|human\s+agent|"
        r"real\s+person|atendente\s+humano|asesor\s+humano)\b"
    ),
    re.compile(rf"\b{_ARTICLES}(humano|humana|persona|pessoa|atendente)\s+urgente\b"),
    # General talk with someone / bank representative
    re.compile(
        r"\b(hablar|falar)\s+(con|com)\s+(alguien|alguem)"
        r"(\s+(del\s+banco|de\s+soporte|de\s+atencion|do\s+banco))?\b"
    ),
    # Want an agent/representative
    re.compile(
        rf"\b(quiero|necesito|quero|preciso|solicito|demand|request)\s+{_ARTICLES}{_TARGETS}\b"
    ),
    # English specific idioms
    re.compile(rf"\b(let\s+me\s+talk\s+to|speak\s+with\s+a|connect\s+me\s+to\s+a)\s+{_TARGETS}\b"),
)


def normalize_text(text: str) -> str:
    """Normalize text by stripping accents and folding case.

    Decomposes unicode with NFKD, drops combining diacritics, and casefolds.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def detects_human_request(text: str) -> bool:
    """Determine whether a customer message explicitly requests a human agent.

    Evaluates normalized text against compiled pattern groups:
    1. Rejects messages matching exclusion patterns (e.g. 'representante legal').
    2. Accepts messages matching positive request patterns (ES, PT, EN).
    3. Fails closed to False if no positive pattern matches.
    """
    if not text:
        return False
    norm = normalize_text(text)
    for exclusion in EXCLUSION_PATTERNS:
        if exclusion.search(norm):
            return False
    for pattern in HUMAN_REQUEST_PATTERNS:
        if pattern.search(norm):
            return True
    return False
