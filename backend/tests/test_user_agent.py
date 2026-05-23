import builtins

import pytest

from api.features.common import user_agent as user_agent_module
from api.features.common.user_agent import parse_user_agent


def test_parse_user_agent_fallback_when_user_agents_import_fails(monkeypatch):
    """Ensure parse_user_agent falls back cleanly when user_agents cannot be imported."""
    monkeypatch.setattr(user_agent_module, "_USER_AGENTS_AVAILABLE", None)
    monkeypatch.setattr(user_agent_module, "_ua_parse", None)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "user_agents":
            raise ImportError("No module named user_agents")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = parse_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )

    assert result["device_type"] == "desktop"
    assert "Chrome" in result["browser"]
    assert "Windows" in result["os"]


def test_parse_user_agent_empty_string_returns_unknown():
    result = parse_user_agent("")
    assert result["device_type"] == "unknown"
    assert result["browser"] == "Unknown"
    assert result["os"] == "Unknown"
