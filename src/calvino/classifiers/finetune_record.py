"""The run record of one Laya fine-tuning run (TSD-020, T-202).

After the maintainer runs the Kaggle notebook, a ``FineTuneRunRecord`` captures what
happened: the base and output checkpoints (commit and ``model.safetensors`` digest),
the environment, every hyperparameter, the exported dataset's manifest, the training
numbers and the leakage-guard result. ``write_run_record`` turns it into
``reports/finetune/T-202-<date>-<revision12>.json`` and ``.md``.

Two rules shape this module:

- **It reports no accuracy.** The only quality numbers are the training-set fit, and
  the Markdown writer prints ``train fit, not evaluation`` beside every one of them.
  Whether the checkpoint is better is T-201's held-out comparison, never this record.
- **A record that could not have come from a valid run does not validate.** A failed
  leakage check, an output identical to the base, or an effective batch that does not
  match the settings raises instead of being written down.

Records are immutable once written: a second record for the same output commit refuses
to overwrite the first.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[3] / "reports" / "finetune"

# Printed beside every training number, so a reader cannot mistake it for a result.
TRAIN_FIT_LABEL = "train fit, not evaluation"

# The leakage-guard checks TSD-020 names; a record must report each one, and pass it.
REQUIRED_LEAKAGE_CHECKS = (
    "wrong-split",
    "text-overlap",
    "shared-keys",
    "portuguese-row",
    "unknown-label",
)

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _commit(value: str) -> str:
    if not _COMMIT.fullmatch(value):
        raise ValueError("must be a full 40-hex lowercase commit")
    return value


def _digest(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError("must be 64 lowercase hex characters")
    return value


class BaseCheckpointRecord(_Frozen):
    """The checkpoint training started from."""

    repo: str
    subfolder: str | None = None
    revision: str
    sha256: str
    # Measured by the run: the vendor notebook says 421M, DECISIONS cites 322M.
    parameter_count: int = Field(gt=0)

    @field_validator("revision")
    @classmethod
    def _full_commit(cls, value: str) -> str:
        return _commit(value)

    @field_validator("sha256")
    @classmethod
    def _full_digest(cls, value: str) -> str:
        return _digest(value)


class OutputCheckpointRecord(_Frozen):
    """The checkpoint training produced, as published (a new commit, never overwritten)."""

    repo: str
    revision: str
    tag: str
    sha256: str

    @field_validator("revision")
    @classmethod
    def _full_commit(cls, value: str) -> str:
        return _commit(value)

    @field_validator("sha256")
    @classmethod
    def _full_digest(cls, value: str) -> str:
        return _digest(value)


class Environment(_Frozen):
    laya_version: str
    torch_version: str
    transformers_version: str
    cuda_version: str | None
    gpu_model: str
    gpu_count: int = Field(gt=0)


class Deviation(_Frozen):
    """A departure from TSD-020, with the reason it was needed."""

    setting: str
    reason: str


LOSS_FULL = "policy gradient + soft cross-entropy"
LOSS_CE_ONLY = "soft cross-entropy only"


class LoopSettings(_Frozen):
    """The settings the vendor notebook fixes in code (TSD-020), recorded rather than assumed."""

    loss: Literal["policy gradient + soft cross-entropy", "soft cross-entropy only"]
    cross_entropy_weight: float = Field(ge=0)
    sigma_start: float = Field(gt=0)
    sigma_end: float = Field(gt=0)
    reward_weight_spherical: float = Field(ge=0)
    reward_weight_rps: float = Field(ge=0)
    max_len: int = Field(gt=0)
    head_max_len: int = Field(gt=0)
    max_tokens_per_batch: int = Field(gt=0)
    gradient_checkpointing: bool
    mixed_precision: str
    # The shuffle seed is this base plus the epoch plus the rank; torch is seeded with the
    # base plus the rank, which the vendor notebook never does (TSD-020 change 5).
    torch_seed_base: int
    # The temperature hold-out is chosen by the exporter, by message.
    holdout_max_items: int = Field(gt=0)
    holdout_fraction_percent: int = Field(gt=0)


class Configuration(_Frozen):
    """Every P2 setting, the seed and any deviation from the spec."""

    epochs: int = Field(gt=0)
    micro_batch: int = Field(gt=0)
    grad_accum: int = Field(gt=0)
    effective_batch: int = Field(gt=0)
    group_size: int = Field(gt=0)
    lr_encoder: float = Field(gt=0)
    lr_head: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    schedule: str
    min_lr: float = Field(ge=0)
    grad_clip: float = Field(gt=0)
    seed: int
    loop: LoopSettings
    deviations: tuple[Deviation, ...] = ()


class DataManifest(_Frozen):
    """The export manifest, in full (TSD-020 exporter)."""

    input_sha256: str
    set_version: str
    rubric_version: str
    question_schema_sha256: str
    counts: dict[str, dict[str, int]]  # question id -> option -> items
    reviewed: int = Field(ge=0)
    unreviewed: int = Field(ge=0)
    excluded: dict[str, int] = {}  # reason -> rows
    exporter_git_sha: str

    @field_validator("input_sha256", "question_schema_sha256")
    @classmethod
    def _full_digest(cls, value: str) -> str:
        return _digest(value)


class Training(_Frozen):
    loss_per_epoch: tuple[float, ...]
    wall_time_seconds: float = Field(gt=0)
    # question id -> training-set accuracy in [0, 1]. Never an evaluation figure.
    train_fit: dict[str, float]
    # laya's own per-type temperatures, fitted on the hold-out slice and baked into the
    # checkpoint's config, which laya applies at inference. Not Calvino's calibration (T-201).
    laya_temperatures: dict[str, float] = {}

    @field_validator("train_fit")
    @classmethod
    def _fit_is_a_fraction(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("report a training fit for at least one question")
        for question, fit in value.items():
            if not 0.0 <= fit <= 1.0:
                raise ValueError(f"train fit for {question!r} must be within [0, 1]")
        return value


class LeakageCheck(_Frozen):
    check: str
    passed: bool


class FineTuneRunRecord(_Frozen):
    """Everything one run produced; the writer renders exactly this."""

    run: int = Field(gt=0)
    run_date: str  # ISO date, supplied by the caller (the writer reads no clock)
    notebook: str  # repository path of the notebook that ran
    base: BaseCheckpointRecord
    output: OutputCheckpointRecord
    environment: Environment
    configuration: Configuration
    data: DataManifest
    training: Training
    leakage_guard: tuple[LeakageCheck, ...]
    notes: str = ""

    @field_validator("run_date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _consistent(self) -> FineTuneRunRecord:
        if self.output.revision == self.base.revision or self.output.sha256 == self.base.sha256:
            raise ValueError("the output checkpoint must differ from the base checkpoint")
        if self.output.tag != f"t202-run{self.run}":
            raise ValueError(f"output tag must be t202-run{self.run}")
        config = self.configuration
        expected = config.micro_batch * config.grad_accum * self.environment.gpu_count
        if config.effective_batch != expected:
            raise ValueError(
                f"effective_batch {config.effective_batch} does not equal micro_batch x "
                f"grad_accum x gpu_count ({expected})"
            )
        if len(self.training.loss_per_epoch) != config.epochs:
            raise ValueError("loss_per_epoch needs exactly one value per epoch")
        reported = {check.check for check in self.leakage_guard}
        missing = [name for name in REQUIRED_LEAKAGE_CHECKS if name not in reported]
        if missing:
            raise ValueError(f"leakage guard did not report: {', '.join(missing)}")
        failed = [check.check for check in self.leakage_guard if not check.passed]
        if failed:
            raise ValueError(f"leakage guard failed, so no record is written: {', '.join(failed)}")
        return self

    @property
    def stem(self) -> str:
        """``T-202-<date>-<revision12>``: the file name both outputs share."""
        return f"T-202-{self.run_date}-{self.output.revision[:12]}"


def load_run_record(path: str | Path) -> FineTuneRunRecord:
    """Read and validate a run record's JSON."""
    return FineTuneRunRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


