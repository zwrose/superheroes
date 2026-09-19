import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(_PLUGIN, "..", ".."))
_FIXTURES = os.path.join(_HERE, "fixtures", "order_lint")

_OBSERVED_TOKENS = []


def _load():
    spec = importlib.util.spec_from_file_location(
        "order_lint", os.path.join(_LIB, "order_lint.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OL = _load()


def _record(result):
    for item in result.get("findings", []):
        _OBSERVED_TOKENS.append(item["token"])
    return result


def _tokens(result):
    return [f["token"] for f in result["findings"]]


def _details(result):
    return [f["detail"] for f in result["findings"]]


def _mk_repo(tmp_path, files=()):
    root = tmp_path / "repo"
    root.mkdir()
    for rel, content in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _accepted_implementer_text():
    return (
        "# WO\n\n"
        "Budget: at most 5 commands.\n\n"
        "Edit `agents/implementer.md` only.\n"
    )


def _accepted_fixer_text():
    return (
        "# Fix\n\n"
        "Run `agents/implementer.md` for protocol.\n"
    )


# --- token tests (implementer) ---


def test_token_unreadable_missing_file(tmp_path):
    # axis: check maps read failures to order-unreadable, never raises
    r = _record(OL.check(str(tmp_path / "nope.md"), str(tmp_path)))
    assert r["ok"] is False
    assert _tokens(r) == [OL.TOKEN_UNREADABLE]


def test_token_unreadable_empty_file(tmp_path):
    order = tmp_path / "empty.md"
    order.write_text("\n", encoding="utf-8")
    r = _record(OL.check(str(order), str(tmp_path)))
    assert r["ok"] is False
    assert _tokens(r) == [OL.TOKEN_UNREADABLE]


def test_token_repo_root_unresolved(tmp_path):
    order = tmp_path / "order.md"
    order.write_text(_accepted_implementer_text(), encoding="utf-8")
    r = _record(OL.check(str(order), str(tmp_path / "missing")))
    assert OL.TOKEN_REPO_ROOT_UNRESOLVED in _tokens(r)


def test_token_path_unresolved(tmp_path):
    # axis: non-exempt path candidates must resolve under a root
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    text = "# WO\n\nBudget 3.\n\nSee `lib/missing_1339.py`.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any(
        f["token"] == OL.TOKEN_PATH_UNRESOLVED and "missing_1339.py" in f["detail"]
        for f in r["findings"]
    )


def test_token_placeholder_unfilled(tmp_path):
    # axis: {{NAME}} and {name} placeholders are detected and refused
    repo = _mk_repo(tmp_path)
    text = "# WO\n\nBudget 2.\n\nHello {{NAME}} and {foo}.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    details = _details(r)
    assert "NAME" in details and "foo" in details


def test_token_result_shape_ambiguous(tmp_path):
    # axis: write-report sentinel beside a native-typed literal is ambiguous
    repo = _mk_repo(tmp_path)
    text = (
        "# WO\n\nBudget 1.\n\n"
        "Print %s on stdout; the shell --output-schema carries it.\n"
        % OL._WRITE_SENTINEL
    )
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS in _tokens(r)


def test_token_budget_missing_implementer(tmp_path):
    # axis: implementer orders must carry a budget signal
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    text = "# WO\n\nEdit `agents/implementer.md`.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_BUDGET_MISSING in _tokens(r)


def test_token_kind_unknown(tmp_path):
    repo = _mk_repo(tmp_path)
    r = _record(OL.check_text("budget 1\n", str(repo), kind="pilot"))
    assert _tokens(r) == [OL.TOKEN_KIND_UNKNOWN]


# --- token tests (fixer) ---


def test_fixer_skips_budget_token(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    text = "# Fix\n\nRun `agents/implementer.md`.\n"
    r = _record(OL.check_text(text, str(repo), kind="fixer"))
    assert OL.TOKEN_BUDGET_MISSING not in _tokens(r)


def test_fixer_placeholder_token(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "# Fix\n\nValue {bar}.\n"
    r = _record(OL.check_text(text, str(repo), kind="fixer"))
    assert OL.TOKEN_PLACEHOLDER_UNFILLED in _tokens(r)


# --- accepted shape ---


def test_accepted_shape_implementer(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    r = OL.check_text(_accepted_implementer_text(), str(repo), kind="implementer")
    assert r["ok"] is True
    assert r["findings"] == []


def test_accepted_shape_fixer(tmp_path):
    # axis: fixer kind skips the budget rule
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    r = OL.check_text(_accepted_fixer_text(), str(repo), kind="fixer")
    assert r["ok"] is True
    assert r["findings"] == []


# --- fail-closed edges 1-10 ---


def test_edge1_unreadable_stops(tmp_path):
    r = _record(OL.check(str(tmp_path / "x.md"), str(tmp_path)))
    assert len(r["findings"]) == 1
    assert r["findings"][0]["token"] == OL.TOKEN_UNREADABLE


def test_edge2_bad_repo_root_skips_paths(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    text = "budget 1\n\n`agents/implementer.md`\n"
    r = _record(OL.check_text(text, str(tmp_path / "nope"), kind="implementer"))
    assert OL.TOKEN_REPO_ROOT_UNRESOLVED in _tokens(r)
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)
    assert OL.TOKEN_BUDGET_MISSING not in _tokens(r)


def test_edge3_bad_alt_root_dropped(tmp_path):
    repo = _mk_repo(tmp_path, [("lib/foo.py", "x = 1\n")])
    text = "budget 1\n\n`lib/foo.py`\n"
    r = OL.check_text(
        text, str(repo), alt_roots=(str(tmp_path / "bad"), str(repo)), kind="implementer",
    )
    assert any(
        f["token"] == OL.TOKEN_REPO_ROOT_UNRESOLVED for f in r["findings"]
    )
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_edge4_unknown_kind_alone(tmp_path):
    r = _record(OL.check_text("budget 1\n`x/y.py`\n", str(tmp_path), kind="other"))
    assert _tokens(r) == [OL.TOKEN_KIND_UNKNOWN]


def test_edge5_path_escapes_root(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "budget 1\n\n`../outside.py`\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("escapes-root" in d for d in _details(r))


def test_edge6_expect_item_refused(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "budget 1\n"
    r = _record(OL.check_text(text, str(repo), expect_items=("/abs.py",), kind="implementer"))
    assert any("absolute" in d for d in _details(r))


def test_edge7_duplicate_placeholder_once(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "budget 1\n\n{{X}} and {{X}}.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert _tokens(r).count(OL.TOKEN_PLACEHOLDER_UNFILLED) == 1


def test_edge8_empty_findings_ok(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    r = OL.check_text(_accepted_implementer_text(), str(repo))
    assert r["ok"] is True
    assert r["findings"] == []


def test_edge9_main_argparse_json(capsys):
    code = OL.main([])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["ok"] is False
    assert out["findings"][0]["token"] == OL.TOKEN_UNREADABLE


def test_edge10_not_text():
    r = _record(OL.check_text(None, "/tmp", kind="implementer"))
    assert r["findings"][0]["detail"] == "not-text"


# --- CLI ---


def test_cli_check_exit_codes(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    good = tmp_path / "good.md"
    good.write_text(_accepted_implementer_text(), encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("# no budget\n", encoding="utf-8")
    script = os.path.join(_LIB, "order_lint.py")
    base = [sys.executable, "-B", script, "check", "--repo-root", str(repo)]
    ok_run = subprocess.run(
        base + ["--order", str(good)], capture_output=True, text=True, check=False,
    )
    assert ok_run.returncode == 0
    assert json.loads(ok_run.stdout)["ok"] is True
    bad_run = subprocess.run(
        base + ["--order", str(bad)], capture_output=True, text=True, check=False,
    )
    assert bad_run.returncode == 1
    bad_out = json.loads(bad_run.stdout)
    assert bad_out["ok"] is False
    assert bad_out["findings"]


def test_tokens_census():
    for token in OL.TOKENS:
        assert token.startswith("order-")
    refused = [
        OL.check_text("budget 1\n{{A}}\n`../x.py`\n", "/tmp", kind="pilot"),
        OL.check_text("budget 1\n", "/tmp", kind="implementer"),
        OL.check_text(
            "budget 1\n%s and --output-schema\n" % OL._WRITE_SENTINEL, "/tmp",
        ),
        OL.check_text("#\n", "/tmp"),
        OL.check_text(None, "/tmp"),
    ]
    seen = set(_OBSERVED_TOKENS)
    for r in refused:
        for f in r["findings"]:
            seen.add(f["token"])
    assert seen.issubset(set(OL.TOKENS))


def test_per_token_exemption_does_not_leak_across_the_line(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "budget 1\n\nAdd `new/x.py` following `missing/reference.md`\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("missing/reference.md" in d for d in _details(r))


def test_generic_add_verb_does_not_exempt_reference_path(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. Add a test modeled on `tests/reference.py`.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("tests/reference.py" in d for d in _details(r))


def test_symlink_escape_is_unresolved(tmp_path):
    # axis: symlink targets outside the root are refused with :escapes-root
    repo = _mk_repo(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    sub = repo / "sub"
    sub.mkdir()
    link = sub / "link.py"
    link.symlink_to(outside)
    text = "budget 1\n\n`sub/link.py`\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("escapes-root" in d for d in _details(r))


# --- C11 layer 3 fixtures ---


def _fixture_path(name):
    return os.path.join(_FIXTURES, name)


def _finding_pairs(result):
    return [(f["token"], f["detail"]) for f in result["findings"]]


def test_fixture_c11_l3_wo_a(tmp_path):
    """At a consuming-project root, ``plugins/superheroes/lib/engine_result_channel.py`` is
    unresolved when the plugin alt-root lacks that file (WO-A2). The deterministic half catches the
    plugin-only path only when linted against a root where it does not exist.
    ``order-result-shape-ambiguous`` is absent — WO-A3's mixed marker/native prose is the semantic
    half's item (b), not the deterministic half's protocol literals."""
    path = _fixture_path("c11_l3_wo_a.md")
    consume = tmp_path / "consume"
    consume.mkdir()
    (consume / "README.md").write_text("hi\n", encoding="utf-8")
    eng_path = "plugins/superheroes/lib/engine_result_channel.py"
    eng_file = consume / "plugins" / "superheroes" / "lib" / "engine_result_channel.py"
    absent_r = OL.check(path, str(consume))
    assert (OL.TOKEN_PATH_UNRESOLVED, eng_path) in _finding_pairs(absent_r)
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS not in _tokens(absent_r)
    eng_file.parent.mkdir(parents=True, exist_ok=True)
    eng_file.write_text("# channel\n", encoding="utf-8")
    present_r = OL.check(path, str(consume))
    assert (OL.TOKEN_PATH_UNRESOLVED, eng_path) not in _finding_pairs(present_r)
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS not in _tokens(present_r)


def test_fixture_c11_l3_wo_c(tmp_path):
    """``lib/conformance_probe.py`` is unresolved when the plugin alt-root lacks that file (WO-C
    cites a sibling file that does not exist). Forbidden phrases are not caught — a phrase is not a
    path, placeholder, contract, or budget (semantic half)."""
    path = _fixture_path("c11_l3_wo_c.md")
    consume = tmp_path / "consume"
    consume.mkdir()
    alt_plugin = tmp_path / "plugins" / "superheroes"
    alt_plugin.mkdir(parents=True)
    absent_r = OL.check(path, str(consume), alt_roots=(str(alt_plugin),))
    assert (
        OL.TOKEN_PATH_UNRESOLVED,
        "lib/conformance_probe.py",
    ) in _finding_pairs(absent_r)
    joined = " ".join(_details(absent_r))
    assert "this layer" not in joined
    probe = alt_plugin / "lib" / "conformance_probe.py"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("# probe\n", encoding="utf-8")
    present_r = OL.check(path, str(consume), alt_roots=(str(alt_plugin),))
    assert (
        OL.TOKEN_PATH_UNRESOLVED,
        "lib/conformance_probe.py",
    ) not in _finding_pairs(present_r)


def test_fixture_c11_l3_wo_a3():
    """``order-result-shape-ambiguous`` is absent — WO-A3's mixed shapes are the semantic half's
    item (b), not the deterministic half's protocol literals. Budget rule passes."""
    path = _fixture_path("c11_l3_wo_a3.md")
    r = OL.check(path, REPO_ROOT, alt_roots=(_PLUGIN,))
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS not in _tokens(r)
    assert OL.TOKEN_BUDGET_MISSING not in _tokens(r)


def test_planted_bad_path_in_fixture_order(tmp_path):
    """BP-OL-8 green half: a planted missing path in a fixture copy is unresolved."""
    # axis: with existence neutralized, a planted missing path is still caught when restore is in place
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    src = _fixture_path("c11_l3_wo_c.md")
    copy = tmp_path / "copy.md"
    copy.write_text(
        open(src, encoding="utf-8").read()
        + "\nSee `plugins/superheroes/lib/does_not_exist_1339.py`.\n",
        encoding="utf-8",
    )
    r = OL.check(str(copy), str(repo), alt_roots=(_PLUGIN,), kind="implementer")
    assert any("does_not_exist_1339.py" in d for d in _details(r))


def test_created_path_exemption_is_order_wide(tmp_path):
    repo = _mk_repo(tmp_path)
    semantic = "plugins/superheroes/rubric/orders/order-lint-semantic.md"
    text = (
        "# WO-3\n\n"
        "Budget: at most 5 commands.\n\n"
        "Create `%(semantic)s` (new file).\n\n"
        "See also `%(semantic)s`.\n"
    ) % {"semantic": semantic}
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)
    repeat = (
        "# WO\n\n"
        "Budget: at most 3 commands.\n\n"
        "`lib/missing_twice.py` and `lib/missing_twice.py`.\n"
    )
    r2 = _record(OL.check_text(repeat, str(repo), kind="implementer"))
    assert _tokens(r2).count(OL.TOKEN_PATH_UNRESOLVED) == 1
    assert "missing_twice.py" in _details(r2)[0]


def test_path_after_fence_is_checked(tmp_path):
    repo = _mk_repo(tmp_path)
    text = (
        "# WO\n\n"
        "Budget: at most 1 command.\n\n"
        "```sh\n"
        "echo ok\n"
        "```\n"
        "Then read `lib/missing_after_fence.py`.\n"
    )
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("missing_after_fence.py" in d for d in _details(r))


def test_shell_expansion_is_not_placeholder(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "# WO\n\nBudget: 1 command.\n\nRun `${PLUGIN_ROOT}/lib/order_lint.py`.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PLACEHOLDER_UNFILLED not in _tokens(r)


def test_prose_path_is_checked(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "# WO\n\nBudget: 1 command.\n\nSee missing/file.py\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("missing/file.py" in d for d in _details(r))


def test_http_prefixed_repo_path_is_checked(tmp_path):
    repo = _mk_repo(tmp_path, [("http/client.py", "# stdlib shim\n")])
    text = "# WO\n\nBudget: 1 command.\n\nSee `http/client.py`.\n"
    r = OL.check_text(text, str(repo), kind="implementer")
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_stdout_protocol_matches_engine_adapter_and_payload_contracts():
    import engine_adapter
    import payload_contracts
    contract, reason = payload_contracts.payload_contract(payload_contracts.P_FIXER)
    assert reason is None
    expected = (
        engine_adapter.WRITE_REPORT_SENTINEL,
        '{"' + contract["required"][0] + '"',
    )
    assert OL._STDOUT_PROTOCOL == expected


def test_result_shape_ambiguous_fires_on_stdout_protocol_literals(tmp_path):
    # axis: the protocol literals, not prose aliases, count as a stdout-report contract
    assert OL._FIXER_LITERAL == '{"fixes"'
    assert OL._WRITE_SENTINEL == "<<<SUPERHEROES-WRITE-REPORT>>>"
    repo = _mk_repo(tmp_path)
    text = (
        "Budget 1.\n\nPrint %s on stdout; the shell --output-schema carries it.\n"
        % OL._WRITE_SENTINEL
    )
    r = OL.check_text(text, str(repo), kind="implementer")
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS in _tokens(r)
    r = OL.check_text(
        'Budget 1.\n\nPrint {"fixes": []} on stdout.\n',
        str(repo),
        expect_items=("lib/new.py",),
        kind="implementer",
    )
    assert (OL.TOKEN_RESULT_SHAPE_AMBIGUOUS, OL._FIXER_LITERAL + "+expect-item") in _finding_pairs(r)
    clean = OL.check_text(
        'Budget 1.\n\nPrint {"fixes": []} on stdout.\n',
        str(repo),
        kind="implementer",
    )
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS not in _tokens(clean)


def test_multi_channel_order_does_not_fire_result_shape(tmp_path):
    repo = _mk_repo(tmp_path)
    text = (
        "Budget: 3 commands.\n"
        "For cursor dispatches, use the marker channel parser.\n"
        "For codex native dispatches, pass --output-schema.\n"
    )
    r = OL.check_text(text, str(repo), kind="implementer")
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS not in _tokens(r)


def test_created_path_exemption_after_fence(tmp_path):
    repo = _mk_repo(tmp_path)
    text = (
        "```sh\n"
        + ("x" * 100)
        + "\n```\nSee `a/b.md`.\nCreate `a/b.md` (new file).\n"
    )
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_sentence_ending_path_is_checked(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. See missing/file.py.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert any("missing/file.py" in d for d in _details(r))


def test_sentence_ending_path_with_line_suffix_is_checked(tmp_path):
    repo = _mk_repo(tmp_path)
    for text in (
        "Budget: 1 command. See missing/file.py:12.\n",
        "Budget: 1 command. See missing/file.py:12-14.\n",
    ):
        r = _record(OL.check_text(text, str(repo), kind="implementer"))
        assert any(d == "missing/file.py" for d in _details(r))


def test_markdown_link_path_is_checked(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. See [file](missing/file.py).\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert _details(r) == ["missing/file.py"]


def test_markdown_link_to_existing_file_is_not_a_finding(tmp_path):
    target = "plugins/superheroes/lib/order_lint.py"
    repo = _mk_repo(tmp_path, [(target, "# lint\n")])
    text = "Budget: 1 command. See [lint](%s) for details.\n" % target
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert r["ok"] is True
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_literal_brace_in_backtick_is_not_placeholder(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. Preserve literal `s3://bucket/{namespace}/x.json`.\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PLACEHOLDER_UNFILLED not in _tokens(r)


def test_literal_brace_in_fence_is_not_placeholder(tmp_path):
    repo = _mk_repo(tmp_path)
    text = (
        "Budget: 1 command.\n\n"
        "```python\n"
        'value = f"{value}"\n'
        "```\n"
    )
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PLACEHOLDER_UNFILLED not in _tokens(r)


def test_double_brace_in_fence_is_still_placeholder(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command.\n\n```\n{{NAME}}\n```\n"
    r = _record(OL.check_text(text, str(repo), kind="implementer"))
    assert OL.TOKEN_PLACEHOLDER_UNFILLED in _tokens(r)


def test_prose_expect_item_exempts_declared_path(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. Edit missing/new.py\n"
    r = OL.check_text(text, str(repo), expect_items=["missing/new.py"], kind="implementer")
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_prose_new_file_marker_exempts_path(tmp_path):
    repo = _mk_repo(tmp_path)
    text = "Budget: 1 command. Create missing/new.py (new file)\n"
    r = OL.check_text(text, str(repo), kind="implementer")
    assert OL.TOKEN_PATH_UNRESOLVED not in _tokens(r)


def test_cli_unknown_kind_reports_kind_token(tmp_path):
    repo = _mk_repo(tmp_path, [("agents/implementer.md", "# x\n")])
    order = tmp_path / "order.md"
    order.write_text(_accepted_implementer_text(), encoding="utf-8")
    script = os.path.join(_LIB, "order_lint.py")
    run = subprocess.run(
        [
            sys.executable, "-B", script, "check",
            "--order", str(order),
            "--repo-root", str(repo),
            "--kind", "pilot",
        ],
        capture_output=True, text=True, check=False,
    )
    assert run.returncode == 1
    out = json.loads(run.stdout)
    assert out["findings"][0]["token"] == OL.TOKEN_KIND_UNKNOWN
