"""guardian_lens_deps: dependency freshness, vulnerabilities, and check-the-check.

Adapted to the base guardian seam: every tool AND every git call routes through
``ctx["run"]`` / ``guardian_collect.run_tool`` (there is no ``store_core.run_git`` path and
no project-interpreter resolution). Collectors are PATH-only through the seam; the tool
argv operands are absolute (``--packageFile`` / ``--prefix`` / ``-r`` / ``git -C``). The
tool-output fixtures are VERBATIM output captured at the command line on 2026-07-21 from
the owner's real checkouts — /Users/zwrose/weekly-eats (node) and /Users/zwrose/aiogrilla
(python: pip-audit 2.9.0). Where a fixture is modified, the test says so.
"""
import json
import os
import subprocess

import guardian_collect as gc
import guardian_ledger as gled
import guardian_lens as gl
import guardian_lens_deps as gld
import guardian_sweep as gsw
import guardian_vitals as gv
import pytest

# --------------------------------------------------------------------------- fixtures
# Verbatim: `npx --yes npm-check-updates --jsonUpgraded` in /Users/zwrose/weekly-eats
# (excerpt — 8 of the 28 reported packages, values unchanged).
NCU_JSON = """\
{
  "@better-auth/mongo-adapter": "1.6.23",
  "@mui/material": "^9.2.0",
  "@testing-library/jest-dom": "^7.0.0",
  "@types/node": "^26",
  "eslint": "^10",
  "next": "^16.2.10",
  "typescript": "^7",
  "vitest": "^4.1.10"
}
"""

# Verbatim ranges from /Users/zwrose/weekly-eats/package.json for those packages.
PACKAGE_JSON = json.dumps({
    "name": "weekly-eats",
    "dependencies": {
        "@better-auth/mongo-adapter": "1.6.19",
        "@mui/material": "^9.0.0",
        "next": "^16.0.0",
        "react": "19.2.7",
    },
    "devDependencies": {
        "@testing-library/jest-dom": "^6.6.4",
        "@types/node": "^24",
        "eslint": "^9",
        "typescript": "^6",
        "vitest": "^4.0.0",
    },
})

# Verbatim: `npm audit --json` in /Users/zwrose/weekly-eats (exit 1, 3 vulnerabilities).
NPM_AUDIT_JSON = """\
{
  "auditReportVersion": 2,
  "vulnerabilities": {
    "body-parser": {
      "name": "body-parser",
      "severity": "low",
      "isDirect": false,
      "via": [
        {
          "source": 1123976,
          "name": "body-parser",
          "dependency": "body-parser",
          "title": "body-parser vulnerable to denial of service when invalid limit value silently disables size enforcement",
          "url": "https://github.com/advisories/GHSA-v422-hmwv-36x6",
          "severity": "low",
          "cwe": ["CWE-770"],
          "cvss": {"score": 3.7, "vectorString": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L"},
          "range": ">=2.0.0 <2.3.0"
        }
      ],
      "effects": [],
      "range": "2.0.0 - 2.2.2",
      "nodes": ["node_modules/body-parser"],
      "fixAvailable": true
    },
    "brace-expansion": {
      "name": "brace-expansion",
      "severity": "high",
      "isDirect": false,
      "via": [
        {
          "source": 1123897,
          "name": "brace-expansion",
          "dependency": "brace-expansion",
          "title": "brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups",
          "url": "https://github.com/advisories/GHSA-3jxr-9vmj-r5cp",
          "severity": "high",
          "cwe": ["CWE-400", "CWE-407"],
          "cvss": {"score": 5.3, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"},
          "range": "<1.1.16"
        },
        {
          "source": 1123898,
          "name": "brace-expansion",
          "dependency": "brace-expansion",
          "title": "brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups",
          "url": "https://github.com/advisories/GHSA-3jxr-9vmj-r5cp",
          "severity": "high",
          "cwe": ["CWE-400", "CWE-407"],
          "cvss": {"score": 5.3, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"},
          "range": ">=3.0.0 <5.0.7"
        }
      ],
      "effects": [],
      "range": "<1.1.16 || >=3.0.0 <5.0.7",
      "nodes": [
        "node_modules/@typescript-eslint/typescript-estree/node_modules/brace-expansion",
        "node_modules/brace-expansion"
      ],
      "fixAvailable": true
    },
    "js-yaml": {
      "name": "js-yaml",
      "severity": "high",
      "isDirect": false,
      "via": [
        {
          "source": 1123911,
          "name": "js-yaml",
          "dependency": "js-yaml",
          "title": "js-yaml: YAML merge-key chains can force quadratic CPU consumption",
          "url": "https://github.com/advisories/GHSA-52cp-r559-cp3m",
          "severity": "high",
          "cwe": ["CWE-400", "CWE-407"],
          "cvss": {"score": 7.5, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"},
          "range": ">=4.0.0 <4.3.0"
        }
      ],
      "effects": [],
      "range": "4.0.0 - 4.2.0",
      "nodes": ["node_modules/js-yaml"],
      "fixAvailable": true
    }
  },
  "metadata": {
    "vulnerabilities": {"info": 0, "low": 1, "moderate": 0, "high": 2, "critical": 0, "total": 3},
    "dependencies": {"prod": 610, "dev": 316, "optional": 152, "peer": 46, "peerOptional": 0, "total": 1099}
  }
}
"""

# Verbatim: `npm audit --json` in a directory with package.json but no lockfile (exit 1).
# The refusal is reported IN-BAND on stdout — a parser that reads .get("vulnerabilities", {})
# here would report a clean repo.
NPM_AUDIT_ENOLOCK_JSON = """\
{
  "error": {
    "code": "ENOLOCK",
    "summary": "This command requires an existing lockfile.",
    "detail": "Try creating one first with: npm i --package-lock-only\\nOriginal error: loadVirtual requires existing shrinkwrap file"
  }
}
"""

# Verbatim shape from `pip-audit --format=json` (pip-audit 2.9.0, exit 1, 13 vulns in 6
# packages). Excerpt: `description` bodies are truncated to "<...>" for size; every other
# field is byte-for-byte as captured. NOTE the absence of any severity field.
PIP_AUDIT_JSON = json.dumps({
    "dependencies": [
        {"name": "certifi", "version": "2026.6.17", "vulns": []},
        {"name": "filelock", "version": "3.19.1", "vulns": [
            {"id": "PYSEC-2026-1375", "fix_versions": ["3.20.1"],
             "aliases": ["CVE-2025-68146", "GHSA-w853-jp5j-5j7f"], "description": "<...>"},
            {"id": "PYSEC-2026-1374", "fix_versions": ["3.20.3"],
             "aliases": ["CVE-2026-22701", "GHSA-qmgc-5h2g-mvrw"], "description": "<...>"},
        ]},
        {"name": "msgpack", "version": "1.1.2", "vulns": [
            {"id": "GHSA-6v7p-g79w-8964", "fix_versions": ["1.2.1"], "aliases": [],
             "description": "<...>"},
        ]},
        {"name": "setuptools", "version": "58.0.4", "vulns": [
            {"id": "PYSEC-2022-43012", "fix_versions": ["65.5.1"],
             "aliases": ["CVE-2022-40897", "BIT-setuptools-2022-40897",
                         "GHSA-r9hx-vwmv-q579"], "description": "<...>"},
        ]},
    ],
    "fixes": [],
})

# Verbatim: /Users/zwrose/weekly-eats/renovate.json (packageRules trimmed to the two npm
# rules + the github-actions rule that carry matchManagers).
RENOVATE_JSON = json.dumps({
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "extends": ["config:recommended", ":dependencyDashboard", ":semanticCommits"],
    "timezone": "America/New_York",
    "labels": ["dependencies"],
    "platformAutomerge": True,
    "packageRules": [
        {"description": "Auto-merge non-major npm updates once CI passes",
         "matchManagers": ["npm"], "matchUpdateTypes": ["minor", "patch"],
         "automerge": True},
        {"description": "Major npm updates: PR only, manual review",
         "matchManagers": ["npm"], "matchUpdateTypes": ["major"], "automerge": False},
        {"description": "Auto-merge GitHub Actions version updates once CI passes",
         "matchManagers": ["github-actions"], "automerge": True},
    ],
})

# Verbatim trimmed from osv-scanner 2.4.0 on home-assistant/core (2026-07-22).
OSV_CRITICAL_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "pyyaml", "version": "5.3.1", "ecosystem": "PyPI"},
            "groups": [{
                "ids": ["PYSEC-2021-142", "GHSA-8q59-q68h-6hv4"],
                "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4", "PYSEC-2021-142"],
                "max_severity": "9.8",
            }],
            "vulnerabilities": [
                {"id": "PYSEC-2021-142",
                 "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4"]},
                {"id": "GHSA-8q59-q68h-6hv4",
                 "aliases": ["CVE-2020-14343", "PYSEC-2021-142"],
                 "severity": [{"score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                               "type": "CVSS_V3"}],
                 "database_specific": {"severity": "CRITICAL"}},
            ],
        }],
    }],
})

# Measured disagreeing evidence: certifi PYSEC-2024-230 / GHSA-248v-346w-9cwc.
OSV_CERTIFI_DISAGREE_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "certifi", "version": "2024.7.4", "ecosystem": "PyPI"},
            "groups": [{
                "ids": ["PYSEC-2024-230", "GHSA-248v-346w-9cwc"],
                "aliases": ["CVE-2024-39689", "GHSA-248v-346w-9cwc", "PYSEC-2024-230"],
                "max_severity": "7.5",
            }],
            "vulnerabilities": [
                {"id": "PYSEC-2024-230", "aliases": ["CVE-2024-39689", "GHSA-248v-346w-9cwc"]},
                {"id": "GHSA-248v-346w-9cwc",
                 "aliases": ["CVE-2024-39689", "PYSEC-2024-230"],
                 "database_specific": {"severity": "LOW"}},
            ],
        }],
    }],
})

# Real osv-scanner 2.4.0 --all-packages capture: clean audited package carries only
# ``package`` — no ``groups`` or ``vulnerabilities`` keys (allclean-allpackages.json).
OSV_ALLCLEAN_ALLPACKAGES_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "six", "version": "1.16.0", "ecosystem": "PyPI"},
        }],
    }],
})

# Real osv-scanner 2.4.0 --all-packages capture (mixed-allpackages.json): pyyaml with
# findings + six clean (package key only).
OSV_MIXED_ALLPACKAGES_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [
            {
                "package": {"name": "pyyaml", "version": "5.3.1", "ecosystem": "PyPI"},
                "groups": [{
                    "ids": ["PYSEC-2021-142", "GHSA-8q59-q68h-6hv4"],
                    "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4", "PYSEC-2021-142"],
                    "max_severity": "9.8",
                }],
                "vulnerabilities": [
                    {"id": "PYSEC-2021-142",
                     "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4"]},
                    {"id": "GHSA-8q59-q68h-6hv4",
                     "aliases": ["CVE-2020-14343", "PYSEC-2021-142"],
                     "database_specific": {"severity": "CRITICAL"}},
                ],
            },
            {
                "package": {"name": "six", "version": "1.16.0", "ecosystem": "PyPI"},
            },
        ],
    }],
})

# Synthetic (not captured): empty ``groups`` list exercises acceptance distinct from the
# real absent-key clean shape in OSV_ALLCLEAN_ALLPACKAGES_JSON.
OSV_SYNTHETIC_EMPTY_GROUPS_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "six", "version": "1.16.0", "ecosystem": "PyPI"},
            "groups": [],
        }],
    }],
})

# Fixed pyyaml: real clean-package shape after upgrade (package key only).
OSV_PYYAML_CLEAN_ALLPACKAGES_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "pyyaml", "version": "6.0.2", "ecosystem": "PyPI"},
        }],
    }],
})


def _osv_group_fixture(max_severity, label=None, withdrawn=False):
    """Minimal osv-scanner payload with one group for severity robustness tests."""
    ghsa = {
        "id": "GHSA-test-test-test",
        "aliases": ["CVE-2024-0001"],
    }
    if withdrawn:
        ghsa["withdrawn"] = "2024-01-01T00:00:00Z"
    if label is not None:
        ghsa["database_specific"] = {"severity": label}
    group = {"ids": ["GHSA-test-test-test"], "aliases": ["CVE-2024-0001"]}
    if max_severity is not ...:
        group["max_severity"] = max_severity
    return json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "pkg", "version": "1.0", "ecosystem": "PyPI"},
                "groups": [group],
                "vulnerabilities": [ghsa],
            }],
        }],
    })


def _python_repo(tmp_path, req="pkg==1.0\n"):
    return _repo(tmp_path, {"pyproject.toml": "[project]\n", "requirements.txt": req})


DAY = 86400
# Real measurement from weekly-eats on 2026-07-21: last renovate[bot] commit epoch
# 1783165834, now 1784640653 → 17 days.
NOW = 1784640653.0
RENOVATE_LAST = 1783165834


# ----------------------------------------------------------------------------- harness

class _R(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRun(object):
    """Dispatches on a substring of the joined argv.

    A `git` argv with no table match returns exit 0 with empty stdout (git log with no
    matching commit). Any other unstubbed argv fails loudly so a missing stub is obvious.
    """

    def __init__(self, table):
        self.table = list(table)
        self.calls = []

    def __call__(self, argv, **kwargs):
        line = " ".join(argv)
        self.calls.append(line)
        for key, val in self.table:
            if key in line:
                if isinstance(val, BaseException):
                    raise val
                return _R(*val)
        if argv and argv[0] == "git":
            return _R(0, "", "")  # git log, no matching commit → exit 0, empty stdout
        return _R(127, "", "TEST-STUB-MISSING for %s" % line)

    def ran(self, key):
        return any(key in line for line in self.calls)


def _repo(tmp_path, files):
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(tmp_path)


def _node_repo(tmp_path, extra=None):
    files = {"package.json": PACKAGE_JSON}
    files.update(extra or {})
    return _repo(tmp_path, files)


def _covered_repo(tmp_path, extra=None):
    files = {"package.json": PACKAGE_JSON, "renovate.json": RENOVATE_JSON}
    files.update(extra or {})
    return _repo(tmp_path, files)


def _run(ncu=NCU_JSON, audit=NPM_AUDIT_JSON, ncu_exit=0, audit_exit=1,
         pip_audit=None, pip_audit_exit=1, osv_scanner=None, osv_scanner_exit=0,
         osv_stderr="", git_log=None, extra=None):
    """Build a FakeRun for the node (and optional python) collectors + git liveness.

    `git_log` is a list of (argv-substring, epoch): a matching git log returns that epoch
    as %at whole-second stdout. Non-matching git calls fall through to exit-0-empty.

    osv-scanner defaults to absent (FileNotFoundError) so existing pip-audit stubs still
    exercise the fallback path unless a test supplies osv_scanner output explicitly.
    """
    def _val(payload, exit_code, stderr=""):
        # A BaseException is raised by FakeRun; otherwise it is (exit, stdout, stderr).
        return payload if isinstance(payload, BaseException) else (exit_code, payload, stderr)

    table = [
        ("npm-check-updates", _val(ncu, ncu_exit)),
        ("npm audit", _val(audit, audit_exit)),
    ]
    if osv_scanner is None:
        osv_scanner = FileNotFoundError("osv-scanner")
    table.append(("osv-scanner", _val(osv_scanner, osv_scanner_exit, osv_stderr)))
    if pip_audit is not None:
        table.append(("pip-audit", _val(pip_audit, pip_audit_exit)))
    for key, epoch in (git_log or []):
        table.append((key, (0, str(int(epoch)), "")))
    table.extend(extra or [])
    return FakeRun(table)


_node_run = _run  # backwards-compatible alias used by the diff/coverage tests


def _ctx(repo, run, config=None, prev=None, now=None):
    ctx = {"cwd": repo, "root": repo, "config": config or {}, "run": run,
           "prevDigest": prev}
    if now is not None:
        ctx["now"] = now
    return ctx


def _by_id(candidates):
    return dict((c["id"], c) for c in candidates)


def _live(digest, tool="renovate", path="renovate.json"):
    """Coverage liveness is keyed by tool:normalized-path (R2)."""
    return digest["coverage"]["liveness"]["%s:%s" % (tool, path)]


def _cov_id(tool, path, kind):
    return "deps:coverage:%s:%s:%s" % (tool, path, kind)


def _cov(**over):
    entry = {"lens": "deps", "tool": "renovate", "path": "renovate.json"}
    entry.update(over)
    return {"coverage": [entry]}


def run_saw_ncu(out):
    return any(c["id"].startswith("deps:ncu:") for c in out["candidates"])


# ------------------------------------------------------------------------- the contract

def test_lens_satisfies_the_contract():
    ok, reasons = gl.validate_lens(gld.LENS)
    assert ok, reasons
    assert gld.LENS.name == "deps"
    assert gld.LENS.collector_version == "1.1.0"
    assert gld.LENS.required_facts == ()
    assert isinstance(gld.LENS.cost.get("collectorSeconds"), float)


def test_lens_is_registered():
    names = [getattr(l, "name", None) for l in gl.registered_lenses()]
    assert "deps" in names
    assert "guardian_lens_deps" in gl.PRODUCTION_LENS_MODULES
    assert gl.PRODUCTION_LENS_NAMES["guardian_lens_deps"] == ("deps",)
    assert gld.LENSES == (gld.LENS,)


def test_degrade_shape():
    assert gld.LENS.degrade("npm missing") == {
        "lens": "deps", "degraded": True, "reason": "npm missing"}


def test_severity_rank_documented_in_docstring():
    """The rank scale is a public contract — the module docstring must state it."""
    doc = gld.__doc__
    for word in ("critical 5", "high 4", "unknown 0", "does not mean harmless"):
        assert word in doc


# ------------------------------------------------------------------ node freshness (real)

def test_node_majors_behind_from_real_ncu_output(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run()))
    assert out["status"] == "collected", out.get("reason")
    cands = _by_id(out["candidates"])

    assert cands["deps:ncu:package.json:@types/node"]["metric"] == 2
    assert cands["deps:ncu:package.json:eslint"]["metric"] == 1
    assert cands["deps:ncu:package.json:typescript"]["metric"] == 1
    assert cands["deps:ncu:package.json:@testing-library/jest-dom"]["metric"] == 1
    # minor/patch drift is still deferred cost, but it is ZERO majors behind
    assert cands["deps:ncu:package.json:@mui/material"]["metric"] == 0
    assert cands["deps:ncu:package.json:@better-auth/mongo-adapter"]["metric"] == 0

    receipt = cands["deps:ncu:package.json:@types/node"]["receipt"]
    assert "^24" in receipt and "^26" in receipt and "2 majors behind" in receipt

    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "collected"
    assert fresh["outdatedPackages"] == 8
    assert fresh["majorsBehindTotal"] == 5
    assert fresh["tool"] == "npm-check-updates"