def record_json(record: FineTuneRunRecord) -> str:
    """The record as stable JSON: sorted keys, so the same record is byte-identical."""
    return json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_markdown(record: FineTuneRunRecord) -> str:
    """The human report. It names both checkpoints and claims no accuracy."""
    base, out, env, cfg = record.base, record.output, record.environment, record.configuration
    data, training = record.data, record.training
    base_name = f"{base.repo}/{base.subfolder}" if base.subfolder else base.repo
    lines = [
        f"# Laya fine-tuning run {record.run}: {record.run_date}",
        "",
        "This record reports **no Laya accuracy**. Its only quality numbers are the "
        f"training-set fit, labelled `{TRAIN_FIT_LABEL}`. Whether the checkpoint is better "
        "than base or calibrated base Laya is decided by the T-201 held-out comparison.",
        "",
        "## Checkpoints",
        "",
        "| | Repository | Commit | `model.safetensors` SHA-256 |",
        "|---|---|---|---|",
        f"| Base | {base_name} | `{base.revision}` | `{base.sha256}` |",
        f"| Output | {out.repo} (tag `{out.tag}`) | `{out.revision}` | `{out.sha256}` |",
        "",
        f"Base parameter count: {base.parameter_count:,} [measured by the run].",
        "",
        "## Environment",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| laya | {env.laya_version} |",
        f"| torch | {env.torch_version} |",
        f"| transformers | {env.transformers_version} |",
        f"| CUDA | {env.cuda_version or 'none'} |",
        f"| GPU | {env.gpu_count} x {env.gpu_model} |",
        f"| Notebook | `{record.notebook}` |",
        "",
        "## Configuration",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Epochs | {cfg.epochs} |",
        f"| Micro-batch / accumulation / effective | {cfg.micro_batch} / {cfg.grad_accum} / "
        f"{cfg.effective_batch} |",
        f"| GRPO group size | {cfg.group_size} |",
        f"| Learning rate (encoder / head) | {cfg.lr_encoder:g} / {cfg.lr_head:g} |",
        f"| Weight decay | {cfg.weight_decay:g} |",
        f"| Schedule | {cfg.schedule} (down to {cfg.min_lr:g}) |",
        f"| Gradient clip | {cfg.grad_clip:g} |",
        f"| Seed | {cfg.seed} |",
        f"| Loss | {cfg.loop.loss} (cross-entropy weight {cfg.loop.cross_entropy_weight:g}) |",
        f"| Exploration noise | {cfg.loop.sigma_start:g} to {cfg.loop.sigma_end:g} |",
        f"| Reward weights (spherical / RPS) | {cfg.loop.reward_weight_spherical:g} / "
        f"{cfg.loop.reward_weight_rps:g} |",
        f"| Sequence lengths (item / head) | {cfg.loop.max_len} / {cfg.loop.head_max_len} |",
        f"| Precision / gradient checkpointing | {cfg.loop.mixed_precision} / "
        f"{cfg.loop.gradient_checkpointing} |",
        f"| Torch seed base | {cfg.loop.torch_seed_base} (plus rank) |",
        f"| Temperature hold-out | min({cfg.loop.holdout_max_items}, "
        f"{cfg.loop.holdout_fraction_percent}% of items), chosen by message |",
        "",
    ]
    if cfg.deviations:
        lines += ["Deviations from TSD-020:", ""]
        lines += [f"- **{item.setting}**: {item.reason}" for item in cfg.deviations]
    else:
        lines += ["No deviation from TSD-020."]
    lines += [
        "",
        "## Data",
        "",
        f"- Input SHA-256: `{data.input_sha256}` (set `{data.set_version}`, rubric "
        f"`{data.rubric_version}`)",
        f"- Question-schema SHA-256: `{data.question_schema_sha256}`",
        f"- Exporter git sha: `{data.exporter_git_sha}`",
        f"- Reviewed rows: {data.reviewed}; unreviewed rows: {data.unreviewed}",
        "",
        "| Question | Option | Items |",
        "|---|---|---|",
    ]
    for question, options in data.counts.items():
        lines += [f"| {question} | {option} | {n} |" for option, n in options.items()]
    lines += ["", "Excluded rows: " + (_excluded(data.excluded)), ""]
    lines += [
        "## Training",
        "",
        f"Wall time: {training.wall_time_seconds:,.0f} s [measured].",
        "",
        "| Metric | Value | Label |",
        "|---|---|---|",
    ]
    for epoch, loss in enumerate(training.loss_per_epoch, start=1):
        lines.append(f"| Loss, epoch {epoch} | {loss:.4f} | {TRAIN_FIT_LABEL} |")
    for question, fit in training.train_fit.items():
        lines.append(f"| Train fit, {question} | {fit:.1%} | {TRAIN_FIT_LABEL} |")
    if training.laya_temperatures:
        temperatures = ", ".join(f"{k} {v:.3f}" for k, v in training.laya_temperatures.items())
        lines += [
            "",
            f"laya's own temperatures, fitted on the hold-out slice and baked into the "
            f"checkpoint's config (not Calvino's calibration, which T-201 fits): {temperatures}.",
        ]
    lines += ["", "## Leakage guard", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {c.check} | {'pass' if c.passed else 'FAIL'} |" for c in record.leakage_guard]
    if record.notes:
        lines += ["", "## Notes", "", record.notes]
    return "\n".join(lines) + "\n"


def _excluded(excluded: dict[str, int]) -> str:
    if not excluded:
        return "none."
    return "; ".join(f"{reason}: {count}" for reason, count in excluded.items()) + "."


def write_run_record(
    record: FineTuneRunRecord, out_dir: str | Path = DEFAULT_RECORD_DIR
) -> tuple[Path, Path]:
    """Write ``<stem>.md`` and ``<stem>.json``; refuses to overwrite an existing record."""
    directory = Path(out_dir)
    md_path, json_path = directory / f"{record.stem}.md", directory / f"{record.stem}.json"
    for path in (md_path, json_path):
        if path.exists():
            raise FileExistsError(f"{path} already exists; a run record is never overwritten")
    directory.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(record), encoding="utf-8")
    json_path.write_text(record_json(record), encoding="utf-8")
    return md_path, json_path
