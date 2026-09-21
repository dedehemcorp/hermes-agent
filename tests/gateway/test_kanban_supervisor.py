"""Local fork: central Kanban supervision subscriptions."""

def test_supervisor_subscribes_home_before_dispatch(monkeypatch, tmp_path):
    from gateway.kanban_watchers_dispatcher import _KanbanDispatcher, _DispatcherSettings, _SupervisorTarget
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    from hermes_cli import kanban_db_notify as kbn

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    kb.init_db()
    with kbc.connect_closing() as conn:
        active_id = kb.create_task(conn, title="active", assignee="worker")
        done_id = kb.create_task(conn, title="done", assignee="worker")
        with kb.write_txn(conn):
            conn.execute("UPDATE tasks SET status='done', completed_at=1 WHERE id=?", (done_id,))

    settings = _DispatcherSettings(60.0, None, None, 3, 900, True, None, 1)
    dispatcher = _KanbanDispatcher(kb, settings)
    target = _SupervisorTarget("telegram", "6301525376", "6301525376", "dm", "default", {"chat_type": "dm"})

    assert dispatcher.ensure_supervisor_subscriptions(target) == 1
    assert dispatcher.ensure_supervisor_subscriptions(target) == 0
    with kbc.connect_closing() as conn:
        active_subs = kbn.list_notify_subs(conn, active_id)
        done_subs = kbn.list_notify_subs(conn, done_id)
    assert len(active_subs) == 1
    assert active_subs[0]["delivery_mode"] == "notify+wake"
    assert active_subs[0]["notifier_profile"] == "default"
    assert done_subs == []
