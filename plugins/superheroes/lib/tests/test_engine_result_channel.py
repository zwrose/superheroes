"""Behaviour tests for engine_result_channel (#1270 WO-A)."""
import copy
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ERC = _load("engine_result_channel")
MR = _load("model_registry")
PC = _load("payload_contracts")
RFS = _load("review_findings_schema")
EA = _load("engine_adapter")


def _is_object_schema_node(node):
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object":
        return True
    if isinstance(node.get("properties"), dict):
        return True
    return False


def _iter_object_schemas(node, path="$"):
    if not isinstance(node, dict):
        return
    if _is_object_schema_node(node):
        yield path, node
    if "oneOf" in node:
        pytest.fail("schema contains forbidden oneOf at %s" % path)
    props = node.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            yield from _iter_object_schemas(sub, "%s.properties.%s" % (path, name))
    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_object_schemas(items, "%s.items" % path)
    for branch in node.get("anyOf") or ():
        yield from _iter_object_schemas(branch, "%s.anyOf" % path)


def _example_finding_member():
    member = {}
    for key in RFS.CANONICAL_MEMBER_KEYS:
        schema = RFS.FINDING_PROPERTY_SCHEMAS[key]
        if "enum" in schema:
            member[key] = next(v for v in schema["enum"] if v is not None)
        elif schema.get("type") == ["integer", "null"]:
            member[key] = None
        elif schema.get("type") == ["boolean", "null"]:
            member[key] = None
        elif schema.get("type") == ["string", "null"]:
            member[key] = "example"
        else:
            member[key] = "example"
    return member


