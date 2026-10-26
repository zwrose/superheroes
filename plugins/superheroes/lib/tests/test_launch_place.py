# plugins/superheroes/lib/tests/test_launch_place.py
"""Conformance: the routing decision and the eight reasons. Every store, account file, repository
and record is built under tmp_path; the reviewer-pass command runs against a clipboard recorder; no
test touches the real home directory, clock, clipboard or network. Requirement numbers in the test
names are for the reader."""
import base64
import datetime
import functools
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import architect_config  # noqa: E402
import cloud_check  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_plugin_pin  # noqa: E402
import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import core_md as CM  # noqa: E402
import definition_doc  # noqa: E402
import launch_place as LP  # noqa: E402
import mode_registry  # noqa: E402
import project_config as PC  # noqa: E402
import store_core  # noqa: E402

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

ACCOUNT = "acct-fixture-one"
OTHER_ACCOUNT = "acct-fixture-two"
ENVIRONMENT = "env-fixture-one"
STAMP = "sha256:" + "ab" * 32
ADVISOR = "1.2.3"
TODAY = datetime.date(2026, 10, 11)
FUTURE = "2026-12-01"
PAST = "2026-10-10"
POLICY_OK = {"schemaVersion": 2, "location": "docs/superheroes", "visibility": "committed",
             "confirmed": True, "disclosures": []}
PHONE = "the phone simulator"
CANON = "this project's Canon"
SPECS = "this project's specs"
BOTH = "this project's Canon and specs"
SETUP_TEXT_FIX = ('To fix it, paste the new setup text into the environment. '
                  'Say "setup text" and I\'ll write it.')


def _needs_text(need):
    return "It needs %s, which only your machine has." % need


# ---------------------------------------------------------------- fixtures: fakes


def _now(ready=True, reason=None, setting=True, cloud=ADVISOR, advisor=ADVISOR,
         environment=ENVIRONMENT, checked=None, conditions=None):
    if conditions is None:
        conditions = {name: True for name in CR.CONDITION_ORDER}
        for name, code in CR.REASON_FOR.items():
            if code == reason:
                conditions[name] = False
    return {"ready": ready, "reason": reason, "conditions": conditions, "setting": setting,
            "account": ACCOUNT, "environment": environment, "cloudVersion": cloud,
            "advisorVersion": advisor, "picksUpVersion": False, "checkedAt": checked}


def _fn(**kw):
    def readiness(cwd, reported=None, root=None, env=None):
        return _now(**kw)
    return readiness


def _no_needs(cwd, premise, root=None):
    return []


def _needs(*things):
    def needs(cwd, premise, root=None):
        return list(things)
    return needs


def _call(place="local", pointed=True, reason=None, by="setting", need=None, cloud=None,
          advisor=None, environment=None, reported=None, failed=None):
    return {"place": place, "pointedAtCloud": pointed, "by": by, "reason": reason, "need": need,
            "cloudVersion": cloud, "advisorVersion": advisor, "environment": environment,
            "reported": reported, "failedCheck": failed}


PLACE_KEYS = {"place", "pointedAtCloud", "by", "reason", "need", "cloudVersion",
              "advisorVersion", "environment", "reported", "failedCheck", "hookGap"}


# ---------------------------------------------------------------- fixtures: stores and worlds


def _store_dir(repo, store):
    return mode_registry.project_store_dir(repo, store)


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _world(base, *, policy=POLICY_OK, canon="repo", mode=mode_registry.IN_REPO, spec=False,
           registry_text=None):
    """A git repository and a store. By default the Canon, the specs and the mode are all in the
    repository; each keyword moves one of them out."""
    repo = str(base / "repo")
    store = str(base / "store")
    subprocess.run(["git", "init", "-q", repo], check=True)
    sdir = _store_dir(repo, store)
    os.makedirs(sdir, exist_ok=True)
    if policy is not None:
        text = policy if isinstance(policy, str) else json.dumps(policy)
        _put(architect_config.policy_path(repo, store), text)
    if canon == "repo":
        _put(os.path.join(repo, "docs", "superheroes", definition_doc.CANON_FILE), "canon\n")
    elif canon == "store":
        _put(os.path.join(sdir, "docs", definition_doc.CANON_FILE), "canon\n")
    if registry_text is not None:
        _put(mode_registry.registry_path(repo, store), registry_text)
    elif mode is not None:
        remote_key = store_core.derive_identifiers(repo)["remote_hash"]
        assert mode_registry.write_registry(repo, mode, remote_key, store) is not None
    if spec:
        _put(os.path.join(sdir, "docs", "some-work-item", "spec.md"), "spec\n")
    return repo, store


@pytest.fixture(scope="module")
def inrepo(tmp_path_factory):
    return _world(tmp_path_factory.mktemp("inrepo"))


def _sub(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


def _join(things):
    if len(things) <= 1:
        return "".join(things)
    return ", ".join(things[:-1]) + " and " + things[-1]


def _tree(path):
    seen = {}
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            seen[full] = open(full, "rb").read() if os.path.isfile(full) else None
    return seen


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _record(repo, store, **over):
    values = {
        "account": ACCOUNT, "environment": ENVIRONMENT, "plugin_version": ADVISOR,
        "picks_up_version": False, "calibration_stamp": STAMP,
        "calibration_date": "2026-10-01", "pass_lapses": FUTURE, "checked_at": "2026-10-09",
    }
    values.update(over)
    got = CS.record_check(repo, root=store, **values)
    assert got["action"] in ("written", "noop"), got
    return got


def _account_env(tmp_path, account=ACCOUNT):
    home = tmp_path / ("home-" + account)
    home.mkdir(exist_ok=True)
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}}), encoding="utf-8")
    return {"HOME": str(home)}