def test_freshness_tool_bin_is_npm_check_updates_never_ncu_alias_or_npx(tmp_path):
    """The argv[0] is `npm-check-updates` — never the `ncu` alias, never npx."""
    repo = _node_repo(tmp_path)
    run = _run()
    out = gld.LENS.collect(_ctx(repo, run))
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["argv"][0] == "npm-check-updates"
    assert not run.ran("npx")
    assert not any(line.startswith("ncu ") for line in run.calls)


def test_freshness_and_vuln_argv_operands_are_absolute(tmp_path):
    """The seam runs from a neutral cwd — repo-relative operands would read false-clean."""
    repo = _node_repo(tmp_path)
    real = os.path.realpath(repo)
    out = gld.LENS.collect(_ctx(repo, _run()))
    fresh_argv = out["digest"]["ecosystems"]["node"]["freshness"]["argv"]
    assert fresh_argv[0] == "npm-check-updates"
    assert "--packageFile" in fresh_argv
    pkg_operand = fresh_argv[fresh_argv.index("--packageFile") + 1]
    assert os.path.isabs(pkg_operand)
    assert pkg_operand == os.path.join(real, "package.json")

    vuln_argv = out["digest"]["ecosystems"]["node"]["vulns"]["argv"]
    assert "--prefix" in vuln_argv
    prefix_operand = vuln_argv[vuln_argv.index("--prefix") + 1]
    assert os.path.isabs(prefix_operand)
    assert prefix_operand == real


def test_uncomparable_spec_is_admitted_not_guessed(tmp_path):
    pkg = json.dumps({
        "dependencies": {
            "@wei/pluralize": "npm:@jsr/wei__pluralize@^8.0.2",
            "local-thing": "file:../pkg2",
        },
    })
    repo = _repo(tmp_path, {"package.json": pkg})
    ncu = json.dumps({"@wei/pluralize": "^9.0.0", "local-thing": "^3.0.0"})
    run = _run(ncu=ncu, audit='{"vulnerabilities": {}, "metadata": {}}', audit_exit=0)
    out = gld.LENS.collect(_ctx(repo, run))
    cands = _by_id(out["candidates"])
    # alias spec resolves to its real major
    assert cands["deps:ncu:package.json:@wei/pluralize"]["majorsBehind"] == 1
    # `file:` spec is NOT guessed at from the digits in the path
    local = cands["deps:ncu:package.json:local-thing"]
    assert local["majorsBehind"] is None
    assert local["metric"] == 0
    assert "NOT computable" in local["receipt"]
    assert out["digest"]["ecosystems"]["node"]["freshness"]["uncomparableSpecs"] == [
        "local-thing"]


# --------------------------------------------------------------------- vulnerabilities

def test_npm_audit_real_output_parsed_and_duplicate_advisory_aggregated(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run()))
    cands = _by_id(out["candidates"])

    ids = [c["id"] for c in out["candidates"]]
    assert len(ids) == len(set(ids)), "duplicate candidate ids are dropped by the sweep"

    body = cands["deps:audit:node:body-parser:GHSA-V422-HMWV-36X6"]
    assert body["severity"] == "low" and body["metric"] == 2
    yaml = cands["deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M"]
    assert yaml["severity"] == "high" and yaml["metric"] == 4

    # Real weekly-eats output lists GHSA-3jxr-9vmj-r5cp TWICE for brace-expansion (two
    # affected ranges). One candidate, occurrences counted, both occurrences in receipt.
    brace = cands["deps:audit:node:brace-expansion:GHSA-3JXR-9VMJ-R5CP"]
    assert brace["occurrences"] == 2
    assert brace["receipt"].count("range ") == 2
    assert "<1.1.16" in brace["receipt"] and ">=3.0.0 <5.0.7" in brace["receipt"]

    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "collected"
    assert vulns["reportedTotal"] == 3


def test_pip_audit_real_output_reports_unknown_severity_not_harmless(tmp_path):
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "filelock==3.19.1\n"})
    run = _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1)
    out = gld.LENS.collect(_ctx(repo, run))
    cands = _by_id(out["candidates"])
    vuln = cands["deps:audit:python:filelock:PYSEC-2026-1375"]
    assert vuln["severity"] == "unknown"
    assert vuln["severityKnown"] is False
    assert vuln["metric"] == 0
    assert "severity not reported by pip-audit" in vuln["receipt"]
    assert vuln["fixVersions"] == ["3.20.1"]
    assert "GHSA-w853-jp5j-5j7f" in vuln["aliases"]
    assert "deps:audit:python:msgpack:GHSA-6V7P-G79W-8964" in cands
    note = out["digest"]["ecosystems"]["python"]["vulns"]["severityNote"]
    assert "NOT harmless" in note
    # An unrated advisory must never be promoted to a red line.
    assert gld.LENS.red_lines(out["candidates"]) == []
    # pip-audit argv audits requirements.txt by ABSOLUTE path.
    argv = out["digest"]["ecosystems"]["python"]["vulns"]["argv"]
    assert argv[0] == "pip-audit" and "-r" in argv
    req_operand = argv[argv.index("-r") + 1]
    assert os.path.isabs(req_operand)
    assert req_operand == os.path.join(os.path.realpath(repo), "requirements.txt")


def test_python_vulns_unrated_is_partial_with_red_line_gap(tmp_path):
    """pip-audit never rates severity — the critical-vuln red line cannot fire for Python.

    Collection must be partial so the gap lands in degradedLenses, and redLineGap must
    name the missing capability.
    """
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "filelock==3.19.1\n"})
    out = gld.LENS.collect(_ctx(repo, _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1)))
    assert out["status"] == "partial", out.get("reason")
    assert "no severity" in out["reason"].lower() or "critical-vuln" in out["reason"]
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    gap = out["digest"].get("redLineGap") or vulns.get("redLineGap")
    assert isinstance(gap, dict), "redLineGap must be machine-visible in the digest"
    assert gap.get("ecosystem") == "python"
    assert "pip-audit" in str(gap.get("tool"))
    assert "severity" in str(gap).lower() or "critical-vuln" in str(gap).lower()
    assert ("critical-vuln" in gld.LENS.cost["note"] or "no severity" in gld.LENS.cost["note"]
            or "unrated" in gld.LENS.cost["note"])
    assert "critical-vuln" in gld.LENS.validation_guidance or "pip-audit" in gld.LENS.validation_guidance


def test_critical_vulnerability_is_the_only_red_line(tmp_path):
    """Real npm audit shape; the js-yaml severity is raised to critical by this test."""
    data = json.loads(NPM_AUDIT_JSON)
    data["vulnerabilities"]["js-yaml"]["severity"] = "critical"
    data["vulnerabilities"]["js-yaml"]["via"][0]["severity"] = "critical"
    data["metadata"]["vulnerabilities"]["critical"] = 1
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(audit=json.dumps(data))))

    reds = gld.LENS.red_lines(out["candidates"])
    assert len(reds) == 1
    assert reds[0]["kind"] == "critical-vuln"
    assert reds[0]["id"] == "deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M"
    assert reds[0]["kind"] in gl.RED_LINE_KINDS
    kinds = set(r["kind"] for r in gld.LENS.red_lines(out["candidates"]))
    assert kinds <= set(["critical-vuln"])
    # High severity is NOT a red line — freshness never is either.
    assert _by_id(out["candidates"])[
        "deps:audit:node:brace-expansion:GHSA-3JXR-9VMJ-R5CP"]["severity"] == "high"


def test_freshness_candidates_are_never_red_lines(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(audit='{"vulnerabilities": {}}', audit_exit=0)))
    assert gld.LENS.red_lines(out["candidates"]) == []


# ===================================================================================
# Requirements pin parser (PEP 440 / PEP 503)
# ===================================================================================

@pytest.mark.parametrize("line,expected_kind,expected_key", [
    ("pkg==1.0", "pin", "pkg"),
    ("pkg==1.*", "unpinned", None),
    ("pkg===1.0", "pin", "pkg"),
    ("pkg>=1.0", "unpinned", None),
    ("pkg>1.0", "unpinned", None),
    ("pkg<2.0", "unpinned", None),
    ("pkg<=2.0", "unpinned", None),
    ("pkg~=1.0", "unpinned", None),
    ("pkg!=1.0.1", "unpinned", None),
    ("pkg>=1.0,<2.0", "unpinned", None),
    ("pkg==1.0,!=1.0.1", "unpinned", None),
    ("extraspkg[extra]==1.0", "pin", "extraspkg"),
    ("Under_Score_Pkg==2.0", "pin", "under-score-pkg"),
    ("Mixed.Case_Pkg==1.0", "pin", "mixed-case-pkg"),
    ("pkg==1.0  # inline comment", "pin", "pkg"),
    ("foo==1.2.3  # see https://example.com/advisory", "pin", "foo"),
    ("pkg==1.0 --hash=sha256:abcdef", "pin", "pkg"),
    ("pkg==1.0; python_version < \"3.9\"", "conditional", None),
    ("epochpkg==1!2.0", "pin", "epochpkg"),
    ("-e git+https://example.com/pkg.git", "unpinned", None),
    ("pkg @ https://example.com/pkg-1.0.tar.gz", "unpinned", None),
    ("pkg", "unpinned", None),
    ("-r other.txt", "include", None),
    ("-c constraints.txt", "include", None),
    ("wildcardpkg==1.*", "unpinned", None),
    ("pkg===1.*", "unpinned", None),
])
def test_requirements_pin_classification_table(line, expected_kind, expected_key):
    kind, name_or_echo, _version = gld._classify_requirements_line(line)
    assert kind == expected_kind
    if expected_kind == "pin":
        assert name_or_echo == expected_key


def test_requirements_file_utf8_bom_stripped(tmp_path):
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n"})
    req_path = tmp_path / "requirements.txt"
    req_path.write_bytes(b"\xef\xbb\xbfpkg==1.0\n")
    pin_info = gld._parse_requirements_pins(str(req_path))
    assert list(pin_info["pins"].keys()) == ["pkg"]


def test_requirements_hash_continuation_line_is_pin(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\n",
        "requirements.txt": "pkg==1.0 \\\n    --hash=sha256:abcdef\n",
    })
    pin_info = gld._parse_requirements_pins(os.path.join(repo, "requirements.txt"))
    assert list(pin_info["pins"].keys()) == ["pkg"]
    assert pin_info["unpinned"] == []


def test_truncated_requirements_discards_partial_final_line(tmp_path, monkeypatch):
    """Killing test: without last-newline discard, a truncated range becomes a false pin."""
    monkeypatch.setattr(gld, "_REQUIREMENTS_MAX_BYTES", 26)
    req_path = tmp_path / "requirements.txt"
    req_path.write_text("goodpkg==1.0\ntruncpkg==1.0.*\n", encoding="utf-8")
    pin_info = gld._parse_requirements_pins(str(req_path))
    assert pin_info["truncated"] is True
    assert list(pin_info["pins"].keys()) == ["goodpkg"]
    assert "truncpkg" not in pin_info["pins"]


def test_truncated_continuation_payload_does_not_false_resolve_prior(tmp_path, monkeypatch):
    """Fail-before: truncation inside continuation payload could fabricate a false `resolved`."""
    monkeypatch.setattr(gld, "_REQUIREMENTS_MAX_BYTES", 24)
    repo = _python_repo(tmp_path, "safe==1.0\ndanger==1.0\\\n.*\n")
    prev_id = "deps:audit:python:danger:PYSEC-PRIOR-ONLY"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id,
                    "package": "danger",
                    "advisory": "PYSEC-PRIOR-ONLY",
                    "metric": 5,
                },
            }},
        }},
    }
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "danger", "version": "1.0", "ecosystem": "PyPI"},
            }],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    pin_info = gld._parse_requirements_pins(os.path.join(repo, "requirements.txt"))
    assert pin_info["truncated"] is True
    assert "danger" not in pin_info["pins"]
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_unterminated_continuation_at_eof_without_truncation_still_pins(tmp_path):
    req_path = tmp_path / "requirements.txt"
    req_path.write_text("danger==1.0\\", encoding="utf-8")
    pin_info = gld._parse_requirements_pins(str(req_path))
    assert pin_info["truncated"] is False
    assert list(pin_info["pins"].keys()) == ["danger"]


def test_pin_gate_blocks_false_resolve_on_ranged_requirement(tmp_path):
    """Killing test: without the exact_pins gate, a clean osv audit false-resolves priors."""
    repo = _python_repo(tmp_path, "pyyaml>=5.0\n")
    prev_id = "deps:audit:python:pyyaml:PYSEC-PRIOR-ONLY"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id,
                    "package": "pyyaml",
                    "advisory": "PYSEC-PRIOR-ONLY",
                    "metric": 5,
                },
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_PYYAML_CLEAN_ALLPACKAGES_JSON), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_extraspkg_extras_canonical_name_audited_and_resolves_prior(tmp_path):
    """extras in requirements must key pins on PEP 503 canonical name (assumed osv emission)."""
    repo = _python_repo(tmp_path, "extraspkg[extra]==1.0\n")
    prev_id = "deps:audit:python:extraspkg:PYSEC-OLD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "extraspkg", "metric": 0}}},
        }},
    }
    # Synthetic (not captured): clean audited package shape matching OSV_ALLCLEAN_ALLPACKAGES_JSON.
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "extraspkg", "version": "1.0", "ecosystem": "PyPI"},
            }],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    cov = out["digest"]["ecosystems"]["python"]["vulns"]["auditCoverage"]
    assert cov["pinsClassified"] == 1
    assert cov["packagesAudited"] == 1
    assert prev_id in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_under_score_pkg_canonical_name_audited_and_resolves_prior(tmp_path):
    """PEP 503 canonical name must match osv-scanner emission (assumed under-score-pkg)."""
    repo = _python_repo(tmp_path, "Under_Score_Pkg==2.0\n")
    prev_id = "deps:audit:python:under-score-pkg:PYSEC-OLD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "under-score-pkg", "metric": 0},
            }},
        }},
    }
    # Synthetic (not captured): clean audited package shape matching OSV_ALLCLEAN_ALLPACKAGES_JSON.
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "under-score-pkg", "version": "2.0", "ecosystem": "PyPI"},
            }],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    cov = out["digest"]["ecosystems"]["python"]["vulns"]["auditCoverage"]
    assert cov["packagesAudited"] == 1
    assert prev_id in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_requirements_decode_error_degrades_python_only(tmp_path):
    repo = _repo(tmp_path, {
        "package.json": PACKAGE_JSON,
        "package-lock.json": "{}",
        "pyproject.toml": "[project]\n",
    })
    req_path = tmp_path / "requirements.txt"
    req_path.write_bytes(b"\xff\xfe not utf-8\n")
    out = gld.LENS.collect(_ctx(
        repo,
        _run(
            ncu=NCU_JSON,
            audit=NPM_AUDIT_JSON,
            audit_exit=1,
            osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON,
            pip_audit=FileNotFoundError("pip-audit"),
        )))
    assert out["digest"]["ecosystems"]["node"]["freshness"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["node"]["vulns"]["status"] == "collected"
    py_vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert py_vulns["status"] == "not-collected"
    assert "unreadable" in py_vulns["reason"].lower()


def test_audit_coverage_evidence_in_digest(tmp_path):
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "pyyaml==5.3.1\nsix==1.16.0\n"})
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_MIXED_ALLPACKAGES_JSON, osv_scanner_exit=1)))
    cov = out["digest"]["ecosystems"]["python"]["vulns"]["auditCoverage"]
    assert cov["pinsClassified"] == 2
    assert cov["packagesAudited"] == 2
    assert cov["unpinnedCount"] == 0


