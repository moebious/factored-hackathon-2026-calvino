# Routing under policy versions (confirmation on unseen rows) (2026-10-05)

Source `evaluation/exploratory/needs-person-holdout-v1.jsonl`: n = 84 (36 labelled needs_person). Evidence label: **confirmation, team-written unseen rows**. Live laya, the hub's own scoring and `decide_route`.

## Single-signal AUROC against the needs_person label

| Signal | AUROC |
|---|---|
| needs_human | 0.39 |
| area: dispute or fraud | 0.72 |
| intent: talk to a person | 0.79 |
| injection | 0.78 |
| max(area, intent, injection) | 0.80 |

## Where rows go

| | v2 | v3 |
|---|---|---|
| routine rows reaching the agent | 3/48 (6%) | 25/48 (52%) |
| needs-a-person rows reaching the agent | 0/36 (0%) | 7/36 (19%) |
| needs-a-person rows sent to a person | 23/36 (64%) | 17/36 (47%) |
| routine rows stopped by | RT-CLARIFY-CONFIDENCE 13, RT-CLARIFY-UNCLEAR 9, RT-DISPUTE-FRAUD 5, RT-ESCALATE 17, RT-INJECTION 1 | RT-CLARIFY-CONFIDENCE 5, RT-CLARIFY-NOT-STUCK 12, RT-DISPUTE-FRAUD 5, RT-INJECTION 1 |
| needs-a-person rows stopped by | RT-CLARIFY-CONFIDENCE 13, RT-DISPUTE-FRAUD 12, RT-ESCALATE 9, RT-INJECTION 2 | RT-CLARIFY-CONFIDENCE 4, RT-CLARIFY-NOT-STUCK 8, RT-DISPUTE-FRAUD 12, RT-INJECTION 2, RT-TALK-TO-PERSON 3 |