def _valid_review_branch(kind):
    investigated = ["path/to/file.py"]
    if kind == "findings":
        return {
            "resultKind": "findings",
            "findings": [_example_finding_member()],
            "verdicts": None,
            "grouping": None,
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    if kind == "verdicts":
        contract, _ = PC.payload_contract(PC.P_VERIFIERS)
        elem = contract["elements"]["verdicts"]
        verdict = {}
        for field in list(elem.get("required") or []) + list(elem.get("optional") or ()):
            if field == "verdict":
                verdict[field] = elem["enums"]["verdict"][0]
            elif field == "id":
                verdict[field] = "finding-001"
            elif field == "reason":
                verdict[field] = "checked"
            else:
                verdict[field] = None
        return {
            "resultKind": "verdicts",
            "findings": None,
            "verdicts": [verdict],
            "grouping": None,
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    if kind == "grouping":
        return {
            "resultKind": "grouping",
            "findings": None,
            "verdicts": None,
            "grouping": [{"member_ids": ["a-001", "b-002"]}],
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    contract, _ = PC.payload_contract(PC.P_AUDITS)
    ruling = {"id": "audit-seat", "ruling": contract["enums"]["ruling"][0], "reason": "grounds"}
    for opt in contract.get("optional") or ():
        ruling[opt] = None
    return {
        "resultKind": "ruling",
        "findings": None,
        "verdicts": None,
        "grouping": None,
        "investigated": investigated,
        **ruling,
    }


def _wrap_result(branch):
    return {"result": branch}


@pytest.mark.parametrize("vendor,expected", [
    ("codex", ERC.CHANNEL_NATIVE),
    ("cursor", ERC.CHANNEL_NATIVE),
    ("claude", ERC.CHANNEL_NATIVE),
])
def test_channel_for_registered_engines(vendor, expected):
    assert ERC.channel_for(vendor) == expected


@pytest.mark.parametrize("bad", ["bogus", None, 7, ""])
def test_channel_for_unknown_engine_refuses(bad):
    with pytest.raises(ERC.UnknownEngineError):
        ERC.channel_for(bad)


def test_channel_engine_set_matches_registry_vendors():
    mapped = frozenset(ERC._CHANNEL_BY_ENGINE)
    assert mapped == frozenset(MR.vendors())


def test_review_schema_root_and_strict_mode_tree():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    assert schema["type"] == "object"
    for path, node in _iter_object_schemas(schema):
        if "oneOf" in node:
            pytest.fail("oneOf at %s" % path)
        if _is_object_schema_node(node):
            assert node.get("additionalProperties") is False, path
            props = node.get("properties") or {}
            required = node.get("required") or []
            assert set(required) == set(props.keys()), "%s required mismatch" % path


@pytest.mark.parametrize("kind", ERC.REVIEW_RESULT_KINDS)
def test_review_discrimination_valid_branch_passes(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    ok, reason = ERC.validate(schema, _wrap_result(_valid_review_branch(kind)))
    assert ok, reason


@pytest.mark.parametrize("kind", ERC.REVIEW_RESULT_KINDS)
def test_review_discrimination_wrong_payload_key_fails(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    branch = _valid_review_branch(kind)
    other = next(k for k in ERC.REVIEW_RESULT_KINDS if k != kind and k != "ruling")
    if other in branch:
        branch[other] = _valid_review_branch(other)[other]
    ok, reason = ERC.validate(schema, _wrap_result(branch))
    assert not ok
    assert reason


def test_review_narrowing_single_branch():
    schema = ERC.declared_schema(
        "codex", ERC.RUN_KIND_REVIEW, expected_result_kind="findings")
    result = schema["properties"]["result"]
    assert "anyOf" not in result
    assert result["properties"]["resultKind"]["enum"] == ["findings"]
    ok, _ = ERC.validate(schema, _wrap_result(_valid_review_branch("findings")))
    assert ok
    wrong = _wrap_result(_valid_review_branch("verdicts"))
    ok, reason = ERC.validate(schema, wrong)
    assert not ok
    assert reason


def _branch_property_schema(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind=kind)
    return schema["properties"]["result"]


def _binding_field_names(phase, field):
    contract, reason = PC.payload_contract(phase)
    assert reason is None
    if field == "ruling":
        return list((contract.get("required") or []) + (contract.get("optional") or ()))
    elem = contract["elements"][field]
    return list((elem.get("required") or []) + list(elem.get("optional") or ()))


def _binding_enums(phase, field, elem_field):
    contract, _ = PC.payload_contract(phase)
    if field == "ruling":
        return contract.get("enums", {}).get(elem_field)
    return contract["elements"][field].get("enums", {}).get(elem_field)


@pytest.mark.parametrize("phase,field,kind", [
    (PC.P_VERIFIERS, "verdicts", "verdicts"),
    (PC.P_SYNTHESIS, "grouping", "grouping"),
    (PC.P_AUDITS, "ruling", "ruling"),
])
def test_generated_branch_tracks_payload_contracts(phase, field, kind):
    branch = _branch_property_schema(kind)
    expected_fields = _binding_field_names(phase, field)
    if kind == "ruling":
        props = branch["properties"]
        for fname in expected_fields:
            assert fname in props
            if fname in (PC.payload_contract(phase)[0].get("enums") or {}):
                assert props[fname]["enum"] == list(
                    PC.payload_contract(phase)[0]["enums"][fname])
    else:
        items = branch["properties"][field]
        if field == "grouping":
            item_props = items["items"]["properties"]
            expected_fields = _binding_field_names(phase, field)
            for fname in expected_fields:
                assert fname in item_props
        else:
            item_props = items["items"]["properties"]
            for fname in expected_fields:
                assert fname in item_props
                enum = _binding_enums(phase, field, fname)
                if enum is not None:
                    assert item_props[fname]["enum"] == list(enum)


@pytest.mark.parametrize("token", sorted(PC.TYPE_TOKENS - {"list", "any"}))
def test_every_type_token_handled(token):
    ERC._json_schema_for_type_token(token)


@pytest.mark.parametrize("token", ("list", "any"))
def test_list_and_any_tokens_require_refinement(token):
    with pytest.raises(ERC.UnrefinedTypeTokenError):
        ERC._json_schema_for_type_token(token)


def test_unrecognised_type_token_raises():
    with pytest.raises(ValueError, match="unknown type token"):
        ERC._json_schema_for_type_token("not-a-real-token")


def test_write_schema_matches_grade_build_report():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    assert set(schema["required"]) == {"ok", "signal", "report", "evidence"}
    assert schema["properties"]["signal"]["enum"] == list(ERC.WRITE_SIGNAL_ENUM)
    specimen = {
        "ok": True,
        "signal": "ok",
        "report": "full prose report",
        "evidence": {"testFailed": False, "testPassed": True},
    }
    ok, reason = ERC.validate(schema, specimen)
    assert ok, reason
    graded = EA._grade_build_report_obj(specimen)
    assert graded["ok"] is True
    assert graded["signal"] == "ok"


def test_checker_additional_properties_rejects_extra_key():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}},
    }
    ok, reason = ERC.validate(schema, {"a": "x", "b": 1})
    assert not ok
    assert "additional properties forbidden" in reason


def test_checker_nullable_type_array():
    schema = {"type": ["string", "null"]}
    assert ERC.validate(schema, "x")[0]
    assert ERC.validate(schema, None)[0]
    ok, reason = ERC.validate(schema, 1)
    assert not ok
    assert reason


def test_checker_anyof_picks_branch():
    schema = {
        "anyOf": [
            {"type": "string", "enum": ["a"]},
            {"type": "integer"},
        ]
    }
    assert ERC.validate(schema, "a")[0]
    assert ERC.validate(schema, 3)[0]
    ok, reason = ERC.validate(schema, True)
    assert not ok
    assert "anyOf failed" in reason


def test_checker_unknown_keyword_raises():
    schema = {"type": "string", "minLength": 1}
    ok, reason = ERC.validate(schema, "x")
    assert not ok
    assert "unknown schema keyword" in reason


def _mutate_specimens(valid):
    specimens = []
    specimens.append((valid, True))
    extra = copy.deepcopy(valid)
    extra["extra"] = True
    specimens.append((extra, False))
    if isinstance(valid, dict):
        for key, value in list(valid.items()):
            if value is None:
                bad = copy.deepcopy(valid)
                bad[key] = "not-null"
                specimens.append((bad, False))
            elif isinstance(value, bool):
                bad = copy.deepcopy(valid)
                bad[key] = "not-bool"
                specimens.append((bad, False))
        if valid:
            missing = copy.deepcopy(valid)
            drop = next(iter(missing))
            del missing[drop]
            specimens.append((missing, False))
    return specimens


@pytest.mark.skipif(jsonschema is None, reason="jsonschema not installed")
@pytest.mark.parametrize("run_kind", [ERC.RUN_KIND_REVIEW, ERC.RUN_KIND_WRITE])
def test_differential_agreement_with_jsonschema(run_kind):
    if run_kind == ERC.RUN_KIND_REVIEW:
        schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
        valid = _wrap_result(_valid_review_branch("findings"))
        wrong_branch = _wrap_result(_valid_review_branch("verdicts"))
        specimens = _mutate_specimens(valid)
        specimens.append((wrong_branch, False))
    else:
        schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
        valid = {
            "ok": False,
            "signal": "plan_wrong",
            "report": "stopped",
            "evidence": {"testFailed": True, "testPassed": False},
        }
        specimens = _mutate_specimens(valid)
    for value, _ in specimens:
        ours_ok, ours_reason = ERC.validate(schema, value)
        try:
            jsonschema.validate(value, schema)
            js_ok = True
            js_reason = ""
        except jsonschema.ValidationError as exc:
            js_ok = False
            js_reason = exc.message
        assert ours_ok == js_ok, (
            "disagreement on %r: ours=%s (%r) jsonschema=%s (%r)"
            % (value, ours_ok, ours_reason, js_ok, js_reason)
        )


def test_claude_native_channel_declared_schema_matches_codex():
    for run_kind in (ERC.RUN_KIND_REVIEW, ERC.RUN_KIND_WRITE):
        assert ERC.declared_schema("claude", run_kind) == ERC.declared_schema("codex", run_kind)
    assert ERC.declared_schema("cursor", ERC.RUN_KIND_REVIEW) is not None
    assert ERC.declared_schema("cursor", ERC.RUN_KIND_WRITE) is not None


def test_file_result_contract_review_forbids_worktree_edits():
    contract = ERC.file_result_contract("{}", "/path/result.json", ERC.RUN_KIND_REVIEW)
    assert 'sole exception to "do not edit anything"' in contract
    assert "create no other file and change nothing else" in contract
    assert "in addition to the repository changes" not in contract


def test_file_result_contract_write_permits_worktree_edits():
    contract = ERC.file_result_contract("{}", "/path/result.json", ERC.RUN_KIND_WRITE)
    assert "in addition to the repository changes your order asks for" in contract
    assert "never add the result file itself to the repository" in contract
    assert 'sole exception to "do not edit anything"' not in contract


def test_result_delivery_registered_engines():
    assert ERC.result_delivery("codex") == ERC.RESULT_DELIVERY_ARGV
    assert ERC.result_delivery("cursor") == ERC.RESULT_DELIVERY_PROMPT
    assert ERC.result_delivery("claude") == ERC.RESULT_DELIVERY_STDOUT


@pytest.mark.parametrize("vendor,expected", [
    ("codex", ERC.RESULT_DELIVERY_ARGV),
    ("cursor", ERC.RESULT_DELIVERY_PROMPT),
    ("claude", ERC.RESULT_DELIVERY_STDOUT),
])
def test_result_delivery_print_default_identity(vendor, expected):
    assert ERC.result_delivery(vendor) == expected
    assert ERC.result_delivery(vendor, None) == expected
    assert ERC.result_delivery(vendor, ERC.MODE_PRINT) == expected


def test_claude_modes_reexported_from_adapter():
    assert ERC.MODE_PRINT == EA.MODE_PRINT
    assert ERC.MODE_BACKGROUND == EA.MODE_BACKGROUND
    assert ERC.CLAUDE_MODES == EA.CLAUDE_MODES


def test_result_delivery_members_closed():
    assert ERC.RESULT_DELIVERY_MEMBERS == frozenset({
        ERC.RESULT_DELIVERY_ARGV,
        ERC.RESULT_DELIVERY_PROMPT,
        ERC.RESULT_DELIVERY_STDOUT,
        ERC.RESULT_DELIVERY_TRANSCRIPT,
    })


def test_result_delivery_contract_builders_cover_all_members():
    review_schema = ERC.declared_schema("claude", ERC.RUN_KIND_REVIEW)
    write_schema = ERC.declared_schema("claude", ERC.RUN_KIND_WRITE)
    for delivery in ERC.RESULT_DELIVERY_MEMBERS:
        assert ERC.review_result_contract_from_schema(review_schema, delivery=delivery)
        assert ERC.write_result_contract_from_schema(write_schema, delivery=delivery)


def test_normalize_claude_mode_treats_omitted_as_print():
    assert ERC.normalize_claude_mode(None) == ERC.MODE_PRINT
    assert ERC.normalize_claude_mode(ERC.MODE_PRINT) == ERC.MODE_PRINT


def test_result_delivery_claude_background_transcript():
    assert ERC.result_delivery("claude", ERC.MODE_BACKGROUND) == ERC.RESULT_DELIVERY_TRANSCRIPT


def _adapter_non_print_capability_pairs():
    pairs = set()
    for mode, engines in EA._NON_PRINT_CLAUDE_MODE_ENGINES.items():
        for engine in engines:
            pairs.add((engine, mode))
    return pairs


def test_non_print_claude_mode_capability_delivery_agree():
    # axis: adapter capability table and derived delivery map stay in bidirectional lockstep
    adapter_pairs = _adapter_non_print_capability_pairs()
    delivery_pairs = set(ERC._RESULT_DELIVERY_BY_ENGINE_MODE)
    missing_delivery = adapter_pairs - delivery_pairs
    assert not missing_delivery, (
        "adapter declares non-print (engine, mode) pairs with no delivery: %r"
        % sorted(missing_delivery)
    )
    ghost_delivery = delivery_pairs - adapter_pairs
    assert not ghost_delivery, (
        "derived delivery map has (engine, mode) pairs adapter does not declare: %r"
        % sorted(ghost_delivery)
    )


@pytest.mark.parametrize("vendor", ["codex", "cursor"])
def test_result_delivery_background_refuses_non_claude(vendor):
    with pytest.raises(ValueError, match="has no delivery for mode"):
        ERC.result_delivery(vendor, ERC.MODE_BACKGROUND)


def test_result_delivery_undeclared_mode_refuses():
    with pytest.raises(ValueError, match="unknown claude mode"):
        ERC.result_delivery("claude", "bogus")


def test_result_delivery_unknown_engine_before_bad_mode():
    with pytest.raises(ERC.UnknownEngineError):
        ERC.result_delivery("bogus", "bogus")


@pytest.mark.parametrize("mode,expected", [
    (None, True),
    (ERC.MODE_PRINT, True),
    (ERC.MODE_BACKGROUND, True),
    ("bogus", False),
])
def test_claude_mode_ok(mode, expected):
    assert ERC.claude_mode_ok(mode) is expected


def test_result_delivery_unknown_engine_refuses():
    with pytest.raises(ERC.UnknownEngineError):
        ERC.result_delivery("bogus")


def test_result_delivery_native_missing_from_table(monkeypatch):
    monkeypatch.setitem(ERC._CHANNEL_BY_ENGINE, "testnative", ERC.CHANNEL_NATIVE)
    with pytest.raises(ValueError, match="no result delivery entry"):
        ERC.result_delivery("testnative")


def test_review_result_contract_stdout_delivery_exact_sentence():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    contract = ERC.review_result_contract_from_schema(schema, delivery=ERC.RESULT_DELIVERY_STDOUT)
    expected = (
        "The graded result is your structured output — the typed final response the --json-schema flag governs; "
        "its root has exactly one property `result` wrapping the graded branch. "
        "Print nothing else as a result; stdout is telemetry."
    )
    assert expected in contract
    assert "result file named in the typed-file contract" not in contract


def test_every_dispatchable_vendor_has_channel_delivery_pin_and_argv():
    # axis: BUILD_ARGV_VENDORS chokepoint — every member has channel, delivery, and argv (#1273)
    matrix_cells = {
        "codex": ("gpt-5.6-terra", "high"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
        "claude": ("sonnet-5", "high"),
    }
    for vendor in EA.BUILD_ARGV_VENDORS:
        assert ERC.channel_for(vendor) == ERC.CHANNEL_NATIVE
        assert ERC.result_delivery(vendor) is not None
        model_id, effort = matrix_cells[vendor]
        seat = {"vendor": vendor, "model": model_id, "effort": effort}
        for role_kind in ("review", "build"):
            res = EA.build_argv_result(seat, role_kind, {})
            assert res["reason"] is None, (vendor, role_kind, res)


def _all_declared_native_schemas():
    schemas = [
        ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW),
        ERC.declared_schema("codex", ERC.RUN_KIND_WRITE),
    ]
    for kind in ERC.REVIEW_RESULT_KINDS:
        schemas.append(
            ERC.declared_schema(
                "codex", ERC.RUN_KIND_REVIEW, expected_result_kind=kind)
        )
    return schemas


@pytest.mark.parametrize("schema", _all_declared_native_schemas(), ids=[
    "review-all",
    "write",
    "review-findings",
    "review-verdicts",
    "review-grouping",
    "review-ruling",
])
def test_assert_strict_mode_valid_passes_every_declared_schema(schema):
    ERC.assert_strict_mode_valid(schema)


@pytest.mark.parametrize("schema,path_fragment", [
    ({"type": "string"}, "root schema must have type 'object'"),
    (
        {"type": "object", "oneOf": [{"type": "string"}]},
        "oneOf is not permitted",
    ),
    (
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["x"],
            "properties": {"x": {}},
        },
        "schema must have a 'type' key",
    ),
    (
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["items"],
            "properties": {"items": {"type": "array"}},
        },
        "array schema missing items",
    ),
    (
        {
            "type": "object",
            "additionalProperties": True,
            "required": [],
            "properties": {},
        },
        "additionalProperties to false",
    ),
], ids=["rule1-root", "rule2-oneof", "rule3-no-type", "rule4-array-items", "rule5-additional"])
def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
    with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
        ERC.assert_strict_mode_valid(schema)
    assert "In context=" in str(exc.value)