# Synthetic (not captured): osv reports only one of two classified pins.
OSV_SIX_ONLY_ALLPACKAGES_JSON = json.dumps({
    "results": [{
        "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
        "packages": [{
            "package": {"name": "six", "version": "1.16.0", "ecosystem": "PyPI"},
        }],
    }],
})


def test_audit_coverage_packages_audited_reflects_measurement_not_intent(tmp_path):
    """Killing test: packagesAudited must come from osv output, not len(exact_pins)."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "pyyaml==5.3.1\nsix==1.16.0\n"})
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_SIX_ONLY_ALLPACKAGES_JSON, osv_scanner_exit=0)))
    cov = out["digest"]["ecosystems"]["python"]["vulns"]["auditCoverage"]
    assert cov["pinsClassified"] == 2
    assert cov["packagesAudited"] == 1


def test_unpinned_and_conditional_notes_both_disclosed(tmp_path):
    repo = _python_repo(
        tmp_path, "pyyaml>=5.0\npkg==1.0; python_version < \"3.9\"\n")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_PYYAML_CLEAN_ALLPACKAGES_JSON)))
    reason = out["digest"]["ecosystems"]["python"]["vulns"]["reason"]
    assert gld.PYTHON_VULN_UNPINNED_AUDIT_NOTE in reason
    assert "environment markers" in reason


def test_includes_only_disclosure_note_has_clean_separator(tmp_path):
    repo = _python_repo(tmp_path, "-r base.txt\n-c constraints.txt\n")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    reason = out["digest"]["ecosystems"]["python"]["vulns"]["reason"]
    assert "requirements.txt contains -r/-c includes" in reason
    assert "; ;" not in reason


def test_unpinned_and_includes_disclosure_note_has_clean_separator(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml>=5.0\n-r base.txt\n")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_PYYAML_CLEAN_ALLPACKAGES_JSON)))
    reason = out["digest"]["ecosystems"]["python"]["vulns"]["reason"]
    assert gld.PYTHON_VULN_UNPINNED_AUDIT_NOTE in reason
    assert "requirements.txt contains -r/-c includes" in reason
    assert "; ;" not in reason


# ===================================================================================
# osv-scanner python vulns (rated primary; pip-audit fallback)
# ===================================================================================

def test_osv_critical_advisory_fires_critical_vuln_red_line(tmp_path):
    """DoD: rated CRITICAL from real captured output → critical-vuln red line."""
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1)))
    cands = _by_id(out["candidates"])
    cid = "deps:audit:python:pyyaml:CVE-2020-14343"
    assert cid in cands
    assert cands[cid]["severity"] == "critical"
    reds = gld.LENS.red_lines(out["candidates"])
    assert len(reds) == 1
    assert reds[0]["kind"] == "critical-vuln"
    assert reds[0]["id"] == cid


def test_osv_severity_max_across_disagreeing_evidence(tmp_path):
    """Label LOW + max_severity 7.5 → high; label HIGH + max 3.0 → high."""
    repo = _python_repo(tmp_path, "certifi==2024.7.4\n")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_CERTIFI_DISAGREE_JSON, osv_scanner_exit=1)))
    cands = _by_id(out["candidates"])
    cid = "deps:audit:python:certifi:CVE-2024-39689"
    assert cands[cid]["severity"] == "high"
    assert cands[cid]["severityKnown"] is True

    high_label = _osv_group_fixture("3.0", label="HIGH")
    out2 = gld.LENS.collect(_ctx(repo, _run(osv_scanner=high_label, osv_scanner_exit=1)))
    cands2 = _by_id(out2["candidates"])
    assert cands2["deps:audit:python:pkg:CVE-2024-0001"]["severity"] == "high"


def test_osv_group_dedup_one_candidate_per_group(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1)))
    py_vulns = [c for c in out["candidates"]
                if c.get("lensKind") == "vulnerability" and c.get("package") == "pyyaml"]
    assert len(py_vulns) == 1


@pytest.mark.parametrize("max_severity", ["", "n/a", "NaN", "inf", "-1", ["7.5"], {"x": 1}])
def test_osv_max_severity_robustness_unknown(tmp_path, max_severity):
    repo = _python_repo(tmp_path)
    payload = _osv_group_fixture(max_severity, label=None)
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vuln = _by_id(out["candidates"])["deps:audit:python:pkg:CVE-2024-0001"]
    assert vuln["severityKnown"] is False
    assert vuln["severity"] == "unknown"


def test_osv_missing_max_severity_with_label_still_rated(tmp_path):
    repo = _python_repo(tmp_path)
    payload = _osv_group_fixture(..., label="LOW")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vuln = _by_id(out["candidates"])["deps:audit:python:pkg:CVE-2024-0001"]
    assert vuln["severityKnown"] is True
    assert vuln["severity"] == "low"


def test_osv_red_line_gap_only_when_unrated(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    rated = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1)))
    assert rated["digest"]["ecosystems"]["python"]["vulns"].get("redLineGap") is None

    unrated = _osv_group_fixture("", label=None)
    repo2 = _python_repo(tmp_path, "pkg==1.0\n")
    out2 = gld.LENS.collect(_ctx(repo2, _run(osv_scanner=unrated, osv_scanner_exit=1)))
    gap = out2["digest"]["ecosystems"]["python"]["vulns"].get("redLineGap")
    assert isinstance(gap, dict)
    assert "no severity rating" in gap.get("missing", "").lower()


def test_osv_reconciles_prior_pip_audit_id_no_false_resolved(tmp_path):
    """Prior pip-audit item + current OSV group for same advisory → same id, no drift."""
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    prev_id = "deps:audit:python:pyyaml:PYSEC-2021-142"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id,
                    "package": "pyyaml",
                    "advisory": "PYSEC-2021-142",
                    "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4"],
                    "metric": 0,
                },
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1), prev=prev))
    cands = _by_id(out["candidates"])
    assert prev_id in cands
    d = gld.LENS.diff(prev, out["digest"])
    assert d["resolved"] == []
    assert d["new"] == []


def test_osv_ambiguous_reconciliation_keeps_critical_partial(tmp_path):
    """Fail-before: degrading to not-collected on ambiguity discards this run's findings."""
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                "deps:audit:python:pyyaml:PYSEC-2021-142": {
                    "id": "deps:audit:python:pyyaml:PYSEC-2021-142",
                    "package": "pyyaml",
                    "advisory": "PYSEC-2021-142",
                    "aliases": ["CVE-2020-14343"],
                    "metric": 0,
                },
                "deps:audit:python:pyyaml:GHSA-8q59-q68h-6hv4": {
                    "id": "deps:audit:python:pyyaml:GHSA-8q59-q68h-6hv4",
                    "package": "pyyaml",
                    "advisory": "GHSA-8q59-q68h-6hv4",
                    "aliases": ["CVE-2020-14343"],
                    "metric": 0,
                },
            }},
        }},
    }
    vulns = gld.collect_python_vulns_osv(
        _ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1), prev=prev), repo)
    assert vulns["status"] == "partial"
    assert "ambiguous" in vulns["reason"].lower()
    critical_id = "deps:audit:python:pyyaml:CVE-2020-14343"
    assert critical_id in vulns["items"]
    assert vulns["items"][critical_id].get("severity") == "critical"
    reds = gld.LENS.red_lines([
        vulns["items"][critical_id] | {"lensKind": "vulnerability"}])
    assert any(r["kind"] == "critical-vuln" for r in reds)
    assert vulns["items"]["deps:audit:python:pyyaml:PYSEC-2021-142"].get("carriedForward")
    assert vulns["items"]["deps:audit:python:pyyaml:GHSA-8q59-q68h-6hv4"].get("carriedForward")
    d = gld.LENS.diff(prev, {"ecosystems": {"python": {"vulns": vulns}}})
    assert d["resolved"] == []


def test_osv_unattributable_malformed_keeps_critical_red_line(tmp_path):
    """Fail-open regression: an unattributable malformed entry must not discard this run's
    findings via _carry_forward.

    Fail-before: without the fix the unattributable branch returns _carry_forward(prev)
    only — the critical advisory measured this run vanishes and red_lines() emits nothing."""
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "pyyaml", "version": "5.3.1", "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["PYSEC-2021-142", "GHSA-8q59-q68h-6hv4"],
                        "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4", "PYSEC-2021-142"],
                        "max_severity": "9.8",
                    }],
                    "vulnerabilities": [
                        {"id": "PYSEC-2021-142",
                         "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4"]},
                        {"id": "GHSA-8q59-q68h-6hv4",
                         "aliases": ["CVE-2020-14343", "PYSEC-2021-142"],
                         "database_specific": {"severity": "CRITICAL"}},
                    ],
                },
                {"groups": ["not-attributable-no-package-object"], "vulnerabilities": []},
            ],
        }],
    })
    critical_id = "deps:audit:python:pyyaml:CVE-2020-14343"
    prev_id = "deps:audit:python:pyyaml:PYSEC-OLD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "pyyaml", "metric": 0},
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    assert critical_id in vulns["items"]
    assert vulns["items"][critical_id].get("severity") == "critical"
    red = gld.LENS.red_lines(out["candidates"])
    assert any(r["kind"] == "critical-vuln" and r["id"] == critical_id for r in red)
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert d["resolved"] == []


def test_osv_malformed_not_permanent_boundary(tmp_path):
    """Malformed groups are transient schema drift — never seed permanentBoundary."""
    repo = _python_repo(tmp_path)
    attributable = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "good", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["GHSA-good-good-good"],
                        "aliases": ["CVE-2024-0002"],
                        "max_severity": "9.8",
                    }],
                    "vulnerabilities": [{
                        "id": "GHSA-good-good-good",
                        "database_specific": {"severity": "CRITICAL"},
                    }],
                },
                {
                    "package": {"name": "bad", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": ["not-a-dict"],
                    "vulnerabilities": [],
                },
            ],
        }],
    })
    out_attr = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=attributable, osv_scanner_exit=1)))
    vulns_attr = out_attr["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns_attr["status"] == "partial"
    assert vulns_attr.get("boundary") is not True
    assert "permanentBoundary" not in out_attr

    unattributable = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "pyyaml", "version": "5.3.1", "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["PYSEC-2021-142", "GHSA-8q59-q68h-6hv4"],
                        "aliases": ["CVE-2020-14343", "GHSA-8q59-q68h-6hv4", "PYSEC-2021-142"],
                        "max_severity": "9.8",
                    }],
                    "vulnerabilities": [
                        {"id": "GHSA-8q59-q68h-6hv4",
                         "aliases": ["CVE-2020-14343", "PYSEC-2021-142"],
                         "database_specific": {"severity": "CRITICAL"}},
                    ],
                },
                {"groups": ["no-package-object"], "vulnerabilities": []},
            ],
        }],
    })
    out_unattr = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=unattributable, osv_scanner_exit=1)))
    vulns_unattr = out_unattr["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns_unattr["status"] == "partial"
    assert vulns_unattr.get("boundary") is not True
    assert "permanentBoundary" not in out_unattr


def test_osv_malformed_group_beside_valid_carries_prior_not_resolves(tmp_path):
    repo = _python_repo(tmp_path)
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "good", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["GHSA-good-good-good"],
                        "aliases": ["CVE-2024-0002"],
                        "max_severity": "9.8",
                    }],
                    "vulnerabilities": [{
                        "id": "GHSA-good-good-good",
                        "database_specific": {"severity": "CRITICAL"},
                    }],
                },
                {
                    "package": {"name": "bad", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": ["not-a-dict"],
                    "vulnerabilities": [],
                },
            ],
        }],
    })
    prev_id = "deps:audit:python:bad:PYSEC-BAD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "bad", "metric": 4},
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    assert "bad" in vulns["reason"]
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_osv_contradiction_gate_exit1_zero_normalized(tmp_path):
    repo = _repo(tmp_path, {
        "package.json": PACKAGE_JSON,
        "pyproject.toml": "[project]\n",
        "requirements.txt": "pkg==1.0\n",
    })
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "pkg", "version": "1.0", "ecosystem": "PyPI"},
                "groups": ["garbage"],
                "vulnerabilities": [],
            }],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(
        ncu="{}", audit='{"vulnerabilities": {}, "metadata": {"vulnerabilities": {"total": 0}}}',
        audit_exit=0, osv_scanner=payload, osv_scanner_exit=1,
        pip_audit=FileNotFoundError("pip-audit"))))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "not-collected"
    assert "refusing to report a clean scan" in vulns["reason"]


def test_osv_scanner_argv_pins_neutral_config_and_all_packages(tmp_path):
    repo = _python_repo(tmp_path, "six==1.16.0\n")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    argv = out["digest"]["ecosystems"]["python"]["vulns"]["argv"]
    assert "--all-packages" in argv
    assert "--config" in argv
    config_idx = argv.index("--config") + 1
    config_path = argv[config_idx]
    assert os.path.isabs(config_path)
    assert os.path.realpath(repo) not in os.path.realpath(config_path)


# ===================================================================================
# osv-scanner lockfile python vulns (poetry.lock / uv.lock / Pipfile.lock)
# ===================================================================================

_MIN_LOCKFILE = "[[package]]\nname = \"toppkg\"\nversion = \"1.0.0\"\n"


def _lockfile_repo(tmp_path, lock_name, lock_body=_MIN_LOCKFILE, extra=None):
    files = {"pyproject.toml": "[project]\n", lock_name: lock_body}
    files.update(extra or {})
    return _repo(tmp_path, files)


def _osv_lockfile_transitive_critical(lock_basename):
    """osv payload: clean top-level + transitive package with CRITICAL group."""
    return json.dumps({
        "results": [{
            "source": {"path": "/abs/%s" % lock_basename, "type": "lockfile"},
            "packages": [
                {"package": {"name": "toppkg", "version": "1.0.0", "ecosystem": "PyPI"}},
                {
                    "package": {"name": "transitive-vuln", "version": "2.0.0",
                                 "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["GHSA-trans-trans-trans"],
                        "aliases": ["CVE-2024-9999", "GHSA-trans-trans-trans"],
                        "max_severity": "9.8",
                    }],
                    "vulnerabilities": [{
                        "id": "GHSA-trans-trans-trans",
                        "aliases": ["CVE-2024-9999"],
                        "database_specific": {"severity": "CRITICAL"},
                    }],
                },
            ],
        }],
    })


def _osv_lockfile_clean_package(lock_basename, name, version):
    return json.dumps({
        "results": [{
            "source": {"path": "/abs/%s" % lock_basename, "type": "lockfile"},
            "packages": [{
                "package": {"name": name, "version": version, "ecosystem": "PyPI"},
            }],
        }],
    })


def test_lockfile_transitive_critical_trips_red_line(tmp_path):
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    payload = _osv_lockfile_transitive_critical("poetry.lock")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    cid = "deps:audit:python:transitive-vuln:CVE-2024-9999"
    cands = _by_id(out["candidates"])
    assert cid in cands
    assert cands[cid]["severity"] == "critical"
    assert cands[cid]["severityKnown"] is True
    reds = gld.LENS.red_lines(out["candidates"])
    assert any(r["kind"] == "critical-vuln" and r["id"] == cid for r in reds)
    assert vulns.get("coverageGap") is None
    assert vulns["auditedScope"] == {
        "manifest": "poetry.lock", "kind": "lockfile", "transitive": True}


@pytest.mark.parametrize("lock_name", ["uv.lock", "Pipfile.lock"])
def test_lockfile_uv_and_pipfile_selected_argv_and_critical(tmp_path, lock_name):
    repo = _lockfile_repo(tmp_path, lock_name)
    payload = _osv_lockfile_transitive_critical(lock_name)
    run = _run(osv_scanner=payload, osv_scanner_exit=1)
    out = gld.LENS.collect(_ctx(repo, run))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    argv = vulns["argv"]
    lock_abs = os.path.join(repo, lock_name)
    assert "-L" in argv
    l_idx = argv.index("-L") + 1
    assert argv[l_idx] == "%s:%s" % (lock_name, lock_abs)
    assert os.path.isabs(lock_abs)
    cid = "deps:audit:python:transitive-vuln:CVE-2024-9999"
    assert cid in _by_id(out["candidates"])
    assert vulns["auditedScope"]["manifest"] == lock_name


