# plugins/superheroes/lib/tests/test_risk_areas.py
"""Risk areas (#1712): the stored-area validator and reader, the one touched reader, the upgrade."""
import ast
import importlib.util
import io
import json
import os
import socket
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


R = _load("risk_areas")
CM = _load("core_md")
PC = _load("project_config")

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


def _repo(tmp_path, areas=None, *, with_key=True):
    """A repo whose core.md holds the fixture facts and, when asked, the given riskAreas."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    if with_key:
        res = CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, areas, root=store)
        assert res["action"] == "written"
    return repo, store


def _raw_core(tmp_path, json_text, *, schema=2):
    """A repo whose in-repo core.md carries exactly the given json block text."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=confirmed created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n" % (schema, json_text)
    )
    with open(os.path.join(d, "core.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return repo, store


def _block(schema=2, **extra):
    block = {"schemaVersion": schema, "verifyCommand": "npm test", "stackTags": ["node"]}
    block.update(extra)
    return json.dumps(block, indent=2)


# --- the canonical pattern form (I4) --------------------------------------------------------


def test_leading_dot_slash_pattern_refused():
    # the token is asserted, not just "refused": the dot-segment rule would also catch this form
    assert CM.risk_area_pattern_problem("./src/payments/*") == "pattern-leading-dot-slash"


@pytest.mark.parametrize("pattern,reason", [
    (5, "pattern-not-a-string"),
    ("", "pattern-empty"),
    ("   ", "pattern-empty"),
    (" src/a", "pattern-surrounding-whitespace"),
    ("src/a ", "pattern-surrounding-whitespace"),
    ("/src/a", "pattern-absolute"),
    ("src\\a", "pattern-backslash"),
    ("src//a", "pattern-empty-segment"),
    ("src/a/", "pattern-empty-segment"),
    ("src/../a", "pattern-dot-segment"),
    ("../a", "pattern-dot-segment"),
    ("src/./a", "pattern-dot-segment"),
    (".", "pattern-dot-segment"),
    ("..", "pattern-dot-segment"),
])
def test_every_non_canonical_pattern_form_is_refused(pattern, reason):
    assert CM.risk_area_pattern_problem(pattern) == reason
    area = dict(PAYMENTS, covers=[pattern])
    assert CM.validate_risk_areas([area]) != []


@pytest.mark.parametrize("pattern", [
    "src/payments/*", "*.sql", "docs/**", "a b/c.py", "src/a.py", ".github/workflows/*", "*",
])
def test_every_accepted_pattern_is_one_a_normalised_path_can_match(pattern):
    # I4: validation accepts only the form a normalised change path takes, so a literal
    # (wildcard-free) accepted pattern is its own normalised path
    assert CM.risk_area_pattern_problem(pattern) is None
    if "*" not in pattern:
        assert R.normalize_change_path(pattern) == pattern
        assert R.pattern_matches(pattern, R.normalize_change_path(pattern))


# --- the stored-area validator --------------------------------------------------------------


def test_valid_areas_and_empty_list_pass():
    assert CM.validate_risk_areas([]) == []
    assert CM.validate_risk_areas([PAYMENTS, CUSTOMER_DATA]) == []


def test_duplicate_names_refused():
    dup = dict(PAYMENTS, name=" payments ", covers=["lib/*"])
    got = CM.validate_risk_areas([PAYMENTS, dup])
    assert got == [{"index": 1, "field": "name", "reason": "risk-area-duplicate-name"}]


def test_missing_undo_refused():
    area = {k: v for k, v in PAYMENTS.items() if k != "undo"}
    got = CM.validate_risk_areas([area])
    assert got == [{"index": 0, "field": "undo", "reason": "risk-area-missing-field"}]


def test_extra_key_refused():
    got = CM.validate_risk_areas([dict(PAYMENTS, owner="finance")])
    assert got == [{"index": 0, "field": "owner", "reason": "risk-area-unknown-field"}]


@pytest.mark.parametrize("field", ["name", "why", "undo"])
@pytest.mark.parametrize("blank", ["", "   ", None, 3])
def test_blank_text_fields_refused(field, blank):
    got = CM.validate_risk_areas([dict(PAYMENTS, **{field: blank})])
    assert got == [{"index": 0, "field": field,
                    "reason": "risk-area-field-not-a-nonempty-string"}]


@pytest.mark.parametrize("covers", [[], "src/*", None, {"a": 1}])
def test_covers_must_be_a_nonempty_list(covers):
    got = CM.validate_risk_areas([dict(PAYMENTS, covers=covers)])
    assert got == [{"index": 0, "field": "covers",
                    "reason": "risk-area-covers-not-a-nonempty-list"}]


def test_value_and_entry_shapes_refused():
    assert CM.validate_risk_areas(None)[0]["reason"] == "risk-areas-not-a-list"
    assert CM.validate_risk_areas({"name": "x"})[0]["reason"] == "risk-areas-not-a-list"
    assert CM.validate_risk_areas(["Payments"]) == [
        {"index": 0, "field": None, "reason": "risk-area-not-an-object"}]


# --- the stored-area reader (read-only, total) ----------------------------------------------


def test_read_risk_areas_reports_stored_areas_as_a_copy(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])
    got = CM.read_risk_areas(repo, root=store)
    assert got["declared"] is True and got["reason"] is None and got["behind"] is False
    assert got["areas"] == [PAYMENTS, CUSTOMER_DATA]
    got["areas"][0]["name"] = "changed"
    assert CM.read_risk_areas(repo, root=store)["areas"][0]["name"] == "Payments"


def test_read_risk_areas_absent_core_md_is_core_md_absent(tmp_path):
    got = CM.read_risk_areas(str(tmp_path), root=str(tmp_path / "store"))
    assert got["declared"] is False and got["areas"] is None
    assert got["reason"] == "core-md-absent"


def test_read_risk_areas_writes_nothing(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    before = sorted(os.listdir(str(tmp_path)))
    CM.read_risk_areas(repo, root=store)
    assert sorted(os.listdir(str(tmp_path))) == before
    assert not os.path.exists(store)


def test_read_risk_areas_malformed_keeps_the_items(tmp_path):
    repo, store = _repo(tmp_path, [{"name": "Payments"}])
    got = CM.read_risk_areas(repo, root=store)
    assert got["declared"] is True and got["areas"] is None
    assert got["reason"] == CM.RISK_AREAS_REASON_MALFORMED
    assert {m["field"] for m in got["malformed"]} == {"covers", "why", "undo"}


def test_read_risk_areas_behind_profile_is_flagged(tmp_path):
    repo, store = _raw_core(tmp_path, _block(
        schema=3, projectConfiguration={"riskAreas": [PAYMENTS]}), schema=3)
    got = CM.read_risk_areas(repo, root=store)
    assert got["behind"] is True
    assert got["areas"] == [PAYMENTS]


# --- the one touched reader -----------------------------------------------------------------


def test_payments_path_and_its_dot_slash_spelling_are_reported_touched(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])
    for spelling in ("src/payments/charge.py", "./src/payments/charge.py",
                     "src\\payments\\charge.py", ".//src//payments/charge.py"):
        got = R.touched(repo, [spelling], root=store)
        assert got["riskAreas"] == "set" and got["reason"] is None
        assert got["touched"] == [{"area": PAYMENTS, "matched": ["src/payments/charge.py"]}]
        assert got["areas"] == [PAYMENTS] + [CUSTOMER_DATA]
        assert got["unmatchable"] == []


def test_matched_paths_are_deduplicated_in_input_order_and_areas_in_stored_order(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])
    got = R.touched(repo, ["migrations/001.sql", "src/payments/b.py", "./src/payments/b.py",
                           "src/payments/a.py"], root=store)
    assert [t["area"]["name"] for t in got["touched"]] == ["Payments", "Customer data"]
    assert got["touched"][0]["matched"] == ["src/payments/b.py", "src/payments/a.py"]
    assert got["touched"][1]["matched"] == ["migrations/001.sql"]


