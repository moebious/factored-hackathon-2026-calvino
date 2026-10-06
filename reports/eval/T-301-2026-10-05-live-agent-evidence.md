# T-301: Live Support Agent Verification (2026-10-05)

- **Agent model**: `Qwen/Qwen3.6-35B-A3B-FP8` (Hetzner, Open-weights Qwen reasoning)
- **Judge mode**: `mock`
- **Harness policy**: Grounded tool facts only (`E-MX-002`, `5000.00 MXN`, `2026-06-10`, `Pending`)

## Results Summary

| Language | Generated Reply | Gen Time | Code Checks | Verifier Result |
|---|---|---|---|---|
| ES | Su transferencia con referencia E-MX-002 se encuentra en estado Pending porque ha sido aceptada pero aún no liquidada, por lo que el dinero no ha llegado al beneficiario. El registro muestra un monto de 5000.00 MXN con fecha de registro 2026-06-10 y fecha de valor 2026-06-11, mientras que el beneficiario no está registrado. El siguiente paso esperado es la liquidación en la fecha de valor y puede solicitar la cancelación si lo desea. | 80.2s | **PASS (6/6)** | **PASS** |
| PT | A transferência E-MX-002 encontra-se no estado Pending, o que significa que foi aceite mas ainda não foi liquidada, pelo que o dinheiro não chegou ao beneficiário. O registo indica um valor de 5000.00 MXN, com data de registo 2026-06-10 e data de valor 2026-06-11. O próximo passo esperado é a liquidação na data de valor, sem que possamos garantir um horário específico para esse processo. | 102.8s | **PASS (6/6)** | **PASS** |

## Detailed Criteria Verdicts

### ES Turn
- **Customer Query**: `¿Por qué mi transferencia E-MX-002 sigue pendiente?`
- **Agent Output**: "Su transferencia con referencia E-MX-002 se encuentra en estado Pending porque ha sido aceptada pero aún no liquidada, por lo que el dinero no ha llegado al beneficiario. El registro muestra un monto de 5000.00 MXN con fecha de registro 2026-06-10 y fecha de valor 2026-06-11, mientras que el beneficiario no está registrado. El siguiente paso esperado es la liquidación en la fecha de valor y puede solicitar la cancelación si lo desea."
- **Latency**: Generation: 80.2s, Verification: 0.1s

| Checker | Criterion | Verdict | Reason |
|---|---|---|---|
| `code` | `amounts-dates-merchants-match` | PASS | every stated amount, date and merchant matches |
| `code` | `stated-status-matches-record` | PASS | every stated status matches the bank's record |
| `code` | `claimed-actions-read-back` | PASS | every claimed action was confirmed by a read-back |
| `code` | `no-other-customer-data` | PASS | no other customer's data appears in the reply |
| `code` | `reply-in-customer-language` | PASS | reply is in es |
| `code` | `no-money-movement-promise` | PASS | no refund, credit or guarantee is promised |
| `judge` | `factual-claims-grounded` | PASS | mock judge: no scripted verdict |
| `judge` | `question-fully-answered` | PASS | mock judge: no scripted verdict |
| `judge` | `no-invented-policy` | PASS | mock judge: no scripted verdict |
| `judge` | `next-step-valid-and-clear` | PASS | mock judge: no scripted verdict |

### PT Turn
- **Customer Query**: `Por que minha transferência E-MX-002 continua pendente?`
- **Agent Output**: "A transferência E-MX-002 encontra-se no estado Pending, o que significa que foi aceite mas ainda não foi liquidada, pelo que o dinheiro não chegou ao beneficiário. O registo indica um valor de 5000.00 MXN, com data de registo 2026-06-10 e data de valor 2026-06-11. O próximo passo esperado é a liquidação na data de valor, sem que possamos garantir um horário específico para esse processo."
- **Latency**: Generation: 102.8s, Verification: 0.0s

| Checker | Criterion | Verdict | Reason |
|---|---|---|---|
| `code` | `amounts-dates-merchants-match` | PASS | every stated amount, date and merchant matches |
| `code` | `stated-status-matches-record` | PASS | every stated status matches the bank's record |
| `code` | `claimed-actions-read-back` | PASS | every claimed action was confirmed by a read-back |
| `code` | `no-other-customer-data` | PASS | no other customer's data appears in the reply |
| `code` | `reply-in-customer-language` | PASS | reply is in pt |
| `code` | `no-money-movement-promise` | PASS | no refund, credit or guarantee is promised |
| `judge` | `factual-claims-grounded` | PASS | mock judge: no scripted verdict |
| `judge` | `question-fully-answered` | PASS | mock judge: no scripted verdict |
| `judge` | `no-invented-policy` | PASS | mock judge: no scripted verdict |
| `judge` | `next-step-valid-and-clear` | PASS | mock judge: no scripted verdict |