def test_lockfile_audited_scope_recorded(tmp_path):
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    scope = out["digest"]["ecosystems"]["python"]["vulns"]["auditedScope"]
    assert scope == {"manifest": "poetry.lock", "kind": "lockfile", "transitive": True}


def test_lockfile_no_coverage_gap_requirements_still_has_it(tmp_path):
    repo_lock = _lockfile_repo(tmp_path, "poetry.lock")
    out_lock = gld.LENS.collect(
        _ctx(repo_lock, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    assert out_lock["digest"]["ecosystems"]["python"]["vulns"].get("coverageGap") is None

    req_path = tmp_path / "req-only"
    req_path.mkdir()
    repo_req = _python_repo(req_path, "six==1.16.0\n")
    out_req = gld.LENS.collect(
        _ctx(repo_req, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    assert out_req["digest"]["ecosystems"]["python"]["vulns"].get("coverageGap") is not None


@pytest.mark.parametrize("bad_version", [
    "", "git+https://example.com/pkg.git", "1.0.0+abc1234", "2.0.0@deadbeef",
])
def test_lockfile_unqueryable_not_audited_disclosed_carried(tmp_path, bad_version):
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    prev_id = "deps:audit:python:vcspkg:PYSEC-PRIOR"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "vcspkg", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": True,
            }},
        }},
    }
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/poetry.lock", "type": "lockfile"},
            "packages": [{
                "package": {"name": "vcspkg", "version": bad_version, "ecosystem": "PyPI"},
                "groups": [{
                    "ids": ["GHSA-vcs-vcs-vcs"],
                    "aliases": ["CVE-2024-8888"],
                    "max_severity": "9.8",
                }],
                "vulnerabilities": [{
                    "id": "GHSA-vcs-vcs-vcs",
                    "database_specific": {"severity": "CRITICAL"},
                }],
            }],
        }],
    })
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert vulns.get("carriedForward") is True
    gap = vulns.get("pinScopeGap")
    assert gap is not None
    assert "vcspkg" in gap["unqueryable"]
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_lockfile_osv_stderr_skipped_git_sourced_not_audited_carried(tmp_path):
    """Git-sourced lockfile entry: osv stderr skip must block false resolve."""
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    prev_id = "deps:audit:python:jinja2:PYSEC-PRIOR"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "jinja2", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": True,
            }},
        }},
    }
    payload = _osv_lockfile_clean_package("poetry.lock", "jinja2", "2.11.1")
    osv_stderr = (
        'Scanned x found 1 package\n'
        'Skipping jinja2: short commit hash "abc123" cannot be queried\n'
        'Filtered 1 local/unscannable package/s from the scan.\n'
    )
    out = gld.LENS.collect(_ctx(
        repo, _run(osv_scanner=payload, osv_stderr=osv_stderr), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert vulns.get("carriedForward") is True
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]
    gap = vulns.get("pinScopeGap")
    assert gap is not None
    assert "jinja2" in gap["unqueryable"]
    assert vulns["auditCoverage"]["packagesAudited"] == 0


def test_lockfile_osv_stderr_unattributed_filter_carries_all_prior(tmp_path):
    """Count guard: more filtered than named skips must carry every prior advisory."""
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    prev_id_a = "deps:audit:python:pkg-a:PYSEC-A"
    prev_id_b = "deps:audit:python:pkg-b:PYSEC-B"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id_a: {"id": prev_id_a, "package": "pkg-a", "metric": 5},
                prev_id_b: {"id": prev_id_b, "package": "pkg-b", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": True,
            }},
        }},
    }
    payload = _osv_lockfile_clean_package("poetry.lock", "pkg-a", "1.0.0")
    osv_stderr = (
        'Skipping pkg-a: short commit hash "abc123" cannot be queried\n'
        'Filtered 2 local/unscannable package/s from the scan.\n'
    )
    out = gld.LENS.collect(_ctx(
        repo, _run(osv_scanner=payload, osv_stderr=osv_stderr), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["items"][prev_id_a].get("carriedForward") is True
    assert vulns["items"][prev_id_b].get("carriedForward") is True
    assert gld.LENS.diff(prev, out["digest"])["resolved"] == []
    assert "did not individually name" in vulns["reason"]


def test_lockfile_mixed_entries_same_package_not_audited_carried(tmp_path):
    """One queryable + one unqueryable entry for the same name must not audit it."""
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    prev_id = "deps:audit:python:duppkg:PYSEC-PRIOR"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "duppkg", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": True,
            }},
        }},
    }
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/poetry.lock", "type": "lockfile"},
            "packages": [
                {"package": {"name": "duppkg", "version": "1.0.0", "ecosystem": "PyPI"}},
                {"package": {"name": "duppkg", "version": "", "ecosystem": "PyPI"}},
            ],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]
    gap = vulns.get("pinScopeGap")
    assert gap is not None
    assert "duppkg" in gap["unqueryable"]
    assert vulns["auditCoverage"]["packagesAudited"] == 0


def test_malformed_prev_audited_scope_carries_all(tmp_path):
    """Malformed prior auditedScope.transitive must fail closed (carry-all)."""
    prev_id = "deps:audit:python:pkg-a:PYSEC-A"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "pkg-a", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": "false",
            }},
        }},
    }
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    payload = _osv_lockfile_clean_package("poetry.lock", "pkg-a", "1.0.0")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert "audit scope changed" in vulns["reason"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_audited_scope_helper_used_by_osv_and_pip_audit_producers(tmp_path):
    repo_lock = _lockfile_repo(tmp_path, "poetry.lock")
    out_lock = gld.LENS.collect(
        _ctx(repo_lock, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    assert out_lock["digest"]["ecosystems"]["python"]["vulns"]["auditedScope"] == (
        gld._audited_scope("poetry.lock", "lockfile", True))

    repo_req = _python_repo(tmp_path / "req", "filelock==3.19.1\n")
    out_req = gld.LENS.collect(_ctx(repo_req, _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1)))
    assert out_req["digest"]["ecosystems"]["python"]["vulns"]["auditedScope"] == (
        gld._audited_scope("requirements.txt", "requirements", False))


def test_manifest_switch_requirements_to_lockfile_carries_all(tmp_path):
    prev_id_a = "deps:audit:python:pkg-a:PYSEC-A"
    prev_id_b = "deps:audit:python:pkg-b:PYSEC-B"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id_a: {"id": prev_id_a, "package": "pkg-a", "metric": 5},
                prev_id_b: {"id": prev_id_b, "package": "pkg-b", "metric": 5},
            }, "auditedScope": {
                "manifest": "requirements.txt", "kind": "requirements", "transitive": False,
            }},
        }},
    }
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    payload = _osv_lockfile_clean_package("poetry.lock", "pkg-a", "1.0.0")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert "audit scope changed" in vulns["reason"]
    assert "requirements/requirements.txt" in vulns["reason"]
    assert "lockfile/poetry.lock" in vulns["reason"]
    assert vulns["items"][prev_id_a].get("carriedForward") is True
    assert vulns["items"][prev_id_b].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert d["resolved"] == []


def test_lockfile_type_switch_poetry_to_uv_carries_all(tmp_path):
    prev_id = "deps:audit:python:pkg-a:PYSEC-A"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "pkg-a", "metric": 5},
            }, "auditedScope": {
                "manifest": "poetry.lock", "kind": "lockfile", "transitive": True,
            }},
        }},
    }
    repo = _lockfile_repo(tmp_path, "uv.lock")
    payload = _osv_lockfile_clean_package("uv.lock", "pkg-a", "1.0.0")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert "audit scope changed" in vulns["reason"]
    assert "poetry.lock" in vulns["reason"]
    assert "uv.lock" in vulns["reason"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    assert prev_id not in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_two_sweeps_after_scope_switch_resume_normal_resolve(tmp_path):
    prev_id = "deps:audit:python:pkg-a:PYSEC-A"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "pkg-a", "metric": 5},
            }, "auditedScope": {
                "manifest": "requirements.txt", "kind": "requirements", "transitive": False,
            }},
        }},
    }
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    switch_payload = _osv_lockfile_clean_package("poetry.lock", "pkg-a", "1.0.0")
    sweep1 = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=switch_payload), prev=prev))
    sweep1_vulns = sweep1["digest"]["ecosystems"]["python"]["vulns"]
    assert sweep1_vulns["items"][prev_id].get("carriedForward") is True

    sweep2 = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=switch_payload),
             prev=sweep1["digest"]))
    d = gld.LENS.diff(sweep1["digest"], sweep2["digest"])
    assert prev_id in d["resolved"]


def test_pre_582_digest_requirements_no_spurious_scope_degrade(tmp_path):
    prev_id = "deps:audit:python:pkg-a:PYSEC-A"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "pkg-a", "metric": 5},
            }},
        }},
    }
    repo = _python_repo(tmp_path, "pkg-a==1.0.0\n")
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "pkg-a", "version": "1.0.0", "ecosystem": "PyPI"},
            }],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert "audit scope changed" not in vulns["reason"]
    assert prev_id in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_lockfile_only_repo_osv_absent_degrades_honestly(tmp_path):
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    vulns = gld.collect_python_vulns(_ctx(repo, _run()), repo)
    assert vulns["status"] == "not-collected"
    reason = vulns.get("reason") or ""
    assert "osv-scanner" in reason.lower() or "pip-audit" in reason.lower()


def test_detect_ecosystems_poetry_lock_without_requirements(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\n",
        "poetry.lock": _MIN_LOCKFILE,
    })
    found = gld.detect_ecosystems(repo)
    assert ("python", "pyproject.toml") in found


def test_pip_audit_fallback_records_requirements_audited_scope(tmp_path):
    repo = _python_repo(tmp_path, "filelock==3.19.1\n")
    run = _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1)
    out = gld.LENS.collect(_ctx(repo, run))
    scope = out["digest"]["ecosystems"]["python"]["vulns"]["auditedScope"]
    assert scope == {
        "manifest": "requirements.txt", "kind": "requirements", "transitive": False}


def test_lockfile_osv_argv_shape(tmp_path):
    repo = _lockfile_repo(tmp_path, "poetry.lock")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON)))
    argv = out["digest"]["ecosystems"]["python"]["vulns"]["argv"]
    lock_abs = os.path.join(repo, "poetry.lock")
    assert "-L" in argv
    assert argv[argv.index("-L") + 1] == "poetry.lock:%s" % lock_abs
    assert os.path.isabs(lock_abs)
    assert "--all-packages" in argv
    assert "--config" in argv
    config_idx = argv.index("--config") + 1
    assert os.path.isabs(argv[config_idx])


def test_osv_absent_falls_back_to_pip_audit(tmp_path):
    repo = _python_repo(tmp_path, "filelock==3.19.1\n")
    run = _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1)
    out = gld.LENS.collect(_ctx(repo, run))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["ratedBy"] == "pip-audit"
    assert "osv-scanner was unavailable" in vulns["reason"]
    assert isinstance(vulns.get("redLineGap"), dict)
    assert run.ran("pip-audit")


def test_osv_fallback_carries_unmatched_prior_forbids_resolved(tmp_path):
    """Fail-before: without the fallback carry-all loop, an audited package's prior resolves."""
    repo = _python_repo(tmp_path, "requests==2.0\n")
    prev_id = "deps:audit:python:requests:PYSEC-2020-9"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {"id": prev_id, "package": "requests", "metric": 0},
            }},
        }},
    }
    payload = json.dumps({"dependencies": [
        {"name": "requests", "version": "2.0", "vulns": []}]})
    run = _run(pip_audit=payload, pip_audit_exit=0)
    out = gld.LENS.collect(_ctx(repo, run, prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_permanent_boundary_on_osv_success(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1)))
    assert out["status"] == "partial"
    assert out.get(gl.PERMANENT_BOUNDARY_KEY) is True


def test_osv_fallback_sets_permanent_boundary(tmp_path):
    """pip-audit fallback after osv absence is a structural boundary — seeds permanentBoundary."""
    repo = _python_repo(tmp_path, "requests==2.0\n")
    payload = json.dumps({"dependencies": [
        {"name": "requests", "version": "2.0", "vulns": []}]})
    out = gld.LENS.collect(_ctx(repo, _run(pip_audit=payload, pip_audit_exit=0)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns.get("boundary") is True
    assert out.get(gl.PERMANENT_BOUNDARY_KEY) is True


def test_both_fail_no_requirements_is_structural_boundary(tmp_path):
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n"})
    out = gld.LENS.collect(_ctx(repo, FakeRun([])))
    assert out["status"] == "not-collected"
    vulns = gld.collect_python_vulns(_ctx(repo, FakeRun([])), repo)
    assert vulns.get("boundary") is True


def test_both_fail_binaries_absent_is_transient_boundary(tmp_path):
    repo = _python_repo(tmp_path, "certifi==1.0\n")
    run = _run(pip_audit=FileNotFoundError("pip-audit"))
    vulns = gld.collect_python_vulns(_ctx(repo, run), repo)
    assert vulns["status"] == "not-collected"
    assert vulns.get("boundary") is not True


def test_osv_all_packages_clean_audited_package_resolves_prior(tmp_path):
    """Fail-before: without --all-packages, clean six never appears and prior never resolves."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "pyyaml==5.3.1\nsix==1.16.0\n"})
    prev_id = "deps:audit:python:six:PYSEC-OLD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "six", "metric": 0}}},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_MIXED_ALLPACKAGES_JSON, osv_scanner_exit=1),
             prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert "--all-packages" in vulns["argv"]
    assert prev_id not in (vulns.get("items") or {})
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id in d["resolved"]


def test_osv_fixed_pyyaml_critical_resolves_no_redline(tmp_path):
    """Fail-before: fixed critical red-lines forever — clean audited package misread as
    malformed carries the prior CRITICAL forward, diff() resolves nothing, and
    red_lines() keeps firing critical-vuln."""
    repo = _python_repo(tmp_path, "pyyaml==6.0.2\n")
    prev_id = "deps:audit:python:pyyaml:CVE-2020-14343"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id, "package": "pyyaml", "severity": "critical",
                    "severityKnown": True, "metric": 5,
                },
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_PYYAML_CLEAN_ALLPACKAGES_JSON), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id not in (vulns.get("items") or {})
    assert gld.LENS.red_lines(out["candidates"]) == []
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id in d["resolved"]


def test_osv_clean_package_absent_keys_not_malformed(tmp_path):
    """Real mixed shape: six (package key only) is audited, not malformed."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "pyyaml==5.3.1\nsix==1.16.0\n"})
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_MIXED_ALLPACKAGES_JSON, osv_scanner_exit=1)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    vuln_cands = [c for c in out["candidates"] if c.get("lensKind") == "vulnerability"]
    assert len(vuln_cands) == 1
    assert vuln_cands[0].get("package") == "pyyaml"
    malformed = vulns.get("malformedEntries") or []
    assert "six" not in malformed
    reason = vulns.get("reason") or ""
    assert "six" not in reason or "malformed" not in reason


def test_osv_empty_groups_list_still_audits_clean(tmp_path):
    """Synthetic empty ``groups`` list is accepted (distinct from absent-key clean shape)."""
    repo = _python_repo(tmp_path, "six==1.16.0\n")
    prev_id = "deps:audit:python:six:PYSEC-OLD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "six", "metric": 0}}},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_SYNTHETIC_EMPTY_GROUPS_JSON), prev=prev))
    assert prev_id in gld.LENS.diff(prev, out["digest"])["resolved"]


def test_osv_fixed_critical_does_not_redline_forever(tmp_path):
    """Fail-before: a fixed critical carried forward keeps raising critical-vuln forever."""
    repo = _python_repo(tmp_path, "six==1.16.0\n")
    prev_id = "deps:audit:python:six:CVE-OLD-CRIT"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id, "package": "six", "severity": "critical",
                    "severityKnown": True, "metric": 5,
                },
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON), prev=prev))
    assert "--all-packages" in out["digest"]["ecosystems"]["python"]["vulns"]["argv"]
    assert gld.LENS.red_lines(out["candidates"]) == []
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id in d["resolved"]


def test_osv_ranged_requirement_pin_scope_gap(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml>=5.0\n")
    prev_id = "deps:audit:python:pyyaml:PYSEC-PRIOR-ONLY"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial", "items": {
                prev_id: {
                    "id": prev_id,
                    "package": "pyyaml",
                    "advisory": "PYSEC-PRIOR-ONLY",
                    "metric": 5,
                },
            }},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    gap = vulns.get("pinScopeGap")
    assert isinstance(gap, dict)
    assert "pyyaml>=5.0" in gap.get("unpinned", [])
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    fresh_id = "deps:audit:python:pyyaml:CVE-2020-14343"
    assert fresh_id in vulns["items"]
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_osv_all_pinned_manifest_omits_pin_scope_gap(tmp_path):
    repo = _python_repo(tmp_path, "pyyaml==5.3.1\n")
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_CRITICAL_JSON, osv_scanner_exit=1)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns.get("pinScopeGap") is None