def _on(tmp_path, **over):
    """A project with a passed check, cloud builds switched on, and the account's environment."""
    repo, store = _setup_repo(tmp_path)
    _record(repo, store, **over)
    assert PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)["action"] == "written"
    return repo, store, _account_env(tmp_path)


def _real(**over):
    args = {"advisor_version": ADVISOR, "today": TODAY, "stamp_fn": lambda cwd, root: STAMP}
    args.update(over)
    return functools.partial(CR.readiness, **args)


def _route(repo, store, env, premise=None, word=None, **kw):
    kw.setdefault("readiness_fn", _real())
    kw.setdefault("needs_fn", _no_needs)
    return LP.route(repo, premise if premise is not None else {}, word, root=store, env=env, **kw)


# ---------------------------------------------------------------- the table


def test_the_eight_reasons_are_the_boards_words():
    assert LP.REASON_CODES[:2] == ("local-word", "needs")
    # the not-ready reasons are exactly the ones the readiness check can give
    assert set(LP.NOT_READY_CODES) == set(CR.REASON_FOR.values())
    assert set(LP.REASON_CODES[2:]) == set(LP.NOT_READY_CODES)
    assert set(LP.REASONS) == set(LP.REASON_CODES)
    assert (LP.LOCAL_WORD, LP.CLOUD_WORD) == ("local", "cloud")
    fix_pass = ('To fix it, run the pass command on your machine, paste the %spass into the '
                'environment and say "check again".')
    assert LP.REASONS == {
        "local-word": {"words": 'You said "this one local".', "fix": None, "short": None,
                       "wasnt": None},
        "needs": {"words": "It needs {need}, which only your machine has.", "fix": None,
                  "short": None, "wasnt": None},
        "pass-lapsed": {
            "words": "The reviewer pass has lapsed.", "fix": fix_pass % "new ",
            "short": 'Paste a fresh pass and say "check again" to fix it.',
            "wasnt": "the reviewer pass has lapsed."},
        "no-pass": {
            "words": "There is no reviewer pass in the cloud environment.", "fix": fix_pass % "",
            "short": 'Paste a pass into the environment and say "check again" to fix it.',
            "wasnt": "there is no reviewer pass in the cloud environment."},
        "no-setup": {
            "words": "This project has no cloud setup on this Claude account.",
            "fix": 'Say "set up cloud builds" and I\'ll walk you through it.',
            "short": 'Say "set up cloud builds" to fix it.',
            "wasnt": "this project has no cloud setup on this Claude account."},
        "version": {
            "words": "The cloud's plugin is {cloud} and mine is {advisor}.",
            "fix": SETUP_TEXT_FIX, "short": "Paste the new setup text to fix it.",
            "wasnt": "its plugin is {cloud} and mine is {advisor}."},
        "calibration": {
            "words": "The cloud's calibration doesn't match this machine's.",
            "fix": SETUP_TEXT_FIX, "short": "Paste the new setup text to fix it.",
            "wasnt": "its calibration doesn't match this machine's."},
        "plugin-pin": {
            "words": ("The plugin pin on the branch this build starts from doesn't name the plugin "
                      "I run, or its pin hook is broken."),
            "fix": ("To fix it, run cloud_plugin_pin.py write on this machine (it pins the plugin "
                    "I run), commit and push the files it names on the branch the build starts "
                    "from, then launch again."),
            "short": "Commit a current plugin pin on the starting branch to fix it.",
            "wasnt": "the plugin pin on the branch it starts from doesn't name my plugin."},
        "dependency-hook": {
            "words": ("The branch this build starts from doesn't carry the dependency hook, or "
                      "a setup file the build adopts can't be shown unchanged since the hook ran "
                      "(it changed, or it is a link), so the cloud could build it with "
                      "out-of-date dependencies."),
            "fix": ("To fix it, commit and push the dependency hook files configure wrote (the "
                    "settings file and the hook script) on the branch the build starts from; if "
                    "the build adopts a branch that changed a dependency file, bring that change "
                    "into the branch it starts from first. A listed setup file that is a link or "
                    "sits under a linked folder cannot be compared, so point both the setup "
                    "command and configure's setup inputs at the regular file itself, with no "
                    "link in between. Then launch again."),
            "short": ("Bring the dependency hook and any adopted setup-file change onto the "
                      "starting branch, and list setup files as regular files, to fix it."),
            "wasnt": ("the branch it starts from doesn't carry the dependency hook, or a setup "
                      "file it adopts can't be shown unchanged.")},
        "unreachable": {
            "words": "The cloud platform couldn't be reached.",
            "fix": "I'll try the cloud again at the next launch.",
            "short": "I'll try the cloud again at the next launch.",
            "wasnt": "the cloud platform couldn't be reached."},
    }


def test_reason_text_renders_each_code_and_fills_unknown_versions():
    assert LP.reason_text(_call(reason=None)) is None
    assert LP.reason_text(_call(reason="not-a-code")) is None
    assert LP.reason_text("not a mapping") is None
    assert LP.reason_text(_call(reason="local-word")) == 'You said "this one local".'
    assert LP.reason_text(_call(reason="needs", need=PHONE)) == _needs_text(PHONE)
    assert LP.reason_text(_call(reason="version", cloud="0.41.0", advisor="0.42.0")) == (
        "The cloud's plugin is 0.41.0 and mine is 0.42.0.")
    assert LP.reason_text(_call(reason="version", cloud=None, advisor="0.42.0")) == (
        "The cloud's plugin is unknown and mine is 0.42.0.")
    assert LP.reason_text(_call(reason="version", cloud="0.41.0", advisor="")) == (
        "The cloud's plugin is 0.41.0 and mine is unknown.")
    assert LP.reason_text(_call(reason="needs", need=None)) == _needs_text("something")


def test_fix_text_is_the_tables_fix_when_no_check_failed():
    for code in LP.REASON_CODES:
        assert LP.fix_text(_call(reason=code)) == LP.REASONS[code]["fix"]


