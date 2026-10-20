# plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py
"""Item 10, Risk and trust (#1712): one item, two halves with one home each, and its view."""
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CV = _load("configure_view")
PC = _load("project_config")
CM = _load("core_md")
MR = _load("mode_registry")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

PAYMENTS = {
    "name": "Payments",
    "covers": ["src/payments/*"],
    "why": "Charges customers.",
    "undo": "Hard: a charge needs a refund.",
}
CUSTOMER_DATA = {
    "name": "Customer data",
    "covers": ["src/db/*.sql", "migrations/*"],
    "why": "Holds personal details.",
    "undo": "Hard: a leak cannot be taken back.",
}
FIVE_KINDS = [
    {"name": "Money", "covers": ["src/billing/*"], "why": "Moves funds.",
     "undo": "Hard: a transfer needs a refund."},
    {"name": "Customer data", "covers": ["src/db/*"], "why": "Holds personal details.",
     "undo": "Hard: a leak cannot be taken back."},
    {"name": "Safety", "covers": ["firmware/*"], "why": "Drives a pump.",
     "undo": "Hard: harm to a person is not reversible."},
    {"name": "Access", "covers": ["src/auth/*"], "why": "Decides who gets in.",
     "undo": "Moderate: rotate keys and sessions."},
    {"name": "Irreversible action", "covers": ["scripts/purge_*.py"], "why": "Deletes records.",
     "undo": "Hard: no backup holds them."},
]


def _init_repo(d):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(d), "remote", "add", "origin", "git@github.com:o/r.git"],
                   check=True)


def _setup_repo(tmp_path, *, threat="single-user", core=True):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    if core:
        facts = dict(_CORE_FACTS, threatModel=threat)
        CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    return repo, store


def _write_raw_core(repo, schema):
    block = {"schemaVersion": schema, "verifyCommand": "npm test", "stackTags": ["node"]}
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=confirmed created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n" % (schema, json.dumps(block, indent=2))
    )
    with open(os.path.join(d, "core.md"), "w", encoding="utf-8") as fh:
        fh.write(text)


def _core_text(repo, store):
    with open(CM.core_path(repo, store), "rb") as fh:
        return fh.read().decode("utf-8")


def _threat_section_bytes(text):
    start = text.index("## Threat model")
    return text[start:text.index("## Canonical patterns")].encode("utf-8")


# --- the registry and the read contract -----------------------------------------------------


def test_item_ten_is_risk_and_trust_and_the_old_slug_is_gone():
    item = next(entry for entry in PC.ITEMS if entry["number"] == 10)
    assert item["slug"] == "riskAndTrust" and item["name"] == "Risk and trust"
    assert item["home"] == PC.HOME_RISK_AND_TRUST == "riskAndTrust"
    assert not hasattr(PC, "HOME_THREAT_MODEL")
    assert len(PC.ITEMS) == 17
    assert "threatModel" not in [entry["slug"] for entry in PC.ITEMS]


def test_old_threat_model_slug_is_unknown_for_get_and_set(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert PC.get_item(repo, "threatModel", root=store) == {
        "action": "refused", "reason": PC.REASON_UNKNOWN_SLUG}
    assert PC.set_item(repo, "threatModel", "multi-tenant", root=store) == {
        "action": "refused", "reason": PC.REASON_UNKNOWN_SLUG}
    assert "single-user" in _core_text(repo, store)


def test_item_with_a_threat_model_and_two_areas_reads_back_each_area(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="Outsiders only.")
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, CUSTOMER_DATA]}, root=store)
    assert res["action"] == "written"
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"] == {"threatModel": "Outsiders only.", "riskAreas": [PAYMENTS, CUSTOMER_DATA]}
    assert got["effective"] == got["raw"]
    assert got["source"] == "stamped" and got["malformed"] is False
    for stored, given in zip(got["effective"]["riskAreas"], [PAYMENTS, CUSTOMER_DATA]):
        assert stored["covers"] == given["covers"]
        assert stored["why"] == given["why"]
        assert stored["undo"] == given["undo"]


def test_unset_item_reads_empty_halves(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="")
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"] == {"threatModel": None, "riskAreas": None}
    assert got["effective"] == {"threatModel": None, "riskAreas": []}
    assert got["source"] == "unset" and got["malformed"] is False