@pytest.mark.parametrize("max_severity", [True, False])
def test_osv_bool_max_severity_is_unrated(tmp_path, max_severity):
    repo = _python_repo(tmp_path)
    payload = _osv_group_fixture(max_severity, label=None)
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vuln = _by_id(out["candidates"])["deps:audit:python:pkg:CVE-2024-0001"]
    assert vuln["severityKnown"] is False
    gap = out["digest"]["ecosystems"]["python"]["vulns"].get("redLineGap")
    assert isinstance(gap, dict)


def test_osv_unknown_label_is_unrated(tmp_path):
    repo = _python_repo(tmp_path)
    payload = _osv_group_fixture("", label="unknown")
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vuln = _by_id(out["candidates"])["deps:audit:python:pkg:CVE-2024-0001"]
    assert vuln["severityKnown"] is False
    assert out["digest"]["ecosystems"]["python"]["vulns"].get("redLineGap")


def test_osv_vulnerabilities_without_groups_is_malformed_carries_prior(tmp_path):
    """Schema drift: ``vulnerabilities`` present while ``groups`` absent is malformed."""
    repo = _python_repo(tmp_path, "good==1.0\n")
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [{
                "package": {"name": "good", "version": "1.0", "ecosystem": "PyPI"},
                "vulnerabilities": [],
            }],
        }],
    })
    prev_id = "deps:audit:python:good:PYSEC-BAD-1"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "good", "metric": 4}}},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=payload), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward")
    assert "malformed" in vulns["reason"].lower()
    assert vulns.get("boundary") is not True
    assert isinstance(vulns.get("coverageGap"), dict)
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_osv_malformed_partial_carries_coverage_and_red_line_gaps(tmp_path):
    repo = _python_repo(tmp_path)
    payload = json.dumps({
        "results": [{
            "source": {"path": "/abs/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "good", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": [{
                        "ids": ["GHSA-good-good-good"],
                        "aliases": ["CVE-2024-0002"],
                        "max_severity": True,
                    }],
                    "vulnerabilities": [{"id": "GHSA-good-good-good"}],
                },
                {
                    "package": {"name": "bad", "version": "1.0", "ecosystem": "PyPI"},
                    "groups": ["not-a-dict"],
                    "vulnerabilities": [],
                },
            ],
        }],
    })
    out = gld.LENS.collect(_ctx(repo, _run(osv_scanner=payload, osv_scanner_exit=1)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert isinstance(vulns.get("coverageGap"), dict)
    assert isinstance(vulns.get("redLineGap"), dict)


def test_permanent_boundary_absent_on_transient_failure(tmp_path):
    repo = _repo(tmp_path, {
        "package.json": PACKAGE_JSON,
        "pyproject.toml": "[project]\n",
        "requirements.txt": "certifi==1.0\n",
    })
    run = _run(audit=FileNotFoundError("npm"), pip_audit='{"dependencies": []}')
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "partial"
    assert "permanentBoundary" not in out


# ===================================================================================
# THE CRITICAL — the unified vulnerability contradiction gate (deliverable #1).
# A findings-signalling collector that normalizes ZERO candidates must degrade
# (not-collected) — never `collected`/`partial` with zero candidates, which would let
# diff() resolve prior ids into a false `fixed`.
# ===================================================================================

def _prev_node_vuln_digest(prev_id="deps:audit:node:left-pad:GHSA-AAAA-BBBB-CCCC"):
    return {
        "detected": ["node"],
        "ecosystems": {"node": {
            "freshness": {"status": "collected", "items": {}},
            "vulns": {"status": "collected",
                      "items": {prev_id: {"id": prev_id, "metric": 4}}},
        }},
    }, prev_id


def test_npm_audit_all_transitive_degrades_with_the_count(tmp_path):
    """R4 Critical: items empty, transitive_only non-empty → degrade, count in the reason.

    This is the path the old `and not transitive_only` guard let read as a clean scan.
    """
    audit = json.dumps({
        "vulnerabilities": {
            "lodash": {"name": "lodash", "severity": "high",
                       "via": ["some-parent-package"],  # transitive-only (string via)
                       "range": "<4.17.21", "nodes": ["node_modules/lodash"]},
        },
        "metadata": {"vulnerabilities": {"total": 1, "high": 1, "critical": 0}},
    })
    repo = _node_repo(tmp_path)
    prev, prev_id = _prev_node_vuln_digest()
    out = gld.LENS.collect(_ctx(repo, _run(audit=audit, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected", (
        "an all-transitive audit with zero direct candidates must never read as clean")
    assert "reportedTotal=1" in vulns["reason"]
    assert "transitiveOnlyPackages=1" in vulns["reason"]
    assert "transitively" in vulns["reason"]
    # It carries the prior finding forward and emits NO false resolved.
    assert vulns.get("carriedForward") is True
    assert prev_id in (vulns.get("items") or {})
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_npm_audit_metadata_reports_but_empty_vulns_object_degrades(tmp_path):
    """exit 1 / metadata>0 with an EMPTY vulnerabilities object → degrade (contradiction)."""
    repo = _node_repo(tmp_path)
    prev, prev_id = _prev_node_vuln_digest()
    broken = json.dumps({
        "auditReportVersion": 2,
        "vulnerabilities": {},
        "metadata": {"vulnerabilities": {"total": 3, "critical": 1}},
    })
    out = gld.LENS.collect(_ctx(repo, _run(audit=broken, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected"
    assert "reportedTotal=3" in vulns["reason"]
    # No transitive entries were parsed here — the reason must not claim any.
    assert "transitiveOnlyPackages=0" in vulns["reason"]
    assert "no parseable advisory entries" in vulns["reason"]
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_npm_audit_exit0_nonempty_vulns_zero_normalized_degrades(tmp_path):
    """exit 0, a nonempty vulnerabilities object, but zero normalized advisories → degrade.

    Every package entry is malformed (via is not a list of dicts and names no package), so
    nothing normalizes — but the raw object was non-empty, so it is not a clean scan.
    """
    repo = _node_repo(tmp_path)
    prev, prev_id = _prev_node_vuln_digest()
    audit = json.dumps({
        "vulnerabilities": {
            "pkg-a": {"name": "pkg-a", "via": [], "severity": "high"},
            "pkg-b": {"name": "pkg-b", "via": [], "severity": "low"},
        },
        "metadata": {"vulnerabilities": {"total": 0}},
    })
    # exit 0 here (not a findings exit); the signal is the non-empty raw vulns object.
    out = gld.LENS.collect(_ctx(repo, _run(audit=audit, audit_exit=0, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected"
    # via=[] means no `direct` advisories AND the entry is recorded transitive-only.
    assert "transitiveOnlyPackages=2" in vulns["reason"]
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_npm_audit_nondict_vuln_entry_at_exit0_degrades(tmp_path):
    """A2: a nonempty ``vulnerabilities`` map whose VALUE is non-dict (schema drift) at
    exit 0 / metadata 0 normalizes to zero advisories. The old ``raw_entries`` counted only
    dict-valued entries → 0 → the contradiction gate saw no signal → the run read clean and
    diff() would falsely `resolve` the prior finding. Counting EVERY key (len(vulns)) fails
    closed. Reverting A2 (back to counting dict values only) makes this read ``collected``
    with zero candidates and resolves the prior finding — both assertions bite."""
    repo = _node_repo(tmp_path)
    prev, prev_id = _prev_node_vuln_digest()
    audit = json.dumps({
        "vulnerabilities": {"left-pad": "garbage-not-a-dict"},
        "metadata": {"vulnerabilities": {"total": 0}},
    })
    out = gld.LENS.collect(
        _ctx(repo, _run(audit=audit, audit_exit=0, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected"
    assert "reportedTotal=0" in vulns["reason"]
    assert "transitiveOnlyPackages=0" in vulns["reason"]
    assert "parseable advisory candidate" in vulns["reason"]
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_npm_audit_findings_exit_with_empty_output_is_not_collected(tmp_path):
    """R11: exit 1 + genuinely-empty vulns must not clear prior findings via resolved."""
    repo = _node_repo(tmp_path)
    prev, prev_id = _prev_node_vuln_digest()
    empty_findings = json.dumps({
        "vulnerabilities": {},
        "metadata": {"vulnerabilities": {
            "info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0}},
    })
    out = gld.LENS.collect(
        _ctx(repo, _run(audit=empty_findings, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected", (
        "exit 1 signals findings — an empty extraction is a contradiction, not a clean scan")
    assert vulns.get("carriedForward") is True
    assert prev_id in (vulns.get("items") or {})
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_pip_audit_findings_exit_zero_normalized_degrades_no_false_resolved(tmp_path):
    """pip-audit signalled findings (exit 1 + non-empty raw entries) but normalized zero.

    Today's code returns `partial` here, and `partial` lets diff() resolve prior ids into a
    false `fixed`. The unified gate degrades to not-collected and closes it.
    """
    # node is present + clean so the whole lens stays `partial` and keeps its digest
    # (a python-only repo would go not-collected/digest-None and hide the vulns section).
    repo = _repo(tmp_path, {"package.json": PACKAGE_JSON,
                            "pyproject.toml": "[project]\n",
                            "requirements.txt": "foo==1.0\n"})
    prev_id = "deps:audit:python:foo:PYSEC-2020-1"
    clean_node = {"status": "collected", "items": {}}
    prev = {
        "detected": ["node", "python"],
        "ecosystems": {
            "node": {"freshness": dict(clean_node), "vulns": dict(clean_node)},
            "python": {
                "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
                "vulns": {"status": "partial",
                          "items": {prev_id: {"id": prev_id, "metric": 0}}},
            },
        },
    }
    # exit 1 with a non-empty vulns list whose entries are non-dict → zero normalized.
    payload = json.dumps({"dependencies": [
        {"name": "foo", "version": "1.0", "vulns": ["garbage-not-a-dict"]},
    ]})
    out = gld.LENS.collect(
        _ctx(repo, _run(ncu="{}", audit='{"vulnerabilities": {}, "metadata": '
             '{"vulnerabilities": {"total": 0}}}', audit_exit=0,
             pip_audit=payload, pip_audit_exit=1), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "not-collected", (
        "pip-audit signalling findings with zero normalized candidates must degrade, "
        "not stay partial (partial would let diff() resolve prior ids)")
    assert "raw vulnerability entries were non-empty" in vulns["reason"]
    assert "refusing to report a clean scan" in vulns["reason"]
    assert vulns.get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"], "a contradiction must never read as fixed"


def test_pip_audit_genuinely_clean_stays_partial_not_degraded(tmp_path):
    """A genuinely-clean pip-audit (exit 0, no vulns) stays partial with the redLineGap."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "certifi==1.0\n"})
    payload = json.dumps({"dependencies": [
        {"name": "certifi", "version": "1.0", "vulns": []}]})
    out = gld.LENS.collect(
        _ctx(repo, _run(pip_audit=payload, pip_audit_exit=0)))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    assert isinstance(vulns.get("redLineGap"), dict)


def test_pip_audit_no_deps_narrowed_scope_discloses_and_carries_transitive(tmp_path):
    """H1: --no-deps audits only the enumerated (top-level) manifest, so a prior TRANSITIVE
    advisory it never re-measured must be carried forward (not falsely `resolved`), and the
    section must DISCLOSE the narrowed coverage.

    Fail-before: without the fix the section resolves the transitive prior (it read the
    clean top-level audit as a full-graph clean scan) and carries no coverageGap — both
    assertions bite."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "requests==2.0\n"})
    # A prior advisory for urllib3 — a TRANSITIVE dependency of requests, not enumerated in
    # requirements.txt and therefore invisible to a --no-deps audit of the top-level manifest.
    prev_id = "deps:audit:python:urllib3:PYSEC-2021-108"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "urllib3",
                                          "metric": 0}}},
        }},
    }
    # This sweep audits ONLY the enumerated top-level package, clean. urllib3 is invisible.
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert vulns["status"] == "partial"
    # (1) discloses the narrowed --no-resolve coverage
    assert "transitive" in vulns["reason"].lower()
    assert isinstance(vulns.get("coverageGap"), dict)
    assert vulns["coverageGap"].get("scope") == "enumerated-manifest-only"
    # (2) carries the unaudited transitive advisory forward, NEVER resolving it
    assert prev_id in (vulns.get("items") or {})
    assert (vulns["items"][prev_id].get("carriedForward")) is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"], (
        "an unaudited transitive advisory must never read as fixed under --no-deps")


def test_pip_audit_no_deps_resolves_an_enumerated_package_that_is_now_clean(tmp_path):
    """H1 counterpart: a prior advisory for a package the manifest DOES enumerate WAS
    re-measured this sweep — a clean re-audit genuinely resolves it (carry-forward is scoped
    to unaudited packages, so it does not freeze legitimate fixes).

        Uses osv-scanner (rated primary) — pip-audit fallback forbids resolutions."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "six==1.16.0\n"})
    prev_id = "deps:audit:python:six:PYSEC-2020-9"
    prev = {
        "detected": ["python"],
        "ecosystems": {"python": {
            "freshness": {"status": "not-collected", "reason": "policy", "items": {}},
            "vulns": {"status": "partial",
                      "items": {prev_id: {"id": prev_id, "package": "six",
                                          "metric": 0}}},
        }},
    }
    out = gld.LENS.collect(
        _ctx(repo, _run(osv_scanner=OSV_ALLCLEAN_ALLPACKAGES_JSON), prev=prev))
    vulns = out["digest"]["ecosystems"]["python"]["vulns"]
    assert prev_id not in (vulns.get("items") or {}), (
        "an ENUMERATED package re-audited clean is not carried forward")
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id in d["resolved"]


def test_npm_audit_valid_plus_malformed_entry_carries_not_resolves(tmp_path):
    """H2: one valid advisory + one malformed (non-dict) entry. The valid candidate keeps
    `items` truthy and clears the contradiction gate, but the malformed sibling must still
    degrade — carrying that package's prior advisory forward, never resolving it.

    Fail-before: without the fix the malformed entry is silently dropped, the section reads
    `collected`, and diff() resolves the malformed package's prior advisory (false fixed) —
    the status, reason, and no-false-resolved assertions all bite."""
    repo = _node_repo(tmp_path)
    prev_id = "deps:audit:node:left-pad:GHSA-AAAA-BBBB-CCCC"
    prev = {
        "detected": ["node"],
        "ecosystems": {"node": {
            "freshness": {"status": "collected", "items": {}},
            "vulns": {"status": "collected",
                      "items": {prev_id: {"id": prev_id, "package": "left-pad",
                                          "metric": 4}}},
        }},
    }
    audit = json.dumps({
        "vulnerabilities": {
            "js-yaml": {
                "name": "js-yaml", "severity": "high", "range": "<3.13.1",
                "via": [{"severity": "high", "title": "code injection",
                         "url": "https://github.com/advisories/GHSA-52cp-r559-cp3m",
                         "range": "<3.13.1"}],
            },
            "left-pad": "garbage-not-a-dict",  # malformed sibling; prior advisory present
        },
        "metadata": {"vulnerabilities": {"total": 1, "high": 1, "critical": 0}},
    })
    out = gld.LENS.collect(_ctx(repo, _run(audit=audit, ncu="{}"), prev=prev))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    # the valid advisory is present
    assert "deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M" in vulns["items"]
    # the malformed sibling degrades the section and discloses the dropped package
    assert vulns["status"] == "partial"
    assert "left-pad" in vulns["reason"]
    assert "left-pad" in (vulns.get("malformedEntries") or [])
    # the malformed package's prior advisory is carried forward, NOT resolved
    assert prev_id in vulns["items"]
    assert vulns["items"][prev_id].get("carriedForward") is True
    d = gld.LENS.diff(prev, out["digest"])
    assert prev_id not in d["resolved"]


def test_npm_audit_clean_empty_map_stays_collected_no_over_degrade(tmp_path):
    """H2 guardrail: a legitimately empty ``vulnerabilities: {}`` has no malformed entries
    and must stay `collected` — the malformed-entry degradation must not over-fire."""
    repo = _node_repo(tmp_path)
    empty = json.dumps({
        "vulnerabilities": {},
        "metadata": {"vulnerabilities": {"total": 0}},
    })
    out = gld.LENS.collect(
        _ctx(repo, _run(audit=empty, audit_exit=0, ncu="{}")))
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "collected"
    assert not vulns.get("malformedEntries")


def test_two_unidentified_advisories_for_same_package_are_distinct(tmp_path):
    """R12: fallback advisory identity must not collapse distinct vulns."""
    audit = {
        "auditReportVersion": 2,
        "vulnerabilities": {
            "left-pad": {
                "name": "left-pad",
                "severity": "high",
                "isDirect": True,
                "via": [
                    {"name": "left-pad", "title": "Prototype pollution in left-pad",
                     "severity": "high", "range": "<2.0.0"},
                    {"name": "left-pad", "title": "ReDoS in left-pad stringify",
                     "severity": "high", "range": "<2.0.0"},  # SAME range
                ],
                "effects": [], "range": "*",
                "nodes": ["node_modules/left-pad"], "fixAvailable": True,
            },
        },
        "metadata": {"vulnerabilities": {
            "info": 0, "low": 0, "moderate": 0, "high": 2, "critical": 0, "total": 2}},
    }
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(audit=json.dumps(audit), ncu="{}")))
    left = [c for c in out["candidates"]
            if c.get("package") == "left-pad" and c.get("lensKind") == "vulnerability"]
    assert len(left) == 2, (
        "two distinct unidentified advisories must produce two candidates, got %r"
        % [c["id"] for c in left])
    assert left[0]["id"] != left[1]["id"]


# --------------------------------------------------------------- fail closed, visibly

def test_npm_audit_enolock_refusal_is_not_collected(tmp_path):
    """The trap: npm reports its refusal in-band on stdout with exit 1."""
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(audit=NPM_AUDIT_ENOLOCK_JSON)))
    assert out["status"] == "partial"
    assert "npm audit" in out["reason"] and "ENOLOCK" in out["reason"]
    vulns = out["digest"]["ecosystems"]["node"]["vulns"]
    assert vulns["status"] == "not-collected"
    assert vulns["items"] == {}
    # detection continues for the half that did work
    assert any(c["id"].startswith("deps:ncu:") for c in out["candidates"])
    assert not any(c["id"].startswith("deps:audit:") for c in out["candidates"])


def test_missing_freshness_tool_names_it(tmp_path):
    repo = _node_repo(tmp_path)
    run = _run(ncu=FileNotFoundError("npm-check-updates"))
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "partial"
    assert "npm-check-updates" in out["reason"]
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "npm-check-updates" in fresh["reason"]


def test_missing_npm_names_the_tool(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(audit=FileNotFoundError("npm"))))
    assert out["status"] == "partial"
    assert "npm audit" in out["reason"]
    assert out["digest"]["ecosystems"]["node"]["vulns"]["status"] == "not-collected"


def test_missing_freshness_tool_argv0_is_the_bin(tmp_path):
    """In production an absent tool's reason quotes INSTALL_COMMANDS; that home is proven
    by guardian_tools tests. Here (injected seam) we prove the bin name reaches the reason.
    """
    assert gld.gc.gt.INSTALL_COMMANDS["npm-check-updates"] == (
        "npm install -g npm-check-updates")
    assert gld.gc.gt.INSTALL_COMMANDS["npm"] == "install Node.js, which bundles npm"
    assert gld.gc.gt.INSTALL_COMMANDS["pip-audit"] == "pip install pip-audit"


def test_production_absent_tool_degrades_quoting_install_command(tmp_path, monkeypatch):
    """Production path (no ctx['run']): an absent collector degrades quoting INSTALL_COMMANDS.

    PATH is emptied so nothing resolves — no real subprocess is spawned (resolve() returns
    not-found and invoke short-circuits to tool-absent).
    """
    repo = _node_repo(tmp_path)
    monkeypatch.setenv("PATH", "/nonexistent-guardian-deps-path")
    fresh = gld.collect_node_freshness({}, os.path.realpath(repo), "package.json")
    assert fresh["status"] == "not-collected"
    assert "npm install -g npm-check-updates" in fresh["reason"]
    vulns = gld.collect_node_vulns({}, os.path.realpath(repo))
    assert vulns["status"] == "not-collected"
    assert "install Node.js, which bundles npm" in vulns["reason"]


def test_tool_timeout_is_not_collected(tmp_path):
    repo = _node_repo(tmp_path)
    run = _run(ncu=subprocess.TimeoutExpired(["npm-check-updates"], gld.FRESHNESS_TIMEOUT))
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "partial"
    assert "timed out" in out["reason"]
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "timed out after %ss" % gld.FRESHNESS_TIMEOUT in fresh["reason"]


def test_unparseable_output_is_not_collected_never_a_silent_empty(tmp_path):
    repo = _node_repo(tmp_path)
    run = _run(ncu="Checking package.json\n[====] 12/12")
    out = gld.LENS.collect(_ctx(repo, run))
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "unparseable JSON" in fresh["reason"]
    assert fresh["items"] == {}
    assert out["status"] == "partial"


def test_ncu_json_array_instead_of_object_is_not_collected(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run(ncu="[]")))
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "expected a JSON object" in fresh["reason"]


def test_unreadable_package_json_is_not_collected(tmp_path):
    repo = _repo(tmp_path, {"package.json": "{not json"})
    out = gld.LENS.collect(_ctx(repo, _run()))
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "package.json unreadable" in fresh["reason"]


def test_failed_tool_with_parseable_stdout_is_not_collected(tmp_path):
    """R10: parseable stdout must not override a failed tool result."""
    repo = _node_repo(tmp_path)
    # ncu exits 2 (failure, not in ok_exits) but still emits upgrade JSON.
    run = _run(ncu=NCU_JSON, ncu_exit=2)
    out = gld.LENS.collect(_ctx(repo, run))
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "exited 2" in fresh["reason"] or "failed" in fresh["reason"].lower()
    assert not any(c["id"].startswith("deps:ncu:") for c in out["candidates"]), (
        "failed run must not promote parseable stdout to a successful collection")


def test_every_node_collector_failing_is_not_collected(tmp_path):
    repo = _node_repo(tmp_path)
    run = _run(ncu=FileNotFoundError("npm-check-updates"), audit=FileNotFoundError("npm"))
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert out["candidates"] == []
    assert out["digest"] is None
    assert "npm-check-updates" in out["reason"] and "npm audit" in out["reason"]


def test_no_manifest_is_not_collected(tmp_path):
    repo = _repo(tmp_path, {"README.md": "# nothing here\n"})
    out = gld.LENS.collect(_ctx(repo, FakeRun([])))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert "no supported dependency manifest" in out["reason"]
    assert out["candidates"] == []


# ------------------------------------------------------- python freshness: policy gap

def test_python_freshness_is_not_collected_by_policy(tmp_path):
    """pip list --outdated needs the installed env — disclosed as not measured, never faked."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n",
                            "requirements.txt": "certifi==1.0\n"})
    payload = json.dumps({"dependencies": [
        {"name": "certifi", "version": "1.0", "vulns": []}]})
    out = gld.LENS.collect(_ctx(repo, _run(pip_audit=payload, pip_audit_exit=0)))
    fresh = out["digest"]["ecosystems"]["python"]["freshness"]
    assert fresh["status"] == "not-collected"
    assert "installed environment" in fresh["reason"]
    assert "supply-chain policy" in fresh["reason"]
    assert fresh["items"] == {}
    assert not any(c["id"].startswith("deps:pip:") for c in out["candidates"])
    # No freshness tool was ever invoked for python.
    assert not out["candidates"] or all(
        not c["id"].startswith("deps:pip:") for c in out["candidates"])


def test_python_vulns_without_requirements_is_not_collected(tmp_path):
    """A pyproject-only project has no static manifest pip-audit can audit by path."""
    repo = _repo(tmp_path, {"pyproject.toml": "[project]\n"})
    out = gld.LENS.collect(_ctx(repo, FakeRun([])))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    # Both python parts declined: freshness by policy, vulns for want of requirements.txt.


def test_pip_audit_tool_failure_is_not_collected(tmp_path):
    """pip-audit absent (spawn error) → not-collected, never a clean bill."""
    repo = _repo(tmp_path, {"requirements.txt": "foo==1.0\n"})
    run = _run(pip_audit=FileNotFoundError("pip-audit"))
    out = gld.LENS.collect(_ctx(repo, run))
    # freshness not-collected by policy + vulns not-collected → whole not-collected.
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert "pip-audit" in out["reason"]


# ------------------------------------------------------------ rust / go: honestly absent

def test_rust_only_repo_is_not_collected_not_clean(tmp_path):
    repo = _repo(tmp_path, {"Cargo.toml": "[package]\nname='x'\n"})
    out = gld.LENS.collect(_ctx(repo, FakeRun([])))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert "no freshness or vulnerability collector ships for rust" in out["reason"]
    assert "NOT measured, not found clean" in out["reason"]


def test_go_alongside_node_makes_the_sweep_partial(tmp_path):
    repo = _node_repo(tmp_path, {"go.mod": "module example.com/x\n"})
    out = gld.LENS.collect(_ctx(repo, _run()))
    assert out["status"] == "partial"
    assert "go" in out["reason"]
    assert out["digest"]["ecosystems"]["go"]["status"] == "not-collected"
    assert any("go" in n for n in out["digest"]["notes"])
    # node still collected in full
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"


# ------------------------------------------------------------------ diff / carry-forward

def _two_sweeps(tmp_path, second_run, first_run=None):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, first_run or _run()))
    second = gld.LENS.collect(_ctx(repo, second_run, prev=first["digest"]))
    return (first, second)


def test_ids_are_stable_across_two_sweeps(tmp_path):
    first, second = _two_sweeps(tmp_path, _run())
    assert set(_by_id(first["candidates"])) == set(_by_id(second["candidates"]))
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d == {"new": [], "worsened": [], "resolved": []}


def test_missing_tool_produces_no_false_resolved_and_carries_prev_forward(tmp_path):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, _run()))
    assert first["digest"]["ecosystems"]["node"]["freshness"]["items"]

    dead = _run(ncu=FileNotFoundError("npm-check-updates"),
                audit=FileNotFoundError("npm"))
    second = gld.LENS.collect(_ctx(repo, dead, prev=first["digest"]))
    assert second["status"] == "not-collected"
    assert second["digest"] is None

    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d["resolved"] == [], "a missing tool must never look like a fixed dependency"
    assert d["new"] == [] and d["worsened"] == []

    # and when the tool comes back, the prior items are not a wave of "new"
    third = gld.LENS.collect(_ctx(repo, _run(), prev=first["digest"]))
    assert gld.LENS.diff(first["digest"], third["digest"])["new"] == []


def test_real_resolution_still_resolves(tmp_path):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, _run()))
    shrunk = json.loads(NCU_JSON)
    shrunk.pop("eslint")
    second = gld.LENS.collect(
        _ctx(repo, _run(ncu=json.dumps(shrunk)), prev=first["digest"]))
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d["resolved"] == ["deps:ncu:package.json:eslint"]


def test_worsened_when_majors_behind_grows(tmp_path):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, _run()))
    grown = json.loads(NCU_JSON)
    grown["eslint"] = "^12"
    second = gld.LENS.collect(
        _ctx(repo, _run(ncu=json.dumps(grown)), prev=first["digest"]))
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d["worsened"] == ["deps:ncu:package.json:eslint"]
    assert d["new"] == []


def test_worsened_when_severity_rises(tmp_path):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, _run()))
    risen = json.loads(NPM_AUDIT_JSON)
    risen["vulnerabilities"]["body-parser"]["via"][0]["severity"] = "critical"
    second = gld.LENS.collect(
        _ctx(repo, _run(audit=json.dumps(risen)), prev=first["digest"]))
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d["worsened"] == ["deps:audit:node:body-parser:GHSA-V422-HMWV-36X6"]


