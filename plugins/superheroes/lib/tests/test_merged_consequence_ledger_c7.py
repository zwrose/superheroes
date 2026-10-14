"""C7 — synthesis carries a merged consequence onto the ledger row; compile drops a non-string file."""
import importlib.util
import os

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
V = _load("verification")


def _finding(title, severity, kind, consequence):
    return {"file": "f.py", "line": 1, "title": title, "severity": severity,
            "verdict": "PLAUSIBLE", "consequence": consequence, "consequenceKind": kind}


def test_synthesis_syncs_merged_consequence_to_ledger_row_and_survives_reseed():
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    rep = _finding("Quality rep", "Important", "code-quality", "harder to maintain")
    member = _finding("Real member", "Minor", "real", "users lose saved work")
    rep["line"], member["line"] = 1, 2
    RD._stage_findings(state, [rep, member])
    staged = V.stage_ids(state["_toVerify"])
    state["_verified"] = staged
    ids = [f["id"] for f in staged]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g", "member_ids": ids}]})
    live = state["findings"][0]
    key = RD._finding_identity_key(live)
    ledger = state["dispositionLedger"]
    row = ledger[RD._ledger_index_by_key(ledger)[key]]
    assert live["consequenceKind"] == "real"
    assert row["consequenceKind"] == "real"
    assert "users lose saved work" in row["consequence"]
    seen = RD._ledger_index_by_key(ledger)
    reraised = dict(rep)
    entry = RD._seed_ledger_entry(state, ledger, seen, reraised, key, 2)
    assert entry["consequenceKind"] == "real"


def test_compile_drops_list_valued_file_without_raising():
    diff = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
    bad = {"file": ["f.py"], "line": 1, "title": "t", "severity": "Important",
           "consequence": "lost work", "consequenceKind": "real"}
    good = dict(bad, file="f.py", title="ok")
    compiled, drops = RD.mechanical_compile([bad, good], diff)
    assert [f["title"] for f in compiled] == ["ok"]
    assert len(drops) == 1