def test_profile_absent_reads_unset_and_refuses_a_set(tmp_path):
    repo, store = _setup_repo(tmp_path, core=False)
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"] == {"threatModel": None, "riskAreas": None}
    assert got["effective"] == {"threatModel": None, "riskAreas": []}
    assert got["source"] == "unset"
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res == {"action": "refused", "reason": PC.REASON_PROFILE_ABSENT}


def test_malformed_stored_areas_read_malformed_with_no_effective_list(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, [{"name": "Payments"}], root=store)
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["malformed"] is True
    assert got["effective"]["riskAreas"] is None
    assert got["effective"]["threatModel"] == "single-user"
    assert got["raw"]["riskAreas"] == [{"name": "Payments"}]


def test_behind_profile_reads_and_a_set_answers_behind(tmp_path):
    repo, store = _setup_repo(tmp_path, core=False)
    _write_raw_core(repo, CM.SCHEMA_VERSION + 1)
    assert PC.get_item(repo, "riskAndTrust", root=store)["behind"] is True
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res["action"] == "behind"
    assert "riskAreas" not in _core_text(repo, store)


# --- what a set accepts ---------------------------------------------------------------------


def test_one_area_each_for_money_data_safety_access_and_an_irreversible_action(tmp_path):
    repo, store = _setup_repo(tmp_path)
    for area in FIVE_KINDS:
        assert PC.validate_item_value(PC._SLUG_INDEX["riskAndTrust"], {"riskAreas": [area]}) is None
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": FIVE_KINDS}, root=store)
    assert res["action"] == "written"
    assert PC.get_item(repo, "riskAndTrust", root=store)["effective"]["riskAreas"] == FIVE_KINDS


@pytest.mark.parametrize("value", [
    {"threatModel": "x", "riskAreas": [PAYMENTS]},
    {},
    {"owner": "finance"},
    {"threatModel": "x", "owner": "finance"},
    {"riskAreas": [PAYMENTS], "owner": "finance"},
    "multi-tenant",
    None,
    [PAYMENTS],
    {"threatModel": ""},
    {"threatModel": "   "},
    {"threatModel": 3},
    {"threatModel": "intro\n## Heading\nmore"},
    {"riskAreas": "payments"},
    {"riskAreas": [{"name": "Payments"}]},
    {"riskAreas": [PAYMENTS, dict(PAYMENTS, name=" payments ")]},
])
def test_set_refuses_a_value_that_is_not_exactly_one_valid_half(tmp_path, value):
    repo, store = _setup_repo(tmp_path)
    before = _core_text(repo, store)
    res = PC.set_item(repo, "riskAndTrust", value, root=store)
    assert res == {"action": "refused", "reason": PC.REASON_MALFORMED_VALUE}
    assert _core_text(repo, store) == before


# --- the two halves each have one home ------------------------------------------------------


def test_set_risk_areas_writes_once_then_noops_and_leaves_the_threat_model_bytes(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before = _core_text(repo, store)
    section_before = CM._section(before, "Threat model")
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res["action"] == "written"
    after = _core_text(repo, store)
    assert CM._section(after, "Threat model") == section_before == "single-user"
    assert _threat_section_bytes(after) == _threat_section_bytes(before)
    block = json.loads(CM._JSON_BLOCK.search(after).group(1))
    assert block["projectConfiguration"]["riskAreas"] == [PAYMENTS]
    assert set(block) == set(json.loads(CM._JSON_BLOCK.search(before).group(1))) | {
        "projectConfiguration"}
    assert block["schemaVersion"] == CM.SCHEMA_VERSION
    again = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert again["action"] == "noop"
    assert _core_text(repo, store) == after


def test_set_threat_model_leaves_the_risk_areas_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, CUSTOMER_DATA]}, root=store)
    before_block = json.loads(CM._JSON_BLOCK.search(_core_text(repo, store)).group(1))
    res = PC.set_item(repo, "riskAndTrust", {"threatModel": "multi-tenant"}, root=store)
    assert res["action"] == "written"
    after = _core_text(repo, store)
    assert json.loads(CM._JSON_BLOCK.search(after).group(1)) == before_block
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"] == {"threatModel": "multi-tenant", "riskAreas": [PAYMENTS, CUSTOMER_DATA]}
    assert PC.set_item(repo, "riskAndTrust", {"threatModel": "multi-tenant"}, root=store)[
        "action"] == "noop"