def test_assert_strict_mode_valid_rule5_required_properties_mismatch():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    with pytest.raises(ERC.StrictModeViolationError, match="required/properties mismatch") as exc:
        ERC.assert_strict_mode_valid(schema)
    assert "b" in str(exc.value)


_CONSUMED_PHASES = (
    (PC.P_VERIFIERS, "verdicts"),
    (PC.P_SYNTHESIS, "grouping"),
    (PC.P_AUDITS, "ruling"),
)


def _iter_binding_fields_needing_refinement(phase, top_field):
    contract, reason = PC.payload_contract(phase)
    assert reason is None
    if top_field == "ruling":
        types = contract.get("types") or {}
        for field in list(contract.get("required") or []) + list(contract.get("optional") or ()):
            tok = types.get(field, "any")
            if tok in ("list", "any") or tok is None:
                yield top_field, field, tok or "any"
        return
    elem = contract["elements"][top_field]
    types = elem.get("types") or {}
    for field in list(elem.get("required") or []) + list(elem.get("optional") or ()):
        tok = types.get(field, "any")
        if tok in ("list", "any") or tok is None:
            yield top_field, field, tok or "any"


def test_strict_mode_refinement_table_covers_all_unrefinable_binding_fields():
    needing = []
    for phase, top_field in _CONSUMED_PHASES:
        needing.extend(_iter_binding_fields_needing_refinement(phase, top_field))
    assert needing, "expected at least one unrefinable field in consumed bindings"
    for result_kind, field, _tok in needing:
        assert (result_kind, field) in ERC._STRICT_MODE_REFINEMENTS


