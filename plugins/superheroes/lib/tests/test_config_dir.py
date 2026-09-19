"""Tests for config_dir.resolve — edge 8 from WO-A (#1273)."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "config_dir", os.path.join(_HERE, "..", "config_dir.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CD = _load()


def test_resolve_strips_padded_override(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    env = {"HOME": str(tmp_path / "home"), "CLAUDE_CONFIG_DIR": " /abs/with-space "}
    assert CD.resolve(env=env) == "/abs/with-space"


def test_resolve_expands_home_against_supplied_env_not_process(monkeypatch):
    monkeypatch.setenv("HOME", "/ambient-home")
    supplied = {"HOME": "/lane-home", "CLAUDE_CONFIG_DIR": "~/.claude-two"}
    assert CD.resolve(env=supplied) == "/lane-home/.claude-two"


def test_resolve_relative_override_with_absolute_cwd(monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    assert CD.resolve(cwd="/build/wt") == "/build/wt/relative/config"


def test_resolve_relative_override_without_absolute_cwd_returns_none(monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    assert CD.resolve() is None
    assert CD.resolve(cwd="not-absolute") is None


def test_resolve_missing_home_and_non_absolute_expanduser_returns_none(monkeypatch):
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setattr(CD.os.path, "expanduser", lambda _path: "relative-home")
    assert CD.resolve(env={}) is None


def test_resolve_review_and_write_cwd_both_absolute_same_answer(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    review_cwd = "/build/review-wt"
    write_cwd = "/build/write-wt"
    env = {"CLAUDE_CONFIG_DIR": "lane/config"}
    assert CD.resolve(env=env, cwd=review_cwd) == os.path.normpath(
        os.path.join(review_cwd, "lane/config"))
    assert CD.resolve(env=env, cwd=write_cwd) == os.path.normpath(
        os.path.join(write_cwd, "lane/config"))