def test_threat_model_is_stored_stripped_so_the_read_back_compares_the_stripped_text(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.set_item(repo, "riskAndTrust", {"threatModel": "\n  multi-tenant  \n\n"}, root=store)
    assert res["action"] == "written"
    assert PC.get_item(repo, "riskAndTrust", root=store)["raw"]["threatModel"] == "multi-tenant"
    assert CM.read(repo, root=store)["threatModel"] == "multi-tenant"


def test_set_whose_stored_half_reads_back_different_is_a_mismatch(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(PC.core_md, "write_project_config_item",
                        lambda *args, **kwargs: {"action": "written"})
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res["action"] == "refused" and res["reason"] == PC.REASON_SET_MISMATCH
    assert res["expected"] == {"riskAreas": [PAYMENTS]}
    assert res["observed"] == {"riskAreas": None}


def test_set_that_changes_the_other_half_is_a_mismatch_naming_that_half(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    real = PC.core_md.write_project_config_item

    def writes_and_also_moves_the_threat_model(*args, **kwargs):
        out = real(*args, **kwargs)
        PC.core_md.write_threat_model(repo, "changed behind the setter's back", root=store)
        return out

    monkeypatch.setattr(PC.core_md, "write_project_config_item",
                        writes_and_also_moves_the_threat_model)
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res["action"] == "refused" and res["reason"] == PC.REASON_SET_MISMATCH
    assert res["expected"] == {"threatModel": "single-user"}
    assert res["observed"] == {"threatModel": "changed behind the setter's back"}


def test_threat_model_set_still_works_while_the_stored_areas_are_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, "not a list", root=store)
    res = PC.set_item(repo, "riskAndTrust", {"threatModel": "multi-tenant"}, root=store)
    assert res["action"] == "written"
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"]["riskAreas"] == "not a list" and got["malformed"] is True


def test_other_items_share_the_project_configuration_with_the_risk_areas(tmp_path):
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    PC.set_item(repo, "digestFloor", "weekly", root=store)
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, CUSTOMER_DATA]}, root=store)
    mapping = CM.read(repo, root=store)["projectConfiguration"]
    assert mapping["digestFloor"] == "weekly"
    assert mapping["riskAreas"] == [PAYMENTS, CUSTOMER_DATA]


# --- the command line the prose uses --------------------------------------------------------


def test_cli_get_and_set_item_risk_and_trust(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    payload = json.dumps({"riskAreas": [PAYMENTS]})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload + "\n"))
    assert PC.main(["set", "--item", "riskAndTrust", "--cwd", repo, "--root", store]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"
    assert PC.main(["get", "--item", "riskAndTrust", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["slug"] == "riskAndTrust"
    assert out["raw"] == {"threatModel": "single-user", "riskAreas": [PAYMENTS]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"threatModel": "multi-tenant"})))
    assert PC.main(["set", "--item", "riskAndTrust", "--cwd", repo, "--root", store]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"


# --- the view -------------------------------------------------------------------------------


def _screen_lines(screen):
    return screen.splitlines()


def test_view_shows_the_threat_model_and_each_risk_area(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="Outsiders only.")
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, CUSTOMER_DATA]}, root=store)
    lines = _screen_lines(CV.render(repo, root=store))
    start = lines.index("### Risk and trust")
    assert lines[start + 1] == "What we defend against:"
    assert lines[start + 2] == "Outsiders only."
    assert lines[start + 3] == "Risk areas:"
    assert lines[start + 4] == (
        "- Payments: Charges customers. Undo: Hard: a charge needs a refund. "
        "Covers: src/payments/*")
    assert lines[start + 5] == (
        "- Customer data: Holds personal details. Undo: Hard: a leak cannot be taken back. "
        "Covers: src/db/*.sql, migrations/*")
    assert "### Threat model" not in lines


def test_view_with_no_areas_says_none_set(tmp_path):
    repo, store = _setup_repo(tmp_path)
    lines = _screen_lines(CV.render(repo, root=store))
    start = lines.index("### Risk and trust")
    assert lines[start + 3:start + 5] == ["Risk areas:", "(none set)"]
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, [], root=store)
    lines = _screen_lines(CV.render(repo, root=store))
    start = lines.index("### Risk and trust")
    assert lines[start + 3:start + 5] == ["Risk areas:", "(none set)"]


