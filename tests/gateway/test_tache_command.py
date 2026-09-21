"""Explicit /tache command: conversation stays conversation unless the user opts in."""

from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform
from gateway.platforms.event import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli import kanban_db as kb, kanban_db_connect as kbc


@pytest.mark.asyncio
async def test_tache_creates_one_assigned_task_and_subscribes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._kanban_notifier_profile = "default"
    runner._kanban_auto_subscribe = AsyncMock(return_value=True)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="6301525376",
        chat_type="dm",
        user_id="6301525376",
        profile="default",
    )

    reply = await runner._handle_tache_command(
        MessageEvent(text="/tache Corriger le serveur\nPuis vérifier le résultat", source=source)
    )

    with kbc.connect() as conn:
        tasks = kb.list_tasks(conn)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.title == "Corriger le serveur"
    assert task.body == "Corriger le serveur\nPuis vérifier le résultat"
    assert task.assignee == "default"
    assert task.created_by == "explicit-/tache"
    assert task.status == "ready"
    assert task.id in reply
    runner._kanban_auto_subscribe.assert_awaited_once()
    subscribed_event, subscribed_task_id, subscribed_board = runner._kanban_auto_subscribe.call_args.args
    assert subscribed_event.text.startswith("/tache ")
    assert subscribed_task_id == task.id
    assert subscribed_board == "default"


@pytest.mark.asyncio
async def test_tache_without_description_is_rejected_without_creating_task(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    runner = GatewayRunner.__new__(GatewayRunner)
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", profile="default")

    reply = await runner._handle_tache_command(MessageEvent(text="/tache", source=source))

    with kbc.connect() as conn:
        assert kb.list_tasks(conn) == []
    assert "Usage" in reply


@pytest.mark.asyncio
@pytest.mark.parametrize("description", ["-h", "--help", "--body", "--json"])
async def test_tache_accepts_descriptions_that_look_like_cli_options(
    description, tmp_path, monkeypatch
):
    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._kanban_notifier_profile = "default"
    runner._kanban_auto_subscribe = AsyncMock(return_value=True)
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", profile="default")

    reply = await runner._handle_tache_command(
        MessageEvent(text=f"/tache {description}", source=source)
    )

    with kbc.connect() as conn:
        tasks = kb.list_tasks(conn)
    assert len(tasks) == 1
    assert tasks[0].title == description
    assert tasks[0].body == description
    assert tasks[0].id in reply


@pytest.mark.asyncio
async def test_tache_idempotency_is_isolated_by_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._kanban_notifier_profile = "default"
    runner._kanban_auto_subscribe = AsyncMock(return_value=True)

    for profile in ("gaston", "gustave"):
        source = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="shared-chat",
            chat_type="dm",
            profile=profile,
        )
        await runner._handle_tache_command(
            MessageEvent(
                text="/tache Même identifiant Telegram",
                source=source,
                message_id="42",
            )
        )

    with kbc.connect() as conn:
        tasks = kb.list_tasks(conn)
    assert len(tasks) == 2
    assert {task.assignee for task in tasks} == {"gaston", "gustave"}


@pytest.mark.asyncio
async def test_tache_pins_creation_and_subscription_to_the_same_board(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    kb.create_board("alpha", name="Alpha")
    kb.set_current_board("alpha")
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._kanban_notifier_profile = "default"
    runner._kanban_auto_subscribe = AsyncMock(return_value=True)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="1",
        chat_type="dm",
        profile="default",
    )

    reply = await runner._handle_tache_command(
        MessageEvent(text="/tache Tâche sur Alpha", source=source, message_id="9")
    )

    with kbc.connect(board="alpha") as conn:
        tasks = kb.list_tasks(conn)
    assert len(tasks) == 1
    assert tasks[0].id in reply
    assert runner._kanban_auto_subscribe.call_args.args[2] == "alpha"