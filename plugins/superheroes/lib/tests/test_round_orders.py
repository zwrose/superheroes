"""Tests for `round_orders` — template renderer and base residual resolver (#723)."""
import json
import os
import re
import shlex
import subprocess

import pytest

import core_md as CM
import round_adapters as RA
import round_orders as RO
import round_phases as RP
import round_records as RR

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "orders")
_CLAUSE_MANIFEST = os.path.join(_FIXTURES, "clause_manifest.json")
_GOLDEN_DIR = os.path.join(_FIXTURES, "golden")

_SESSION = "/tmp/superheroes-session-wo4-golden"
_REPO = "/home/user/proj"
_PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PLUGIN_RUBRIC = os.path.join(_PLUGIN_ROOT, "rubric", "review-base.md")
_CORE_UNRESOLVED = "(Core calibration not resolved for this project)"
_LAYER_UNRESOLVED = "(Review-crew layer calibration not resolved for this project)"
_ESCALATION = os.path.join(_PLUGIN_ROOT, "lib", "escalation_resolve.py")


def _base_context(**over):
    ctx = {
        "session_dir": _SESSION,
        "round": 2,
        "attempt": 0,
        "diff_path": os.path.join(_SESSION, "round-2", "diff.txt"),
        "rubric_path": _PLUGIN_RUBRIC,
        "core_path": "",
        "layer_path": "",
        "repo_root": _REPO,
        "landing_path": os.path.join(_SESSION, "round-2", "landing", "seat.a0.json"),
        "envelope_stub_path": os.path.join(_SESSION, "round-2", "stubs", "seat.json"),
        "ratified_residuals": "- Flaky integration test in CI lane B is accepted",
        "residuals_provenance": "Residuals below are read from the review base commit (base-pinned).",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": False,
        "placeholders": {},
    }
    ctx.update(over)
    return ctx


def _panel_placeholders(channel="file", pr_checkout=False):
    ph = {
        "MODE": "branch",
        "REPO": "acme/widget",
        "TARGET": "feature/wo4",
        "DIFF_PATH": os.path.join(_SESSION, "round-2", "diff.txt"),
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CORE_PATH": _CORE_UNRESOLVED,
        "LAYER_PATH": _LAYER_UNRESOLVED,
        "PR_CHECKOUT_PATH": os.path.join(_SESSION, "repo") if pr_checkout else "",
        "PRIOR_COMMENTS_PATH": os.path.join(_SESSION, "prior-comments.json"),
        "FOCUS_NOTES": "touch auth paths carefully",
        "DIMENSION": "Code",
        "CHANNEL": channel,
        "FINDINGS_OUTPUT_PATH": os.path.join(_SESSION, "round-2", "findings-code.json"),
    }
    return ph


def _verifier_placeholders(channel="file"):
    return {
        "CLUSTER_FINDINGS_PATH": os.path.join(_SESSION, "round-2", "clusters", "0.json"),
        "DIFF_PATH": os.path.join(_SESSION, "round-2", "diff.txt"),
        "VERIFICATION_ROOT": _REPO,
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CHANNEL": channel,
    }


def _synthesis_placeholders(channel="file"):
    return {
        "VERIFIED_FINDINGS_PATH": os.path.join(_SESSION, "round-2", "verified.json"),
        "DIFF_PATH": os.path.join(_SESSION, "round-2", "diff.txt"),
        "VERIFICATION_ROOT": _REPO,
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "GROUPING_OUTPUT_PATH": os.path.join(_SESSION, "round-2", "grouping.json"),
        "CHANNEL": channel,
    }


def _fixer_placeholders():
    return {
        "FIX_BATCH_PATH": os.path.join(_SESSION, "round-2", "fix-batch.json"),
        "PROFILE_PATH": "(Project profile not resolved for this project)",
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CWD": _REPO,
        "REPO_ROOT": shlex.quote(_REPO),
        "ESCALATION_WRAPPER_PATH": shlex.quote(_ESCALATION),
        "VERIFY_COMMAND": "npm test",
        "ROUND": "2",
    }


def _gapsweep_placeholders(channel="file"):
    return {
        "DIFF_PATH": os.path.join(_SESSION, "round-2", "diff.txt"),
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CORE_PATH": _CORE_UNRESOLVED,
        "LAYER_PATH": _LAYER_UNRESOLVED,
        "VERIFICATION_ROOT": _REPO,
        "FINDINGS_OUTPUT_PATH": os.path.join(_SESSION, "round-2", "gap-sweep-findings.json"),
        "CHANNEL": channel,
    }


