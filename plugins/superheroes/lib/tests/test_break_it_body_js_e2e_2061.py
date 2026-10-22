"""#2061: a JavaScript or TypeScript break-it test counts as kept by its body at any path.

End to end through `break_it.check_kept` against real fixture git repos. No node or vitest runs: a fake runner
records the block it was handed and returns a passed or failed record built by `break_it._record`. The helpers
are copied from `test_break_it_body_2053.py`, never imported."""
import hashlib
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import break_it_body  # noqa: E402

# The fixture repo's commits pass an inline identity (a CI runner has no configured one); the throwaway fixture repo also signs nothing.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        target.write_bytes(text)
    else:
        target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _write(root, "README.md", "fixture\n")
    _write(root, "web/weekly.ts", "export const weeklyTotal = (kcal: number[]) => kcal.reduce((a, b) => a + b, 0);\n")
    _commit(root, "base")
    return root


OWN = "web/eats.test.ts"
HOST = "web/weekly.test.ts"
COMMAND = "npx vitest run %s" % OWN
# The test as the loop wrote it: single quotes, no trailing commas, and a semicolon only where a line break does not
# end the statement (a block-final statement followed by `}` gets no automatic one, so a formatter adding it reads unequal).
ORIG = """import { describe, it, expect } from 'vitest'
import { weeklyTotal } from './weekly'

const eats = [{ day: 'mon', kcal: 500 }, { day: 'tue', kcal: 700 }]
const kcal = eats.map(e => e.kcal)

describe('weekly eats', () => {
  it('sums a week of eats', () => {
    expect(weeklyTotal(kcal)).toBe(1200);
  });
})
"""
# The same test after prettier: quotes, semicolons, trailing commas, wrapped lines, `(x) =>`.
FORMATTED = """import { describe, it, expect } from "vitest";
import { weeklyTotal } from "./weekly";

const eats = [
  { day: "mon", kcal: 500 },
  { day: "tue", kcal: 700 },
];
const kcal = eats.map((e) => e.kcal);

describe("weekly eats", () => {
  it("sums a week of eats", () => {
    expect(
      weeklyTotal(kcal),
    ).toBe(
      1200,
    );
  });
});
"""
HOST_IMPORTS = 'import { describe, expect, it } from "vitest";\nimport { planWeek, weeklyTotal } from "./weekly";\n'
HOST_OWN = '\nit("plans seven days", () => {\n  expect(planWeek()).toHaveLength(7);\n});\n\n'
HOST_BODY = FORMATTED.split('import { weeklyTotal } from "./weekly";\n\n', 1)[1].replace(
    '"weekly eats"', '"weekly eats (folded)"').replace('"sums a week of eats"', '"sums a week of eats (folded)"')


def _host(imports=HOST_IMPORTS, before=""):
    return imports + before + HOST_OWN + HOST_BODY


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record(content=ORIG, path=OWN, command=COMMAND, **extra):
    out = {"path": path, "command": command, "sha256": _sha(content), "content": content}
    out.update(extra)
    return out


def _stage(repo, files):
    """Commit ``files`` ({path: text or bytes}) on top of the fixture base; return (base, head)."""
    base = _git(repo, "rev-parse", "HEAD")
    for rel, text in files.items():
        _write(repo, rel, text)
    return base, _commit(repo, "head")


def _stub(calls, outcome="passed"):
    def runner(repo_root, head, block, **kwargs):
        calls.append(dict(block))
        return break_it._record(head, block, outcome, exit_code=0 if outcome == "passed" else 1)
    return runner


def _got(result):
    return result["outcome"], result["reason"]


def _check(repo, base, head, record, runner=None):
    kwargs = {"runner": runner} if runner else {}
    return break_it.check_kept(str(repo), base, head, record, **kwargs)


# ---- (a) the weekly-eats shape: folded into a host that already has vitest imports and its own it() ----

def test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host(repo):
    base, head = _stage(repo, {HOST: _host()})
    calls = []
    result = _check(repo, base, head, _record(), _stub(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["run"]["outcome"] == "passed"
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]
    assert calls[0]["path"] == HOST
    assert break_it_body.locate(ORIG, OWN, [(HOST, _host())])["titles"] == [
        ("weekly eats", "weekly eats (folded)"), ("sums a week of eats", "sums a week of eats (folded)")]


# ---- (b) a prettier-style reformat at the test's own path -----------------------------------------------

def test_a_prettier_reformat_at_its_own_path_is_kept_and_the_command_is_unchanged(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    # Doubled spaces and a quoted path: a command rebuilt from its tokens would not be these bytes.
    command = "npx  vitest run  '%s'" % OWN
    calls = []
    result = _check(repo, base, head, _record(command=command), _stub(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == [command]
    assert calls[0]["path"] == OWN


# ---- (c) a changed test is not kept, at its own path or moved --------------------------------------------

CHANGES = {
    "assertion-value": lambda t: t.replace("1200", "1201"),
    "fixture-value": lambda t: t.replace("kcal: 700", "kcal: 701"),
}


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_ts_test_at_its_own_path_reads_changed(repo, change):
    assert CHANGES[change](ORIG) != ORIG and CHANGES[change](FORMATTED) != FORMATTED
    base, head = _stage(repo, {OWN: CHANGES[change](FORMATTED)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("changed", "sha256-differs")
    assert calls == []


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_ts_test_in_a_moved_copy_reads_missing(repo, change):
    assert CHANGES[change](_host()) != _host()
    base, head = _stage(repo, {HOST: CHANGES[change](_host())})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("missing", "not-in-head")
    assert calls == []


# ---- (d) unreadable and ambiguous searches read unresolved ------------------------------------------------

def test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match(repo):
    broken = ORIG + '\nconst broken = "oops\n'
    base, head = _stage(repo, {HOST: _host(), "web/broken.test.ts": broken})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
    assert calls == []


def test_a_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved(repo):
    base, head = _stage(repo, {"web/broken.test.ts": ORIG + '\nconst broken = "oops\n'})
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "body-unparseable")


def test_two_matching_copies_are_ambiguous(repo):
    base, head = _stage(repo, {"web/a.test.ts": ORIG.replace("weekly eats", "copy a"), "web/b.test.ts": FORMATTED})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "match-ambiguous")
    assert calls == []


# ---- (e) module-level test setup the host adds ------------------------------------------------------------

def test_a_host_top_level_before_each_is_host_setup(repo):
    host = _host(imports=HOST_IMPORTS.replace("describe", "beforeEach, describe"),
                 before="\nbeforeEach(() => {\n  window.localStorage.clear();\n});\n")
    base, head = _stage(repo, {HOST: host})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_a_host_it_only_is_host_setup(repo):
    base, head = _stage(repo, {HOST: _host(before='\nit.only("focused", () => {});\n')})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_a_host_side_effect_import_is_host_setup(repo):
    base, head = _stage(repo, {HOST: _host(imports=HOST_IMPORTS + 'import "./setup";\n')})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


# ---- (f) moved but failing --------------------------------------------------------------------------------

def test_a_moved_ts_test_whose_runner_fails_reads_failing(repo):
    base, head = _stage(repo, {HOST: _host()})
    calls = []
    result = _check(repo, base, head, _record(), _stub(calls, "failed"))
    assert result["outcome"] == "failing"
    assert result["run"]["outcome"] == "failed"
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]