def test_the_dependency_hook_fix_says_to_point_command_and_inputs_at_the_regular_file():
    fix = LP.fix_text(_call(reason="dependency-hook"))
    assert ("point both the setup command and configure's setup inputs at the regular file "
            "itself, with no link in between") in fix
    assert fix.endswith("Then launch again.")
    assert "regular files" in LP.REASONS["dependency-hook"]["short"]


def test_E10_fix_text_without_a_reason_or_a_fix_is_none():
    assert LP.fix_text(_call(reason=None)) is None
    assert LP.fix_text(_call(reason="not-a-code", failed=["reviewer"])) is None
    assert LP.fix_text("not a mapping") is None
    for code in ("local-word", "needs"):
        assert LP.fix_text(_call(reason=code, failed=["version"])) is None


def test_fix_text_after_a_failed_check_asks_for_the_check_again():
    # axis: after a failed check the fix ends by asking for the check to be run again
    # a no-setup that came from a failed check says what the check failed on, in the paused wording
    assert LP.fix_text(_call(reason="no-setup", failed=[])) == (
        'Fix what it named, then say "check again".')
    assert LP.fix_text(_call(reason="no-setup", failed=["record"])) == (
        'To fix it, tell me so I can look at the store, then say "check again".')
    assert LP.fix_text(_call(reason="no-setup", failed=None)) == LP.REASONS["no-setup"]["fix"]
    assert LP.fix_text(_call(reason="version", failed=["version"])) == (
        SETUP_TEXT_FIX + ' Then say "check again".')
    assert LP.fix_text(_call(reason="calibration", failed=["calibration"])) == (
        SETUP_TEXT_FIX + ' Then say "check again".')


def test_fix_text_does_not_repeat_check_again_where_the_fix_has_it():
    fix = LP.REASONS["no-pass"]["fix"]
    assert 'say "check again"' in fix
    assert LP.fix_text(_call(reason="no-pass", failed=["reviewer"])) == fix


def test_fix_text_leaves_the_other_reasons_alone_after_a_failed_check():
    for code in ("pass-lapsed", "unreachable"):
        assert LP.fix_text(_call(reason=code, failed=["reviewer"])) == LP.REASONS[code]["fix"]


# ---------------------------------------------------------------- what only the machine has


def test_machine_needs_is_empty_when_everything_is_in_the_repository(inrepo):
    repo, store = inrepo
    assert LP.machine_needs(repo, {}, root=store) == []
    assert LP.machine_needs(repo, {"iphoneCheck": False, "needs": []}, root=store) == []


def test_machine_needs_orders_the_judgment_then_the_simulator_and_adds_nothing_for_a_stack(inrepo):
    repo, store = inrepo
    premise = {"needs": ["a signed-in browser", "", "  ", 7, None, "a signed-in browser",
                         PHONE],
               "iphoneCheck": True, "stack": {"layer": 2}}
    assert LP.machine_needs(repo, premise, root=store) == ["a signed-in browser", PHONE]


@pytest.mark.parametrize("premise,expected", [
    ({"iphoneCheck": True}, [PHONE]),
    ({"iphoneCheck": "yes"}, []),
    ({"iphoneCheck": 1}, []),
    ({"stack": None}, []),
    ({"stack": 7, "layerPosition": 3}, []),
    ({"needs": "a signed-in browser"}, []),
    ({"needs": ["a", "b"]}, ["a", "b"]),
])
def test_machine_needs_reads_each_premise_field_exactly(inrepo, premise, expected):
    repo, store = inrepo
    assert LP.machine_needs(repo, premise, root=store) == expected


def test_machine_needs_creates_writes_and_backfills_nothing(tmp_path):
    repo, store = _world(tmp_path, canon="store", mode=None, policy=None)
    before = _tree(store)
    LP.machine_needs(repo, {}, root=store)
    assert _tree(store) == before
    repo2, store2 = _world(_sub(tmp_path, "second"), policy=POLICY_OK)
    before2 = _tree(store2)
    assert LP.machine_needs(repo2, {}, root=store2) == []
    assert _tree(store2) == before2


def test_canon_alone_outside_is_named(tmp_path):
    repo, store = _world(tmp_path, canon="store")
    assert LP.machine_needs(repo, {}, root=store) == [CANON]


def test_specs_alone_outside_is_named(tmp_path):
    repo, store = _world(tmp_path, spec=True)
    assert LP.machine_needs(repo, {}, root=store) == [SPECS]


def test_both_outside_is_named_together(tmp_path):
    repo, store = _world(tmp_path, policy=None, canon=None, mode=None)
    assert LP.machine_needs(repo, {}, root=store) == [BOTH]
    repo2, store2 = _world(_sub(tmp_path, "second"), canon="store", spec=True)
    assert LP.machine_needs(repo2, {}, root=store2) == [BOTH]


def test_E9_a_canon_lookup_that_raises_counts_as_outside(inrepo, monkeypatch):
    repo, store = inrepo

    def boom(**kwargs):
        raise definition_doc.CanonLookupError("could not probe")

    monkeypatch.setattr(definition_doc, "resolve_canon", boom)
    assert LP.machine_needs(repo, {}, root=store) == [CANON]


def test_a_repository_root_that_cannot_be_found_is_both_outside(tmp_path):
    plain = tmp_path / "not-a-repository"
    plain.mkdir()
    assert LP.machine_needs(str(plain), {}, root=str(tmp_path / "store")) == [BOTH]


def test_any_other_error_while_judging_is_both_outside(inrepo, monkeypatch):
    repo, store = inrepo

    def boom(cwd, root):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(LP, "_specs_outside", boom)
    assert LP.machine_needs(repo, {}, root=store) == [BOTH]