def test_unrefined_list_token_raises_at_schema_build():
    with pytest.raises(ERC.UnrefinedTypeTokenError, match="no strict-mode refinement"):
        ERC._strict_schema_for_field("synthetic", "orphan", "list")


def test_validate_none_schema_refuses():
    ok, reason = ERC.validate(None, {"anything": True})
    assert not ok
    assert "schema is None" in reason


def test_ruling_new_issues_detailed_entry_validates_and_survives_grading(tmp_path):
    # axis: ruling newIssues with detailed entry validates and survives native grading
    ed = _load("engine_dispatch")

    new_issue = _example_finding_member()
    new_issue["title"] = "Detailed new issue from audit"
    new_issue["body"] = "Concrete defect description"
    branch = _valid_review_branch("ruling")
    branch["newIssues"] = [new_issue]
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, "ruling")
    ok, reason = ERC.validate(schema, _wrap_result(branch))
    assert ok, reason

    run_dir = str(tmp_path / "run")
    repo_root = os.path.join(_HERE, "..", "..", "..")
    os.makedirs(run_dir, exist_ok=True)
    schema_path = os.path.join(run_dir, ed.NATIVE_SCHEMA_NAME)
    result_path = ed._native_result_path(run_dir, 1)
    with open(schema_path, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, separators=(",", ":"))
        fh.write("\n")
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(_wrap_result(branch), fh, separators=(",", ":"))
        fh.write("\n")
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    opened = {
        "engine": "codex",
        "roleKind": ERC.RUN_KIND_REVIEW,
        "cwd": repo_root,
        "fedPrompt": "",
        "channel": ERC.CHANNEL_NATIVE,
        "nativeSchemaPath": schema_path,
        "expectedResultKind": "ruling",
    }
    envelope = _wrap_result(branch)
    scrubbed = ed._scrub_native_payload(envelope)
    ended = {
        "exit": 0, "timedOut": False, "refusal": None,
        "stdoutBytes": 0, "wallSeconds": 1.0,
    }
    ended.update(ERC.completion_stamp(1.0, ERC.canonical_payload_digest(scrubbed)))
    ed._journal_append(run_dir, {"kind": "attempt-ended", "attempt": 1, **ended})
    state = {
        "opened": opened,
        "attempts": {1: {"ended": ended}},
    }
    grade = ed._grade_review_attempt(run_dir, state, 1)
    assert grade.get("ok") is True
    assert grade["ruling"]["newIssues"][0]["title"] == "Detailed new issue from audit"


