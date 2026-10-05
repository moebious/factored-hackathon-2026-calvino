"""Laya service and calibration (TSD-005): System 1 typed decisions with calibrated probabilities.

Public API:
- FineTuneRunRecord, write_run_record: the record of one fine-tuning run (TSD-020).
- CheckpointRef, load_registry, router_kwargs: pinned checkpoints (commit plus
  weights digest) listed in classifiers.yaml (TSD-020).
- LayaClient: wrapper around laya.Router pinned to one multilingual model.
- QuestionBuilder and the workflow question builders: laya question definitions
  that obey the usage rules (2-10 options, neutral binary keys).
- parse_answers: laya payload -> validated LayaAnswer records (act_probability
  is never exposed).
- Calibrator: temperature scaling fit per (question type, option count) with
  ECE/Brier before and after, and a reliability plot file.
"""

from calvino.classifiers.calibration import CalibrationReport, Calibrator
from calvino.classifiers.checkpoints import (
    CheckpointRef,
    ClassifierRegistry,
    load_registry,
    router_kwargs,
)
from calvino.classifiers.finetune_record import (
    FineTuneRunRecord,
    load_run_record,
    write_run_record,
)
from calvino.classifiers.laya import (
    LayaAnswer,
    LayaClient,
    QuestionBuilder,
    parse_answers,
    workflow_questions,
)

__all__ = [
    "CalibrationReport",
    "Calibrator",
    "CheckpointRef",
    "ClassifierRegistry",
    "FineTuneRunRecord",
    "LayaAnswer",
    "LayaClient",
    "QuestionBuilder",
    "load_registry",
    "load_run_record",
    "parse_answers",
    "router_kwargs",
    "workflow_questions",
    "write_run_record",
]