# Each strict leg. The Canon reader normalizes a defective policy (and falls back to analyzing the
# repository when there is none), so the Canon stays in the repository wherever it reads one there.
_SPECS_LEGS = [
    ("E10-policy-missing", dict(policy=None), [SPECS]),
    ("E10-policy-unparseable", dict(policy="{not json"), [SPECS]),
    ("E10-policy-not-a-dict", dict(policy="[]"), [SPECS]),
    ("E11-schema-too-new", dict(policy=dict(POLICY_OK, schemaVersion=3)), [SPECS]),
    ("E11-schema-a-string", dict(policy=dict(POLICY_OK, schemaVersion="2")), [SPECS]),
    ("E11-schema-a-bool", dict(policy=dict(POLICY_OK, schemaVersion=True)), [SPECS]),
    ("E11-schema-a-float", dict(policy=dict(POLICY_OK, schemaVersion=2.0)), [SPECS]),
    ("E12-visibility-absent",
     dict(policy={k: v for k, v in POLICY_OK.items() if k != "visibility"}), [SPECS]),
    ("E12-visibility-gitignored", dict(policy=dict(POLICY_OK, visibility="gitignored")), [BOTH]),
    ("E12-visibility-other-case", dict(policy=dict(POLICY_OK, visibility="Committed")), [SPECS]),
    ("E12-visibility-not-a-string", dict(policy=dict(POLICY_OK, visibility=1)), [SPECS]),
    ("E13-location-escapes", dict(policy=dict(POLICY_OK, location="../elsewhere")), [SPECS]),
    ("E13-location-absolute", dict(policy=dict(POLICY_OK, location="/abs/place")), [SPECS]),
    ("E13-location-not-normal", dict(policy=dict(POLICY_OK, location="docs/superheroes/")),
     [SPECS]),
    ("E13-location-not-a-string", dict(policy=dict(POLICY_OK, location=7)), [SPECS]),
    ("E13-location-absent",
     dict(policy={k: v for k, v in POLICY_OK.items() if k != "location"}), [SPECS]),
    ("E14-mode-global-with-store-spec", dict(mode=mode_registry.GLOBAL, spec=True), [SPECS]),
    ("E15-spec-in-the-store", dict(spec=True), [SPECS]),
]


@pytest.mark.parametrize("name,world,expected", _SPECS_LEGS, ids=[leg[0] for leg in _SPECS_LEGS])
def test_R_FR13b_specs_outside_at_each_strict_leg(tmp_path, name, world, expected):
    repo, store = _world(tmp_path, **world)
    assert LP.machine_needs(repo, {}, root=store) == expected


def test_specs_leg_visibility_must_be_committed(tmp_path):
    # The Canon reader normalizes these to committed, so only the strict specs leg can name them.
    for index, visibility in enumerate((None, "Committed", "", 1, True)):
        policy = {k: v for k, v in POLICY_OK.items() if k != "visibility"}
        if visibility is not None:
            policy["visibility"] = visibility
        repo, store = _world(_sub(tmp_path, str(index)), policy=policy)
        assert LP.machine_needs(repo, {}, root=store) == [SPECS], visibility


def test_specs_in_the_repository_whatever_the_storage_mode(tmp_path):
    # axis: the storage mode does not decide where the specs are; a global, absent or too-new mode
    # with a committed policy and no store spec is in the repository
    worlds = (
        dict(mode=mode_registry.GLOBAL),
        dict(mode=None),
        dict(mode=None,
             registry_text=json.dumps({"schemaVersion": 99, "storageMode": "in-repo"})),
    )
    for index, world in enumerate(worlds):
        repo, store = _world(_sub(tmp_path, str(index)), **world)
        before = _tree(store)
        assert LP.machine_needs(repo, {}, root=store) == [], world
        assert _tree(store) == before, world


def test_specs_leg_store_must_hold_no_spec(tmp_path):
    repo, store = _world(tmp_path, spec=True)
    assert LP.machine_needs(repo, {}, root=store) == [SPECS]


# ---------------------------------------------------------------- the five premises


def _five():
    return [{"issue": 1}, {"issue": 2}, {"issue": 3}, {"issue": 4, "iphoneCheck": True},
            {"issue": 5, "needs": ["a signed-in browser"]}]


_FIVE_WANT = [(), (), (), (PHONE,), ("a signed-in browser",)]


def test_R_FR12_cloud_builds_on_and_the_cloud_ready_puts_only_the_free_three_in_the_cloud(inrepo):
    repo, store = inrepo
    calls = [LP.route(repo, premise, None, readiness_fn=_fn(), root=store)
             for premise in _five()]
    assert len(calls) == 5 and all(set(c) == PLACE_KEYS for c in calls)
    assert [c["place"] for c in calls] == ["cloud", "cloud", "cloud", "local", "local"]
    assert [c["reason"] for c in calls] == [None, None, None, "needs", "needs"]
    assert [c["need"] for c in calls] == [None, None, None, PHONE, "a signed-in browser"]
    assert all(c["environment"] == ENVIRONMENT for c in calls[:3])
    assert all(c["pointedAtCloud"] and c["by"] == "setting" for c in calls)


def test_R_FR11_the_local_word_wins_over_the_setting():
    call = LP.route("cwd", {}, "local", readiness_fn=_fn(setting=True), needs_fn=_no_needs)
    assert call["place"] == "local" and call["reason"] == "local-word"
    assert call["pointedAtCloud"] is True and call["by"] == "setting"
    assert LP.reason_text(call) == 'You said "this one local".'
    quiet = LP.route("cwd", {}, "local", readiness_fn=_fn(setting=False), needs_fn=_no_needs)
    assert quiet["place"] == "local" and quiet["reason"] is None
    assert quiet["pointedAtCloud"] is False and quiet["by"] is None


