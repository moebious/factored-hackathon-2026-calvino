# Routing under policy versions (2026-10-05)

Source `evaluation/exploratory/needs-person-dev-v0.jsonl`: n = 110 (46 labelled needs_person). Evidence label: **exploratory, team-written rows the thresholds were chosen on**. Live laya, the hub's own scoring and `decide_route`.

## Single-signal AUROC against the needs_person label

| Signal | AUROC |
|---|---|
| needs_human | 0.43 |
| area: dispute or fraud | 0.72 |
| intent: talk to a person | 0.75 |
| injection | 0.75 |
| max(area, intent, injection) | 0.86 |

## Where rows go

| | v2 | v3 |
|---|---|---|
| routine rows reaching the agent | 0/64 (0%) | 35/64 (55%) |
| needs-a-person rows reaching the agent | 1/46 (2%) | 8/46 (17%) |
| needs-a-person rows sent to a person | 37/46 (80%) | 33/46 (72%) |
| routine rows stopped by | RT-CLARIFY-BAND 1, RT-CLARIFY-CONFIDENCE 16, RT-CLARIFY-UNCLEAR 7, RT-DISPUTE-FRAUD 7, RT-ESCALATE 32, RT-INJECTION 1 | RT-CLARIFY-CONFIDENCE 2, RT-CLARIFY-NOT-STUCK 19, RT-DISPUTE-FRAUD 7, RT-INJECTION 1 |
| needs-a-person rows stopped by | RT-CLARIFY-BAND 1, RT-CLARIFY-CONFIDENCE 7, RT-DISPUTE-FRAUD 25, RT-ESCALATE 11, RT-INJECTION 1 | RT-CLARIFY-CONFIDENCE 1, RT-CLARIFY-NOT-STUCK 4, RT-DISPUTE-FRAUD 25, RT-INJECTION 1, RT-TALK-TO-PERSON 7 |