def test_ruling_branch_fields_match_audits_binding():
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None
    expected = list(contract.get("required") or []) + list(contract.get("optional") or ())
    assert ERC._ruling_branch_fields() == expected


def test_review_result_contract_from_schema_names_root_result_envelope():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    contract = ERC.review_result_contract_from_schema(schema)
    assert "single `result` property" in contract
    assert "`resultKind`" in contract
    assert "`investigated`" in contract
    for kind in ERC.REVIEW_RESULT_KINDS:
        assert "`%s`" % kind in contract


def test_review_result_contract_from_schema_derives_kind_list_from_schema():
    schema = ERC.declared_schema(
        "codex", ERC.RUN_KIND_REVIEW, expected_result_kind="verdicts",
    )
    contract = ERC.review_result_contract_from_schema(schema)
    assert "`verdicts`" in contract
    assert "`findings`" not in contract.split("`verdicts`", 1)[0]


def test_review_result_contract_from_schema_lists_active_payload_properties():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="ruling")
    contract = ERC.review_result_contract_from_schema(schema)
    for field in ERC._ruling_branch_fields():
        assert "`%s`" % field in contract


def test_write_report_contract_bytes_unchanged_by_field_semantics_lift():
    import hashlib
    assert hashlib.sha256(EA.WRITE_REPORT_CONTRACT.encode()).hexdigest() == (
        "09e850054142c4f2eee6daee3481061799e4f0584184769f3f9f6b9ebebbd911"
    )