def test_view_with_a_threat_model_missing_says_none(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="")
    lines = _screen_lines(CV.render(repo, root=store))
    start = lines.index("### Risk and trust")
    assert lines[start + 1:start + 3] == ["What we defend against:", "(none)"]


def test_view_with_malformed_areas_shows_the_unreadable_line(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, [{"name": "Payments"}], root=store)
    lines = _screen_lines(CV.render(repo, root=store))
    start = lines.index("### Risk and trust")
    assert lines[start + 4] == (
        "(unreadable — risk-areas-malformed; the review treats the risk areas as not set)")


def test_view_without_a_core_prints_no_risk_and_trust_block(tmp_path):
    repo, store = _setup_repo(tmp_path, core=False)
    screen = CV.render(repo, root=store)
    assert "(no core calibration yet)" in screen
    assert "### Risk and trust" not in screen


def _item_ten_row(screen):
    rows = [line for line in screen.splitlines() if line.startswith("10. ")]
    assert len(rows) == 1
    return rows[0]


def test_item_ten_row_reads_risk_and_trust_with_the_threat_model_and_area_count(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="")
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — unset — threat model not set; 0 risk areas")
    PC.set_item(repo, "riskAndTrust", {"threatModel": "Outsiders only."}, root=store)
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — threat model set; 1 risk area")
    PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, CUSTOMER_DATA]}, root=store)
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — threat model set; 2 risk areas")


def test_item_ten_row_flags_unreadable_areas_on_one_line(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, [{"name": "Payments"}], root=store)
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — threat model set; risk areas unreadable")


# --- the one canonical read: item 10's areas half agrees with core_md.read_risk_areas -------------


def _write_project_configuration(repo, store, value):
    path = CM.core_path(repo, store)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    match = CM._JSON_BLOCK.search(text)
    block = json.loads(match.group(1))
    block["projectConfiguration"] = value
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text[:match.start(1)] + json.dumps(block, indent=2) + text[match.end(1):])


