"""compression.summary_guidance is appended to every summary prompt."""
from unittest.mock import patch

from agent import context_compressor as cc
from tests.agent.test_compress_focus import _make_compressor


def _prompt(guidance):
    comp = _make_compressor()
    with patch("hermes_cli.config.load_config", return_value={"compression": {"summary_guidance": guidance}}):
        return comp._build_summary_prompt("turns", 1000, None, "", True)


def test_standing_guidance_injected():
    prompt = _prompt("Garder  decisions,\n fichiers et prochaine etape.")
    assert "STANDING PRIORITIES" in prompt
    assert "Garder decisions, fichiers et prochaine etape." in prompt


def test_no_guidance_no_block():
    assert "STANDING PRIORITIES" not in _prompt("")
    assert "STANDING PRIORITIES" not in _prompt(None)


def test_guidance_before_focus():
    comp = _make_compressor()
    with patch("hermes_cli.config.load_config", return_value={"compression": {"summary_guidance": "G"}}):
        prompt = comp._build_summary_prompt("turns", 1000, "topic", "", True)
    assert prompt.index("STANDING PRIORITIES") < prompt.index("FOCUS TOPIC")
    assert len(cc._standing_summary_guidance()) <= cc._STANDING_GUIDANCE_MAX_CHARS
