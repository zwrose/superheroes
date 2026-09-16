"""dispatch-entry.md generator: drift guard, idempotence, and envelope binding."""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN = os.path.normpath(os.path.join(_LIB, ".."))
_COMMITTED = os.path.join(
    _PLUGIN, "skills", "workhorse", "reference", "dispatch-entry.md"
)
_GEN_SCRIPT = os.path.join(_LIB, "dispatch_entry_doc.py")


def _load(name: str, filename: str):
    path = os.path.join(_LIB, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DED = _load("dispatch_entry_doc", "dispatch_entry_doc.py")
ED = _load("engine_dispatch", "engine_dispatch.py")
DG = _load("dispatch_guard", "dispatch_guard.py")
EA = _load("engine_adapter", "engine_adapter.py")
LC = _load("liveness_cache", "liveness_cache.py")


def _iter_leaf_subcommands(parser: argparse.ArgumentParser):
    stack: list[tuple[tuple[str, ...], argparse.ArgumentParser]] = [((), parser)]
    while stack:
        path, current = stack.pop()
        subparsers = None
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                subparsers = action
                break
        if subparsers is not None:
            for name, subparser in subparsers.choices.items():
                stack.append((path + (name,), subparser))
            continue
        yield path


def _expected_subcommand_labels():
    labels = []
    for cli_name, build_parser in (
        ("engine_dispatch.py", ED.build_parser),
        ("engine_adapter.py", EA.build_parser),
        ("dispatch_guard.py", DG.build_parser),
    ):
        parser = build_parser()
        for path in _iter_leaf_subcommands(parser):
            if path:
                labels.append("%s %s" % (cli_name, " ".join(path)))
            else:
                labels.append(cli_name)
    return labels


def test_generated_doc_matches_committed_file():
    # bite-axis: the generated doc matches the declaration.
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md") as fh:
        tmp_path = fh.name
    try:
        text = DED.generate()
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(_COMMITTED, encoding="utf-8") as fh:
            committed = fh.read()
        assert text == committed
    finally:
        os.unlink(tmp_path)


def test_generator_idempotent():
    first = DED.generate()
    second = DED.generate()
    assert first == second


def test_every_subcommand_appears_in_output():
    text = DED.generate()
    for label in _expected_subcommand_labels():
        assert "#### `%s`" % label in text


def test_envelope_values_match_modules():
    values = DED._envelope_values()
    assert values["max_wait_min"] == ED.MIN_SYNC_WAIT
    assert values["max_wait_max"] == ED.MAX_SYNC_WAIT
    assert values["run_lock_ttl"] == ED.RUN_LOCK_TTL
    assert values["dispatch_timeout"] == ED.RETRY_MIN_TIMEOUT
    assert values["expected_items_cap"] == ED.MAX_EXPECTED_ITEMS
    assert values["stdout_capture_cap"] == ED.MAX_STDOUT_CAPTURE
    assert values["stderr_capture_cap"] == ED.MAX_STDERR_CAPTURE
    assert values["abandon_confirm_seconds"] == ED.ABANDON_CONFIRM_SECONDS
    assert values["liveness_cache_ttl"] == LC.DEFAULT_TTL_SECONDS
    text = DED.generate()
    assert "| `--max-wait` range | [%d, %d] seconds |" % (
        ED.MIN_SYNC_WAIT, ED.MAX_SYNC_WAIT,
    ) in text
    assert "| Run-lock TTL | %d seconds" % ED.RUN_LOCK_TTL in text
    assert "| Dispatch timeouts" in text and "%d seconds |" % ED.RETRY_MIN_TIMEOUT in text
    assert "%d paths |" % ED.MAX_EXPECTED_ITEMS in text
    assert "%d bytes |" % ED.MAX_STDOUT_CAPTURE in text
    assert "%d bytes |" % ED.MAX_STDERR_CAPTURE in text
    assert "%d seconds |" % ED.ABANDON_CONFIRM_SECONDS in text
    assert "%d seconds |" % LC.DEFAULT_TTL_SECONDS in text


def test_undeclared_contract_is_a_generator_defect():
    # bite-axis: undeclared caller-contract arguments fail generation, not silent omission.
    parser = DED.engine_dispatch.build_parser()
    sub = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            sub = action
            break
    assert sub is not None
    leaked = sub.choices["dispatch-review"]
    leaked.add_argument("--bite-proof-leak", dest="bite_proof_leak")
    original = DED.engine_dispatch.build_parser
    DED.engine_dispatch.build_parser = lambda: parser
    try:
        with pytest.raises(DED.DispatchEntryDocError, match="undeclared"):
            DED.generate()
    finally:
        DED.engine_dispatch.build_parser = original


def test_cli_writes_file(tmp_path, monkeypatch):
    out = tmp_path / "dispatch-entry.md"
    monkeypatch.setattr(DED, "_DEFAULT_OUT", str(out))
    rc = DED.main([])
    assert rc == 0
    assert out.is_file()
    on_disk = out.read_text(encoding="utf-8")
    assert on_disk == DED.generate()


def test_cli_check_absent_file_refuses(tmp_path, monkeypatch):
    missing = tmp_path / "dispatch-entry.md"
    monkeypatch.setattr(DED, "_DEFAULT_OUT", str(missing))
    rc = DED.main(["--check"])
    assert rc == 1
