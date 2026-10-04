"""Offline CLI tests: no AWS credential file and no live S3 calls."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from calvino.data.inventory_access import TABLE_NAMES, SourceManifest, SourceObject


def _main() -> object:
    script = Path(__file__).resolve().parents[3] / "scripts" / "full_data_inventory.py"
    return runpy.run_path(str(script))["main"]


def test_cli_requires_reviewed_manifest_before_any_body_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    main = _main()
    manifest = SourceManifest(
        tuple(SourceObject(name, f"data/{name}.csv", 10, "fake", None) for name in TABLE_NAMES),
        "reviewed-digest",
    )
    reads = []
    monkeypatch.setitem(main.__globals__, "load_credentials", lambda: "synthetic-bucket")
    monkeypatch.setitem(main.__globals__, "s3_client", lambda: object())
    monkeypatch.setitem(main.__globals__, "discover", lambda *_: manifest)
    monkeypatch.setitem(main.__globals__, "build_report", lambda *_: reads.append("read"))
    assert main(["--manifest"]) == 0
    assert '"total_bytes": 130' in capsys.readouterr().out
    assert main(["--run", "--manifest-digest", "wrong", "--max-source-bytes", "130"]) == 1
    assert reads == []
    assert "manifest changed" in capsys.readouterr().err
    assert main(["--run", "--manifest-digest", "reviewed-digest", "--max-source-bytes", "1"]) == 1
    assert reads == []
    monkeypatch.setitem(
        main.__globals__,
        "review_type_flags",
        lambda *_: reads.append("targeted") or {"label": "diagnostic", "tables": {}},
    )
    assert (
        main(["--review-types", "--manifest-digest", "reviewed-digest", "--max-source-bytes", "30"])
        == 0
    )
    assert reads == ["targeted"]
    assert '"label": "diagnostic"' in capsys.readouterr().out


def test_cli_access_check_does_not_discover_or_stage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    main = _main()
    calls = []
    monkeypatch.setitem(main.__globals__, "load_credentials", lambda: "synthetic-bucket")
    monkeypatch.setitem(main.__globals__, "s3_client", lambda: object())
    monkeypatch.setitem(main.__globals__, "probe", lambda *_: calls.append("probe"))
    monkeypatch.setitem(main.__globals__, "discover", lambda *_: calls.append("discover"))
    assert main(["--check-access"]) == 0
    assert calls == ["probe"]
    assert capsys.readouterr().out.strip() == "access=ok"