def test_stored_null_areas_read_malformed_with_no_effective_list(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_project_configuration(repo, store, {"riskAreas": None})
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["malformed"] is True
    assert got["raw"]["riskAreas"] is None
    assert got["effective"]["riskAreas"] is None
    assert "risk areas unreadable" in _item_ten_row(CV.render(repo, root=store))


def test_string_areas_read_malformed_with_no_effective_list(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_project_configuration(repo, store, {"riskAreas": "payments"})
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["malformed"] is True
    assert got["raw"]["riskAreas"] == "payments"
    assert got["effective"]["riskAreas"] is None
    assert "risk areas unreadable" in _item_ten_row(CV.render(repo, root=store))


def test_project_configuration_that_is_a_list_reads_malformed_with_no_effective_list(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_project_configuration(repo, store, ["riskAreas"])
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["malformed"] is True
    assert got["raw"]["riskAreas"] is None
    assert got["effective"]["riskAreas"] is None
    assert "risk areas unreadable" in _item_ten_row(CV.render(repo, root=store))


def test_absent_areas_key_reads_an_unset_row(tmp_path):
    repo, store = _setup_repo(tmp_path, threat="")
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"]["riskAreas"] is None and got["effective"]["riskAreas"] == []
    assert got["malformed"] is False
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — unset — threat model not set; 0 risk areas")


def test_absent_core_reads_an_unset_row(tmp_path):
    repo, store = _setup_repo(tmp_path, core=False)
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["effective"]["riskAreas"] == [] and got["malformed"] is False
    assert _item_ten_row(CV.render(repo, root=store)) == (
        "10. Risk and trust — unset — threat model not set; 0 risk areas")


def test_valid_empty_list_reads_empty_and_not_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, [], root=store)
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"]["riskAreas"] == [] and got["effective"]["riskAreas"] == []
    assert got["malformed"] is False


# --- the setup sitting, driven end to end --------------------------------------------------


_REFERENCE = os.path.join(_REPO_ROOT, "plugins/superheroes/skills/configure/reference")


def _menu_routing():
    """Read the 'Set up Risk and trust' action in view-and-tune.md and return (run, skipped):
    the set-up.md section numbers the action runs and the ones it says it does not."""
    text = open(os.path.join(_REFERENCE, "view-and-tune.md"), encoding="utf-8").read()
    action = next(ln for ln in text.splitlines() if ln.startswith("- **Set up Risk and trust**"))
    skipped = set(re.findall(r"not\s+\u00a7\s*(\d+\.\d+)", action))
    run = set(re.findall(r"\u00a7\s*(\d+\.\d+)", action)) - skipped
    return run, skipped


def _section_blocks(number):
    """The fenced bash blocks under set-up.md's `## <number>` heading, up to the next `## `."""
    lines = open(os.path.join(_REFERENCE, "set-up.md"), encoding="utf-8").read().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## " + number))
    blocks, cur = [], None
    for ln in lines[start + 1:]:
        if cur is None and ln.startswith("## "):
            break
        if ln.startswith("```bash"):
            cur = []
        elif ln.startswith("```") and cur is not None:
            blocks.append("\n".join(cur))
            cur = None
        elif cur is not None:
            cur.append(ln)
    return blocks


def _setup_headings():
    lines = open(os.path.join(_REFERENCE, "set-up.md"), encoding="utf-8").read().splitlines()
    return [m.groups() for m in (re.match(r"## (\d+\.\d+)\b(.*)", ln) for ln in lines) if m]


def _setup_section_numbers():
    return [number for number, _ in _setup_headings()]


def _setup_heading(number):
    return dict(_setup_headings())[number]


def _sitting_commands():
    """The command blocks the menu action routes to, derived from the menu's own text."""
    run, skipped = _menu_routing()
    return [b for number in sorted(run) for b in _section_blocks(number)]


def _is_coverage_block(block):
    return re.search(r'risk_areas\.py"? touched\b', block) is not None


def test_the_menu_action_routes_to_the_sitting_and_not_the_migration_step():
    run, skipped = _menu_routing()
    # Both expected sections are identified from set-up.md's own content, not by number.
    sitting = {n for n in _setup_section_numbers() if "Risk and trust" in _setup_heading(n)}
    migration = {n for n in _setup_section_numbers()
                 if any("migrate-material-line" in b for b in _section_blocks(n))}
    assert len(sitting) == 1 and len(migration) == 1 and not (sitting & migration)
    assert run == sitting and skipped == migration
    assert not any("migrate-material-line" in b for b in _sitting_commands())


@pytest.mark.parametrize("who_set", [True, False])
def test_menu_action_sitting_commands_end_to_end(tmp_path, who_set):
    """Start from the menu entry on an already-configured project and run the commands it routes
    to. Whether the who-it's-for question is skipped follows from what the sitting's own read
    command returns, not from the fixture flag. (That the advisor then really declines to ask
    the question aloud is conversational and not testable here.)"""
    repo, store = _setup_repo(tmp_path, threat="Outsiders only.")
    plugin = os.path.join(_REPO_ROOT, "plugins/superheroes")
    blocks = _sitting_commands()
    assert blocks
    who_text = "Clinics, to book visits."
    if who_set:
        assert PC.set_item(repo, "whoItsFor", who_text, root=store)["action"] == "written"
    answers = {"whoItsFor": json.dumps("Owners of small shops, to take payments."),
               "riskAndTrust": json.dumps({"riskAreas": [PAYMENTS]})}
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=plugin)
    head_before = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", "HEAD"],
                                 capture_output=True).returncode
    ran, who_read = [], None
    wrote_areas_at, coverage_runs = None, []
    for position, block in enumerate(blocks):
        if _is_coverage_block(block):
            assert wrote_areas_at is not None and position > wrote_areas_at
            cmd = block.replace("--cwd .", "--cwd . --root " + shlex.quote(store))
            res = subprocess.run(["bash", "-c", cmd], env=env, cwd=repo,
                                 capture_output=True, text=True)
            assert res.returncode == 0, res.stderr
            coverage_runs.append(json.loads(res.stdout))
            continue
        if "project_config.py" not in block:
            continue
        item = "riskAndTrust" if "riskAndTrust" in block else "whoItsFor"
        is_set = " set " in block
        if is_set:
            if item == "whoItsFor" and who_read is not None and who_read["raw"]:
                continue  # the read command returned a recorded answer: not asked again
            if item == "riskAndTrust" and '"threatModel"' in block:
                continue  # the threat-model half is offered only on the owner's yes
            cmd = block.split("<<'SUPERHEROES_ANSWER'")[0].replace("--cwd .", "--cwd . --root " + shlex.quote(store))
            res = subprocess.run(["bash", "-c", cmd], input=answers[item] + "\n", env=env,
                                 cwd=repo, capture_output=True, text=True)
        else:
            cmd = block.replace("--cwd .", "--cwd . --root " + shlex.quote(store))
            res = subprocess.run(["bash", "-c", cmd], env=env, cwd=repo,
                                 capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        out = json.loads(res.stdout)
        if not is_set and item == "whoItsFor":
            who_read = out
        ran.append((item, is_set, out))
        if is_set and item == "riskAndTrust":
            wrote_areas_at = position
    assert who_read is not None and bool(who_read["raw"]) is who_set
    assert any(i == "whoItsFor" and s for i, s, o in ran) is (not who_set)
    assert any(s and o["action"] == "written" and i == "riskAndTrust" for i, s, o in ran)
    assert coverage_runs and all(run["riskAreas"] == "set" for run in coverage_runs)
    who = PC.get_item(repo, "whoItsFor", root=store)
    assert who["raw"] == (who_text if who_set else "Owners of small shops, to take payments.")
    got = PC.get_item(repo, "riskAndTrust", root=store)
    assert got["raw"] == {"threatModel": "Outsiders only.", "riskAreas": [PAYMENTS]}
    assert not os.path.exists(os.path.join(repo, ".canon"))
    assert subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", "HEAD"],
                          capture_output=True).returncode == head_before


