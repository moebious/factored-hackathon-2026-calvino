"""Shared setup for the tool tests: the synthetic bank fixture, a fixed clock and token helpers."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from calvino.tools import (
    BankAdapter,
    BankTools,
    CleanedTableAdapter,
    DatasetAdapter,
    HmacConfirmationVerifier,
    Session,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "bank" / "synthetic_bank.json"
CLEANED_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "cleaned_bank"
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
KEY = b"synthetic-test-key-0123456789-abcdef"  # test only; real keys come from the environment


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_dataset_adapter() -> DatasetAdapter:
    return DatasetAdapter(load_fixture(), clock=lambda: NOW)


# Every adapter the conformance suite runs against. A new adapter adds a factory here and must serve
# the same scenario ids as tests/fixtures/bank/synthetic_bank.json.
ADAPTER_FACTORIES: dict[str, Callable[[Path], BankAdapter]] = {
    "cleaned": lambda tmp_path: CleanedTableAdapter(
        CLEANED_FIXTURE,
        lineage_path=tmp_path / "cleaned-lineage.json",
        clock=lambda: NOW,
    ),
    "dataset": lambda _: make_dataset_adapter(),
}


@dataclass
class Env:
    adapter: BankAdapter
    verifier: HmacConfirmationVerifier
    tools: BankTools

    def session(self, customer_id: str, ttl: timedelta = timedelta(hours=1)) -> Session:
        return Session(customer_id=customer_id, expires_at=NOW + ttl)

    def token(self, customer_id: str, action: str, entry_reference: str) -> str:
        """What the hub would issue after an allow verdict, for exactly this action."""
        entry = self.adapter.get_entry_detail(self.session(customer_id), entry_reference)
        return self.verifier.issue(
            customer_id=customer_id,
            action=action,
            target_reference=entry_reference,
            amount=entry.amount,
            currency=entry.currency,
        )


def build_env(adapter: BankAdapter) -> Env:
    verifier = HmacConfirmationVerifier(KEY, clock=lambda: NOW)
    return Env(adapter, verifier, BankTools(adapter, verifier, clock=lambda: NOW))


@pytest.fixture(params=sorted(ADAPTER_FACTORIES))
def env(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Env]:
    adapter = ADAPTER_FACTORIES[request.param](tmp_path)
    try:
        yield build_env(adapter)
    finally:
        close = getattr(adapter, "close", None)
        if close is not None:
            close()


@pytest.fixture
def dataset_env() -> Env:
    return build_env(make_dataset_adapter())