def _audits_placeholders(channel="file"):
    return {
        "TARGET_SUMMARY_PATH": os.path.join(_SESSION, "round-2", "audit-targets", "t0.json"),
        "HEAD_DIFF_PATH": os.path.join(_SESSION, "round-2", "head.diff"),
        "VERIFICATION_ROOT": _REPO,
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "TARGET_ID": "finding::auth.py::12",
        "CHANNEL": channel,
    }


def _scoped_placeholders(channel="file"):
    return {
        "HUNKS_PATH": os.path.join(_SESSION, "round-2", "scoped-hunks.json"),
        "HEAD_DIFF_PATH": os.path.join(_SESSION, "round-2", "head.diff"),
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CORE_PATH": _CORE_UNRESOLVED,
        "LAYER_PATH": _LAYER_UNRESOLVED,
        "VERIFICATION_ROOT": _REPO,
        "FINDINGS_OUTPUT_PATH": os.path.join(_SESSION, "round-2", "scoped-findings.json"),
        "CHANNEL": channel,
    }


_GOLDEN_CONTEXTS = {
    RP.P_PANEL: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.payload.json"),
        placeholders=_panel_placeholders(),
    ),
    RP.P_VERIFIERS: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-verifiers",
                                  "verifier:0.a0.payload.json"),
        placeholders=_verifier_placeholders(),
    ),
    RP.P_SYNTHESIS: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-synthesis",
                                  "synthesis.a0.payload.json"),
        placeholders=_synthesis_placeholders(),
    ),
    RP.P_FIXER: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-fixer",
                                  "fixer.a0.payload.json"),
        placeholders=_fixer_placeholders(),
    ),
    RP.P_GAPSWEEP: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-gap-sweep",
                                  "gap-sweep.a0.payload.json"),
        placeholders=_gapsweep_placeholders(),
    ),
    RP.P_AUDITS: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-audits",
                                  RR.storage_key("finding::auth.py::12", 0) + ".a0.payload.json"),
        placeholders=_audits_placeholders(),
    ),
    RP.P_SCOPED: lambda: _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-scoped-finder",
                                  "scoped-finder.a0.payload.json"),
        placeholders=_scoped_placeholders(),
    ),
}


def _render_golden(phase):
    ctx = _GOLDEN_CONTEXTS[phase]()
    text, reason = RO.render_order(phase, "golden-seat", ctx)
    assert reason is None, reason
    return text


def _normalize_golden_machine_paths(text):
    """Fold checkout-specific plugin-root prefixes; goldens pin content, not machine paths."""
    real_root = os.path.realpath(_PLUGIN_ROOT)
    text = text.replace(real_root, "${PLUGIN_ROOT}")
    return re.sub(
        r"/[^\s'\"()]+/plugins/superheroes[^\s'\"()]*",
        lambda m: "${PLUGIN_ROOT}" + m.group(0).split("/plugins/superheroes", 1)[1],
        text,
    )


# --- fail-closed edges ---------------------------------------------------------


@pytest.mark.parametrize("phase", [RP.P_VERIFY, RP.P_JUDGMENT, RP.P_STALL])
def test_render_refuses_phases_without_templates(phase):
    text, reason = RO.render_order(phase, "seat", _base_context())
    assert text is None
    assert reason == "no-template:%s" % phase


def test_render_refuses_missing_template_file(tmp_path, monkeypatch):
    missing = os.path.join(tmp_path, "rubric", "orders")
    os.makedirs(missing)
    monkeypatch.setattr(RO, "order_template_path", lambda phase, root=None: os.path.join(
        missing, phase + ".md"))
    text, reason = RO.render_order(RP.P_PANEL, "seat", _base_context(placeholders=_panel_placeholders()))
    assert text is None
    assert reason == "template-missing:dispatch-panel"


def test_render_refuses_unfilled_placeholder():
    ph = _panel_placeholders()
    del ph["DIMENSION"]
    text, reason = RO.render_order(RP.P_PANEL, "seat", _base_context(placeholders=ph))
    assert text is None
    assert reason == "unfilled-placeholder:DIMENSION"


def test_render_refuses_unused_context_key():
    ph = _panel_placeholders()
    ph["ORPHAN_KEY"] = "unused"
    text, reason = RO.render_order(RP.P_PANEL, "seat", _base_context(placeholders=ph))
    assert text is None
    assert reason == "unused-context-key:ORPHAN_KEY"


def test_render_success_has_no_placeholder_syntax():
    text, reason = RO.render_order(RP.P_PANEL, "seat",
                                   _base_context(placeholders=_panel_placeholders()))
    assert reason is None
    assert "{{" not in text


