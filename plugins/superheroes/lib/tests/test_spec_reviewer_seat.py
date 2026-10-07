# plugins/superheroes/lib/tests/test_spec_reviewer_seat.py
"""The spec checks' reviewer-seat resolver (engine_pref.resolve_spec_reviewer_seat) and its
`core_md.py spec-reviewer-seat` verb."""
import json
import os
import shutil
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_pref  # noqa: E402
import model_registry  # noqa: E402
import seat_bundle  # noqa: E402

ROLE = "brief-check"
_CORE_MD = os.path.join(_LIB, "core_md.py")


def _resolve(author, live, configured=None, **extra):
    prefs = dict(extra)
    if configured is not None:
        prefs["specReviewer"] = configured
    return engine_pref.resolve_spec_reviewer_seat(prefs, author, live)


def _assert_cell(got):
    model, effort = model_registry.matrix_config(ROLE, got["engine"])
    assert (got["model"], got["effort"]) == (model, effort)
    assert got["seat"] == {"vendor": got["engine"], "model": model, "effort": effort,
                           "role": ROLE}
    assert got["family"] == model_registry.family_for(ROLE, got["engine"])


def test_unset_claude_author_picks_installed_cross_family_engine():
    # Bites on: rule 2 dropping the live filter or the family exclusion (claude author, live [claude, codex] -> codex)
    got = _resolve("claude", ["claude", "codex"])
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")
    assert (got["configuredState"], got["configured"], got["configuredReason"]) == ("unset", None, None)
    assert got["sameFamily"] is False
    assert got["ok"] is True
    _assert_cell(got)


def test_unset_all_live_takes_first_vendor_in_registry_order():
    # Bites on: rule 2 not walking model_registry.vendors() order (claude author, all live -> codex before cursor)
    got = _resolve("claude", ["cursor", "codex", "claude"])
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")
    assert model_registry.vendors().index("codex") < model_registry.vendors().index("cursor")


def test_configured_cross_family_live_engine_wins():
    # Bites on: rule 1 not honoring a valid configured engine (cursor configured, all live -> cursor)
    got = _resolve("claude", ["claude", "codex", "cursor"], configured="cursor")
    assert (got["engine"], got["source"]) == ("cursor", "configured")
    assert (got["configured"], got["configuredState"], got["configuredReason"]) == ("cursor", "valid", None)
    _assert_cell(got)


def test_configured_same_family_is_passed_over():
    # Bites on: rule 1 dropping the family-differs condition (claude configured for a claude author -> codex)
    got = _resolve("claude", ["claude", "codex"], configured="claude")
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")
    assert (got["configuredState"], got["configuredReason"]) == ("valid", "configured-same-family")


def test_configured_engine_not_live_is_passed_over():
    # Bites on: rule 1 dropping the `in live_engines` condition (codex configured, live [claude] -> claude fallback)
    got = _resolve("claude", ["claude"], configured="codex")
    assert (got["engine"], got["source"]) == ("claude", "same-family-fallback")
    assert (got["configuredState"], got["configuredReason"]) == ("valid", "configured-unavailable")
    assert got["sameFamily"] is True


def test_unset_only_claude_live_falls_back_to_same_family():
    # Bites on: rule 2 dropping the family-differs condition (live [claude] must reach same-family-fallback)
    got = _resolve("claude", ["claude"])
    assert (got["engine"], got["source"]) == ("claude", "same-family-fallback")
    assert got["sameFamily"] is True
    assert got["family"] == got["authorFamily"]
    _assert_cell(got)


def test_codex_author_unset_picks_claude():
    # Bites on: rule 2 skipping the claude engine for a non-claude author (codex author, live [claude, codex] -> claude)
    got = _resolve("codex", ["claude", "codex"])
    assert (got["engine"], got["source"]) == ("claude", "cross-family-installed")
    assert got["authorEngine"] == "codex"
    assert got["authorFamily"] == model_registry.family_for(ROLE, "codex")
    _assert_cell(got)


def test_cursor_author_unset_picks_claude():
    # Bites on: rule 2 picking the author's own family for a cursor author (live [claude, cursor] -> claude)
    got = _resolve("cursor", ["claude", "cursor"])
    assert (got["engine"], got["source"]) == ("claude", "cross-family-installed")
    _assert_cell(got)


def test_invalid_configured_reports_its_reason_and_resolves_as_unset():
    # Bites on: ignoring invalidSpecReviewer (state must be invalid with the classifier's reason)
    prefs = {"invalidSpecReviewer": {"value": "gemini", "reason": "spec-reviewer-unknown-engine"}}
    got = engine_pref.resolve_spec_reviewer_seat(prefs, "claude", ["claude", "codex"])
    assert (got["configuredState"], got["configuredReason"]) == ("invalid", "spec-reviewer-unknown-engine")
    assert got["configured"] is None
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")