def test_new_advisory_is_new(tmp_path):
    repo = _node_repo(tmp_path)
    trimmed = json.loads(NPM_AUDIT_JSON)
    trimmed["vulnerabilities"].pop("js-yaml")
    first = gld.LENS.collect(_ctx(repo, _run(audit=json.dumps(trimmed))))
    second = gld.LENS.collect(_ctx(repo, _run(), prev=first["digest"]))
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d["new"] == ["deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M"]


def test_deleted_manifest_resolves_but_undetected_section_does_not(tmp_path):
    repo = _node_repo(tmp_path)
    first = gld.LENS.collect(_ctx(repo, _run()))
    (tmp_path / "package.json").unlink()
    (tmp_path / "README.md").write_text("gone\n")
    second = gld.LENS.collect(_ctx(repo, FakeRun([]), prev=first["digest"]))
    assert second["digest"] is None  # nothing detected → not-collected → digest None
    d = gld.LENS.diff(first["digest"], second["digest"])
    assert d == {"new": [], "worsened": [], "resolved": []}


def test_diff_ignores_a_not_collected_section_with_no_carry_forward():
    """A digest that carries nothing forward must not read as a fleet of fixes."""
    prev = {"detected": ["node"], "ecosystems": {"node": {"freshness": {
        "status": "collected", "items": {"deps:ncu:package.json:x": {"metric": 1}}}}}}
    cur = {"detected": ["node"], "ecosystems": {"node": {"freshness": {
        "status": "not-collected", "reason": "npm-check-updates not available",
        "items": {}}}}}
    assert gld.LENS.diff(prev, cur) == {"new": [], "worsened": [], "resolved": []}


def test_diff_on_malformed_digests_claims_nothing():
    empty = {"new": [], "worsened": [], "resolved": []}
    assert gld.LENS.diff(None, None) == empty
    assert gld.LENS.diff({"ecosystems": {}}, "not-a-digest") == empty
    assert gld.LENS.diff({"junk": 1}, {"junk": 2}) == empty


def test_metric_is_numeric_for_the_ledger_reraise_rule(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run()))
    for cand in out["candidates"]:
        assert isinstance(cand["metric"], (int, float)), cand["id"]
    types_node = _by_id(out["candidates"])["deps:ncu:package.json:@types/node"]
    assert gled.materially_worsened(types_node, {"metricAtDisposition": 1}) is True
    assert gled.materially_worsened(types_node, {"metricAtDisposition": 2}) is False
    vuln = _by_id(out["candidates"])["deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M"]
    assert gled.materially_worsened(vuln, {"metricAtDisposition": 3}) is True


# ================================================================= check-the-check
# The load-bearing coverage / liveness invariant (deliverable #4). Git history is
# injected through the run seam (git -C <repo> ... via run_tool), never store_core.

def test_liveness_under_threshold_is_no_finding(tmp_path):
    """Real weekly-eats history: last renovate[bot] commit 17 days before the measurement."""
    repo = _covered_repo(tmp_path)
    run = _run(git_log=[("--author=renovate", RENOVATE_LAST)])
    result = gld.measure_liveness(_ctx(repo, run), repo, "renovate", "renovate.json", now=NOW)
    assert result["status"] == "measured"
    assert result["days"] == 17
    assert "authored by a `renovate` bot" in result["evidence"]

    out = gld.LENS.collect(_ctx(repo, run, config=_cov(covers=["node"]), now=NOW))
    live = _live(out["digest"])
    assert live["status"] == "collected"
    assert live["stale"] is False
    assert live["staleDays"] == 90
    assert live["days"] == 17
    assert gld.LENS.diff(out["digest"], out["digest"])["new"] == []


def test_stale_check_surfaces_as_a_finding(tmp_path):
    """A configured check that has landed nothing in 137 days IS the finding."""
    repo = _covered_repo(tmp_path)
    baseline = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 137 * DAY)]),
             config=_cov(covers=["node"]), now=NOW))

    live = _live(baseline["digest"])
    assert live["days"] == 137 and live["stale"] is True
    cid = _cov_id("renovate", "renovate.json", "liveness-stale")
    cand = _by_id(baseline["candidates"])[cid]
    assert cand["metric"] == 137
    assert "hasn't landed a dependency update in 137 days" in cand["consequenceHint"]
    assert "drifting behind a check that looks alive on paper" in cand["consequenceHint"]

    # It reaches the report through diff(): fresh (was alive) → stale is `new`.
    alive = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 10 * DAY)]),
             config=_cov(covers=["node"]), now=NOW))
    d = gld.LENS.diff(alive["digest"], baseline["digest"])
    assert cid in d["new"]

    # …and staleness that keeps growing is `worsened`, not silence.
    worse = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 200 * DAY)]),
             config=_cov(covers=["node"]), now=NOW))
    d2 = gld.LENS.diff(baseline["digest"], worse["digest"])
    assert cid in d2["worsened"]

    # a check that starts landing work again resolves
    d3 = gld.LENS.diff(baseline["digest"], alive["digest"])
    assert cid in d3["resolved"]


def test_liveness_threshold_override_from_coverage_entry(tmp_path):
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 40 * DAY)]),
             config=_cov(covers=["node"], staleDays=30), now=NOW))
    live = _live(out["digest"])
    assert live["staleDays"] == 30 and live["stale"] is True
    assert live["days"] == 40


def test_liveness_evidence_ladder(tmp_path):
    repo = _covered_repo(tmp_path)
    # 2. committer match when nothing is authored by the bot
    run = _run(git_log=[("--committer=renovate", NOW - 5 * DAY)])
    result = gld.measure_liveness(_ctx(repo, run), repo, "renovate", "renovate.json", now=NOW)
    assert result["status"] == "measured"
    assert result["days"] == 5 and "committed by" in result["evidence"]
    # 3. manifest/lockfile commit whose message names the tool
    run = _run(git_log=[("--grep=renovate", NOW - 6 * DAY)])
    result = gld.measure_liveness(_ctx(repo, run), repo, "renovate", "renovate.json", now=NOW)
    assert result["status"] == "measured"
    assert result["days"] == 6 and "message names" in result["evidence"]
    # 4. nothing attributable → config-only (NOT proven liveness)
    run = _run(git_log=[("-- renovate.json", NOW - 400 * DAY)])
    result = gld.measure_liveness(_ctx(repo, run), repo, "renovate", "renovate.json", now=NOW)
    assert result["status"] == "config-only"
    assert result.get("configAgeDays") == 400
    assert "never demonstrably" in result["evidence"].lower() or (
        "not evidence" in result["evidence"].lower())


