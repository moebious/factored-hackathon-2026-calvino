# T-207: Intent-driven customer experience and visual investigation

| | |
|---|---|
| Wave | 2 |
| Branch | `feat/intent-driven-customer-app` |
| Spec | [TSD-022](../specs/TSD-022-intent-driven-customer-app.md) |
| Depends on | T-205, T-003 |
| Blocked by | — |
| Model | standard model |
| Can run in parallel | yes |
| References | decisions 10, 17, 30, 38; PRD FR-7, FR-8, FR-12, FR-13 |

**Goal.** Evolucionar la aplicación cliente hacia una experiencia de investigación visual continua basada en Intent-Driven Cards, entrada de voz con Web Speech API, modelo CaseStudy, trazabilidad con AI Elements y presentación desacoplada policy-agnostic.

**Inputs.** El contrato oficial HubReply (`/api/hub/message`, `/api/hub/resume`), el catálogo de 8 cards, la máquina de estados de UI calma, y los registros de auditoría de `decisions.jsonl`.

**Outputs.** Compositor morfológico Intent-Driven Card, hooks desacoplados `useHubConversation` y `useSpeechRecognition`, modelo y vista `CaseDossier`, componentes AI Elements (`ChainOfThought` y `ReasoningStep`), registro `vocabulary.ts`, y paridad i18n estricta (ES/PT).

**Done when.**
1. El compositor transmuta fluidamente entre intenciones bancarias (split, checklist, status track, acción).
2. La transcripción de voz (Web Speech API) opera con desactivación limpia en navegadores no soportados.
3. El expediente CaseStudy acumula el estado de la investigación sin alterar los contratos del backend.
4. ChainOfThought renderiza exclusivamente pasos auditados de trace sin simular pensamientos privados.
5. Se resuelven las 4 fricciones del cliente (distinción de escalated en confirmación, panel para operator_queue, enums traducidos y closure de selección resuelto).
6. 100% de los strings del chrome cumplen paridad ES/PT en `i18n.ts` (FR-13).
7. `npm run lint`, `npm run build` y los 1042 tests de pytest pasan en verde.
