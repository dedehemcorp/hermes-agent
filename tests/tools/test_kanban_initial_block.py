"""The registered tool enforces the same initial-block contract as the DB."""
import json
from pathlib import Path

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_db_connect as kbc
from tools import kanban_tools  # noqa: F401 — register the real tool
from tools.registry import registry


def test_registered_create_requires_and_preserves_block_evidence(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(home / "isolated.db"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for key in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_BOARD",
                "HERMES_SESSION_ID", "HERMES_SESSION_KEY"):
        monkeypatch.delenv(key, raising=False)
    fields = dict(title="Approval gate", assignee="operator", initial_status="blocked")
    rejected = json.loads(registry.dispatch("kanban_create", fields))
    assert "block_reason" in rejected["error"]
    with kbc.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
    evidence = dict(block_reason="Owner has not approved publication", block_kind="needs_input",
                    unblock_action="Owner confirms publication, then unblocks this card")
    schema = registry.get_schema("kanban_create")["parameters"]["properties"]
    assert all(key in schema for key in evidence)
    created = json.loads(registry.dispatch("kanban_create", {**fields, **evidence}))
    assert created["ok"], created
    tid = created["task_id"]
    shown = json.loads(registry.dispatch("kanban_show", {"task_id": tid}))
    assert shown["task"]["status"] == "blocked"
    event = next(e for e in shown["events"] if e["kind"] == "blocked")
    assert event["payload"]["reason"] == evidence["block_reason"]
    assert event["payload"]["unblock_action"] == evidence["unblock_action"]
    with kbc.connect() as conn:
        assert kb.get_task(conn, tid).block_kind == "needs_input"