def test_resolve_base_residuals_no_base_oid():
    text, reason = RO.resolve_base_residuals("/repo", None, ".claude/superheroes/core.md")
    assert text == ""
    assert reason == "no-base-oid"


def test_resolve_base_residuals_no_core_at_base(tmp_path):
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    subprocess.run(["git", "-C", repo, "commit", "--allow-empty", "-qm", "init"], check=True)
    base = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    text, reason = RO.resolve_base_residuals(repo, base, "missing/core.md")
    assert text == ""
    assert reason == "no-core-at-base"


def _write_core_file(repo, rel, residual):
    facts = {
        "schemaVersion": 1,
        "verifyCommand": "true",
        "stackTags": [],
        "enginePreferences": {},
        "threatModel": "t",
        "patterns": "p",
        "showItSurface": "",
        "ratifiedResiduals": residual,
    }
    text = CM.render_core(facts, "confirmed", "2026-01-01", "2026-01-01")
    path = os.path.join(repo, rel)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_resolve_base_residuals_no_residual_section(tmp_path):
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    _write_core_file(repo, "core.md", "")
    subprocess.run(["git", "-C", repo, "add", "core.md"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "core"], check=True)
    base = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    text, reason = RO.resolve_base_residuals(repo, base, "core.md")
    assert text == ""
    assert reason is None


def test_resolve_base_residuals_reads_base_not_worktree(tmp_path):
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    core_rel = "core.md"

    _write_core_file(repo, core_rel, "base residual only")
    subprocess.run(["git", "-C", repo, "add", core_rel], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "base"], check=True)
    base = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()

    _write_core_file(repo, core_rel, "branch-widened residual list")
    subprocess.run(["git", "-C", repo, "commit", "-am", "widen"], check=True)

    text, reason = RO.resolve_base_residuals(repo, base, core_rel)
    assert reason is None
    assert text == "base residual only"


def test_resolve_base_residuals_git_failure(monkeypatch):
    def _boom(*_a, **_k):
        raise FileNotFoundError("git missing")

    monkeypatch.setattr(RO.subprocess, "run", _boom)
    text, reason = RO.resolve_base_residuals("/repo", "abc123", "core.md")
    assert text == ""
    assert reason.startswith("git-cat-file-failed:")


# --- clause manifest -----------------------------------------------------------


def _clause_in_rendered(clause, text):
    return clause in text or " ".join(clause.split()) in " ".join(text.split())


def test_clause_manifest_covers_every_order_template():
    manifest = json.load(open(_CLAUSE_MANIFEST, encoding="utf-8"))
    templates_dir = os.path.join(_PLUGIN_ROOT, "rubric", "orders")
    for name in sorted(os.listdir(templates_dir)):
        if not name.endswith(".md"):
            continue
        template_name = name[:-3]
        assert template_name in manifest, "uncovered template: %s" % template_name


def test_clause_manifest_survives_in_rendered_orders():
    manifest = json.load(open(_CLAUSE_MANIFEST, encoding="utf-8"))
    phase_map = {
        "dispatch-panel": (RP.P_PANEL, lambda: _panel_placeholders(pr_checkout=True)),
        "dispatch-verifiers": (RP.P_VERIFIERS, _verifier_placeholders),
        "dispatch-synthesis": (RP.P_SYNTHESIS, _synthesis_placeholders),
        "dispatch-fixer": (RP.P_FIXER, _fixer_placeholders),
        "dispatch-gap-sweep": (RP.P_GAPSWEEP, _gapsweep_placeholders),
        "dispatch-audits": (RP.P_AUDITS, _audits_placeholders),
        "dispatch-scoped-finder": (RP.P_SCOPED, _scoped_placeholders),
    }
    test_clause_manifest_covers_every_order_template()
    for template_name, clauses in manifest.items():
        phase, ph_fn = phase_map[template_name]
        text, reason = RO.render_order(phase, "seat", _base_context(placeholders=ph_fn()))
        assert reason is None, "%s: %s" % (template_name, reason)
        for clause in clauses:
            assert _clause_in_rendered(clause, text), (
                "missing clause %r in %s" % (clause, template_name))


# --- template contract census --------------------------------------------------


def _template_body(phase):
    path = RO.order_template_path(phase)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _contract_vocabulary(phase):
    contract, reason = RA.payload_contract(phase)
    assert reason is None, reason
    fields = set()
    fields.update(contract.get("required") or [])
    fields.update(contract.get("optional") or [])
    fields.update((contract.get("conditional") or {}).keys())
    enum_values = []
    for values in (contract.get("enums") or {}).values():
        enum_values.extend(values)
    return fields, enum_values