def test_R_FR11_the_cloud_word_wins_over_the_setting_off():
    call = LP.route("cwd", {}, "cloud", readiness_fn=_fn(setting=False), needs_fn=_no_needs)
    assert call["place"] == "cloud" and call["by"] == "word" and call["pointedAtCloud"] is True
    assert call["environment"] == ENVIRONMENT


def test_route_local_word_wins_over_a_need():
    call = LP.route("cwd", {}, "local", readiness_fn=_fn(), needs_fn=_needs(PHONE))
    assert call["place"] == "local" and call["reason"] == "local-word"
    assert call["need"] is None


def test_route_cloud_word_never_overrides_a_need():
    call = LP.route("cwd", {}, "cloud", readiness_fn=_fn(setting=False), needs_fn=_needs(PHONE))
    assert call["place"] == "local" and call["reason"] == "needs"
    assert call["by"] == "word" and call["pointedAtCloud"] is True
    assert LP.reason_text(call) == _needs_text(PHONE)


def test_R_FR13a_a_phone_check_is_local_with_its_words(inrepo):
    repo, store = inrepo
    call = LP.route(repo, {"iphoneCheck": True}, None, readiness_fn=_fn(), root=store)
    assert call["place"] == "local" and call["reason"] == "needs" and call["need"] == PHONE
    assert LP.reason_text(call) == "It needs the phone simulator, which only your machine has."
    word = LP.route(repo, {"iphoneCheck": True}, "cloud", readiness_fn=_fn(setting=False),
                    root=store)
    assert word["place"] == "local" and word["reason"] == "needs" and word["by"] == "word"
    assert LP.reason_text(word) == "It needs the phone simulator, which only your machine has."


def test_a_need_not_pointed_at_the_cloud_gives_no_reason():
    call = LP.route("cwd", {}, None, readiness_fn=_fn(setting=False), needs_fn=_needs(PHONE))
    assert call["place"] == "local" and call["reason"] is None and call["need"] is None
    assert call["pointedAtCloud"] is False and call["by"] is None


def test_C7s_a_stack_layer_with_the_cloud_ready_and_no_other_need_routes_to_the_cloud(monkeypatch):
    monkeypatch.setattr(LP, "_canon_outside", lambda cwd, root: False)
    monkeypatch.setattr(LP, "_specs_outside", lambda cwd, root: False)
    call = LP.route("cwd", {"stack": 7, "layerPosition": 3}, None, readiness_fn=_fn())
    assert call["place"] == "cloud" and call["reason"] is None and call["need"] is None
    assert call["environment"] == ENVIRONMENT


def test_C7s_a_stack_layer_that_needs_the_phone_simulator_still_routes_locally(monkeypatch):
    monkeypatch.setattr(LP, "_canon_outside", lambda cwd, root: False)
    monkeypatch.setattr(LP, "_specs_outside", lambda cwd, root: False)
    call = LP.route("cwd", {"stack": 7, "layerPosition": 3, "iphoneCheck": True}, None, readiness_fn=_fn())
    assert call["place"] == "local" and call["reason"] == "needs" and call["need"] == PHONE
    assert LP.reason_text(call) == "It needs the phone simulator, which only your machine has."


def test_several_needs_join_with_commas_and_a_final_and():
    for things, text in (((PHONE,), PHONE), ((PHONE, "a signed-in browser"), PHONE + " and a signed-in browser"),
                         ((PHONE, "a signed-in browser", CANON), PHONE + ", a signed-in browser and " + CANON)):
        call = LP.route("cwd", {}, None, readiness_fn=_fn(), needs_fn=_needs(*things))
        assert call["need"] == text
        assert LP.reason_text(call) == _needs_text(text)


@pytest.mark.parametrize("name,world", [(leg[0], leg[1]) for leg in _SPECS_LEGS] + [
    ("canon-outside", dict(canon="store")),
    ("both-outside", dict(policy=None, canon=None, mode=None)),
], ids=[leg[0] for leg in _SPECS_LEGS] + ["canon-outside", "both-outside"])
def test_R_FR13b_every_one_of_five_premises_goes_local_with_the_matching_needs_text(
        tmp_path, name, world):
    repo, store = _world(tmp_path, **world)
    outside = LP.machine_needs(repo, {}, root=store)
    assert len(outside) == 1 and outside[0] in (CANON, SPECS, BOTH)
    calls = [LP.route(repo, premise, None, readiness_fn=_fn(), root=store)
             for premise in _five()]
    assert [c["place"] for c in calls] == ["local"] * 5
    for call, extra in zip(calls, _FIVE_WANT):
        assert call["reason"] == "needs"
        assert LP.reason_text(call) == _needs_text(_join(list(extra) + outside))


# ---------------------------------------------------------------- not ready, with real readiness


def test_R_FR14_the_cloud_ready_goes_to_the_cloud(tmp_path):
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, env)
    assert call["place"] == "cloud" and call["reason"] is None
    assert call["environment"] == ENVIRONMENT and call["by"] == "setting"
    assert call["cloudVersion"] == ADVISOR and call["advisorVersion"] == ADVISOR


def test_R_FR14_no_setup_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path)
    os.unlink(CS.record_path(repo, ACCOUNT, store))
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "no-setup"
    assert LP.reason_text(call) == "This project has no cloud setup on this Claude account."


def test_R_FR14_a_lapsed_pass_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path, pass_lapses=PAST)
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "pass-lapsed"
    assert LP.reason_text(call) == "The reviewer pass has lapsed."


def test_R_FR14_a_version_apart_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="1.2.2")
    call = _route(repo, store, env)
    assert call["reason"] == "version"
    assert LP.reason_text(call) == "The cloud's plugin is 1.2.2 and mine is 1.2.3."


def test_R_FR14_a_calibration_that_differs_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, env, readiness_fn=_real(stamp_fn=lambda cwd, root: "none"))
    assert call["reason"] == "calibration"
    assert LP.reason_text(call) == "The cloud's calibration doesn't match this machine's."