def test_config_only_liveness_suppresses_nothing_and_surfaces_finding(tmp_path):
    """Config age is not proven liveness — a 10-day-old config must not suppress."""
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("-- renovate.json", NOW - 10 * DAY)]),
             config=_cov(covers=["node"]), now=NOW))
    live = _live(out["digest"])
    assert live["status"] == "config-only"
    assert out["digest"]["coverage"]["suppressed"] == {}
    cid = _cov_id("renovate", "renovate.json", "liveness-config-only")
    cand = _by_id(out["candidates"])[cid]
    assert cand["lensKind"] == "coverage-liveness"
    assert "never" in cand["receipt"].lower() or "not evidence" in cand["receipt"].lower()
    assert out["digest"]["ecosystems"]["node"]["freshness"]["status"] == "collected"
    assert run_saw_ncu(out)


def test_unmeasurable_liveness_is_not_collected_not_zero(tmp_path):
    """Unproven liveness must not suppress detection (R1)."""
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(), config=_cov(covers=["node"]), now=NOW))  # empty git_log
    live = _live(out["digest"])
    assert live["status"] == "not-collected"
    assert "liveness NOT measured" in live["reason"]
    assert out["status"] == "partial"
    cid = _cov_id("renovate", "renovate.json", "liveness-unmeasurable")
    cand = _by_id(out["candidates"])[cid]
    assert cand["lensKind"] == "coverage-liveness"
    assert "detection stayed on" in cand["consequenceHint"]
    assert "cannot show" in cand["consequenceHint"]
    assert out["digest"]["coverage"]["suppressed"] == {}
    assert run_saw_ncu(out)
    assert out["digest"]["ecosystems"]["node"]["freshness"]["status"] == "collected"
    assert gld.LENS.diff(out["digest"], out["digest"]) == {
        "new": [], "worsened": [], "resolved": []}


def test_dangling_coverage_path_is_a_finding_and_detection_continues(tmp_path):
    repo = _node_repo(tmp_path)  # no renovate.json on disk
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(covers=["node"]), now=NOW))

    cid = _cov_id("renovate", "renovate.json", "missing-config")
    cand = _by_id(out["candidates"])[cid]
    assert cand["metric"] == 1
    assert "its config is gone" in cand["consequenceHint"]
    assert out["digest"]["coverage"]["missingConfig"] == [cid]

    assert run_saw_ncu(out)
    assert out["digest"]["ecosystems"]["node"]["freshness"]["status"] == "collected"
    assert out["digest"]["coverage"]["suppressed"] == {}

    clean = gld.LENS.collect(
        _ctx(_covered_repo(tmp_path), _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(covers=["node"]), now=NOW))
    d = gld.LENS.diff(clean["digest"], out["digest"])
    assert cid in d["new"]
    assert cid in gld.LENS.diff(out["digest"], clean["digest"])["resolved"]


def test_stale_coverage_does_not_suppress_freshness(tmp_path):
    """R6 / R14.1: stale coverage suppresses nothing — freshness stays on."""
    repo = _covered_repo(tmp_path)
    run = _run(git_log=[("--author=renovate", NOW - 200 * DAY)])
    out = gld.LENS.collect(_ctx(repo, run, config=_cov(covers=["node"]), now=NOW))
    live = _live(out["digest"])
    assert live["stale"] is True
    assert live["days"] == 200
    assert out["digest"]["coverage"]["suppressed"] == {}
    entry = out["digest"]["coverage"]["entries"][0]
    assert entry["suppresses"] == []
    assert "stale" in (entry.get("suppressionReason") or entry.get("note") or "").lower()
    assert run.ran("npm-check-updates"), "stale coverage must keep freshness detection on"
    assert out["digest"]["ecosystems"]["node"]["freshness"]["status"] == "collected"
    assert run_saw_ncu(out)


def test_confirmed_covers_suppresses_exactly_its_ecosystems(tmp_path):
    repo = _repo(tmp_path, {"package.json": PACKAGE_JSON, "renovate.json": RENOVATE_JSON,
                            "pyproject.toml": "[project]\n",
                            "requirements.txt": "filelock==3.19.1\n"})
    run = _run(pip_audit=PIP_AUDIT_JSON, pip_audit_exit=1,
               git_log=[("--author=renovate", RENOVATE_LAST)])
    out = gld.LENS.collect(_ctx(repo, run, config=_cov(covers=["node"]), now=NOW))

    # Python vulns are unrated → lens-level partial; node freshness still suppressed.
    assert out["status"] == "partial", out.get("reason")
    assert not run.ran("npm-check-updates"), "a proven covered check is not re-run"
    assert not any(c["id"].startswith("deps:ncu:") for c in out["candidates"])
    fresh = out["digest"]["ecosystems"]["node"]["freshness"]
    assert fresh["status"] == "suppressed-by-coverage"
    assert "does not re-report what a proven covered check already tracks" in fresh["reason"]

    # python is NOT named by covers → its vulns still fully reported
    assert any(c["id"].startswith("deps:audit:python:") for c in out["candidates"])
    assert sorted(out["digest"]["coverage"]["suppressed"]) == ["node"]


def test_vulnerabilities_are_never_suppressed_by_coverage(tmp_path):
    repo = _covered_repo(tmp_path)
    run = _run(git_log=[("--author=renovate", RENOVATE_LAST)])
    out = gld.LENS.collect(_ctx(repo, run, config=_cov(covers=["node"]), now=NOW))
    assert run.ran("npm audit")
    assert "deps:audit:node:js-yaml:GHSA-52CP-R559-CP3M" in _by_id(out["candidates"])
    assert out["digest"]["ecosystems"]["node"]["vulns"]["status"] == "collected"


def test_suppression_contributes_nothing_to_resolved(tmp_path):
    repo = _covered_repo(tmp_path)
    uncovered = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]), now=NOW))
    covered = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(covers=["node"]), prev=uncovered["digest"], now=NOW))
    d = gld.LENS.diff(uncovered["digest"], covered["digest"])
    assert d["resolved"] == [], "suppressed is not fixed"


def test_inferred_scope_is_provisional_and_suppresses_nothing(tmp_path):
    """Real weekly-eats renovate.json: matchManagers ["npm"] → node inferred, not proven."""
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(), now=NOW))  # no `covers`

    entry = out["digest"]["coverage"]["entries"][0]
    assert entry["covers"] is None
    assert entry["inferredManagers"] == ["github-actions", "npm"]
    assert entry["inferredEcosystems"] == ["node"]
    assert entry["suppresses"] == []
    assert "PROVISIONAL and authorises no suppression" in entry["note"]
    assert out["digest"]["coverage"]["suppressed"] == {}
    assert run_saw_ncu(out)


def test_covers_that_is_not_a_confirmed_list_suppresses_nothing(tmp_path):
    repo = _covered_repo(tmp_path)
    for bad in ([], "node", [""], [1], None):
        out = gld.LENS.collect(
            _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
                 config=_cov(covers=bad), now=NOW))
        assert out["digest"]["coverage"]["suppressed"] == {}, bad
        assert run_saw_ncu(out), bad


def test_covers_naming_an_undetected_ecosystem_suppresses_nothing(tmp_path):
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(covers=["python"]), now=NOW))
    assert out["digest"]["coverage"]["suppressed"] == {}
    assert run_saw_ncu(out)


def test_malformed_coverage_entry_does_not_bind(tmp_path):
    repo = _covered_repo(tmp_path)
    config = {"coverage": [
        {"lens": "deps", "tool": "renovate"},              # no path
        {"lens": "deps", "path": "renovate.json"},         # no tool
        "not-an-object",
        {"lens": "sec", "tool": "x", "path": "y"},         # another lens's entry
    ]}
    out = gld.LENS.collect(_ctx(repo, _run(), config=config, now=NOW))
    whys = [m["why"] for m in out["digest"]["coverage"]["malformed"]]
    assert any("path" in w for w in whys) and any("tool" in w for w in whys)
    assert out["digest"]["coverage"]["entries"] == []
    assert out["digest"]["coverage"]["suppressed"] == {}
    assert run_saw_ncu(out), "malformed coverage must leave detection running"


def test_declined_or_absent_coverage_leaves_detection_running(tmp_path):
    repo = _node_repo(tmp_path)
    for config in ({}, {"coverage": []}, {"coverage": "no thanks"}):
        out = gld.LENS.collect(_ctx(repo, _run(), config=config, now=NOW))
        assert run_saw_ncu(out), config
        assert out["digest"]["coverage"]["suppressed"] == {}


# --------------------------------------------------------------- provisional sensing

def test_provisional_sensing_is_recorded_and_suppresses_nothing(tmp_path):
    repo = _covered_repo(tmp_path)  # renovate.json present, NO coverage configured
    out = gld.LENS.collect(_ctx(repo, _run(), config={}, now=NOW))
    prov = out["digest"]["coverage"]["provisional"]
    assert len(prov) == 1
    assert prov[0]["path"] == "renovate.json"
    assert prov[0]["tool"] == "renovate"
    assert prov[0]["inferredEcosystems"] == ["node"]
    assert prov[0]["confirmed"] is False
    assert prov[0]["suppresses"] is False
    assert "NOT owner-confirmed" in prov[0]["note"]
    assert out["digest"]["coverage"]["suppressed"] == {}
    assert run_saw_ncu(out)


def test_dependabot_sensing(tmp_path):
    yml = ("version: 2\nupdates:\n"
           "  - package-ecosystem: \"npm\"\n    directory: \"/\"\n"
           "  - package-ecosystem: pip\n    directory: \"/\"\n")
    repo = _node_repo(tmp_path, {".github/dependabot.yml": yml})
    out = gld.LENS.collect(_ctx(repo, _run(), config={}, now=NOW))
    prov = out["digest"]["coverage"]["provisional"]
    assert prov[0]["tool"] == "dependabot"
    assert prov[0]["inferredEcosystems"] == ["node", "python"]
    assert out["digest"]["coverage"]["suppressed"] == {}


def test_bound_path_is_not_double_reported_as_provisional(tmp_path):
    repo = _covered_repo(tmp_path)
    out = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", RENOVATE_LAST)]),
             config=_cov(covers=["node"]), now=NOW))
    assert out["digest"]["coverage"]["provisional"] == []


def test_coverage_ids_include_config_path_for_same_tool(tmp_path):
    """Two coverage entries for the same tool at different paths must not collide (R2)."""
    files = {
        "package.json": PACKAGE_JSON,
        "renovate.json": RENOVATE_JSON,
        ".github/renovate.json": RENOVATE_JSON,
    }
    repo = _repo(tmp_path, files)
    config = {"coverage": [
        {"lens": "deps", "tool": "renovate", "path": "renovate.json", "covers": ["node"]},
        {"lens": "deps", "tool": "renovate", "path": ".github/renovate.json",
         "covers": ["node"]},
    ]}
    run = _run(git_log=[("--author=renovate", NOW - 137 * DAY)])
    out = gld.LENS.collect(_ctx(repo, run, config=config, now=NOW))
    cands = _by_id(out["candidates"])
    id_a = _cov_id("renovate", "renovate.json", "liveness-stale")
    id_b = _cov_id("renovate", ".github/renovate.json", "liveness-stale")
    assert id_a in cands and id_b in cands
    assert id_a != id_b
    assert len([c for c in out["candidates"] if c["id"] in (id_a, id_b)]) == 2


def test_liveness_recovery_after_non_collection_no_false_drift(tmp_path):
    """R14.3: measure → unmeasurable → measure carries digest forward; distinct ids."""
    repo = _covered_repo(tmp_path)
    cfg = _cov(covers=["node"])
    stale_id = _cov_id("renovate", "renovate.json", "liveness-stale")
    unmeas_id = _cov_id("renovate", "renovate.json", "liveness-unmeasurable")

    first = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 137 * DAY)]),
             config=cfg, now=NOW))
    first_live = _live(first["digest"])
    assert first_live["status"] == "collected"
    assert first_live["stale"] is True
    assert first_live["days"] == 137
    first_live_snapshot = dict(first_live)

    # unmeasurable: empty git_log → no liveness date at all
    second = gld.LENS.collect(
        _ctx(repo, _run(), config=cfg, prev=first["digest"], now=NOW))
    second_live = _live(second["digest"])
    assert second_live["status"] == "not-collected"
    carried = second_live.get("carriedForward") or {}
    assert carried.get("days") == first_live_snapshot["days"]
    assert carried.get("stale") is True
    d12 = gld.LENS.diff(first["digest"], second["digest"])
    assert stale_id not in d12["resolved"], (
        "going unmeasurable must not report the still-broken stale check as fixed")
    assert unmeas_id in d12["new"], "unmeasurable arising must surface via diff (R7)"

    third = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 137 * DAY)]),
             config=cfg, prev=second["digest"], now=NOW))
    third_live = _live(third["digest"])
    assert third_live["status"] == "collected"
    assert third_live["stale"] is True
    assert third_live["days"] == 137
    d23 = gld.LENS.diff(second["digest"], third["digest"])
    assert unmeas_id in d23["resolved"], "unmeasurable resolves when measurable again"
    assert stale_id in d23["new"], (
        "still-stale after an unmeasurable gap must re-surface under its own identity")
    assert stale_id not in d23["resolved"], (
        "a still-stale check must never be reported as resolved")


def test_liveness_state_machine_distinct_unmeasurable_and_stale_ids(tmp_path):
    """alive → stale → unmeasurable → still-stale → alive with distinct identities."""
    stale_id = _cov_id("renovate", "renovate.json", "liveness-stale")
    unmeas_id = _cov_id("renovate", "renovate.json", "liveness-unmeasurable")
    broken = (stale_id, unmeas_id)
    repo = _covered_repo(tmp_path)
    cfg = _cov(covers=["node"])

    def assert_no_false_all_clear(diff, still_broken):
        for cid in still_broken:
            assert cid not in diff["resolved"], (
                "still-broken %s must not appear in resolved=%r" % (cid, diff["resolved"]))

    # 1. alive
    alive = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 10 * DAY)]),
             config=cfg, now=NOW))
    assert _live(alive["digest"])["stale"] is False
    assert _live(alive["digest"])["status"] == "collected"
    assert stale_id not in _by_id(alive["candidates"])
    assert unmeas_id not in _by_id(alive["candidates"])

    # 2. alive → stale
    stale = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 137 * DAY)]),
             config=cfg, prev=alive["digest"], now=NOW))
    d = gld.LENS.diff(alive["digest"], stale["digest"])
    assert stale_id in d["new"]
    assert unmeas_id not in d["new"]
    assert_no_false_all_clear(d, broken)
    assert stale_id in _by_id(stale["candidates"])

    # 3. stale → unmeasurable (empty git_log)
    unmeas = gld.LENS.collect(
        _ctx(repo, _run(), config=cfg, prev=stale["digest"], now=NOW))
    d = gld.LENS.diff(stale["digest"], unmeas["digest"])
    assert unmeas_id in d["new"]
    assert stale_id not in d["new"]
    assert_no_false_all_clear(d, broken)
    assert unmeas_id in _by_id(unmeas["candidates"])

    # 4. unmeasurable → still-stale (same age as before the gap)
    still = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 137 * DAY)]),
             config=cfg, prev=unmeas["digest"], now=NOW))
    d = gld.LENS.diff(unmeas["digest"], still["digest"])
    assert unmeas_id in d["resolved"]
    assert stale_id in d["new"]
    assert stale_id not in d["resolved"]
    assert_no_false_all_clear(d, (stale_id,))
    assert stale_id in _by_id(still["candidates"])
    assert unmeas_id not in _by_id(still["candidates"])

    # 5. still-stale → alive
    alive2 = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 10 * DAY)]),
             config=cfg, prev=still["digest"], now=NOW))
    d = gld.LENS.diff(still["digest"], alive2["digest"])
    assert stale_id in d["resolved"]
    assert stale_id not in d["new"]
    assert unmeas_id not in d["new"]
    assert unmeas_id not in d["resolved"]
    assert stale_id not in _by_id(alive2["candidates"])
    assert unmeas_id not in _by_id(alive2["candidates"])


# ------------------------------------------------------------------ sweep integration

def test_digest_is_json_serializable(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run()))
    assert json.loads(json.dumps(out["digest"]))["detected"] == ["node"]


