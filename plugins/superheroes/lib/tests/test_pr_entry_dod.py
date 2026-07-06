# plugins/superheroes/lib/tests/test_pr_entry_dod.py
"""End-to-end proof of the ship-phase honesty wiring in pr_entry (issue #228):
  - mark-ready PARKS (never flips ready) when a DoD bullet is unaddressed, naming the bullet;
  - a spec-less quick route is not-applicable and passes the DoD gate;
  - draft seeding writes the DoD table + generated Stubbed-seams section into the PR body.
"""
import json
import types

import dod_gate
import pr_body
import pr_entry

SPEC = """---
superheroes: doc
---
## Definition of done / success

- **Live run.** the marked live one-shot passes.
- **Reshape.** the #112 reshape landed.
"""
B_LIVE = "**Live run.** the marked live one-shot passes."
B_RESHAPE = "**Reshape.** the #112 reshape landed."


def _fake_run(stdout="deadbeef\n", rc=0):
    def _run(*a, **k):
        return types.SimpleNamespace(returncode=rc, stdout=stdout, stderr="")
    return _run


def _drive_mark_ready(monkeypatch, capsys, *, spec, body):
    monkeypatch.setattr(pr_entry, "_gh_pr",
                        lambda branch: {"number": 7, "isDraft": True, "url": "u", "state": "OPEN"})
    monkeypatch.setattr(pr_entry, "_spec_lookup", lambda root, wi: (spec is not None, spec))
    monkeypatch.setattr(pr_entry, "_gh_pr_body", lambda n: body)
    monkeypatch.setattr(pr_entry.subprocess, "run", _fake_run())
    monkeypatch.setattr(pr_entry.pr_phase, "mark_ready_status_action", lambda r: {"action": "proceed"})
    monkeypatch.setattr(pr_entry.test_pilot_status, "status_path", lambda root, wi: "x")
    monkeypatch.setattr(pr_entry.test_pilot_status, "assert_current", lambda p, h: {"ok": True})
    # if the gate passes, flipping is a no-op success (we only assert on the gate here)
    monkeypatch.setattr(pr_entry.idempotent_write, "idempotent_apply",
                        lambda key, r, a: {"ok": True, "reason": "flipped"})
    try:
        pr_entry.main(["--step", "mark-ready", "--work-item", "wi"])
    except SystemExit:
        pass
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_mark_ready_parks_with_bullet_named_when_unaddressed(monkeypatch, capsys):
    # a table that disposes only the first bullet — the reshape bullet is unaddressed
    body = pr_body.compose_body("PR intro", pr_body.seed_dod_block([B_LIVE, B_RESHAPE]), "")
    # fill only the live-run row's disposition
    body = body.replace("| %s |  |  |" % dod_gate.cellsafe(B_LIVE),
                        "| %s | done | test_live.py::test_oneshot |" % dod_gate.cellsafe(B_LIVE))
    out = _drive_mark_ready(monkeypatch, capsys, spec=SPEC, body=body)
    assert out["ok"] is False
    assert "DoD gate" in out["reason"]
    assert "Reshape" in out["reason"]


def test_mark_ready_dod_park_carries_machine_gate_field(monkeypatch, capsys):
    # The bundle's filler leg (issue #228 "build/ship legs fill it", 0.10.0 qualification)
    # keys on gate == "dod" + the pr number — machine fields, never the reason string
    # (CONVENTIONS §11: dod_gate owns the wording; this field is the cross-boundary contract).
    import dod_gate as _dg
    body = _dg.seed_table_stub([B_LIVE, B_RESHAPE]) if hasattr(_dg, "seed_table_stub") else (
        _dg.TABLE_MARKER + "\n\n| Bullet | Disposition | Evidence / issue |\n|---|---|---|\n"
        + "".join("| %s |  |  |\n" % _dg.cellsafe(b) for b in (B_LIVE, B_RESHAPE)))
    out = _drive_mark_ready(monkeypatch, capsys, spec=SPEC, body=body)  # blank rows -> dod park
    assert out["ok"] is False and out.get("gate") == "dod"
    assert out.get("pr") == 7


def test_mark_ready_parks_when_no_table(monkeypatch, capsys):
    out = _drive_mark_ready(monkeypatch, capsys, spec=SPEC, body="a body with no disposition table")
    assert out["ok"] is False and "DoD gate" in out["reason"]


def test_mark_ready_passes_dod_gate_on_quick_route(monkeypatch, capsys):
    # spec-less (quick route) -> not-applicable -> gate does not park; the flip proceeds
    out = _drive_mark_ready(monkeypatch, capsys, spec=None, body="whatever")
    assert "DoD gate" not in out.get("reason", "")


def test_mark_ready_passes_when_all_disposed(monkeypatch, capsys):
    body = pr_body.compose_body("intro", pr_body.seed_dod_block([B_LIVE, B_RESHAPE]), "")
    body = body.replace("| %s |  |  |" % dod_gate.cellsafe(B_LIVE),
                        "| %s | done | test_live.py |" % dod_gate.cellsafe(B_LIVE))
    body = body.replace("| %s |  |  |" % dod_gate.cellsafe(B_RESHAPE),
                        "| %s | deferred | #231 reshape tracked separately |" % dod_gate.cellsafe(B_RESHAPE))
    out = _drive_mark_ready(monkeypatch, capsys, spec=SPEC, body=body)
    assert "DoD gate" not in out.get("reason", "")


def test_draft_seed_writes_table_and_stub_section(monkeypatch):
    captured = {}
    monkeypatch.setattr(pr_entry, "_spec_lookup", lambda root, wi: (True, SPEC))
    monkeypatch.setattr(pr_entry, "_branch_diff",
                        lambda branch, base, root:
                        "+++ b/acceptance_launch.py\n+x = 0  # STUB(#231): spend ceiling inert\n")
    monkeypatch.setattr(pr_entry, "_gh_pr_body", lambda n: "first commit body")
    monkeypatch.setattr(pr_entry, "_gh_edit_body", lambda n, body: captured.update(n=n, body=body))

    pr_entry._seed_pr_body("/root", "wi", "branch", "main", 7)

    body = captured["body"]
    assert captured["n"] == 7
    assert dod_gate.TABLE_MARKER in body
    assert dod_gate.cellsafe(B_LIVE) in body and dod_gate.cellsafe(B_RESHAPE) in body
    assert pr_body.STUBS_MARKER in body
    assert "- `acceptance_launch.py` — spend ceiling inert (#231)" in body
    # the freshly seeded (blank) table must itself park the gate — nothing disposed yet
    assert dod_gate.decide([B_LIVE, B_RESHAPE], body, spec_present=True)["verdict"] == "park"


def test_draft_seed_skips_when_nothing_to_add(monkeypatch):
    called = {"edit": False}
    monkeypatch.setattr(pr_entry, "_spec_lookup", lambda root, wi: (False, None))  # quick route, no spec
    monkeypatch.setattr(pr_entry, "_branch_diff", lambda branch, base, root: "no markers here\n")
    monkeypatch.setattr(pr_entry, "_gh_edit_body", lambda n, body: called.update(edit=True))
    pr_entry._seed_pr_body("/root", "wi", "branch", "main", 7)
    assert called["edit"] is False  # no DoD bullets and no stubs -> no body edit
