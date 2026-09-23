"""A recurring LLM cron must carry a wake gate when the rule is enabled."""
import pytest

from cron import jobs


@pytest.fixture
def rule(monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"cron": {"require_gate_for_recurring_llm": True}})


def test_ungated_recurring_llm_job_is_refused(rule):
    with pytest.raises(ValueError, match="must be gated"):
        jobs._require_gate_for_recurring_llm({"kind": "interval"}, {})


@pytest.mark.parametrize("fields", [{"script": "g.py"}, {"monitor_script": "m.py"}, {"monitor_url": "http://x"}, {"no_agent": True}])
def test_gated_recurring_jobs_are_allowed(rule, fields):
    jobs._require_gate_for_recurring_llm({"kind": "cron"}, fields)


def test_one_shot_llm_job_needs_no_gate(rule):
    jobs._require_gate_for_recurring_llm({"kind": "once"}, {})


def test_rule_off_by_default(monkeypatch):
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    jobs._require_gate_for_recurring_llm({"kind": "interval"}, {})