def test_R_FR14_a_platform_that_cannot_be_reached_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, env, premise={"reportedCloud": {"unreachable": True}})
    assert call["reason"] == "unreachable"
    assert call["reported"] == {"unreachable": True}
    assert LP.reason_text(call) == "The cloud platform couldn't be reached."


def test_R_FR14_no_pass_in_the_cloud_gives_its_words(tmp_path):
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, env, premise={"reportedCloud": {"noPass": True}})
    assert call["reason"] == "no-pass"
    assert LP.reason_text(call) == "There is no reviewer pass in the cloud environment."


def _fail_the_check(repo, store, parts):
    path = cloud_check.failed_check_path(repo, ACCOUNT, store)
    marker = {"schema": cloud_check.FAILED_CHECK_SCHEMA, "account": ACCOUNT,
              "environment": ENVIRONMENT, "failedAt": "2026-10-10T00:00:00Z",
              "failedParts": parts}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(marker, fh)


def test_the_place_call_carries_the_failed_check_from_readiness(tmp_path):
    repo, store, env = _on(tmp_path)
    assert _route(repo, store, env)["failedCheck"] is None
    _fail_the_check(repo, store, ["version"])
    call = _route(repo, store, env)
    assert set(call) == PLACE_KEYS
    assert call["place"] == "local" and call["reason"] == "version"
    assert call["failedCheck"] == ["version"]
    assert LP.fix_text(call) == SETUP_TEXT_FIX + ' Then say "check again".'


def test_a_failed_check_with_no_fix_to_name_gives_no_setup_in_the_paused_words(tmp_path):
    repo, store, env = _on(tmp_path)
    _fail_the_check(repo, store, ["unread"])
    call = _route(repo, store, env)
    assert call["reason"] == "no-setup" and call["failedCheck"] == ["unread"]
    assert LP.reason_text(call) == "This account's last setup check failed on reporting back."
    assert LP.wasnt_text(call) == "this account's last setup check failed on reporting back."
    assert LP.fix_text(call) == 'Say "check again" and I\'ll run it once more.'


def test_route_reads_the_marker_of_an_account_with_no_setup_record(tmp_path):
    repo, store, env = _on(tmp_path)
    os.unlink(CS.record_path(repo, ACCOUNT, store))
    plain = _route(repo, store, env)
    assert plain["reason"] == "no-setup" and plain["failedCheck"] is None
    _fail_the_check(repo, store, ["version"])
    call = _route(repo, store, env)
    assert set(call) == PLACE_KEYS
    assert call["place"] == "local" and call["reason"] == "no-setup"
    assert call["failedCheck"] == ["version"]
    assert LP.reason_text(call) == "This account's last setup check failed on the plugin version."
    # a build the owner kept local gives its own reason, and the marker is not read into the call
    local_word = _route(repo, store, env, word="local")
    assert local_word["reason"] == "local-word" and local_word["failedCheck"] is None
    # a marker that cannot be read counts as a damaged one: the empty list
    with open(cloud_check.failed_check_path(repo, ACCOUNT, store), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    damaged = _route(repo, store, env)
    assert damaged["reason"] == "no-setup" and damaged["failedCheck"] == []
    assert LP.reason_text(damaged) == "This account's last setup check failed."
    # setting off and no word: the build was never pointed at the cloud, so the marker is not read
    assert PC.set_item(repo, "cloudBuilds", False, root=store)["action"] == "written"
    quiet = _route(repo, store, env)
    assert quiet["pointedAtCloud"] is False and quiet["failedCheck"] is None


def test_the_paused_words_are_built_from_the_marker_and_never_say_no_cloud_setup():
    for parts, failed, fix in (
            (["reviewer"], "last setup check failed on the reviewer pass.",
             'To fix it, paste a fresh pass into the environment, then say "check again".'),
            ([], "last setup check failed.", 'Fix what it named, then say "check again".'),
            (["unread", "nonsense"], "last setup check failed on reporting back.",
             'Say "check again" and I\'ll run it once more.')):
        call = _call(reason="no-setup", failed=parts)
        assert LP.reason_text(call) == "This account's " + failed
        assert LP.wasnt_text(call) == "this account's " + failed
        assert LP.fix_text(call) == fix
        assert "no cloud setup" not in LP.reason_text(call)
    # without a failed check the no-setup words are the table's, unchanged
    plain = _call(reason="no-setup", failed=None)
    assert LP.reason_text(plain) == "This project has no cloud setup on this Claude account."
    # any other reason keeps its own words with a failed check beside it
    assert LP.reason_text(_call(reason="pass-lapsed", failed=["reviewer"])) == (
        "The reviewer pass has lapsed.")


def test_failed_check_is_on_every_path_and_none_when_not_known():
    assert LP.route("cwd", {}, None, readiness_fn=_fn(), needs_fn=_no_needs)["failedCheck"] is None
    assert LP.route("cwd", {}, "local", readiness_fn=_fn(), needs_fn=_no_needs)["failedCheck"] is None
    assert LP.route("cwd", {}, None, readiness_fn=_fn(), needs_fn=_needs(PHONE))["failedCheck"] is None

    def boom(cwd, reported=None, root=None, env=None):
        raise RuntimeError("readiness exploded")

    assert LP.route("cwd", {}, None, readiness_fn=boom, needs_fn=_no_needs)["failedCheck"] is None

    def now_failed(cwd, reported=None, root=None, env=None):
        got = _now(ready=False, reason="no-setup")
        got["failedCheck"] = ["record"]
        return got

    def needs_boom(cwd, premise, root=None):
        raise RuntimeError("needs exploded")

    after = LP.route("cwd", {}, None, readiness_fn=now_failed, needs_fn=needs_boom)
    assert after["failedCheck"] == ["record"]
    waiting = LP.route("cwd", {}, None, readiness_fn=now_failed, needs_fn=_no_needs)
    assert waiting["failedCheck"] == ["record"]


def test_R_FR10_a_record_for_another_account_is_no_setup(tmp_path):
    repo, store, env = _on(tmp_path)
    other = _account_env(tmp_path, OTHER_ACCOUNT)
    call = _route(repo, store, other)
    assert call["place"] == "local" and call["reason"] == "no-setup"
    assert call["pointedAtCloud"] is True and call["by"] == "setting"
    assert LP.reason_text(call) == "This project has no cloud setup on this Claude account."


def test_E1_an_account_that_cannot_be_read_is_no_setup(tmp_path):
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, {"HOME": str(tmp_path / "no-such-home")})
    assert call["place"] == "local" and call["reason"] == "no-setup"