def test_read_error_is_unreadable_with_the_reason_token():
    # Bites on: readError not surfaced as unreadable (reason is the text before the first colon, stripped)
    prefs = {"specReviewer": "cursor", "readError": " core-md-unreadable : boom: detail"}
    got = engine_pref.resolve_spec_reviewer_seat(prefs, "claude", ["claude", "codex", "cursor"])
    assert (got["configuredState"], got["configuredReason"]) == ("unreadable", "core-md-unreadable")
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")


def test_prefs_that_is_not_a_dict_is_treated_as_unset():
    # Bites on: a non-dict prefs raising instead of resolving as unset
    got = engine_pref.resolve_spec_reviewer_seat(None, "claude", ["claude", "codex"])
    assert (got["configuredState"], got["engine"]) == ("unset", "codex")


def test_unknown_author_engine_raises_value_error():
    # Bites on: an unknown author engine resolving instead of raising ValueError
    with pytest.raises(ValueError):
        engine_pref.resolve_spec_reviewer_seat({}, "gemini", ["claude"])


def test_result_keys_are_exactly_the_contract():
    # Bites on: a result key added, dropped or renamed against the shared contract
    got = _resolve("claude", ["claude", "codex"])
    assert sorted(got) == sorted([
        "ok", "engine", "model", "effort", "family", "authorEngine", "authorFamily", "sameFamily",
        "source", "configured", "configuredState", "configuredReason", "seat"])
    assert got["source"] in engine_pref.SPEC_REVIEWER_SOURCES


@pytest.mark.parametrize("author,live,configured", [
    ("claude", ["claude", "codex"], None),
    ("claude", ["claude"], None),
    ("claude", ["claude", "codex", "cursor"], "cursor"),
    ("codex", ["claude", "codex"], None),
    ("cursor", ["claude", "cursor"], None),
])
def test_every_resolved_seat_passes_the_dispatch_review_brief_check_entry(author, live, configured):
    # Bites on: a seat bundle dispatch-review --mode brief-check would refuse
    got = _resolve(author, live, configured=configured)
    res = seat_bundle.resolve_entry(json.dumps(got["seat"]), verb="dispatch-review", mode="brief-check")
    assert res["ok"] is True, res


# --- the verb --------------------------------------------------------------

def _verb(tmp_path, *, fake_binaries, author="claude"):
    """Run the verb with PATH holding only a `git` passthrough and the named fake CLIs."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    real_git = shutil.which("git")
    (bindir / "git").write_text('#!/bin/sh\nexec "%s" "$@"\n' % real_git)
    (bindir / "git").chmod(0o755)
    for name in fake_binaries:
        (bindir / name).write_text("#!/bin/sh\nexit 0\n")
        (bindir / name).chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    env = {"PATH": str(bindir), "HOME": str(tmp_path / "home")}
    proc = subprocess.run(
        [sys.executable, "-B", _CORE_MD, "spec-reviewer-seat", "--cwd", str(project),
         "--root", str(tmp_path / "store"), "--author-engine", author],
        capture_output=True, text=True, env=env, timeout=60)
    return proc


def test_verb_picks_codex_when_a_codex_cli_is_on_path(tmp_path):
    # Bites on: the verb not reading installed engines (fake codex on PATH -> codex cross-family-installed)
    proc = _verb(tmp_path, fake_binaries=["codex"])
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert (got["engine"], got["source"]) == ("codex", "cross-family-installed")
    _assert_cell(got)


def test_verb_falls_back_to_claude_with_no_other_cli(tmp_path):
    # Bites on: the verb inventing a cross-family engine when none is installed
    proc = _verb(tmp_path, fake_binaries=[])
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert (got["engine"], got["source"]) == ("claude", "same-family-fallback")
    assert got["sameFamily"] is True


def test_verb_counts_claude_always_live_for_a_codex_author(tmp_path):
    # Bites on: the verb not adding claude to the live set (codex author, no CLIs -> claude cross-family-installed)
    proc = _verb(tmp_path, fake_binaries=[], author="codex")
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert (got["engine"], got["source"]) == ("claude", "cross-family-installed")


def test_verb_refuses_an_unknown_author_engine_as_a_usage_error(tmp_path):
    # Bites on: an unknown --author-engine accepted instead of an argparse exit 2
    proc = subprocess.run(
        [sys.executable, "-B", _CORE_MD, "spec-reviewer-seat", "--cwd", str(tmp_path),
         "--author-engine", "gemini"],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2
