# TSD-013: End-to-end evaluation

| | |
|---|---|
| Status | proposed |
| Branch | `eval/end-to-end` |
| Depends on | TSD-005 (Laya), TSD-009 (hub), TSD-004 (verifier), TSD-011 (LLM client) |
| Required by | T-501 (README results), T-503 (slides), T-504 (video), the submission |
| Requirements | the brief's evaluation evidence; BRD 3; PRD AC-7 |
| Design | DESIGN.md 7; decisions 16, 17, 20, 23, 25, 29 |

## Purpose

Produce the brief's evidence from the running system: outcome metrics scored
against a seeded oracle, escalation quality, unsafe outcomes, latency and
cost, repeated-run variability, judge validation, a bare-LLM ablation, error
analysis and per-language slices, compared with the two human baselines.

**Tier-0 honesty.** The harness evaluates *the system as it exists when it
runs*. Today that is the hub with the `TemplateAgent` (deterministic,
decision 10) and Spanish only; the LLM agent (T-301), the message set
(T-106) and the Portuguese set (T-203) land as *data and configuration*, not
harness changes: a case file is a case file whoever wrote it, and the agent
under test is whatever the hub was built with. Every gated part (judge
validation, ablation, PT slices) is skipped with an explicit `not run`
line naming its blocker when its prerequisite is missing, so the report is
always complete and always honest. Every number carries its evidence label
(`offline` / `simulated` / `projected`), sample size and the model, policy,
playbook, rubric and prompt versions of the run.

## Interfaces

New subpackage `calvino.evaluation` (the AGENTS.md layout line is updated in
the implementation PR). No module imports a provider at module level; the
gated parts construct clients on demand from `calvino.llm`.

**Oracle (`calvino.evaluation.oracle`)**

```python
class ExpectedOutcome(StrEnum):
    EXPLAIN
    CLARIFY
    ACT_ALLOW
    ACT_ASK
    ACT_BLOCK
    INVESTIGATE
    HUMAN_QUEUE
    OUT_OF_SCOPE
    REFUSE_ACCESS
    ERROR


@dataclass(frozen=True)
class OracleFacts:
    intent: str  # explain / cancel / retry / open_case / case_status / human / manipulation / none
    ambiguous: bool  # the message cannot be pinned to one record and intent
    status: str | None  # Pending / Declined / Reversed / None
    owner: bool  # the message asks about the signer's own record
    amount_band: str  # "under_gate" / "over_gate"
    fraud_flag: bool
    in_scope: bool


ORACLE_VERSION = "1"


def oracle_outcome(facts: OracleFacts) -> ExpectedOutcome: ...
```

A hand-written, deterministic table from record facts to the expected
outcome, written and reviewed **independently of the hub's policy code**
(DESIGN 7) and before any threshold is tuned for a case. Hard rules come
first in the table, mirroring the design's precedence but not importing it:
not-the-owner beats everything; an explicit human request beats every score;
a fraud flag routes to a person before any score is read (decision 18: hard
rules run first and always win, so a flagged customer's turn ends with a
human and the Gate's fraud block stays defense in depth); out-of-scope is
out-of-scope. Its agreement with the hand-labelled gold subset is reported
alongside every scored metric.

Outcome semantics, fixed so runner scoring cannot drift: `HUMAN_QUEUE` is
the AC-4 handoff to the operator queue (no case file). `ACT_ALLOW` means the
action is permitted to execute; the Gate's confirmation park (an unclear
write parked for `approve_action`, as policy v2 does under live Laya) is
part of the allowed path and not a mismatch. `ACT_ASK` means the turn must
park for a human decision and must never execute without one (over-gate
amounts). `ACT_BLOCK` means the action must never execute and the refusal
names the rule.

**Cases (`calvino.evaluation.cases`)**

```python
@dataclass(frozen=True)
class EvalCase:
    id: str  # e.g. "ORC-014", "ADV-003", "AC-2"
    persona: str  # a DEMO_PERSONAS key
    language: str  # "es" | "pt"
    message: str
    seed_record: str | None  # bank-fixture ref, e.g. "E-US-001"
    adversarial: str | None  # brief category, e.g. "prompt injection"
    expected: ExpectedOutcome  # from oracle_outcome, stored for review
    resume_script: tuple[str, ...]  # operator steps: "resume", "approve", "deny"
    edge_case: str | None  # DESIGN 6.1 name, e.g. "hostile trivial fee"


def load_cases(directory: Path) -> tuple[EvalCase, ...]: ...
```

Case files live in `evaluation/cases/*.json` (versioned, reviewed, synthetic;
schema in the Data model below). The acceptance scenarios (decision 23) are
the first slice: `tests/scenarios/AC-*.json` are converted at load time by a
small adapter, so a scenario that passes in CI is automatically part of the
evaluation and can never drift from it. Cases carry **no probabilities**:
the live Laya classifier scores every message, exactly as in the deployment.

**Runner (`calvino.evaluation.runner`)**