def test_R_UFR4_a_lapsed_pass_sends_all_four_launches_to_the_machine(tmp_path):
    repo, store, env = _on(tmp_path, pass_lapses=PAST)
    calls = [_route(repo, store, env) for _ in range(4)]
    assert [c["place"] for c in calls] == ["local"] * 4
    assert [c["reason"] for c in calls] == ["pass-lapsed"] * 4
    assert all(LP.reason_text(c) == "The reviewer pass has lapsed." for c in calls)
    fix = ('To fix it, run the pass command on your machine, paste the new pass into the '
           'environment and say "check again".')
    assert LP.REASONS["pass-lapsed"]["fix"] == fix


def test_R_UFR5_a_record_whose_version_differs_names_both_versions(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="0.41.0", picks_up_version=False)
    call = _route(repo, store, env, readiness_fn=_real(advisor_version="0.42.0"))
    assert call["reason"] == "version"
    assert (call["cloudVersion"], call["advisorVersion"]) == ("0.41.0", "0.42.0")
    assert LP.reason_text(call) == "The cloud's plugin is 0.41.0 and mine is 0.42.0."


def test_R_UFR5_a_version_the_builder_reported_names_both_versions(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="0.42.0", picks_up_version=False)
    call = _route(repo, store, env, readiness_fn=_real(advisor_version="0.42.0"),
                  premise={"reportedCloud": {"pluginVersion": "0.41.0"}})
    assert call["reason"] == "version"
    assert (call["cloudVersion"], call["advisorVersion"]) == ("0.41.0", "0.42.0")
    assert call["reported"] == {"pluginVersion": "0.41.0"}
    assert LP.reason_text(call) == "The cloud's plugin is 0.41.0 and mine is 0.42.0."


def _signin(tmp_path, exp):
    def b64u(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def jwt(tag):
        head = b64u(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        body = b64u(json.dumps({"exp": exp, "sub": tag}).encode())
        return ".".join([head, body, b64u(("sig-" + tag).encode())])

    path = tmp_path / "pass-home" / ".codex-cloud" / "auth.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "auth_mode": "chatgpt", "OPENAI_API_KEY": None,
        "tokens": {"id_token": jwt("ident"), "access_token": jwt("access"),
                   "refresh_token": b64u(b"renewal-fixture-key"), "account_id": "acct-fixture"},
        "last_refresh": "2026-10-10T12:00:00Z"}), encoding="utf-8")
    return {"HOME": str(tmp_path / "pass-home")}


def test_R_R3_a_pass_the_pass_command_made_does_not_move_the_lapse_date(tmp_path):
    repo, store, env = _on(tmp_path, pass_lapses=PAST)
    record = CS.record_path(repo, ACCOUNT, store)
    before = open(record, "rb").read()
    now = 1_800_000_000
    copied = []
    made = cloud_pass.make(env=_signin(tmp_path, now + 10 * 86400), clipboard=copied.append,
                           now=now)
    assert made["action"] == "copied" and len(copied) == 1
    assert made["passLapses"] > TODAY.isoformat()
    assert open(record, "rb").read() == before
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "pass-lapsed"


def test_R_FR37_a_cloud_that_picks_up_the_version_goes_to_the_cloud(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="1.2.2", picks_up_version=True)
    call = _route(repo, store, env)
    assert call["place"] == "cloud" and call["reason"] is None
    assert call["cloudVersion"] == "1.2.2" and call["advisorVersion"] == ADVISOR


def test_R_FR37_a_cloud_that_does_not_pick_up_the_version_gets_the_setup_text_fix(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="1.2.2", picks_up_version=False)
    place_call = _route(repo, store, env)
    assert place_call["place"] == "local" and place_call["reason"] == "version"
    assert place_call["cloudVersion"] == "1.2.2" and place_call["advisorVersion"] == ADVISOR
    reason = LP.reason_text(place_call)
    assert "1.2.2" in reason and ADVISOR in reason
    assert LP.fix_text(place_call) == LP.REASONS["version"]["fix"]
    assert "paste the new setup text" in LP.REASONS["version"]["fix"]


def test_R_FU1_a_record_that_goes_bad_after_the_switch_reads_as_no_setup(tmp_path):
    repo, store, env = _on(tmp_path)
    assert _route(repo, store, env)["place"] == "cloud"
    with open(CS.record_path(repo, ACCOUNT, store), "w", encoding="utf-8") as fh:
        fh.write("{ this is not json")
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "no-setup"
    assert call["pointedAtCloud"] is True
    again = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)
    assert again["action"] == "refused" and again["reason"] == CS.REASON_MISSING


_PAIRS = [
    ("setup-over-pass", dict(record=None, reported={"noPass": True}), "no-setup"),
    ("pass-over-lapse", dict(over=dict(pass_lapses=PAST), reported={"noPass": True}), "no-pass"),
    ("lapse-over-version", dict(over=dict(pass_lapses=PAST, plugin_version="1.2.2")),
     "pass-lapsed"),
    ("version-over-calibration", dict(over=dict(plugin_version="1.2.2"), stamp="none"), "version"),
    ("calibration-over-platform", dict(stamp="none", reported={"unreachable": True}),
     "calibration"),
]