@pytest.mark.parametrize("phase", list(RO.ORDER_PHASES))
def test_template_body_does_not_restate_payload_contract(phase):
    body = _template_body(phase)
    fields, enum_values = _contract_vocabulary(phase)
    violations = []
    for field in sorted(fields):
        if re.search(r"\b" + re.escape(field) + r"\b", body):
            violations.append("field %s in %s" % (field, RO.order_template_path(phase)))
    for value in enum_values:
        if re.search(r"\b" + re.escape(value) + r"\b", body):
            violations.append("enum value %r in %s" % (value, RO.order_template_path(phase)))
    assert not violations, "; ".join(violations)


# --- golden fixtures -----------------------------------------------------------


@pytest.mark.parametrize("phase", list(_GOLDEN_CONTEXTS))
def test_golden_render_matches_fixture(phase):
    golden_path = os.path.join(_GOLDEN_DIR, phase + ".txt")
    rendered = _render_golden(phase)
    with open(golden_path, encoding="utf-8") as fh:
        expected = fh.read()
    assert _normalize_golden_machine_paths(rendered) == _normalize_golden_machine_paths(expected)


# --- FX-1: host-seat and stdout-channel golden coverage (fix 14) ----------------


def test_golden_host_seat_landing_block_asserts_payload_path():
    landing = os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                           "code-reviewer.a0.payload.json")
    ctx = _base_context(
        host_seat=True,
        landing_path=landing,
        placeholders=_panel_placeholders(channel="file"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert "Payload landing path: %s" % landing in text
    assert "stdout channel" not in text.split("## Return your result")[1]


def test_golden_host_seat_landing_block_no_stub_copy():
    ctx = _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.payload.json"),
        placeholders=_panel_placeholders(channel="file"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert "stub" not in text.lower() or "no stub copy" in text.lower()
    assert "Payload landing path" in text
    assert "Envelope stub:" not in text
    assert "Copy the envelope stub" not in text


def test_golden_stdout_channel_panel_order():
    ctx = _base_context(
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.json"),
        placeholders=_panel_placeholders(channel="stdout"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert "stdout" in text.lower() or "final stdout" in text
    assert "do not write a findings file" in text


# --- FX-1: focus normalization (fix 8) -----------------------------------------


@pytest.mark.parametrize("focus,expected_substr", [
    ({"area": "auth"}, '"area":"auth"'),
    (["auth", "payments"], '["auth","payments"]'),
    (None, ""),
])
def test_render_normalizes_focus_notes(focus, expected_substr):
    ph = _panel_placeholders()
    ph["FOCUS_NOTES"] = focus if focus is not None else ""
    if focus is None:
        ph.pop("FOCUS_NOTES", None)
    ctx = _base_context(placeholders=ph)
    if focus is not None:
        ctx["placeholders"]["FOCUS_NOTES"] = focus
    # Driver normalizes before render; simulate via derived placeholders path
    import round_driver as RD
    normalized = RD._normalize_focus_notes(focus)
    ph["FOCUS_NOTES"] = normalized
    text, reason = RO.render_order(RP.P_PANEL, "seat", _base_context(placeholders=ph))
    assert reason is None
    if expected_substr:
        assert expected_substr.replace('"', '"') in text or expected_substr in text


def test_render_focus_dict_via_driver_normalization():
    import round_driver as RD
    focus = {"scope": "auth"}
    assert RD._normalize_focus_notes(focus) == '{"scope":"auth"}'
    ph = _panel_placeholders()
    ph["FOCUS_NOTES"] = RD._normalize_focus_notes(focus)
    text, reason = RO.render_order(RP.P_PANEL, "seat", _base_context(placeholders=ph))
    assert reason is None
    assert "auth" in text


# --- FX-1: resolve_order_residuals (fix 6) -------------------------------------


def test_resolve_order_residuals_in_repo_reads_base(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    _write_core_file(repo, ".claude/superheroes/core.md", "base residual only")
    subprocess.run(["git", "-C", repo, "add", ".claude/superheroes/core.md"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "base"], check=True)
    base = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    _write_core_file(repo, ".claude/superheroes/core.md", "branch widened")
    subprocess.run(["git", "-C", repo, "commit", "-am", "widen"], check=True)
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.IN_REPO})
    text, prov, failure = RO.resolve_order_residuals(repo, base)
    assert failure is None
    assert "base-pinned" in prov
    assert text == "base residual only"


def test_resolve_order_residuals_out_of_repo_reads_store(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    facts = {
        "verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": "p",
        "ratifiedResiduals": "store residual line",
    }
    CM.write(repo, facts, "confirmed", now="2026-01-01")
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.GLOBAL})
    text, prov, failure = RO.resolve_order_residuals(repo, "abc123")
    assert failure is None
    assert "store file" in prov
    assert text == "store residual line"


def test_resolve_order_residuals_unreadable_store(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path)
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.GLOBAL})
    text, prov, failure = RO.resolve_order_residuals(repo, None)
    assert text == ""
    assert failure == "core-unreadable-or-absent"
    assert "store file" in prov


def test_resolve_order_residuals_empty_store_section_is_not_failure(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    facts = {
        "verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": "p",
        "ratifiedResiduals": "",
    }
    CM.write(repo, facts, "confirmed", now="2026-01-01")
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.GLOBAL})
    text, prov, failure = RO.resolve_order_residuals(repo, "abc123")
    assert failure is None
    assert text == ""
    assert "store file" in prov


