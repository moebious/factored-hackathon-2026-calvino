"""Pinned Laya checkpoints and the registry that names them (TSD-020, commit 1).

A checkpoint is pinned by two things the Hub cannot silently change: a 40-hex commit
and the SHA-256 of ``model.safetensors``. ``classifiers.yaml`` at the repository root
lists every checkpoint Calvino may load (the base today, a fine-tuned candidate later)
and names the default, so which weights answered a run is a diff somebody reads.

``router_kwargs`` turns one entry into the ``models`` / ``revisions`` /
``sha256_digests`` arguments laya 0.3.24's ``Router`` reads. laya checks the digest
against the file under the checkpoint's own folder before any weight is parsed, so a
tampered or re-pointed artifact fails at load instead of answering customers.

The registry never holds a key or a weight: ``HF_TOKEN`` stays in the environment.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# <repo>/classifiers.yaml, found from this file (src/calvino/classifiers/checkpoints.py).
DEFAULT_CLASSIFIERS_PATH = Path(__file__).resolve().parents[3] / "classifiers.yaml"

# The one artifact laya verifies for every checkpoint Calvino loads.
WEIGHTS_FILE = "model.safetensors"

# A full commit, lowercase: a branch, tag or short SHA can move or be ambiguous, which is
# exactly what a pin exists to rule out.
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class CheckpointRef(BaseModel):
    """One pinned checkpoint: where it lives, the exact commit and the weights' digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    # laya's Router only accepts its own three checkpoint names as `models` keys, so a
    # candidate loads by taking over a slot (the multilingual one) with its own repo.
    slot: Literal["english", "multilingual", "typed-decisions"] = "multilingual"
    repo: str
    subfolder: str | None = None
    revision: str
    sha256: str
    # The laya package version this checkpoint was trained or evaluated with; a mismatch
    # at preload is an error, because 0.3.26 already drifted into a keyed run unnoticed.
    laya_version: str
    # Run record under reports/finetune/ for a fine-tuned candidate; None for the base.
    run_record: str | None = None

    @field_validator("name", "repo", "laya_version")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("revision")
    @classmethod
    def _full_commit(cls, value: str) -> str:
        if not _COMMIT.fullmatch(value):
            raise ValueError("revision must be a full 40-hex lowercase commit, not a branch or tag")
        return value

    @field_validator("sha256")
    @classmethod
    def _full_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return value

    @property
    def checkpoint_id(self) -> str:
        """``name@revision``: what a log line or report header says answered."""
        return f"{self.name}@{self.revision}"


class ClassifierRegistry(BaseModel):
    """The contents of ``classifiers.yaml``: the checkpoints and which one is the default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default: str
    checkpoints: dict[str, CheckpointRef]

    @model_validator(mode="after")
    def _consistent(self) -> ClassifierRegistry:
        if self.default not in self.checkpoints:
            raise ValueError(f"default {self.default!r} is not a listed checkpoint")
        for key, ref in self.checkpoints.items():
            if ref.name != key:
                raise ValueError(f"checkpoint key {key!r} does not match its name {ref.name!r}")
        return self

    def get(self, name: str | None = None) -> CheckpointRef:
        """The named checkpoint, or the default; an unknown name lists the known ones."""
        key = self.default if name is None else name
        try:
            return self.checkpoints[key]
        except KeyError:
            raise KeyError(
                f"unknown checkpoint {key!r}; known: {sorted(self.checkpoints)}"
            ) from None


def load_registry(path: str | Path = DEFAULT_CLASSIFIERS_PATH) -> ClassifierRegistry:
    """Read and validate ``classifiers.yaml``."""
    with open(path, encoding="utf-8") as handle:
        return ClassifierRegistry.model_validate(yaml.safe_load(handle))


def router_kwargs(ref: CheckpointRef) -> dict:
    """The ``laya.Router`` keyword arguments that load exactly this checkpoint.

    Router merges ``models`` over its defaults, so an entry in the ``multilingual`` slot
    replaces the unpinned bundled one. The digest path is relative to the checkpoint's
    folder (the subfolder when there is one), which is where laya looks for it.
    """
    spec = (ref.repo, ref.subfolder) if ref.subfolder else ref.repo
    return {
        "models": {ref.slot: spec},
        "revisions": {ref.slot: ref.revision},
        "sha256_digests": {ref.slot: {WEIGHTS_FILE: ref.sha256}},
    }