@pytest.mark.parametrize("name,spec,expected", _PAIRS, ids=[p[0] for p in _PAIRS])
def test_R_order_two_false_conditions_report_the_first_in_order(tmp_path, name, spec, expected):
    repo, store, env = _on(tmp_path, **spec.get("over", {}))
    if "record" in spec:
        os.unlink(CS.record_path(repo, ACCOUNT, store))
    readiness = _real(stamp_fn=(lambda cwd, root: spec["stamp"]) if "stamp" in spec
                      else (lambda cwd, root: STAMP))
    premise = {"reportedCloud": spec["reported"]} if "reported" in spec else {}
    call = _route(repo, store, env, premise=premise, readiness_fn=readiness)
    assert call["place"] == "local" and call["reason"] == expected


# ---------------------------------------------------------------- never held, never cloud by accident


def test_R_held_a_readiness_that_raises_still_returns_a_placement():
    def boom(cwd, reported=None, root=None, env=None):
        raise RuntimeError("readiness exploded")

    call = LP.route("cwd", {"reportedCloud": {"noPass": True}}, None, readiness_fn=boom,
                    needs_fn=_no_needs)
    assert set(call) == PLACE_KEYS and call["place"] == "local"
    assert call["pointedAtCloud"] is False and call["reason"] is None
    assert call["reported"] == {"noPass": True}
    word = LP.route("cwd", {}, "cloud", readiness_fn=boom, needs_fn=_no_needs)
    assert word["place"] == "local" and word["reason"] is None


def test_E18_a_failure_after_the_cloud_is_the_target_reads_as_no_setup():
    def boom(cwd, premise, root=None):
        raise RuntimeError("needs exploded")

    call = LP.route("cwd", {}, None, readiness_fn=_fn(), needs_fn=boom)
    assert call["place"] == "local" and call["pointedAtCloud"] is True
    assert call["by"] == "setting" and call["reason"] == "no-setup"
    assert LP.reason_text(call) == "This project has no cloud setup on this Claude account."
    quiet = LP.route("cwd", {}, None, readiness_fn=_fn(setting=False), needs_fn=boom)
    assert quiet["place"] == "local" and quiet["pointedAtCloud"] is False
    assert quiet["reason"] is None
    assert LP.route("cwd", "not a premise", None, readiness_fn=_fn())["place"] == "local"


@pytest.mark.parametrize("now", [
    {"ready": True, "reason": "version", "setting": True},
    {"ready": "yes", "reason": None, "setting": True},
    {"ready": False, "reason": None, "setting": True},
    {"ready": False, "reason": "not-a-code", "setting": True},
    {"setting": True},
    {},
])
def test_I1_nothing_short_of_a_clean_ready_ever_places_in_the_cloud(now):
    def readiness(cwd, reported=None, root=None, env=None):
        return now

    call = LP.route("cwd", {}, "cloud", readiness_fn=readiness, needs_fn=_no_needs)
    assert call["place"] == "local"
    if "setting" in now:
        assert call["reason"] in LP.NOT_READY_CODES


def test_a_launch_word_that_is_neither_local_nor_cloud_is_refused():
    for word in ("Local", "cloud ", "", "yes", 1, True):
        with pytest.raises(ValueError):
            LP.route("cwd", {}, word, readiness_fn=_fn(), needs_fn=_no_needs)


def test_I4_n_calls_make_n_placements():
    calls = [LP.route("cwd", {"issue": i}, None, readiness_fn=_fn(), needs_fn=_no_needs)
             for i in range(7)]
    assert len(calls) == 7 and {c["place"] for c in calls} == {"cloud"}


# ---------------------------------------------------------------- the plugin pin reason

PIN_WORDS = ("The plugin pin on the branch this build starts from doesn't name the plugin I run, "
             "or its pin hook is broken.")
PIN_FIX = ("To fix it, run cloud_plugin_pin.py write on this machine (it pins the plugin I run), "
           "commit and push the files it names on the branch the build starts from, then launch "
           "again.")


def _commit_pin(repo, version):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.devnull,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo,
                       env=env, capture_output=True, check=True)

    git("init", "-q")
    pin = {"source": "https://github.com/acme/superheroes.git", "commit": "a" * 40,
           "subdir": "plugins/superheroes", "version": version}
    assert cloud_plugin_pin.sync(repo, pin)["action"] == "written"
    git("add", ".claude")
    git("commit", "-q", "-m", "pin")


def test_the_plugin_pin_reason_gives_its_words_and_its_fix():
    call = _call(reason="plugin-pin")
    assert LP.reason_text(call) == PIN_WORDS
    assert LP.fix_text(call) == PIN_FIX
    assert LP.REASONS["plugin-pin"]["short"] == (
        "Commit a current plugin pin on the starting branch to fix it.")
    assert LP.REASONS["plugin-pin"]["wasnt"] == (
        "the plugin pin on the branch it starts from doesn't name my plugin.")


def test_after_a_failed_check_the_plugin_pin_fix_asks_for_the_check_again():
    # axis: after a failed check the fix ends by asking for the check to be run again
    assert LP.fix_text(_call(reason="plugin-pin", failed=["pin"])) == (
        PIN_FIX + ' Then say "check again".')


def test_a_pin_naming_another_version_routes_local_with_the_plugin_pin_reason(tmp_path):
    _commit_pin(str(tmp_path), "1.2.2")
    repo, store, env = _on(tmp_path)
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "plugin-pin"
    assert LP.reason_text(call) == PIN_WORDS
    (tmp_path / "current").mkdir()
    _commit_pin(str(tmp_path / "current"), ADVISOR)
    repo, store, env = _on(tmp_path / "current")
    assert _route(repo, store, env)["place"] == "cloud"