def test_matching_is_case_sensitive_and_star_crosses_slash(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS])
    deep = R.touched(repo, ["src/payments/deep/er/x.py"], root=store)
    assert [t["area"]["name"] for t in deep["touched"]] == ["Payments"]
    assert R.touched(repo, ["SRC/payments/x.py"], root=store)["touched"] == []


def _covered(tmp_path, covers, path):
    repo, store = _repo(tmp_path, [dict(PAYMENTS, covers=covers)])
    return R.touched(repo, [path], root=store)["touched"] != []


def test_a_folder_pattern_covers_every_file_beneath_it(tmp_path):
    area = dict(PAYMENTS, covers=["src/payments"])
    repo, store = _repo(tmp_path, [area])
    for path in ("src/payments/charge.py", "src/payments/sub/refund.py", "src/payments"):
        got = R.touched(repo, ["./" + path], root=store)
        assert got["touched"] == [{"area": area, "matched": [path]}]


def test_a_folder_pattern_stops_at_the_slash_boundary(tmp_path):
    assert not _covered(tmp_path, ["src/pay"], "src/payments/charge.py")
    assert not R.pattern_matches("src/pay", "src/payments/charge.py")
    assert R.pattern_matches("src/pay", "src/pay/charge.py")


def test_a_folder_named_with_glob_characters_covers_what_is_beneath_it(tmp_path):
    assert _covered(tmp_path, ["app/[id]"], "app/[id]/page.tsx")
    assert R.pattern_matches("what?", "what?/x.py")


