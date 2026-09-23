"""Creation rejects unactionable blocks before any durable write."""
import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_db_connect as kbc


@pytest.mark.parametrize("fields", [
    {},
    {"block_reason": " ", "block_kind": "needs_input", "unblock_action": "Approve access"},
    {"block_reason": "Access denied", "block_kind": "needs_input"},
    {"block_reason": "Access denied", "block_kind": "dependency", "unblock_action": "Wait"},
    {"block_reason": "Access denied", "block_kind": "gave_up", "unblock_action": "Retry"},
    {"block_reason": 42, "block_kind": "capability", "unblock_action": "Grant access"},
    {"block_reason": "Access denied", "block_kind": "capability", "unblock_action": "\n"},
    {"block_reason": "Access denied", "unblock_action": "Grant access"},
    {"initial_status": "running", "block_reason": "Access denied"},
    {"triage": True, "block_reason": "Access denied", "block_kind": "capability", "unblock_action": "Grant access"},
])
def test_invalid_initial_block_is_atomic(tmp_path, fields):
    with kbc.connect(tmp_path / "isolated.db") as conn:
        with pytest.raises(ValueError, match="block_reason|block_kind|unblock_action|triage"):
            kb.create_task(conn, title="Gate", **{"initial_status": "blocked", **fields})
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM task_events").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["needs_input", "capability", "transient"])
def test_initial_block_is_actionable_sticky_and_retry_safe(tmp_path, kind):
    with kbc.connect(tmp_path / "isolated.db") as conn:
        fields = dict(title="Gate", initial_status="blocked", block_kind=kind,
                      block_reason=" Access denied by deployment owner ",
                      unblock_action=" Owner grants deployment access, then unblock this card ",
                      idempotency_key="gate")
        tid = kb.create_task(conn, **fields)
        assert kb.create_task(conn, **fields) == tid
        task = kb.get_task(conn, tid)
        assert task.status == "blocked"
        assert task.block_kind == kind
        assert task.block_recurrences == 1
        events = [e for e in kb.list_events(conn, tid) if e.kind == "blocked"]
        assert len(events) == 1
        assert events[0].payload["reason"] == fields["block_reason"].strip()
        assert events[0].payload["unblock_action"] == fields["unblock_action"].strip()
        assert events[0].payload["kind"] == kind
        assert kb.recompute_ready(conn) == 0
        assert kb.get_task(conn, tid).status == "blocked"
        assert kb.unblock_task(conn, tid)
        assert kb.get_task(conn, tid).status == "ready"
