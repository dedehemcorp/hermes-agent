"""Fresh CLI processes must reject bad gates and persist actionable ones."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).parents[2]


def test_cli_initial_block_round_trip(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    db = home / "isolated.db"
    env = os.environ.copy()
    for key in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_BOARD",
                "HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SESSION_ID", "HERMES_SESSION_KEY"):
        env.pop(key, None)
    env.update(HERMES_HOME=str(home), HERMES_KANBAN_HOME=str(home),
               HERMES_KANBAN_DB=str(db), PYTHONPATH=str(ROOT))

    def run(*args):
        return subprocess.run([sys.executable, "-m", "hermes_cli.main", "kanban", *args],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    bad = run("create", "Gate", "--initial-status", "blocked", "--json")
    assert bad.returncode != 0
    assert "block_reason" in bad.stderr
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM task_events").fetchone()[0] == 0
    good = run("create", "Gate", "--initial-status", "blocked",
               "--block-reason", "Owner has not approved publication",
               "--block-kind", "needs_input", "--unblock-action",
               "Owner confirms publication and unblocks this card", "--json")
    assert good.returncode == 0, good.stderr
    tid = json.loads(good.stdout)["id"]
    shown = run("show", tid, "--json")
    assert shown.returncode == 0, shown.stderr
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT status, block_kind FROM tasks WHERE id = ?", (tid,)).fetchone() == (
            "blocked", "needs_input")
        event = json.loads(conn.execute(
            "SELECT payload FROM task_events WHERE task_id = ? AND kind = 'blocked'", (tid,)
        ).fetchone()[0])
        assert event["reason"] == "Owner has not approved publication"
        assert event["unblock_action"] == "Owner confirms publication and unblocks this card"