def test_a_literal_pattern_holding_glob_characters_covers_its_own_path(tmp_path):
    assert _covered(tmp_path, ["app/[id]/page.tsx"], "app/[id]/page.tsx")
    assert R.pattern_matches("app/[id]", "app/[id]")


def test_a_glob_that_names_folders_covers_what_is_beneath_them(tmp_path):
    assert _covered(tmp_path, ["src/*/payments"], "src/eu/payments/charge.py")
    assert R.pattern_matches("src/*/payments", "src/eu/payments")
    assert not R.pattern_matches("src/*/payments", "src/eu/other/charge.py")


def test_a_file_glob_does_not_match_by_prefix(tmp_path):
    repo, store = _repo(tmp_path, [dict(PAYMENTS, covers=["src/db/*.sql"])])
    assert R.touched(repo, ["src/db/q.sql"], root=store)["touched"] != []
    assert R.touched(repo, ["src/db/notes.txt"], root=store)["touched"] == []
    assert R.touched(repo, ["src/db.sql"], root=store)["touched"] == []


def test_change_outside_every_area_is_set_and_touches_none(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])
    got = R.touched(repo, ["docs/readme.md"], root=store)
    assert got["riskAreas"] == "set"
    assert got["touched"] == []
    assert got["reason"] is None


def test_no_change_paths_with_areas_set_touches_none(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS])
    got = R.touched(repo, [], root=store)
    assert got["riskAreas"] == "set" and got["touched"] == []


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.py", "src/../../x", "", "./", "."])
def test_unmatchable_paths_are_listed_and_never_match(tmp_path, path):
    repo, store = _repo(tmp_path, [dict(PAYMENTS, covers=["*"])])
    got = R.touched(repo, [path], root=store)
    assert got["riskAreas"] == "set"
    assert got["touched"] == []
    assert got["unmatchable"] == [path]


def _assert_not_set(got, reason):
    assert got["riskAreas"] == "not-set"
    assert got["reason"] == reason
    assert got["reason"] in ("missing", "empty", "unreadable")
    assert got["touched"] == []
    assert got["areas"] == []


def test_no_core_md_is_not_set_missing(tmp_path):
    got = R.touched(str(tmp_path), ["src/payments/charge.py"], root=str(tmp_path / "store"))
    _assert_not_set(got, "missing")


def test_no_riskareas_key_is_not_set_missing(tmp_path):
    repo, store = _repo(tmp_path, with_key=False)
    _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "missing")


def test_empty_list_is_not_set_empty(tmp_path):
    repo, store = _repo(tmp_path, [])
    _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "empty")


def test_malformed_list_is_not_set_unreadable(tmp_path):
    repo, store = _repo(tmp_path, [{"name": "Payments", "covers": ["./src/*"]}])
    got = R.touched(repo, ["src/payments/charge.py"], root=store)
    _assert_not_set(got, "unreadable")
    assert got["detail"] == CM.RISK_AREAS_REASON_MALFORMED


def test_project_configuration_not_an_object_is_not_set_unreadable(tmp_path):
    repo, store = _raw_core(tmp_path, _block(projectConfiguration=["risk"]))
    got = R.touched(repo, ["src/payments/charge.py"], root=store)
    _assert_not_set(got, "unreadable")
    assert "project-configuration-not-an-object" in got["detail"]
    assert CM.read_risk_areas(repo, root=store)["reason"] == CM.RISK_AREAS_REASON_UNREADABLE


def test_project_configuration_null_or_string_is_not_set_unreadable(tmp_path):
    for bad in (None, "riskAreas", 3):
        repo, store = _raw_core(tmp_path, _block(projectConfiguration=bad))
        _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "unreadable")


def test_corrupt_json_block_is_not_set_unreadable(tmp_path):
    repo, store = _raw_core(tmp_path, "{ not json")
    _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "unreadable")


def test_duplicate_keys_in_the_block_are_not_set_unreadable(tmp_path):
    text = ('{"schemaVersion": 2, "verifyCommand": "npm test", "stackTags": [],'
            ' "projectConfiguration": {"riskAreas": [], "riskAreas": []}}')
    repo, store = _raw_core(tmp_path, text)
    got = R.touched(repo, ["src/payments/charge.py"], root=store)
    _assert_not_set(got, "unreadable")
    assert CM.read_risk_areas(repo, root=store)["reason"] == CM.RISK_AREAS_REASON_UNREADABLE


