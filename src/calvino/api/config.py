"""Runtime configuration for the demo API (TSD-003).

Every location and secret is configuration, never code: the durable-storage
directory (``CALVINO_DATA_DIR``) and the demo rate limit
(``CALVINO_DEMO_RATE_LIMIT``) come from environment variables. A Space's own
disk is wiped on restart, so in the deployment ``CALVINO_DATA_DIR`` must
point at the persistent-storage mount (``/data``); ``decisions.jsonl`` and
the hub's checkpointer database both live there, which is what makes cases
and the audit log survive restarts (DESIGN 4.0.2).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DECISIONS_LOG_NAME = "decisions.jsonl"
CHECKPOINT_DB_NAME = "checkpoints.sqlite"

# Local-development default only; the deployment sets CALVINO_DATA_DIR=/data.
DEFAULT_DATA_DIR = Path(".calvino-data")

# The synthetic bank fixture the hub's tools serve in the demo (TSD-010),
# found from this file: <repo>/tests/fixtures/bank/synthetic_bank.json. The
# Docker image copies the fixture to the same relative location, so the
# default resolves there too; CALVINO_BANK_FIXTURE overrides both.
DEFAULT_BANK_FIXTURE = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "bank" / "synthetic_bank.json"
)


class ApiSettings(BaseModel):
    """The configuration of one API process."""

    model_config = ConfigDict(frozen=True)

    data_dir: Path = DEFAULT_DATA_DIR
    bank_fixture: Path = DEFAULT_BANK_FIXTURE
    demo_rate_limit_per_minute: int = Field(default=30, ge=1)

    @property
    def decisions_log(self) -> Path:
        """The append-only decision log on the configured storage."""
        return self.data_dir / DECISIONS_LOG_NAME

    @property
    def checkpoint_db(self) -> Path:
        """Where the LangGraph checkpointer will keep its database (T-204/T-401).

        Reserved here so the hub lands on the same durable storage as the
        decision log instead of the ephemeral container disk.
        """
        return self.data_dir / CHECKPOINT_DB_NAME


def settings_from_env(env: Mapping[str, str] | None = None) -> ApiSettings:
    """Build settings from environment variables (``os.environ`` by default)."""
    source = os.environ if env is None else env
    raw_limit = source.get("CALVINO_DEMO_RATE_LIMIT")
    return ApiSettings(
        data_dir=Path(source.get("CALVINO_DATA_DIR", str(DEFAULT_DATA_DIR))),
        bank_fixture=Path(source.get("CALVINO_BANK_FIXTURE", str(DEFAULT_BANK_FIXTURE))),
        demo_rate_limit_per_minute=int(raw_limit) if raw_limit else 30,
    )