def test_write_result_contract_lists_schema_required_and_omits_sentinel():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    contract = ERC.write_result_contract_from_schema(schema)
    for key in schema.get("required") or []:
        assert "`%s`" % key in contract
    assert EA.WRITE_REPORT_SENTINEL not in contract
    assert EA.WRITE_REPORT_FIELD_SEMANTICS.strip() in contract


def test_verdict_reason_required_in_contract_and_schema():
    contract, _ = PC.payload_contract(PC.P_VERIFIERS)
    elem = contract["elements"]["verdicts"]
    assert "reason" in elem["required"]
    assert elem["types"]["reason"] == "non-empty-string"
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="verdicts")
    branch = _valid_review_branch("verdicts")
    branch["verdicts"][0].pop("reason", None)
    ok, _reason = ERC.validate(schema, _wrap_result(branch))
    assert not ok
    branch["verdicts"][0]["reason"] = "x"
    ok, _reason = ERC.validate(schema, _wrap_result(branch))
    assert ok


def _malformed_ruling_branch_with_spurious_findings_list():
    """Ruling branch that structurally matches findings via a present-but-null key."""
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None
    ruling_val = contract["enums"]["ruling"][0]
    return {
        "resultKind": "ruling",
        "findings": None,
        "verdicts": None,
        "investigated": ["path/to/file.py"],
        "id": "audit-seat",
        "ruling": ruling_val,
        "reason": "grounds",
    }