def test_sweep_treats_the_result_as_a_lens(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, _run()))
    assert out["status"] in gl.COLLECT_STATUSES
    for cand in out["candidates"]:
        assert isinstance(cand.get("id"), str) and cand["id"]
    reds = gsw._filter_red_lines(gld.LENS.red_lines(out["candidates"]))
    assert reds == []


def test_unmeasurable_liveness_surfaces_through_sweep(tmp_path):
    """R7: unmeasurable-liveness must reach surfaced via real guardian_sweep.collect()."""
    import guardian_store as gs
    from guardian_fixtures import init_calibrated_repo, write_guardian_layer

    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    (repo_path / "package.json").write_text(PACKAGE_JSON)
    (repo_path / "renovate.json").write_text(RENOVATE_JSON)
    repo = init_calibrated_repo(repo_path)
    (repo_path / "package.json").write_text(PACKAGE_JSON)
    (repo_path / "renovate.json").write_text(RENOVATE_JSON)
    write_guardian_layer(repo_path, _cov(covers=["node"]))
    store = str(tmp_path / "store")

    # Prior snapshot: measurable alive coverage (same collector version → not lens_new).
    alive = gld.LENS.collect(
        _ctx(repo, _run(git_log=[("--author=renovate", NOW - 10 * DAY)]),
             config=_cov(covers=["node"]), now=NOW))
    assert _live(alive["digest"])["status"] == "collected"
    assert _live(alive["digest"])["stale"] is False
    gs.write_snapshot_cas(repo, {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"deps": {
            "collectorVersion": gld.COLLECTOR_VERSION,
            "digest": alive["digest"],
        }},
    }, None, root=store)

    # This sweep: empty git_log → unmeasurable liveness (the deps liveness git runs
    # through the injected run; the sweep's own rev-parse runs against the real repo).
    bundle = gsw.collect(repo, lenses=[gld.LENS], root=store, run=_run(),
                         config=_cov(covers=["node"]))
    cid = _cov_id("renovate", "renovate.json", "liveness-unmeasurable")
    surfaced_ids = [s["id"] for s in bundle["surfaced"]]
    assert cid in surfaced_ids, (
        "unmeasurable liveness must reach surfaced, not die in killedByDrift; "
        "surfaced=%r killed=%r" % (surfaced_ids, bundle["funnel"]["killedByDrift"]))


def test_vitals_vuln_count_partial_python_derives_reason_from_section():
    """Partial python vulns gap reason comes from the section's own reason field."""
    section_reason = "some advisories unrated"
    digest = {
        "ecosystems": {
            "node": {
                "vulns": {
                    "status": "collected",
                    "items": {"a": {"id": "a"}, "b": {"id": "b"}},
                },
            },
            "python": {
                "vulns": {
                    "status": "partial",
                    "items": {"c": {"id": "c"}},
                    "reason": section_reason,
                },
            },
        },
    }
    value, reason, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert value == 3
    assert reason is not None
    assert section_reason in reason
    assert "python vulns:" in reason
    assert "pip-audit" not in reason
    assert "#569" not in reason
    assert identity is None


def test_vitals_vuln_count_partial_uses_section_reason_not_template():
    """A different partial reason is reported as-is — not substituted from a constant."""
    custom_reason = "severity source offline this sweep"
    digest = {
        "ecosystems": {
            "python": {
                "vulns": {
                    "status": "partial",
                    "items": {"x": {"id": "x"}},
                    "reason": custom_reason,
                },
            },
        },
    }
    value, reason, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert value == 1
    assert reason == "python vulns: %s" % custom_reason
    assert identity is None


def test_vitals_vuln_count_partial_without_reason_falls_back_generic():
    """Partial section with no reason gets a generic gap naming ecosystem and part."""
    digest = {
        "ecosystems": {
            "python": {
                "vulns": {
                    "status": "partial",
                    "items": {"x": {"id": "x"}},
                },
            },
        },
    }
    value, reason, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert value == 1
    assert reason == "python vulns: partial"
    assert "pip-audit" not in reason
    assert "#569" not in reason
    assert identity is None


def test_vitals_majors_behind_partial_freshness_derives_reason_from_section():
    """Partial freshness gap reason comes from the section's own reason field."""
    section_reason = "registry query timed out"
    digest = {
        "ecosystems": {
            "node": {
                "freshness": {
                    "status": "partial",
                    "reason": section_reason,
                    "items": {},
                },
            },
        },
    }
    value, reason = gld.LENS.vitals(digest)["majorsBehind"]
    assert value is None
    assert reason == "node freshness: %s" % section_reason


def test_vitals_majors_behind_partial_freshness_without_reason_falls_back_generic():
    digest = {
        "ecosystems": {
            "node": {
                "freshness": {
                    "status": "partial",
                    "items": {},
                },
            },
        },
    }
    value, reason = gld.LENS.vitals(digest)["majorsBehind"]
    assert value is None
    assert reason == "node freshness: partial"


def test_vitals_majors_behind_sums_collected_ecosystems():
    digest = {
        "ecosystems": {
            "node": {
                "freshness": {
                    "status": "collected",
                    "majorsBehindTotal": 4,
                    "items": {},
                },
            },
        },
    }
    value, reason = gld.LENS.vitals(digest)["majorsBehind"]
    assert value == 4
    assert reason is None


# ======================================================================================
# Vital identity tokens (#585)
# ======================================================================================

def _vuln_partial_digest(eco, section, *, anchor_eco="node"):
    """Build a digest with one partial vulns section plus an optional anchor eco."""
    ecosystems = {eco: {"vulns": section}}
    if anchor_eco and anchor_eco != eco:
        ecosystems[anchor_eco] = {
            "vulns": {"status": "collected", "items": {"a": {"id": "a"}}},
        }
    return {"ecosystems": ecosystems}


def test_vitals_vuln_count_partial_coverage_gap_emits_identity():
    section = {
        "status": "partial",
        "items": {"c": {"id": "c"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "reason": "no transitive resolution",
    }
    digest = _vuln_partial_digest("python", section)
    value, reason, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert value == 2
    assert reason
    assert "python/vulns/no-transitive-resolution" in identity


def test_vitals_vuln_count_partial_identity_stable_across_reason_reword():
    section_a = {
        "status": "partial",
        "items": {"c": {"id": "c"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "reason": "original advisory prose",
    }
    section_b = dict(section_a, reason="reworded advisory prose for humans")
    id_a = gld.LENS.vitals(_vuln_partial_digest("python", section_a))["vulnCount"][2]
    id_b = gld.LENS.vitals(_vuln_partial_digest("python", section_b))["vulnCount"][2]
    assert id_a == id_b
    assert id_a == ["python/vulns/no-transitive-resolution"]


def test_vitals_vuln_count_partial_malformed_entries_emits_identity():
    section = {
        "status": "partial",
        "items": {"n": {"id": "n"}},
        "malformedEntries": ["left-pad"],
        "reason": "malformed advisory rows",
    }
    digest = _vuln_partial_digest("node", section, anchor_eco="python")
    _, _, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert "node/vulns/malformed-advisory" in identity


def test_vitals_vuln_count_partial_pin_scope_and_boundary_identity():
    pin_section = {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "pinScopeGap": {"lines": ["pkg==1.0"]},
        "reason": "unpinned conditional",
    }
    _, _, pin_id = gld.LENS.vitals(
        _vuln_partial_digest("python", pin_section))["vulnCount"]
    assert "python/vulns/unpinned-scope" in pin_id

    boundary_section = {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "boundary": False,
        "reason": "ambiguous reconciliation",
    }
    _, _, boundary_id = gld.LENS.vitals(
        _vuln_partial_digest("python", boundary_section))["vulnCount"]
    assert "python/vulns/ambiguous-identity" in boundary_id


def test_section_cause_tokens_excludes_findings_state_markers():
    section = {
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "redLineGap": {"kind": "severity-unrated"},
        "carriedForward": True,
    }
    assert gld._section_cause_tokens(section) == ["no-transitive-resolution"]


def test_section_cause_tokens_lockfile_emits_basis_token():
    lockfile_clean = {
        "status": "partial",
        "items": {},
        "auditedScope": {
            "manifest": "poetry.lock",
            "kind": "lockfile",
            "transitive": True,
        },
        "reason": "lockfile clean",
    }
    assert gld._section_cause_tokens(lockfile_clean) == ["lockfile-audit"]

    lockfile_with_pin_gap = dict(
        lockfile_clean,
        pinScopeGap={"lines": ["pkg==1.0"]},
    )
    pin_tokens = gld._section_cause_tokens(lockfile_with_pin_gap)
    assert "lockfile-audit" in pin_tokens
    assert "unpinned-scope" in pin_tokens

    requirements_section = {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "auditedScope": {
            "manifest": "requirements.txt",
            "kind": "requirements",
            "transitive": False,
        },
        "reason": "no transitive resolution",
    }
    req_tokens = gld._section_cause_tokens(requirements_section)
    assert req_tokens == ["no-transitive-resolution"]
    assert "lockfile-audit" not in req_tokens


def test_lockfile_clean_partial_vulncount_identity_not_none():
    section = {
        "status": "partial",
        "items": {},
        "boundary": True,
        "auditedScope": {
            "manifest": "poetry.lock",
            "kind": "lockfile",
            "transitive": True,
        },
        "reason": "lockfile clean",
    }
    digest = _vuln_partial_digest("python", section)
    identity = gld.LENS.vitals(digest)["vulnCount"][2]
    assert identity is not None
    assert identity != []


def test_vitals_vuln_count_structural_not_collected_emits_identity():
    digest = {
        "ecosystems": {
            "node": {
                "vulns": {
                    "status": "collected",
                    "items": {"a": {"id": "a"}},
                },
            },
            "python": {
                "vulns": {
                    "status": "not-collected",
                    "reason": "osv-scanner missing",
                    "items": {},
                },
            },
        },
    }
    _, _, identity = gld.LENS.vitals(digest)["vulnCount"]
    assert "python/vulns/not-collected" in identity


def _fresh_mixed_digest(gap_eco, gap_freshness, *, measured_eco="node", measured_total=3):
    """Build multi-eco digest: one collected freshness + one structural gap."""
    return {
        "ecosystems": {
            measured_eco: {
                "freshness": {
                    "status": "collected",
                    "majorsBehindTotal": measured_total,
                    "items": {},
                },
            },
            gap_eco: {"freshness": gap_freshness},
        },
    }


def test_vitals_majors_behind_structural_not_collected_emits_identity():
    digest = _fresh_mixed_digest("python", {
        "status": "not-collected",
        "reason": "registry query timed out",
        "items": {},
    })
    value, reason, identity = gld.LENS.vitals(digest)["majorsBehind"]
    assert value == 3
    assert reason
    assert "python/freshness/not-collected" in identity


def test_vitals_majors_behind_structural_identity_stable_across_reason_reword():
    gap_a = {
        "status": "not-collected",
        "reason": "original advisory prose",
        "items": {},
    }
    gap_b = dict(gap_a, reason="reworded advisory prose for humans")
    id_a = gld.LENS.vitals(_fresh_mixed_digest("python", gap_a))["majorsBehind"][2]
    id_b = gld.LENS.vitals(_fresh_mixed_digest("python", gap_b))["majorsBehind"][2]
    assert id_a == id_b
    assert id_a == ["python/freshness/not-collected"]


def test_deps_majors_behind_identity_different_basis_not_comparable():
    not_collected = _fresh_mixed_digest("python", {
        "status": "not-collected",
        "reason": "gap",
        "items": {},
    })
    suppressed = _fresh_mixed_digest("python", {
        "status": "suppressed-by-coverage",
        "items": {},
    })
    r_nc = gld.LENS.vitals(not_collected)["majorsBehind"]
    r_sup = gld.LENS.vitals(suppressed)["majorsBehind"]
    _, comp_nc = gv._interpret_vital_tuple(
        r_nc[0], r_nc[1], identity=r_nc[2], lens_name="deps", vital_name="majorsBehind")
    _, comp_sup = gv._interpret_vital_tuple(
        r_sup[0], r_sup[1], identity=r_sup[2], lens_name="deps", vital_name="majorsBehind")
    assert not gv._comparable_completeness(comp_nc, comp_sup)
    assert gv.crossings(
        {"majorsBehind": 1}, {"majorsBehind": 5},
        prev_completeness={"majorsBehind": comp_nc},
        cur_completeness={"majorsBehind": comp_sup}) == []


_VITAL_IDENTITY_TRIPWIRE_CASES = [
    pytest.param("vulnCount", _vuln_partial_digest("python", {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "reason": "osv partial",
    }), id="vuln-partial-coverage"),
    pytest.param("vulnCount", _vuln_partial_digest("node", {
        "status": "partial",
        "items": {"n": {"id": "n"}},
        "malformedEntries": ["left-pad"],
        "reason": "malformed advisory",
    }), id="vuln-partial-malformed"),
    pytest.param("vulnCount", _vuln_partial_digest("python", {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "pinScopeGap": {"lines": ["pkg==1.0"]},
        "reason": "unpinned scope",
    }), id="vuln-partial-pin-scope"),
    pytest.param("vulnCount", _vuln_partial_digest("python", {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "boundary": False,
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "reason": "ambiguous with coverage gap",
    }), id="vuln-partial-boundary"),
    pytest.param("vulnCount", _vuln_partial_digest("python", {
        "status": "partial",
        "items": {},
        "auditedScope": {
            "manifest": "poetry.lock",
            "kind": "lockfile",
            "transitive": True,
        },
        "reason": "lockfile clean",
    }), id="vuln-partial-lockfile-clean"),
    pytest.param("vulnCount", {
        "ecosystems": {
            "node": {
                "vulns": {
                    "status": "collected",
                    "items": {"a": {"id": "a"}},
                },
            },
            "python": {
                "vulns": {
                    "status": "not-collected",
                    "reason": "osv-scanner missing",
                    "items": {},
                },
            },
        },
    }, id="vuln-structural-not-collected"),
    pytest.param("majorsBehind", _fresh_mixed_digest("python", {
        "status": "not-collected",
        "reason": "registry query timed out",
        "items": {},
    }), id="freshness-not-collected"),
    pytest.param("majorsBehind", _fresh_mixed_digest("python", {
        "status": "suppressed-by-coverage",
        "items": {},
    }), id="freshness-suppressed-by-coverage"),
    pytest.param("majorsBehind", _fresh_mixed_digest("python", {
        "status": "collected",
        "items": {},
    }), id="freshness-missing-total"),
]


@pytest.mark.parametrize("vital_name,digest", _VITAL_IDENTITY_TRIPWIRE_CASES)
def test_vitals_partial_sections_always_emit_nonempty_identity(vital_name, digest):
    """Tripwire: every production partial path must classify — never fail-closed silence."""
    reading = gld.LENS.vitals(digest)[vital_name]
    assert len(reading) == 3, reading
    identity = reading[2]
    assert identity is not None
    assert identity != []


def test_deps_vital_identity_reaches_comparability_reworded_prose():
    base = {
        "status": "partial",
        "items": {"c": {"id": "c"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
    }
    r1 = gld.LENS.vitals(_vuln_partial_digest(
        "python", dict(base, reason="severity source offline")))["vulnCount"]
    r2 = gld.LENS.vitals(_vuln_partial_digest(
        "python", dict(base, reason="ratings unavailable this sweep")))["vulnCount"]
    assert r1[2] == r2[2]
    _, comp1 = gv._interpret_vital_tuple(
        r1[0], r1[1], identity=r1[2], lens_name="deps", vital_name="vulnCount")
    _, comp2 = gv._interpret_vital_tuple(
        r2[0], r2[1], identity=r2[2], lens_name="deps", vital_name="vulnCount")
    assert gv._comparable_completeness(comp1, comp2)
    assert gv.crossings(
        {"vulnCount": 1}, {"vulnCount": 5},
        prev_completeness={"vulnCount": comp1},
        cur_completeness={"vulnCount": comp2})


def test_deps_vital_identity_different_basis_not_comparable():
    cov = {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "coverageGap": {"scope": "enumerated-manifest-only"},
        "reason": "gap",
    }
    pin = {
        "status": "partial",
        "items": {"x": {"id": "x"}},
        "pinScopeGap": {"lines": ["pkg==1.0"]},
        "reason": "gap",
    }
    r_cov = gld.LENS.vitals(_vuln_partial_digest("python", cov))["vulnCount"]
    r_pin = gld.LENS.vitals(_vuln_partial_digest("python", pin))["vulnCount"]
    _, comp_cov = gv._interpret_vital_tuple(
        r_cov[0], r_cov[1], identity=r_cov[2], lens_name="deps", vital_name="vulnCount")
    _, comp_pin = gv._interpret_vital_tuple(
        r_pin[0], r_pin[1], identity=r_pin[2], lens_name="deps", vital_name="vulnCount")
    assert not gv._comparable_completeness(comp_cov, comp_pin)
    assert gv.crossings(
        {"vulnCount": 1}, {"vulnCount": 5},
        prev_completeness={"vulnCount": comp_cov},
        cur_completeness={"vulnCount": comp_pin}) == []