def test_render_residual_block_empty_store_section_shows_none_recorded(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    facts = {
        "verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": "p",
        "ratifiedResiduals": "",
    }
    CM.write(repo, facts, "confirmed", now="2026-01-01")
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.GLOBAL})
    text, prov, failure = RO.resolve_order_residuals(repo, None)
    assert failure is None
    ctx = _base_context(
        ratified_residuals=text,
        residuals_provenance=prov,
        residuals_read_failure=failure,
        placeholders=_panel_placeholders(),
    )
    rendered, reason = RO.render_order(RP.P_PANEL, "seat", ctx)
    assert reason is None
    assert "No ratified residuals are recorded" in rendered
    assert "Residuals could not be read" not in rendered


def test_render_residual_block_unreadable_store_shows_failure(tmp_path, monkeypatch):
    import mode_registry as mr
    repo = str(tmp_path)
    monkeypatch.setattr(mr, "resolve", lambda cwd, root=None: {"mode": mr.GLOBAL})
    text, prov, failure = RO.resolve_order_residuals(repo, None)
    assert failure == "core-unreadable-or-absent"
    ctx = _base_context(
        ratified_residuals=text,
        residuals_provenance=prov,
        residuals_read_failure=failure,
        placeholders=_panel_placeholders(),
    )
    rendered, reason = RO.render_order(RP.P_PANEL, "seat", ctx)
    assert reason is None
    assert "Residuals could not be read" in rendered
    assert "core-unreadable-or-absent" in rendered


# --- FX-1: shipped resource guard (fix 1) --------------------------------------


def test_shipped_resource_refusal_when_rubric_missing(monkeypatch):
    import round_driver as RD
    ph = _panel_placeholders()
    missing = "/nonexistent/review-base.md"
    ph["RUBRIC_PATH"] = missing
    monkeypatch.setattr(RD, "_shipped_rubric_path", lambda: missing)
    reason = RD._shipped_resource_refusal(ph)
    assert reason == "shipped-resource-missing:RUBRIC_PATH"


def test_shipped_resource_refusal_when_quoted_escalation_path_missing(tmp_path, monkeypatch):
    """Compare-path-forms probe — quoted emission must still refuse a missing shipped resource."""
    import round_driver as RD
    plugin_with_space = os.path.join(str(tmp_path), "plugin root")
    missing = os.path.join(plugin_with_space, "lib", "escalation_resolve.py")
    monkeypatch.setattr(RD, "_shipped_escalation_wrapper_path", lambda: missing)
    ph = {"ESCALATION_WRAPPER_PATH": shlex.quote(missing), "RUBRIC_PATH": _PLUGIN_RUBRIC}
    monkeypatch.setattr(RD, "_shipped_rubric_path", lambda: _PLUGIN_RUBRIC)
    reason = RD._shipped_resource_refusal(ph)
    assert reason == "shipped-resource-missing:ESCALATION_WRAPPER_PATH"


def test_shipped_resource_refusal_when_quoted_escalation_path_present(tmp_path, monkeypatch):
    import round_driver as RD
    plugin_with_space = os.path.join(str(tmp_path), "plugin root")
    present = os.path.join(plugin_with_space, "lib", "escalation_resolve.py")
    os.makedirs(os.path.dirname(present), exist_ok=True)
    with open(present, "w", encoding="utf-8") as fh:
        fh.write("# probe\n")
    monkeypatch.setattr(RD, "_shipped_escalation_wrapper_path", lambda: present)
    ph = {"ESCALATION_WRAPPER_PATH": shlex.quote(present), "RUBRIC_PATH": _PLUGIN_RUBRIC}
    monkeypatch.setattr(RD, "_shipped_rubric_path", lambda: _PLUGIN_RUBRIC)
    assert RD._shipped_resource_refusal(ph) is None