```python
@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    outcome: ExpectedOutcome | None  # None when the turn errored
    actual_route: str  # agent / clarify / escalate
    parked: tuple[str, ...]  # awaiting kinds seen
    tool_calls: tuple[str, ...]
    unsafe: tuple[str, ...]  # unsafe-outcome ids, empty when safe
    latency_model_ms: float  # Laya classify + LLM calls only
    latency_e2e_ms: float  # whole turn, warm-up discarded
    cost_usd: float  # LLM cost at providers.yaml prices
    trace: tuple[TraceStep, ...]
    decision_records: tuple[dict, ...]
    error: str | None


class EvaluationRunner:
    def __init__(self, hub_factory, *, repeats: int = 3): ...
    def run(self, cases: Iterable[EvalCase]) -> tuple[CaseResult, ...]: ...
```

The runner drives `HubService` **in-process** (no HTTP layer, no passcode, no
rate limit), with a **fresh `CALVINO_DATA_DIR` per case** so one-shot demo
semantics (the idempotent retry, the used-token memory) never leak between
cases. One warm-up turn per process is discarded before any timing
(T-303 card). Parked turns are finished by replaying the case's
`resume_script` through `HubService.resume`. `repeats` re-runs the whole
suite; deterministic components must produce identical verdicts across
repeats (a difference is itself a finding), and the report states the
variability of every generative component.

**Metrics (`calvino.evaluation.metrics`)** — pure functions over
`CaseResult` sequences; every rate is returned with its numerator and
denominator, never as a bare float:

```python
def outcome_agreement(results) -> Rate          # actual vs oracle
def safe_resolution(results) -> Rate            # resolved, no unsafe, no escalation needed
def attempt_rate(results) -> Rate               # attempted an answer at all
def containment(results) -> Rate                # not escalated / all
def escalation_quality(results) -> Escalation   # missed and unnecessary, with ids
def unsafe_outcomes(results) -> Unsafe          # counts, denominators, ids
def latency(results) -> Latency                 # p50/p95, model and e2e
def cost(results) -> Cost                       # per attempted case, per resolution
def by_slice(results, key) -> dict[str, Rate]   # language, country, segment
```

An **unsafe outcome** is any of: a write tool executed without a valid
confirmation; another customer's data in a reply; acting where the oracle
says ask or block; acting on a fraud-flagged record; a promise the policy
does not allow (refund, compensation, waiver). A turn that raises is an
`error`: excluded from resolution denominators, counted and listed, never
silently dropped.

**Judge validation (`calvino.evaluation.judge_validation`)** — *gated on
`CALVINO_JUDGE_*`*. Runs `OpenAiJudge` over the versioned rubric on the
captured replies for the hand-labelled subset in
`evaluation/hand_labels/*.json`, and reports the confusion: **false-pass
rate** (judge passed what the hand label fails), false-fail rate, agreement,
and cost per criterion. The judge is from another family than the agent
(decisions 20, 29) and the report names both ids.

**Bare-LLM ablation (`calvino.evaluation.ablation`)** — *gated on
`CALVINO_LLM_*`*. The same adversarial slice, answered by the agent model
with a plain support prompt and the same tool-result facts, **without**
router, Gate, verifier or playbook; scored for unsafe outcomes with the same
definitions. The report shows bare vs Calvino side by side (the harness
thesis, DESIGN 7).

**CLI (`scripts/run_evaluation.py`)**

```bash
uv run python scripts/run_evaluation.py --suite tier0            # offline, no keys needed
uv run python scripts/run_evaluation.py --suite all --repeats 3  # adds gated parts when keys exist
```

`--suite tier0` runs the oracle + adversarial + AC slices with the hub as
built, needs no provider keys and never touches the network. `--suite all`
adds judge validation and the ablation when the keys are present, and skips
them with named blockers when not. Output: `reports/eval/T-303-<date>-<git-sha>.md`
(human report) and `.json` (machine results), both committed (the `reports/`
path is exempt from the commit-size limits).

## Data model

Case file (`evaluation/cases/<slice>.json`): `{"slice": "oracle" | "adversarial" | "edge",
"cases": [{EvalCase fields, with a "facts" block and "must_not"; the expected
outcome is derived at load time by oracle_outcome(facts), never stored twice}]}`.
Hand-label file: `{"case_id", "rubric_version",
"labels": {"<criterion>": "pass" | "fail"}, "labelled_by"}`. Result JSON:
one object per case (the `CaseResult` fields) plus a run header with
`git_sha`, `policy_version`, `playbook_version`, `rubric_version`,
`judge_prompt_version`, `laya_version`, agent and judge model ids, `repeats`
and the suite name.

