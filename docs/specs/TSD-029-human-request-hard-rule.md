# TSD-029: Deterministic Human-Request Hard Rule (HR-ASKS-HUMAN)

| | |
|---|---|
| Status | implemented |
| Branch | `feat/human-request-rule` |
| Depends on | TSD-001, TSD-009 |
| Required by | T-208 (Human request hard rule), PRD AC-4 |
| Requirements | PRD FR-9; PRD UC-4; AC-4 |
| Design | DESIGN.md 4.2, 6.1; decisions 4, 18, 37 |

## Purpose

Provide a robust, deterministic, trilingual hard-rule detector for explicit customer requests to speak with a human agent, replacing the legacy 11-phrase raw substring match in `src/calvino/hub/graph.py`.

Prior to this specification, `intake()` checked:
```python
asks_for_human = any(phrase in lowered for phrase in HUMAN_REQUEST_PHRASES)
```
with 11 raw substrings. This had two major failure modes:
1. **False Negatives (Missed Escalations)**: Missed natural variations such as *"pásame con un asesor"*, *"necesito que un humano revise mi cuenta"* (ORC-021), *"comunícame con un agente"*, *"quero falar com um atendente"* (Portuguese), and *"let me talk to an agent"* (English).
2. **False Positives (Unnecessary Escalations)**: Plain substring matching falsely fired on look-alikes like *"el **representante** legal de mi empresa..."*, *"mi **agente humano** de seguros..."*, and *"voy a **hablar con alguien** de mi familia..."*, dragging routine banking queries into the human operator queue.

TSD-029 defines a compiled, token-aware pattern detector with explicit negative exclusions, supporting Spanish, Portuguese, and English with accent and case normalization.

## Invariants & Constraints

1. **Hard Rules Run First and Always Win (Non-Negotiable)**:
   Per DESIGN §4.2 and decision 4, an explicit customer request for a human routes immediately to `Route.HUMAN` under rule `RT-NEEDS-PERSON` before System 1 (Laya) scores are evaluated.
2. **Zero Model Dependencies (Deterministic & Offline)**:
   The detector must remain 100% deterministic, running regex token evaluations in sub-millisecond time. No LLM or classifier is invoked.
3. **Trilingual Parity (ES, PT, EN)**:
   Patterns must cover Spanish, Portuguese (PRD bilingual mandate), and English customer phrases.
4. **Accent & Case Insensitivity**:
   Text normalization uses NFKD unicode decomposition to strip combining diacritics, matching accented (*"pásame"*, *"comunícame"*, *"atenção"*) and unaccented variants identically.
5. **Word Boundary & Context Exclusion Safety**:
   Patterns enforce `\b` word boundaries and negative exclusion patterns for legal roles (*"representante legal"*), third-party agents (*"agente de seguros"*, *"agente inmobiliario"*), and personal relations (*"hablar con mi familia"*, *"alguien de mi familia"*).
6. **Harness Separation**:
   Inert demo decisions (`calvino.api.decide`) keep inert `Facts(asks_for_human=False)` so raw classifier thresholds can be isolated without harness intervention. System 1.5 graph decisions (`calvino.hub.graph.intake`) evaluate `detects_human_request(message)`.

## Architecture & Interfaces

### Module: `calvino.hub.human_request`

```python
def normalize_text(text: str) -> str:
    """Normalize text for matching: NFKD decomposed, combining accents stripped, casefolded."""
    ...


def detects_human_request(text: str) -> bool:
    """Determine whether the customer explicitly asks for a human agent or person.

    Returns True if an explicit request pattern matches and no exclusion rule applies.
    """
    ...
```

### Integration Points

1. **`calvino.hub.graph.intake`**:
   ```python
   asks_for_human = detects_human_request(state.get("message", ""))
   ```

## Test & Acceptance Criteria

1. **Positive Match Table (Must Detect True Requests)**:
   - ES: *"Necesito hablar con un humano urgente, mi transferencia no llega."* (AC-4)
   - ES: *"Quiero hablar con una persona."* (ORC-020)
   - ES: *"Necesito que un humano revise mi cuenta."* (ORC-021)
   - ES: *"Quiero hablar con alguien del banco."*
   - ES: *"pásame con un asesor"* / *"pasame a un asesor"*
   - ES: *"comunícame con un agente"*
   - ES: *"quiero que me atienda una persona"*
   - PT: *"quero falar com um atendente"*
   - PT: *"preciso falar com uma pessoa"*
   - PT: *"me transfira para um humano"*
   - EN: *"talk to a human"* / *"speak to a representative"* / *"connect me to an agent"*
2. **Negative Match Table (Must NOT Detect Look-Alikes)**:
   - *"el representante legal de mi empresa cambió"*
   - *"mi agente humano de seguros me recomendó esto"*
   - *"hablar con alguien de mi familia"*
   - *"voy a hablar con mi esposa antes de transferir"*
   - Routine inquiries: *"¿Por qué sigue pendiente mi pago E-MX-002?"*, *"Quiero cancelar mi pago"*.
3. **Scenario & Evaluation Preservation**:
   - Scenario AC-4 passes without regression.
   - Full evaluation run confirms zero new regressions on the 50 frozen test cases.
