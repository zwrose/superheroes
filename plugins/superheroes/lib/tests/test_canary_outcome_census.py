"""Static AST census: canary-native non-pass outcome literals stay in canary_outcome.py (#1247).

The live sweep bans only the canary-native non-pass members (`not-engaged`,
`plant-undetected`). The pass token `ok` is excluded from the live sweep because it is
ubiquitous elsewhere (e.g. dispatch results `{"ok": true}`); it is proven instead by
``test_matcher_catches_ok_literal_on_synthetic_source``, which runs the matcher with
``member_set=ALL_OUTCOMES``. Re-exported dispatch-failure members are homed in
``dispatch_outcome.py``. A banned member literal is a violation in any syntactic position
— dict keys and ``.get()`` arguments are not exempt.
"""
import ast
import glob
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
_PLUGIN_ROOT = os.path.realpath(os.path.join(_LIB, ".."))
_REPO_ROOT = os.path.realpath(os.path.join(_PLUGIN_ROOT, "..", ".."))
_EVAL = os.path.join(_PLUGIN_ROOT, "eval")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import canary_outcome  # noqa: E402
import dispatch_outcome  # noqa: E402
import round_driver  # noqa: E402

_CANARY_OUTCOME_PATH = os.path.join(_LIB, "canary_outcome.py")
_EXEMPT_MODULE = "canary_outcome.py"
# CONTROL_PROBE reads vocabulary collides with canary OUTCOME_NOT_ENGAGED — unrelated domain.
_LITERAL_EXEMPT_BASENAMES = frozenset({"package_read_audit.py"})
_AUTO_FIX_LOOP = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md")
_ROUND_DRIVER = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")
# axis: canary-native outcomes the probe section scores on two axes
_AUTO_FIX_LOOP_MEMBERS = frozenset({
    canary_outcome.OUTCOME_NOT_ENGAGED,
    canary_outcome.OUTCOME_PLANT_UNDETECTED,
})
# axis: every non-pass outcome maps to a disclosure or dead/unproven status at fold
_ROUND_DRIVER_MEMBERS = canary_outcome.NON_PASS_OUTCOMES
_LIVE_BANNED_LITERALS = frozenset({
    canary_outcome.OUTCOME_NOT_ENGAGED,
    canary_outcome.OUTCOME_PLANT_UNDETECTED,
})


def _lineno(source_path, node):
    return "%s:%d" % (os.path.basename(source_path), node.lineno)


def _parse_source(source, source_path):
    try:
        return ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (source_path, exc)
        ) from exc


def census_violations_from_source(source, source_path, *, member_set=None):
    if member_set is None:
        member_set = _LIVE_BANNED_LITERALS
    tree = _parse_source(source, source_path)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if node.value not in member_set:
            continue
        violations.append(
            "%s: literal '%s' (clause: canary-native non-pass outcome literals live only "
            "in canary_outcome.py regardless of syntactic position; the pass token is "
            "excluded from the live sweep — see module docstring)"
            % (_lineno(source_path, node), node.value)
        )
    return violations


def census_violations(source_path, *, member_set=None):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    return census_violations_from_source(source, source_path, member_set=member_set)


def _repo_rel(abs_path):
    return os.path.relpath(abs_path, _REPO_ROOT).replace(os.sep, "/")


def _consumer_module_paths():
    paths = []
    for pattern in (
        os.path.join(_LIB, "*.py"),
        os.path.join(_EVAL, "*.py"),
    ):
        paths.extend(glob.glob(pattern))
    paths = [
        p for p in paths
        if os.path.basename(p) != _EXEMPT_MODULE
    ]
    paths.sort()
    return paths


def _imports_canary_outcome(source_path):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, source_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "canary_outcome":
                    return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "canary_outcome":
                return True
    return False


def _derived_consumers():
    return frozenset(
        _repo_rel(p) for p in _consumer_module_paths()
        if _imports_canary_outcome(p)
    )


def _literal_census_modules():
    """Modules that must not spell canary outcome literals outside canary_outcome.py."""
    modules = []
    for pattern in (
        os.path.join(_LIB, "*.py"),
        os.path.join(_EVAL, "*.py"),
    ):
        for path in glob.glob(pattern):
            if os.path.basename(path) == _EXEMPT_MODULE:
                continue
            if os.path.basename(path) in _LITERAL_EXEMPT_BASENAMES:
                continue
            modules.append(path)
    modules.sort()
    return modules


def _outcome_member_from_assign(node, members):
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign):
        if not isinstance(node.target, ast.Name):
            return
        targets = [node.target]
        value = node.value
    else:
        return
    for target in targets:
        if not isinstance(target, ast.Name):
            continue
        if not target.id.startswith("OUTCOME_"):
            continue
        if value is not None and isinstance(value, ast.Constant) and isinstance(value.value, str):
            members.add(value.value)


def _outcome_members_from_ast(source_path=_CANARY_OUTCOME_PATH):
    with open(source_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=source_path)
    members = set()
    for node in tree.body:
        _outcome_member_from_assign(node, members)
    dispatch_members = set(dispatch_outcome.NOT_RUN_REASONS)
    return members | dispatch_members