def test_riskareas_not_a_list_is_not_set_unreadable(tmp_path):
    repo, store = _raw_core(tmp_path, _block(projectConfiguration={"riskAreas": "payments"}))
    _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "unreadable")


@pytest.mark.parametrize("paths", ["src/payments/charge.py", None, [3], ["a", None], {"a": 1}])
def test_paths_that_are_not_a_list_of_strings_are_not_set_unreadable(tmp_path, paths):
    repo, store = _repo(tmp_path, [PAYMENTS])
    _assert_not_set(R.touched(repo, paths, root=store), "unreadable")


def test_touched_writes_nothing(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS])
    core = CM.core_path(repo, store)
    with open(core, "rb") as fh:
        before = fh.read()
    R.touched(repo, ["src/payments/charge.py"], root=store)
    with open(core, "rb") as fh:
        assert fh.read() == before


def test_touched_makes_no_model_call(tmp_path, monkeypatch):
    repo, store = _repo(tmp_path, [PAYMENTS])
    real_run, real_popen = subprocess.run, subprocess.Popen
    passed_through = []

    def _refuse(*args, **kwargs):
        raise AssertionError("a process, a shell or a connection was started")

    def _is_identity_lookup(argv):
        # the repo-root and gitdir lookups (rev-parse) and the remote lookup (remote get-url)
        return bool(argv) and argv[0] == "git" and (
            "rev-parse" in argv or argv[-3:-1] == ["remote", "get-url"])

    def _only_the_identity_lookups(argv, *args, **kwargs):
        if _is_identity_lookup(argv):
            passed_through.append(list(argv))
            # the real run starts its process through Popen: let it, for this one call only
            monkeypatch.setattr(subprocess, "Popen", real_popen)
            try:
                return real_run(argv, *args, **kwargs)
            finally:
                monkeypatch.setattr(subprocess, "Popen", _refuse)
        return _refuse()

    # no warming call and no identity memo: the reader's git identity lookups run for real, and
    # anything else it started would reach the raising stand-ins
    monkeypatch.setattr(subprocess, "run", _only_the_identity_lookups)
    monkeypatch.setattr(subprocess, "Popen", _refuse)
    monkeypatch.setattr(os, "system", _refuse)
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    got = R.touched(repo, ["src/payments/charge.py", "./src/payments/charge.py"], root=store)
    assert got["riskAreas"] == "set"
    assert got["touched"] == [{"area": PAYMENTS, "matched": ["src/payments/charge.py"]}]
    assert passed_through and all(_is_identity_lookup(argv) for argv in passed_through)