def test_coverage_check_names_an_area_that_covers_no_tracked_file(tmp_path):
    repo, store = _setup_repo(tmp_path)
    os.makedirs(os.path.join(repo, "src", "payments"))
    with open(os.path.join(repo, "src", "payments", "charge.py"), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    subprocess.run(["git", "-C", repo, "add", "src/payments/charge.py"], check=True)
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-q", "-m", "fixture"], check=True)
    areas = [dict(PAYMENTS, covers=["src/payments"]),
             dict(CUSTOMER_DATA, name="Ghost", covers=["src/nowhere"])]
    assert PC.set_item(repo, "riskAndTrust", {"riskAreas": areas}, root=store)["action"] == "written"
    section = next(n for n in _setup_section_numbers() if "Risk and trust" in _setup_heading(n))
    block = next(b for b in _section_blocks(section) if _is_coverage_block(b))
    cmd = block.replace("--cwd .", "--cwd . --root " + shlex.quote(store))
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=os.path.join(_REPO_ROOT, "plugins/superheroes"))
    res = subprocess.run(["bash", "-c", cmd], env=env, cwd=repo, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["riskAreas"] == "set"
    assert [a["name"] for a in out["areas"]] == ["Payments", "Ghost"]
    assert [t["area"]["name"] for t in out["touched"]] == ["Payments"]
    assert out["touched"][0]["matched"] == ["src/payments/charge.py"]


def test_coverage_check_matches_non_ascii_names_and_runs_from_a_subfolder(tmp_path):
    repo, store = _setup_repo(tmp_path)
    os.makedirs(os.path.join(repo, "src", "payments"))
    name = "r\u00e9fund.py"
    with open(os.path.join(repo, "src", "payments", name), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    subprocess.run(["git", "-C", repo, "add", "src/payments"], check=True)
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-q", "-m", "fixture"], check=True)
    areas = [dict(PAYMENTS, covers=["src/payments"])]
    assert PC.set_item(repo, "riskAndTrust", {"riskAreas": areas}, root=store)["action"] == "written"
    section = next(n for n in _setup_section_numbers() if "Risk and trust" in _setup_heading(n))
    block = next(b for b in _section_blocks(section) if _is_coverage_block(b))
    cmd = block.replace("--cwd .", "--cwd . --root " + shlex.quote(store))
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=os.path.join(_REPO_ROOT, "plugins/superheroes"))
    for cwd in (repo, os.path.join(repo, "src", "payments")):
        res = subprocess.run(["bash", "-c", cmd], env=env, cwd=cwd, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        out = json.loads(res.stdout)
        assert [t["area"]["name"] for t in out["touched"]] == ["Payments"], cwd
        assert out["touched"][0]["matched"] == ["src/payments/" + name], cwd