def test_native_branch_narrowing_consults_payload_key_home_for_ruling():
    # axis: ruling is narrowed like every other kind — not exempt by omission
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_h_payload_key_home.md
    branch = _malformed_ruling_branch_with_spurious_findings_list()
    assert "ruling" in EA._recognised_review_kinds(branch)
    assert "findings" in EA._recognised_review_kinds(branch)
    shape = ERC.native_review_payload_shape(
        "native-result-schema-invalid", branch=branch)
    assert shape["parsed"] != EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS
    assert [
        k for k in EA._recognised_review_kinds(branch)
        if (key := EA.review_payload_key(k)) is not None
        and branch.get(key) is not None
    ] == ["ruling"]


def test_native_branch_narrowing_null_payload_key_not_carried():
    # axis: present-but-null payload keys for covered kinds stop matching
    branch = _valid_review_branch("ruling")
    assert "verdicts" in EA._recognised_review_kinds(branch)
    assert EA.review_payload_carried(branch, "verdicts") == (False, None)
    narrowed = [
        k for k in EA._recognised_review_kinds(branch)
        if EA.review_payload_carried(branch, k)[0]
    ]
    assert "verdicts" not in narrowed


def test_native_branch_narrowing_present_but_null_grouping_not_second_kind():
    # axis: present-but-null grouping key does not count as a second matched kind
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_h_payload_key_home.md
    branch = _valid_review_branch("findings")
    assert "grouping" in EA._recognised_review_kinds(branch)
    assert EA.review_payload_carried(branch, "grouping") == (True, None)
    shape = ERC.native_review_payload_shape(
        "native-result-schema-invalid", branch=branch)
    assert shape["parsed"] != EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS


def test_engine_output_byte_cap_single_home():
    # axis: ENGINE_OUTPUT_MAX_BYTES is the single literal home for the 8 MiB cap
    home = EA.ENGINE_OUTPUT_MAX_BYTES
    ed = _load("engine_dispatch")
    assert ERC.NATIVE_RESULT_MAX_BYTES == home
    assert ed.MAX_STDOUT_CAPTURE == home
    assert home == 8 * 1024 * 1024


# --- result completion contract (#1273 WO-A) ---

_DIGEST_X = ERC.payload_digest(b"x")


def _completion_record(mono_at, digest=_DIGEST_X, **extra):
    stamp = ERC.completion_stamp(mono_at, digest)
    assert stamp is not None
    record = dict(stamp)
    record.update(extra)
    return record


def test_mono_epoch_stable_and_non_empty():
    first = ERC.mono_epoch()
    second = ERC.mono_epoch()
    assert isinstance(first, str)
    assert first
    assert first == second


def test_payload_digest_bytes_and_str_agree():
    digest = ERC.payload_digest(b"x")
    assert digest == ERC.payload_digest("x")
    assert digest == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"


def test_payload_digest_returns_none_for_non_bytes_str():
    assert ERC.payload_digest(1) is None
    assert ERC.payload_digest(None) is None


def test_payload_digest_surrogate_string_never_raises():
    lone = "a\ud800b"
    digest = ERC.payload_digest(lone)
    assert digest is not None
    assert len(digest) == 64


@pytest.mark.parametrize("mono_at,deadline_mono", [
    (10.0, 20.0),
    (15.0, 15.0),
])
def test_completion_stamp_round_trips_through_completion_window(mono_at, deadline_mono):
    ended = _completion_record(mono_at)
    ended.update(ERC.deadline_stamp(deadline_mono))
    assert ERC.completion_window(ended, _DIGEST_X) == ("admit", None)


def test_completion_window_no_deadline_key():
    ended = _completion_record(10.0)
    assert ERC.completion_window(ended, _DIGEST_X) == ("no-deadline", None)