def test_risk_areas_module_imports_no_process_network_or_engine_module():
    path = os.path.join(_LIB, "risk_areas.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"subprocess", "socket", "urllib", "http", "engine_dispatch"}


# --- the command line -----------------------------------------------------------------------


def test_cli_prints_the_result_and_exits_zero_even_when_not_set(tmp_path, capsys):
    repo, store = _repo(tmp_path, [PAYMENTS])
    rc = R.main(["touched", "--cwd", repo, "--root", store, "--path", "src/payments/charge.py"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["riskAreas"] == "set"
    assert out["touched"][0]["area"] == PAYMENTS
    rc = R.main(["touched", "--cwd", str(tmp_path / "nowhere"), "--root", store, "--path", "a"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["riskAreas"] == "not-set"


def test_cli_reads_paths_from_a_file_and_from_stdin(tmp_path, capsys, monkeypatch):
    repo, store = _repo(tmp_path, [PAYMENTS])
    listing = tmp_path / "paths.txt"
    listing.write_text("docs/readme.md\n\nsrc/payments/a.py\n", encoding="utf-8")
    rc = R.main(["touched", "--cwd", repo, "--root", store, "--paths-file", str(listing),
                 "--path", "src/payments/b.py"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["touched"][0]["matched"] == ["src/payments/b.py", "src/payments/a.py"]
    monkeypatch.setattr(sys, "stdin", io.StringIO("src/payments/c.py\n"))
    rc = R.main(["touched", "--cwd", repo, "--root", store, "--paths-file", "-"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["touched"][0]["matched"] == ["src/payments/c.py"]


def test_cli_keeps_in_name_whitespace_and_drops_only_line_endings(tmp_path, capsys):
    repo, store = _repo(tmp_path, [PAYMENTS])
    listing = tmp_path / "paths.txt"
    listing.write_bytes(b"src/payments/a b.py \r\n   \r\n")
    rc = R.main(["touched", "--cwd", repo, "--root", store, "--paths-file", str(listing)])
    from_file = json.loads(capsys.readouterr().out)
    assert rc == 0 and from_file["touched"][0]["matched"] == ["src/payments/a b.py "]
    rc = R.main(["touched", "--cwd", repo, "--root", store, "--path", "src/payments/a b.py "])
    by_flag = json.loads(capsys.readouterr().out)
    assert rc == 0 and by_flag["touched"][0]["matched"] == ["src/payments/a b.py "]


def test_cli_unreadable_paths_file_exits_two_with_an_error(tmp_path, capsys):
    repo, store = _repo(tmp_path, [PAYMENTS])
    rc = R.main(["touched", "--cwd", repo, "--root", store,
                 "--paths-file", str(tmp_path / "missing.txt")])
    assert rc == 2
    assert "error" in json.loads(capsys.readouterr().out)


# --- the upgrade: a core.md the previous version wrote --------------------------------------

# Produced by the base commit e26b430f8's core_md.render_core for facts verifyCommand "npm test",
# stackTags ["node"], a multi-line threatModel (one line ends in two spaces, one blank line inside),
# patterns "", projectConfiguration {"digestFloor": "weekly"}, status "confirmed", created and
# updated 2026-06-26. The two trailing spaces are written \x20 so the file holds no stray run.
_PREVIOUS_VERSION_CORE = (
    "<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26"
    " updated=2026-06-26 -->\n\n"
    "## Threat model\n\n"
    "Single-tenant app; attackers are outsiders.\x20\x20\n"
    "Secrets live in the vault.\n\n"
    "No insider threat is modelled.\n\n"
    "## Canonical patterns\n\n\n\n"
    "```json superheroes-core\n"
    "{\n"
    '  "schemaVersion": 2,\n'
    '  "verifyCommand": "npm test",\n'
    '  "stackTags": [\n'
    '    "node"\n'
    "  ],\n"
    '  "enginePreferences": {},\n'
    '  "projectConfiguration": {\n'
    '    "digestFloor": "weekly"\n'
    "  }\n"
    "}\n"
    "```\n"
)


def _threat_model_bytes(text):
    """The raw bytes of the ``## Threat model`` section, heading through the next heading."""
    start = text.index("## Threat model")
    return text[start:text.index("## Canonical patterns")].encode("utf-8")


def test_previous_version_core_md_reads_with_its_threat_model_intact_and_no_risk_areas(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    core = os.path.join(d, "core.md")
    with open(core, "w", encoding="utf-8", newline="") as fh:
        fh.write(_PREVIOUS_VERSION_CORE)

    section = CM._section(_PREVIOUS_VERSION_CORE, "Threat model")
    assert section.startswith("Single-tenant app")
    item = PC.get_item(repo, "riskAndTrust", root=store)
    assert item["raw"] == {"threatModel": section, "riskAreas": None}
    assert item["effective"] == {"threatModel": section, "riskAreas": []}
    assert item["source"] == "stamped" and item["malformed"] is False
    assert R.touched(repo, ["src/payments/charge.py"], root=store)["reason"] == "missing"

    before_section = _threat_model_bytes(_PREVIOUS_VERSION_CORE)
    res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
    assert res["action"] == "written"
    with open(core, encoding="utf-8", newline="") as fh:
        after_text = fh.read()
    assert _threat_model_bytes(after_text) == before_section
    assert after_text.split("```json")[0] == _PREVIOUS_VERSION_CORE.split("```json")[0]
    assert CM._section(after_text, "Threat model") == section
    block = json.loads(CM._JSON_BLOCK.search(after_text).group(1))
    assert block["schemaVersion"] == 2 == CM.SCHEMA_VERSION
    assert block["projectConfiguration"] == {"digestFloor": "weekly", "riskAreas": [PAYMENTS]}
    assert set(block) == {"schemaVersion", "verifyCommand", "stackTags", "enginePreferences",
                          "projectConfiguration"}
    assert R.touched(repo, ["src/payments/charge.py"], root=store)["riskAreas"] == "set"


def test_reading_never_changes_the_threat_model_bytes(tmp_path):
    repo, store = _repo(tmp_path, [PAYMENTS])
    core = CM.core_path(repo, store)
    with open(core, "rb") as fh:
        before = fh.read()
    PC.read(repo, root=store)
    R.touched(repo, ["src/payments/charge.py"], root=store)
    CM.read_risk_areas(repo, root=store)
    with open(core, "rb") as fh:
        assert fh.read() == before