def _minimal_probe(outcome, *, engaged=True, detected_plant=True):
    return {
        "engine": "codex",
        "outcome": outcome,
        "engaged": engaged,
        "detectedPlant": detected_plant,
        "evidence": {},
        "detail": "probe-detail",
    }


def _probe_for_outcome(outcome):
    if outcome == canary_outcome.OUTCOME_PLANT_UNDETECTED:
        return _minimal_probe(outcome, engaged=True, detected_plant=False)
    if outcome == canary_outcome.OUTCOME_NOT_ENGAGED:
        return _minimal_probe(outcome, engaged=False, detected_plant=False)
    return _minimal_probe(outcome, engaged=False, detected_plant=False)


def _load_fabricate():
    import importlib.util
    eval_dir = os.path.join(_PLUGIN_ROOT, "eval")
    saved = list(sys.path)
    try:
        if eval_dir not in sys.path:
            sys.path.insert(0, eval_dir)
        spec_path = os.path.join(eval_dir, "review_loop_runner.py")
        spec = importlib.util.spec_from_file_location(
            "review_loop_runner_census", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.fabricate_canary_probes_for
    finally:
        sys.path[:] = saved


def _canary_liveness_for_probe(probe):
    dims = ["code-reviewer"]
    status = {"code-reviewer": "run"}
    seats = {"code-reviewer": {"findings": []}}
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex"}}}
    return round_driver.canary_liveness(
        dims, status, seats, seat_map, {}, probe)


def test_outcome_members_from_ast_includes_annotated_constant(tmp_path):
    """axis: annotated OUTCOME_* declarations are included in the derived member set."""
    path = tmp_path / "fake_canary_outcome_typed.py"
    path.write_text('OUTCOME_TYPED: str = "typed"\n', encoding="utf-8")
    derived = _outcome_members_from_ast(source_path=str(path))
    assert "typed" in derived


def test_normalize_declared_non_pass_never_upgrades_to_pass():
    """axis: no declared non-pass member normalizes to a pass member when fields imply pass."""
    for outcome in canary_outcome.NON_PASS_OUTCOMES:
        probe = _minimal_probe(outcome, engaged=True, detected_plant=True)
        norm_outcome, fault = canary_outcome.normalize(probe)
        assert not canary_outcome.is_pass(norm_outcome), (
            "declared %r with engaged/detected must not normalize to pass; got %r (fault=%r)"
            % (outcome, norm_outcome, fault)
        )


def test_normalize_declared_ok_with_refusing_fields_reredives_downward():
    """axis: declared ok with refusing fields still re-derives downward."""
    probe = _minimal_probe(canary_outcome.OUTCOME_OK, engaged=False, detected_plant=False)
    norm_outcome, fault = canary_outcome.normalize(probe)
    assert norm_outcome == canary_outcome.OUTCOME_NOT_ENGAGED
    assert fault == "canary-outcome-contradicts-fields"


def test_contradictory_plant_undetected_probe_folds_dead():
    """axis: plant-undetected with engaged not true normalizes to not-engaged and folds dead."""
    probe = {
        "engine": "codex",
        "outcome": canary_outcome.OUTCOME_PLANT_UNDETECTED,
        "engaged": False,
        "detectedPlant": False,
        "evidence": {},
        "detail": "contradictory probe",
    }
    live = _canary_liveness_for_probe(probe)
    assert live["byVendor"]["codex"]["status"] == "dead"


def test_leg1_member_set_derived():
    """axis: a member absent from ALL_OUTCOMES is caught."""
    derived = _outcome_members_from_ast()
    assert derived == canary_outcome.ALL_OUTCOMES, (
        "ALL_OUTCOMES must equal every OUTCOME_* constant plus re-exported dispatch reasons; "
        "derived=%r declared=%r"
        % (sorted(derived), sorted(canary_outcome.ALL_OUTCOMES))
    )
    assert canary_outcome.PASS_OUTCOMES == frozenset({canary_outcome.OUTCOME_OK})
    assert canary_outcome.NON_PASS_OUTCOMES == (
        canary_outcome.ALL_OUTCOMES - canary_outcome.PASS_OUTCOMES)


def test_leg2_consumer_set_derived():
    """axis: an unregistered consumer is caught."""
    derived = _derived_consumers()
    assert derived == canary_outcome.CONSUMERS, (
        "CONSUMERS must equal every module that imports canary_outcome; "
        "derived=%r declared=%r"
        % (sorted(derived), sorted(canary_outcome.CONSUMERS))
    )


def test_leg3_literal_ban_clean():
    """axis: a token spelled outside its home is caught."""
    violations = []
    for path in _literal_census_modules():
        violations.extend(census_violations(path))
    assert violations == [], (
        "INVARIANT: canary-native non-pass outcome literals live only in canary_outcome.py; "
        "violations:\n  "
        + "\n  ".join(violations)
    )


def test_matcher_catches_ok_literal_on_synthetic_source():
    """Prove the matcher would catch \"ok\" even though the live census excludes it."""
    source = (
        "def bad():\n"
        "    return \"ok\"\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(
        source, path, member_set=canary_outcome.ALL_OUTCOMES)
    assert violations, violations
    assert any("'ok'" in v for v in violations), violations


def test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source():
    """axis: a banned member spelled as a dict key is reported."""
    source = (
        "def bad():\n"
        "    return {\"plant-undetected\": 1}\n"
    )
    path = os.path.join(_LIB, "fake_consumer_dict_key.py")
    violations = census_violations_from_source(
        source, path, member_set=canary_outcome.ALL_OUTCOMES)
    assert violations, violations
    assert any("'plant-undetected'" in v for v in violations), violations


def test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source():
    """axis: a banned member spelled as a .get() argument is reported."""
    source = (
        "def bad(probe):\n"
        "    return probe.get(\"not-engaged\")\n"
    )
    path = os.path.join(_LIB, "fake_consumer_get_arg.py")
    violations = census_violations_from_source(
        source, path, member_set=canary_outcome.ALL_OUTCOMES)
    assert violations, violations
    assert any("'not-engaged'" in v for v in violations), violations


def test_matcher_one_violation_per_occurrence_on_synthetic_source():
    """axis: duplicate literals yield one violation each, not one per file or value."""
    source = (
        "def bad():\n"
        "    a = \"not-engaged\"\n"
        "    b = \"not-engaged\"\n"
    )
    path = os.path.join(_LIB, "fake_consumer_dup.py")
    violations = census_violations_from_source(
        source, path, member_set=canary_outcome.ALL_OUTCOMES)
    assert len(violations) == 2, violations


def test_matcher_ignores_non_str_constants_on_synthetic_source():
    """axis: non-str constants are not census violations."""
    source = (
        "def bad():\n"
        "    return 42\n"
    )
    path = os.path.join(_LIB, "fake_consumer_int.py")
    violations = census_violations_from_source(
        source, path, member_set=canary_outcome.ALL_OUTCOMES)
    assert violations == [], violations


def test_leg4_non_pass_fail_closed_cross_product():
    """axis: a consumer that passes a non-pass member is caught."""
    non_pass = sorted(canary_outcome.NON_PASS_OUTCOMES)
    assert non_pass, "NON_PASS_OUTCOMES cross-product must be non-empty"
    covered = set()
    for outcome in non_pass:
        covered.add(outcome)
        assert canary_outcome.is_pass(outcome) is False
        live = _canary_liveness_for_probe(_probe_for_outcome(outcome))
        assert live["byVendor"]["codex"]["status"] != "proven", outcome
    assert covered == canary_outcome.NON_PASS_OUTCOMES

    fabricate = _load_fabricate()
    probes = fabricate({"seats": {"x": {"vendor": "codex"}}})
    assert len(probes) == 1
    norm_outcome, _fault = canary_outcome.normalize(probes[0])
    assert canary_outcome.is_pass(norm_outcome), (
        "fabricate_canary_probes_for must normalize to pass; got %r" % (norm_outcome,))

    live_ok = _canary_liveness_for_probe(_minimal_probe(canary_outcome.OUTCOME_OK))
    assert live_ok["byVendor"]["codex"]["status"] == "proven"

    live_unknown = _canary_liveness_for_probe({
        "engine": "codex",
        "outcome": "not-a-real-outcome",
        "engaged": True,
        "detectedPlant": False,
        "evidence": {},
        "detail": "unknown-outcome",
    })
    assert live_unknown["byVendor"]["codex"]["status"] != "proven"

    live_malformed = round_driver.canary_liveness(
        ["code-reviewer"], {"code-reviewer": "run"},
        {"code-reviewer": {"findings": []}},
        {"seats": {"code-reviewer": {"vendor": "codex"}}}, {}, "not-a-mapping")
    assert live_malformed["byVendor"]["codex"]["status"] != "proven"

    live_missing_keys = _canary_liveness_for_probe({"engine": "codex"})
    assert live_missing_keys["byVendor"]["codex"]["status"] != "proven"


def test_leg5_vocabulary_sweep_docs():
    """axis: a member the docs never name is caught."""
    with open(_AUTO_FIX_LOOP, encoding="utf-8") as fh:
        auto_doc = fh.read()
    with open(_ROUND_DRIVER, encoding="utf-8") as fh:
        round_doc = fh.read()
    missing_auto = sorted(m for m in _AUTO_FIX_LOOP_MEMBERS if m not in auto_doc)
    missing_round = sorted(m for m in _ROUND_DRIVER_MEMBERS if m not in round_doc)
    assert missing_auto == [], (
        "auto-fix-loop.md missing canary-native outcome member(s): %s"
        % ", ".join(missing_auto)
    )
    assert missing_round == [], (
        "round-driver.md missing non-pass outcome member(s): %s"
        % ", ".join(missing_round)
    )