# --- FB-6: seat transport from seat_map compose (detector 1) -------------------


def test_seat_transport_classifies_vendors_from_compose_output():
    """Engine seats (codex/cursor) → stdout; host seat (claude) → file — off SM.build()."""
    import round_driver as RD
    import seat_map as SM

    composed = SM.build(
        roster=("code-reviewer", "security-reviewer", "architecture-reviewer"),
        live_vendors=["codex", "cursor", "claude"],
        author_family="anthropic",
        narrative_family="openai",
        seed=723,
        pins={
            "code-reviewer": {"vendor": "codex"},
            "security-reviewer": {"vendor": "cursor"},
            "architecture-reviewer": {"vendor": "claude"},
        },
    )
    state = {"seatMap": {"seats": composed["seats"]}, "config": {"repoRoot": _REPO}}
    expectations = {
        "code-reviewer": ("stdout", True),
        "security-reviewer": ("stdout", True),
        "architecture-reviewer": ("file", False),
    }
    for seat, (want_channel, want_engine) in expectations.items():
        seat_cfg = composed["seats"][seat]
        assert isinstance(seat_cfg.get("vendor"), str) and seat_cfg["vendor"], (
            "composed seat %r missing vendor — seat_map schema drift" % seat)
        row = RD._seat_transport_row(state, RP.P_PANEL, seat, 0, state["config"], {}, _REPO)
        assert row["vendor"] == seat_cfg["vendor"]
        is_engine = RD._seat_is_engine(row)
        assert is_engine is want_engine, "%s: vendor=%r" % (seat, row["vendor"])
        channel = "stdout" if is_engine else "file"
        assert channel == want_channel


def test_seat_transport_vendor_absent_is_not_engine():
    import round_driver as RD

    row = RD._seat_transport_row({"seatMap": {"seats": {}}}, RP.P_PANEL, "missing", 0,
                                 {}, {}, _REPO)
    assert not RD._seat_is_engine(row)
    assert not RD._seat_is_engine({"vendor": None, "model": "m", "engine": None})


def test_seat_transport_unknown_vendor_refuses_order_render():
    import round_driver as RD

    session_dir = os.path.join(_SESSION, "probe-unknown-vendor")
    state = {
        "config": {"repoRoot": _REPO, "fixerVendor": "gemini"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "seatMap": {"seats": {}},
    }
    try:
        RD._build_order_render_context(session_dir, state, 2, RP.P_FIXER, 0, "fixer", 0, {})
    except ValueError as exc:
        assert "order-render-refused" in str(exc)
        assert "unknown-vendor:fixer:gemini" in str(exc)
    else:
        raise AssertionError("expected order-render-refused for unknown fixer vendor")


def test_fixer_order_shell_paths_are_quoted_for_metacharacters(tmp_path):
    import round_driver as RD

    repo = str(tmp_path / "proj$(echo pwned)")
    os.makedirs(repo)
    session_dir = os.path.join(str(tmp_path), "session")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": repo, "fixerVendor": "claude"},
        "reviewedDiff": "diff --git a/f b/f\n",
    }
    paths = {
        "storage_key": "fixer.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths,
    )
    ctx = _base_context(
        host_seat=True,
        landing_path=paths["bare_payload_path"],
        repo_root=repo,
        placeholders=ph,
    )
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None
    assert "$(echo pwned)" in text
    assert shlex.quote(repo) in text