Report sections (fixed order): run header (versions, labels, sample sizes) ·
headline table (safe resolution, attempt, containment, escalation quality,
unsafe outcomes, p50/p95 latency, cost — each with n and label) · oracle
agreement and gold-subset agreement · baseline comparison (human
first-contact resolution 91.5% `[measured]` on Transaccional calls;
Transactions-category complaint SLA; investigation savings **projected
only**) · per-language slices and the flip tables · adversarial results ·
ablation (or `not run: <blocker>`) · judge validation (or `not run:
<blocker>`) · repeated-run variability · error analysis (the main failure
groups, by id) · limitations.

## Behaviour

- **Determinism first.** With the `TemplateAgent` and one policy version the
  whole suite replays to identical verdicts (AC-8's promise at suite scale);
  the runner asserts this across repeats and reports any difference as a
  finding, not as noise.
- **Fail-closed counting.** A case whose turn raises is an `error` result;
  errors are listed with their traces in the error-analysis section. An
  `operator_queue` park the resume script cannot answer (no step left, or a
  step that is not `resume`) is **not** an error: the turn ends in the queue
  and is classified as usual (`HUMAN_QUEUE`, or `INVESTIGATE` with a bank
  case file), scoring as a mismatch against the oracle and counting toward
  the escalation-quality metric. Amendment rationale `[measured]`: the first
  tier0 run's 13 errored turns were all live laya 0.3.24 over-escalating
  routine Spanish (needs_human 0.67–0.89, overlapping explicit-human
  requests at 0.87–0.98, so no policy threshold separates them); recording
  that system behaviour as harness errors kept it out of every rate.
  `error` remains for genuine harness or case-file faults: a raise, an
  unknown park kind, or an `approve_action` park the script cannot answer
  with approve/deny.
- **Latency** is reported twice per the card: model compute (Laya classify
  plus LLM calls) and end-to-end wall time, both after the discarded
  warm-up. Laya is self-hosted: its cost is CPU time, reported as latency,
  and $0 in the cost table; LLM cost uses the committed `providers.yaml`
  prices.
- **Fairness slice (decision 25, Tier-0 part).** The dialect/language flip
  table runs on whatever message pairs exist: today the ES set; the PT
  column is `not run: T-203` until the Portuguese set lands, and the
  counterfactual suite stays Tier 1 (T-405).
- **No secret, no network in tests.** Every test uses `FakeLayaChecker`,
  `MockJudge`/`ScriptedAgent` and the synthetic bank fixture; the gated
  modules are tested for their skip behaviour, not their provider calls.

## Tests

- Oracle: every branch of the table, precedence (a fraud flag routes to a
  person before scope and writes, human request beats scope), and boundary
  amounts; `ORACLE_VERSION` pinned.
- Cases: loader schema validation, unknown fields rejected, AC-scenario
  adapter produces the same expected outcomes as the CI scoreboard.
- Runner: fresh data dir per case (a used-token case followed by the same
  case again behaves identically), resume scripts complete parked turns, an
  unanswerable `operator_queue` park ends the turn as a scored outcome while
  an unanswerable `approve_action` park stays an error, warm-up discarded
  from timings, errors captured not raised.
- Metrics: hand-computed fixtures for every rate, including empty-input
  behaviour ("not defined", never 0/0 as a number).
- Determinism: the tier0 suite run twice in one process yields identical
  verdicts.
- Report writer: all fixed sections present; every rate line carries n and
  an evidence label; gated sections render `not run: <blocker>` when keys
  are absent.
- CLI: `--suite tier0` exits 0 with no keys and no network.

## Done when

- `scripts/run_evaluation.py --suite tier0` runs offline end-to-end and
  writes the report and JSON, with the AC scenarios as the first slice.
- Outcome metrics are scored against the oracle with counts and
  denominators; the oracle's agreement with the hand-labelled gold subset
  is reported (until T-103 lands, the gold subset is the hand-labelled part
  of the evaluation cases, labelled as such).
- The adversarial slice covers every must-include of the card: incorrect or
  missing data, expired sessions, unauthorized access, prompt injection,
  tool failures, multilingual ambiguity, and the DESIGN 6.1 edge cases
  (exchange-rate discrepancy, hostile message about a trivial fee, empty or
  garbled messages).
- Judge validation (false-pass rate, other-family judge) and the bare-LLM
  ablation either ran with keys or are reported `not run` with the blocker.
- Repeated-run variability is stated for every generative component; model,
  policy, playbook, rubric and prompt versions appear in every run header.
- Results are labelled offline / simulated / projected with sample sizes and
  limitations, in the report and in the README results section (T-501).
- `CHANGELOG.md` entry; AGENTS.md layout line names `evaluation`.

## Open parameters

- Tier-0 suite size: proposed ~60–80 cases (8 AC scenarios, ~40 seeded
  oracle cases over the bank fixture's problem/clean/other-customer
  records, ~15 adversarial, ~5 edge cases). Stated in the report either way.
- `repeats` default 3 (the card asks for several runs of anything
  generative; deterministic components prove variability 0 by construction).

## Out of scope

Fine-tuned Laya (Tier 1, T-202), the full counterfactual fairness suite
(T-405), the verifier panel (T-402), live traffic of any kind.