@pytest.mark.parametrize("ended", [None, [], "x"])
def test_completion_window_non_dict_ended_forfeits_unrecorded(ended):
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_empty_dict_forfeits_unrecorded():
    assert ERC.completion_window({}, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_missing_completion_epoch_forfeits_unrecorded():
    ended = _completion_record(10.0)
    del ended[ERC.FIELD_RESULT_COMPLETE_EPOCH]
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_epoch_mismatch_forfeits_unrecorded():
    ended = _completion_record(10.0)
    ended.update(ERC.deadline_stamp(20.0))
    ended[ERC.FIELD_DEADLINE_EPOCH] = ended[ERC.FIELD_DEADLINE_EPOCH] + "-other"
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_bool_complete_at_forfeits_unrecorded():
    ended = {
        ERC.FIELD_RESULT_COMPLETE_AT: True,
        ERC.FIELD_RESULT_COMPLETE_EPOCH: ERC.mono_epoch(),
        ERC.FIELD_RESULT_COMPLETE_SHA256: _DIGEST_X,
        ERC.FIELD_DEADLINE_MONO: 20.0,
        ERC.FIELD_DEADLINE_EPOCH: ERC.mono_epoch(),
    }
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_bool_deadline_mono_forfeits_unrecorded():
    ended = _completion_record(10.0)
    ended[ERC.FIELD_DEADLINE_MONO] = False
    ended[ERC.FIELD_DEADLINE_EPOCH] = ended[ERC.FIELD_RESULT_COMPLETE_EPOCH]
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_equality_at_deadline_admits():
    ended = _completion_record(15.0)
    ended.update(ERC.deadline_stamp(15.0))
    assert ERC.completion_window(ended, _DIGEST_X) == ("admit", None)


def test_completion_window_deadline_without_completion_forfeits_unrecorded():
    ended = {ERC.FIELD_DEADLINE_MONO: 20.0, ERC.FIELD_DEADLINE_EPOCH: ERC.mono_epoch()}
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


@pytest.mark.parametrize("bad_payload", [
    None,
    "",
    "A" * 64,
    "a" * 63,
])
def test_completion_window_bad_payload_sha256_forfeits_mismatch(bad_payload):
    ended = _completion_record(10.0)
    assert ERC.completion_window(ended, bad_payload) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_PAYLOAD_MISMATCH,
    )


def test_completion_window_valid_different_digest_forfeits_payload_mismatch():
    ended = _completion_record(10.0, digest=_DIGEST_X)
    digest_b = ERC.payload_digest(b"y")
    assert digest_b is not None
    assert digest_b != _DIGEST_X
    assert ERC.completion_window(ended, digest_b) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_PAYLOAD_MISMATCH,
    )


def test_completion_window_nested_complete_at_forfeits_unrecorded():
    ended = {
        ERC.FIELD_RESULT_COMPLETE_AT: {"a": 1},
        ERC.FIELD_RESULT_COMPLETE_EPOCH: ERC.mono_epoch(),
        ERC.FIELD_RESULT_COMPLETE_SHA256: _DIGEST_X,
    }
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
    )


def test_completion_window_after_deadline_forfeits():
    ended = _completion_record(25.0)
    ended.update(ERC.deadline_stamp(20.0))
    assert ERC.completion_window(ended, _DIGEST_X) == (
        "forfeit", ERC.REFUSAL_RESULT_COMPLETION_AFTER_DEADLINE,
    )


@pytest.mark.parametrize("mono_now", [True, False, "x", None, {}])
def test_completion_stamp_bad_mono_now_returns_none(mono_now):
    assert ERC.completion_stamp(mono_now, _DIGEST_X) is None


@pytest.mark.parametrize("digest", [None, "", "A" * 64, "a" * 63, 1])
def test_completion_stamp_bad_digest_returns_none(digest):
    assert ERC.completion_stamp(10.0, digest) is None


@pytest.mark.parametrize("mono_deadline", [True, False, "x", None, {}])
def test_deadline_stamp_bad_mono_deadline_returns_none(mono_deadline):
    assert ERC.deadline_stamp(mono_deadline) is None


# --- canonical_payload_digest (#1273 WO-B) ---


def test_canonical_payload_digest_stable_across_key_order():
    first = ERC.canonical_payload_digest({"a": 1, "b": 2})
    second = ERC.canonical_payload_digest({"b": 2, "a": 1})
    assert first is not None
    assert first == second


def test_canonical_payload_digest_literal():
    # axis: the literal hex is the cross-process contract for canonical_payload_digest
    payload = {
        "z": "café",
        "a": {"nested": True},
        "m": [1, "two", {"three": 3}],
        "b": 2,
    }
    assert ERC.canonical_payload_digest(payload) == (
        "2b185d042f72ca66e7d6e6d19e9c6fb8ef2c3f124ab59b41a4ef585fc4814bef"
    )


@pytest.mark.parametrize("bad_obj", [
    [],
    "x",
    {"nested": {1, 2}},
    {"value": float("nan")},
])
def test_canonical_payload_digest_returns_none_for_edge_one_inputs(bad_obj):
    assert ERC.canonical_payload_digest(bad_obj) is None


@pytest.mark.parametrize("bad_digest", [
    "+" + "a" * 63,
    "a_" + "a" * 62,
    "A" * 64,
    "a" * 63,
    "a" * 65,
    1,
])
def test_is_valid_sha256_hex_rejects_non_canonical_shapes(bad_digest):
    assert ERC._is_valid_sha256_hex(bad_digest) is False


def test_is_valid_sha256_hex_accepts_hashlib_output():
    digest = ERC.payload_digest(b"x")
    assert ERC._is_valid_sha256_hex(digest) is True
