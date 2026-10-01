# plugins/superheroes/lib/tests/test_verify_command_type_check.py
"""#1331: a present verifyCommand that is not a non-empty string is refused at the one reader
(core_md.parse_core), and every named caller surfaces the refusal instead of reading it as
"no verify command". Axis: refusal by type and content at parse; the callers never see a
non-string verify command."""
import json
import os

import pytest

import configure_view as cv
import core_md as cm
import guardian_sweep as gsw
import review_code_config as rcc
from guardian_fixtures import FixtureLens, init_calibrated_repo, write_guardian_layer

# Falsy wrong type, truthy wrong type, non-string scalar, empty and whitespace-only strings.
MALFORMED = [[], 0, 7, ["x"], "   ", ""]
REFUSAL_TOKEN = "verify-command-malformed"
ACCEPTED_SHAPE = "must be a non-empty string, or null for none"


def _core_text(verify):
    return cm.render_core({"verifyCommand": verify, "stackTags": [], "threatModel": "x",
                           "patterns": ""}, "confirmed", "2026-10-01", "2026-10-01")


def _write_core(repo, verify):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "core.md"), "w", encoding="utf-8") as fh:
        fh.write(_core_text(verify))


@pytest.mark.parametrize("bad", MALFORMED, ids=repr)
def test_parse_core_refuses_malformed_verify_command(bad):
    with pytest.raises(cm.VerifyCommandMalformed) as exc:
        cm.parse_core(_core_text(bad))
    assert exc.value.reason == REFUSAL_TOKEN
    assert str(exc.value).startswith(REFUSAL_TOKEN + ": ")
    assert ACCEPTED_SHAPE in str(exc.value)


@pytest.mark.parametrize("good", [None, "npm test", " make check "], ids=repr)
def test_parse_core_keeps_null_and_real_commands(good):
    assert cm.parse_core(_core_text(good))["verifyCommand"] == good


def test_parse_core_absent_key_reads_as_none():
    text = _core_text("x").replace('"verifyCommand": "x",\n', "")
    assert '"verifyCommand"' not in text
    assert cm.parse_core(text)["verifyCommand"] is None


@pytest.mark.parametrize("bad", MALFORMED, ids=repr)
def test_review_config_surfaces_refusal_and_skips_profile_fallback(bad, tmp_path, monkeypatch):
    repo = str(tmp_path)
    _write_core(repo, bad)
    # A legacy profile that WOULD supply a command if the refusal were swallowed into the fallback.
    prof = os.path.join(repo, "review-profile.md")
    with open(prof, "w", encoding="utf-8") as fh:
        fh.write("## Verify\ncommand: make test\n")
    import calibration_resolve as cr
    monkeypatch.setattr(cr, "resolve", lambda cwd, root=None, **kw: {
        "exists": True, "dispatch_layer": prof, "legacy_path": None})
    out = rcc.resolve(repo, root=str(tmp_path / "store"))
    assert out["calibrationRefusal"]["reason"] == REFUSAL_TOKEN
    assert ACCEPTED_SHAPE in out["calibrationRefusal"]["remedy"]
    assert out["verifyCommand"] == "none"  # the review gate receives a string, never `bad`


@pytest.mark.parametrize("bad", MALFORMED, ids=repr)
def test_guardian_verify_step_never_runs_a_malformed_command(bad, tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command=bad)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        raise AssertionError("verify step ran %r" % (cmd,))

    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(required_facts=("verify-command",))
    with pytest.raises(cm.VerifyCommandMalformed):
        gsw.collect(repo, lenses=[lens], root=str(tmp_path / "store"), run=fake_run)
    assert calls == []


def test_guardian_cli_reports_the_refusal(tmp_path, capsys):
    repo = init_calibrated_repo(tmp_path, verify_command=[])
    gsw.main(["collect", "--cwd", repo, "--root", str(tmp_path / "store")])
    out = json.loads(capsys.readouterr().out)
    assert out["error"].startswith(REFUSAL_TOKEN + ": ")


def test_dispatch_gates_classify_the_refusal_as_named_unreadable(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="   ")
    store = str(tmp_path / "store")
    prefs = cm.engine_preferences_for_gate(cwd=repo, root=store)
    policy = cm.review_gate_policy_for_gate(cwd=repo, root=store)
    for gate in (prefs, policy):
        assert gate.status == cm.CONFIG_UNREADABLE
        assert gate.detail.startswith(REFUSAL_TOKEN + ": ")


def test_core_resolve_cli_refuses_by_name_and_exits_nonzero(tmp_path, capsys):
    repo = init_calibrated_repo(tmp_path, verify_command=["x"])
    rc = cm.main(["resolve", "--cwd", repo, "--root", str(tmp_path / "store")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == REFUSAL_TOKEN
    assert "verifyCommand" not in out


def test_configure_view_refuses_instead_of_showing_none(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command=0)
    with pytest.raises(cm.VerifyCommandMalformed, match=REFUSAL_TOKEN):
        cv.render(repo, root=str(tmp_path / "store"))
