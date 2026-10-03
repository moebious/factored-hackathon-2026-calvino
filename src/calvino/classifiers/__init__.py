"""Laya service and calibration (TSD-005): System 1 typed decisions with calibrated probabilities.

Public API:
- LayaClient: wrapper around laya.Router pinned to one multilingual model.
- QuestionBuilder and the workflow question builders: laya question definitions
  that obey the usage rules (2-10 options, neutral binary keys).
- parse_answers: laya payload -> validated LayaAnswer records (act_probability
  is never exposed).
- Calibrator: temperature scaling fit per (question type, option count) with
  ECE/Brier before and after, and a reliability plot file.
"""

from calvino.classifiers.calibration import CalibrationReport, Calibrator
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
    "LayaAnswer",
    "LayaClient",
    "QuestionBuilder",
    "parse_answers",
    "workflow_questions",
]
