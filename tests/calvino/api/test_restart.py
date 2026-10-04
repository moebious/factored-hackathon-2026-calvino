"""The restart test (TSD-003): state survives a restart of the process.

A Space's own disk is wiped on restart, so everything that must survive lives
under ``CALVINO_DATA_DIR`` (the persistent-storage mount in the deployment).
This test simulates the restart at the boundary the API controls: one app
instance writes a decision record and a checkpoint database on the configured
storage, then a *new* app instance (same settings, fresh loader) reads both
back. The full container restart is a documented Docker check in
docs/DEPLOY.md; the LangGraph checkpointer (T-204) will use
``settings.checkpoint_db``, which is what the second half of this test pins.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from calvino.api.app import create_app
from calvino.api.config import ApiSettings
from calvino.decision_log import read_records


def test_state_survives_a_restart(fake_loader_factory, policy, tmp_path):
    settings = ApiSettings(data_dir=tmp_path / "data")

    # First "process": serve one decision, then write a checkpoint row where
    # the hub's checkpointer will keep its database.
    payload = {"text": "mi pago no llega"}
    with TestClient(create_app(fake_loader_factory(), settings, policy)) as first:
        response = first.post("/api/demo/decide", json=payload)
    assert response.status_code == 200
    decision_id = response.json()["decision_id"]

    connection = sqlite3.connect(settings.checkpoint_db)
    connection.execute("create table checkpoints (thread_id text primary key, blob text)")
    connection.execute("insert into checkpoints values ('thread-1', 'checkpoint-state')")
    connection.commit()
    connection.close()

    # Second "process": a new app instance on the same storage reads both back.
    with TestClient(create_app(fake_loader_factory(), settings, policy)) as second:
        assert second.get("/ready").json() == {"ready": True}

    records = list(read_records(settings.decisions_log))
    assert [record.decision_id for record in records] == [decision_id]

    connection = sqlite3.connect(settings.checkpoint_db)
    rows = connection.execute("select thread_id, blob from checkpoints").fetchall()
    connection.close()
    assert rows == [("thread-1", "checkpoint-state")]
