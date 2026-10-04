# TSD-017: README usage and results (T-501)

| | |
|---|---|
| Status | proposed |
| Branch | `docs/results` |
| Depends on | TSD-013 (end-to-end evaluation), TSD-012 (deployed demo) |
| Required by | T-502 (release), T-503 (slides), T-504 (video), T-505 (submission) |
| Requirements | T-501 card; AGENTS.md standard 1; the brief's "working prototype, production readiness, honest remaining work" |
| Design | DESIGN.md 7 (evaluation), 9 (readiness); PLAN.md Tier 0 gate ("deployed, results in README") |

Numbering note: TSD-016 is taken by the support-agent spec (branch
`docs/tsd-016-support-agent`, not yet merged), so this spec takes TSD-017.

## Purpose

Make the repository self-explaining for judges. A reader can install the
project, run the demo, reproduce the evaluation, and find **every reported
number** with its evidence label, sample size and source report — including
the numbers that are not there yet, each with the blocker that keeps it out.
Done when (card): a reader can run the demo and find every reported number.

## Scope

README changes plus this spec. No code, and **no new numbers**: every figure
in the README is copied from a committed report (`reports/eval/`,
`reports/baseline/`, `reports/data-quality/`) or is stated as
`not run: <blocker>`. The card's "results report" deliverable is the
committed evaluation report itself (`reports/eval/T-303-*.md`); the README is
the summary and index into it, never a second source of truth. When a newer
run lands (for example the keyed `--suite all` run), the README rows are
updated from it in the same change that commits the run.

## README structure after this change

Existing sections stay in place except where noted:

1. Title, thesis, workflow table, mermaid flow (unchanged).
2. Quick start (kept; every command verified by running it as written).
3. **Results** (new, directly after Quick start): the summary below.
4. **Remaining work** (new, short): the honest gap list below.
5. Start here; credits and license (unchanged).

The read-only full-data inventory block moves under Quick start's "more
commands" tail or stays where it is if it reads cleanly; no inventory
wording changes.

## Results section: required rows

Every row carries its evidence label (`[measured]` / `[projected]` /
`[vendor]`), n, and a link to the source report. Source for the evaluation
rows: the latest committed tier0 run, named by filename in the section.

- **Outcome agreement vs the oracle** (22/50, 44.0% at the time of writing)
  with the run's model, policy and agent named (laya 0.3.24, policy v2,
  TemplateAgent — no LLM language work yet).
- **Unsafe outcomes** (0/50 fired), including the adversarial slice
  (0 of 12): the safety claim with its conservative-checks caveat.
- **Escalation quality** (required 15, escalated 27, missed 1,
  unnecessary 13) — the human-handoff story with both error directions.
- **Containment** (23/50) and **safe resolution** (9/50).
- **Determinism**: repeats replayed identically, zero findings.
- **Latency** model and end-to-end p50/p95, and **cost** ($0 under the
  TemplateAgent; laya is self-hosted CPU time).
- **Human baseline**: 91.5% first-contact resolution on Transaccional calls
  `[measured]`, stated as the target, with the honest gap to the current
  agreement number.
- **Named failure**: live laya 0.3.24 over-escalates routine Spanish — 13
  unnecessary escalations listed by case id; needs_human scores for routine
  questions (0.67–0.89) overlap explicit-human requests (0.87–0.98), so no
  policy threshold separates them `[measured]`. This is the headline
  remaining-work item, not a footnote.
- **Gated rows**, each as `not run: <blocker>`: judge validation and the
  bare-LLM ablation (provider keys — PLAN's protected measurements,
  required for the submission), the PT slice (T-203), gold-subset
  agreement (T-103 hand-labelling), live-LLM agent numbers (T-301).

## Usage with real output: requirements

- Each command block is followed by its **captured** output, trimmed to the
  lines that matter (pytest summary line; the evaluation CLI's results
  line; the demo API's `/health` JSON; the frontend's ready line). Captured
  means produced by running the block as written on the branch, never
  handwritten examples.
- The demo flow shows one real hub turn (a seeded scenario message in, the
  card or park out) so a judge sees what the product does without deploying
  it.
- Commands stay in sync with AGENTS.md's Commands section.

## Remaining work section: requirements

One line per gap, each naming its blocker: the live deploy at
`calvino.rubrica.dev` (TSD-012, maintainer), the live-LLM agent (T-301,
provider keys), the keyed `--suite all` run with judge validation and the
ablation (PLAN's protected measurements), the Portuguese set (T-203), gold
hand-labelling (T-103) and the message set (T-106). No gap without a
blocker; no blocker without its task id.

## Verification (docs-only change: no tests)

- Cross-check table before proposing the push: every number in the README
  appears verbatim in a committed report.
- Every command block ran as written, on the branch's machine, and its
  captured output is in the README.
- Markdown renders: tables, links and the untouched mermaid diagram.

## Done when

- The Results and Remaining work sections exist; every number carries its
  evidence label, n and a link to its source report.
- The quick-start and demo commands are verified by running them.
- `CHANGELOG.md` entry; specs index line for TSD-017.

## Out of scope

Slides (T-503), video (T-504), release notes and tags (T-502), and any new
measurement: the keyed `--suite all` run is its own work item, and this
spec only says how the README reports it once it exists.