def test_engine_panel_landing_block_uses_phase_stdout_contract():
    ctx = _base_context(
        host_seat=False,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.json"),
        placeholders=_panel_placeholders(channel="stdout"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert '{"findings": [...], "investigated": [...]}' in text
    assert "Delivery section above" in text


# --- FX-4A: core path drift guard ------------------------------------------------


def test_in_repo_core_path_matches_resolve_order_residuals_home(tmp_path, monkeypatch):
    """resolve_order_residuals must derive in-repo core layout from core_md — never hand-typed."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)

    def fake_resolve_base(repo_root, base_oid, core_rel_path):
        assert core_rel_path == CM.in_repo_core_rel_path()
        return "probe residual", None

    monkeypatch.setattr(RO, "resolve_base_residuals", fake_resolve_base)
    import mode_registry as mr
    monkeypatch.setattr(mr, "resolve", lambda _cwd: {"mode": mr.IN_REPO})
    text, prov, failure = RO.resolve_order_residuals(repo, "abc123")
    assert failure is None
    assert text == "probe residual"
    assert CM.in_repo_core_rel_path() == os.path.join(".claude", "superheroes", "core.md")


# --- FX-4A: order-render-refused wiring ----------------------------------------


def test_next_surfaces_order_render_refused(tmp_path, monkeypatch):
    import round_driver as RD

    def refuse_placeholders(*_a, **_k):
        raise ValueError("order-render-refused:probe-seat:probe-reason")

    monkeypatch.setattr(RD, "_order_placeholders", refuse_placeholders)
    d = str(tmp_path / "s")
    os.makedirs(d)
    cfg = {"leg": "code", "vendors": ["claude"], "diff": "diff --git a/f b/f\n", "fixerVendor": "claude"}
    out = RD.cmd_next(d, cfg)
    assert out["ok"] is False
    assert out["reason"] == "order-render-refused"
    assert "probe-reason" in out.get("detail", "")


# --- FX-4A: unmatched verifier cluster -----------------------------------------


def test_unmatched_verifier_cluster_refuses_render():
    import round_driver as RD

    session_dir = os.path.join(_SESSION, "probe")
    state = {"config": {"repoRoot": _REPO}, "reviewedDiff": "", "seatMap": {"seats": {}}}
    paths = {"storage_key": "verifier:missing.a0"}
    try:
        RD._order_placeholders(
            RP.P_VERIFIERS, "verifier:missing", 0, state, state["config"],
            {"clusters": [{"key": "other:0", "findings": []}]},
            session_dir, 2, paths)
    except ValueError as exc:
        assert "unmatched-verifier-cluster:missing" in str(exc)
    else:
        raise AssertionError("expected ValueError for unmatched verifier cluster")


# --- FX-4A: panel dimension rubric label ---------------------------------------


def test_panel_order_dimension_uses_rubric_label(tmp_path):
    import round_driver as RD

    session_dir = os.path.join(str(tmp_path), "s")
    os.makedirs(session_dir)
    state = {"config": {"repoRoot": str(tmp_path)}, "reviewedDiff": "", "seatMap": {"seats": {}}}
    paths = {"storage_key": "code-reviewer.a0"}
    ph = RD._order_placeholders(
        RP.P_PANEL, "code-reviewer", 0, state, state["config"], {},
        session_dir, 2, paths)
    assert ph["DIMENSION"] == "Code"
    ph_sec = RD._order_placeholders(
        RP.P_PANEL, "premortem-reviewer", 0, state, state["config"], {},
        session_dir, 2, paths)
    assert ph_sec["DIMENSION"] == "Failure-Mode"


# --- FX-4A: PR checkout two-arm clause coverage --------------------------------


def test_panel_order_without_pr_checkout_omits_checkout_clause():
    text, reason = RO.render_order(
        RP.P_PANEL, "code-reviewer", _base_context(placeholders=_panel_placeholders()))
    assert reason is None
    assert "PR branch checkout" not in text
    assert "ONLY source of truth for verifying code" not in text


def test_panel_order_with_pr_checkout_includes_checkout_clause():
    text, reason = RO.render_order(
        RP.P_PANEL, "code-reviewer",
        _base_context(placeholders=_panel_placeholders(pr_checkout=True)))
    assert reason is None
    assert "PR branch checkout:" in text
    assert "ONLY source of truth for verifying code" in text


def test_golden_render_with_pr_checkout_matches_fixture():
    golden_path = os.path.join(_GOLDEN_DIR, "dispatch-panel-with-checkout.txt")
    ctx = _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.payload.json"),
        placeholders=_panel_placeholders(pr_checkout=True),
    )
    text, reason = RO.render_order(RP.P_PANEL, "golden-seat", ctx)
    assert reason is None
    with open(golden_path, encoding="utf-8") as fh:
        expected = fh.read()
    assert _normalize_golden_machine_paths(text) == _normalize_golden_machine_paths(expected)


# --- FX-4A: engine landing stdout channel --------------------------------------


_FILE_CHANNEL_MARKERS = (
    "Write candidate records to",
    "Write your groups to",
    "Write a JSON array to this cluster",
    "Write the JSON array to",
)


@pytest.mark.parametrize("phase,ph_fn", [
    (RP.P_PANEL, lambda: _panel_placeholders(channel="stdout")),
    (RP.P_VERIFIERS, lambda: _verifier_placeholders(channel="stdout")),
    (RP.P_SYNTHESIS, lambda: _synthesis_placeholders(channel="stdout")),
    (RP.P_GAPSWEEP, lambda: _gapsweep_placeholders(channel="stdout")),
    (RP.P_SCOPED, lambda: _scoped_placeholders(channel="stdout")),
])
def test_engine_order_template_body_has_no_file_channel_delivery(phase, ph_fn):
    ctx = _base_context(host_seat=False, placeholders=ph_fn())
    text, reason = RO.render_order(phase, "seat", ctx)
    assert reason is None
    body = text.split("## Ratified residuals")[0]
    for marker in _FILE_CHANNEL_MARKERS:
        assert marker not in body, "%s still instructs file-channel delivery: %r" % (phase, marker)


def test_engine_order_landing_block_uses_stdout_not_file_write():
    ctx = _base_context(
        host_seat=False,
        placeholders=_panel_placeholders(channel="stdout"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert "stdout channel" in text
    assert "Landing path:" not in text
    assert "Envelope stub:" not in text


def test_host_order_landing_block_uses_payload_file():
    ctx = _base_context(
        host_seat=True,
        landing_path=os.path.join(_SESSION, "round-2", "landing", "dispatch-panel",
                                  "code-reviewer.a0.payload.json"),
        placeholders=_panel_placeholders(channel="file"),
    )
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", ctx)
    assert reason is None
    assert "Payload landing path:" in text
    assert "stdout channel" not in text.split("## Return your result")[1]


# --- FB-7: unresolvable calibration root vs resolved-empty order text ----------------


def _fb7_panel_order_placeholders(repo_root, monkeypatch, resolve_impl):
    import calibration_resolve as cr
    import round_driver as RD
    import round_phases as RP

    monkeypatch.setattr(cr, "resolve", resolve_impl)
    session_dir = os.path.join(repo_root, ".session")
    os.makedirs(session_dir, exist_ok=True)
    state = {"config": {"repoRoot": repo_root}, "reviewedDiff": ""}
    paths = {
        "storage_key": "code-reviewer.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env-landing.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }
    return RD._order_placeholders(
        RP.P_PANEL, "code-reviewer", 0, state, state["config"], {},
        session_dir, 1, paths,
    )


def test_order_calibration_unresolvable_root_differs_from_resolved_empty(tmp_path, monkeypatch):
    import calibration_resolve as cr

    repo = str(tmp_path / "repo")
    os.makedirs(repo)

    def resolve_empty(_cwd, **kwargs):
        return {"dispatch_core": None, "dispatch_layer": None}

    empty_ph = _fb7_panel_order_placeholders(repo, monkeypatch, resolve_empty)
    assert empty_ph["CORE_PATH"] == _CORE_UNRESOLVED
    assert empty_ph["LAYER_PATH"] == _LAYER_UNRESOLVED

    def resolve_unresolvable(_cwd, **kwargs):
        raise cr.UnresolvableRootError(
            str(tmp_path / "bad-store"), repo, "review-crew", "global", "/layer.md")

    unres_ph = _fb7_panel_order_placeholders(repo, monkeypatch, resolve_unresolvable)
    assert cr.REASON_UNRESOLVABLE_ROOT in unres_ph["CORE_PATH"]
    assert cr.REASON_UNRESOLVABLE_ROOT in unres_ph["LAYER_PATH"]
    assert "calibration refused" in unres_ph["CORE_PATH"]
    assert "not resolved for this project" not in unres_ph["CORE_PATH"]
    assert unres_ph["CORE_PATH"] != empty_ph["CORE_PATH"]
    assert unres_ph["LAYER_PATH"] != empty_ph["LAYER_PATH"]


def test_order_calibration_unresolvable_root_renders_distinct_panel_text(tmp_path, monkeypatch):
    import calibration_resolve as cr
    import round_driver as RD
    import round_phases as RP

    repo = str(tmp_path / "repo")
    os.makedirs(repo)

    def resolve_unresolvable(_cwd, **kwargs):
        raise cr.UnresolvableRootError(
            str(tmp_path / "bad-store"), repo, "review-crew", "global", "/layer.md")

    ph = _fb7_panel_order_placeholders(repo, monkeypatch, resolve_unresolvable)
    text, reason = RO.render_order(
        RP.P_PANEL, "code-reviewer", _base_context(placeholders=ph))
    assert reason is None
    assert cr.REASON_UNRESOLVABLE_ROOT in text
    assert _CORE_UNRESOLVED not in text
