#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_deps.py
"""Guardian dependency-freshness lens — deferred cost said plainly, danger said loudly.

Stdlib-only. Outdated dependencies are deferred cost, not danger; known vulnerabilities
are danger. This lens reports both in their own register and never inflates one into the
other (ratified #41 proposal §3.4, and §3 "coverage is senior").

Every external tool is invoked through ``guardian_collect.run_tool`` — in production the
spawn routes through ``guardian_tools.invoke``'s hardening (neutral cwd, sanitized env,
PATH-only identity-checked resolution, no fetch); in tests / conformance it routes through
the injected ``ctx["run"]`` seam. Because the seam runs collectors from a **neutral cwd**
and ``run_tool`` does not absolutize operands, every argv this lens builds carries
**absolute** repo operands (an ``--packageFile``/``--prefix``/``-r`` path, or ``git -C``).

Two modes:

  A. uncovered (default) — detect ecosystems from repo-root manifests and measure:
     * node freshness  : ``npm-check-updates --packageFile <abs package.json>
       --jsonUpgraded`` (PATH-only; the pinned-npx fetch fallback is gone — an absent
       tool degrades to not-collected quoting the install command).
     * node vulns      : ``npm audit --json --prefix <abs repo>``.
     * python vulns    : ``osv-scanner scan source --format json --no-resolve`` with a
       pinned neutral ``--config`` and ``-L <manifest>:<abs path>`` (PATH). A lockfile
       (``poetry.lock`` / ``uv.lock`` / ``Pipfile.lock``) is preferred when present and
       gives full transitive coverage (every locked entry is exactly pinned); otherwise
       ``requirements.txt`` is audited top-level only (``--no-resolve``). Severity is
       rated from OSV evidence when present; unrated advisories still disclose a
       ``redLineGap``. When osv-scanner is absent or degrades, falls back to
       ``pip-audit --format=json --no-deps -r <abs requirements.txt>`` (PATH, unrated;
       requirements.txt-only).
     * python freshness: NOT collected. ``pip list --outdated`` needs the project's
       installed environment, which the sweep will not execute from inside the
       repository (supply-chain policy). The degradation is disclosed, never faked.
     * rust / go       : NO collector ships in collector 1.0.0. They are recorded as
       explicitly not-collected per ecosystem — never silently omitted, because an
       omitted ecosystem reads as a clean one.

  B. check-the-check — when the owner's guardian.md calibration records a covering tool
     (e.g. Renovate), verify the check still EXISTS (its config path resolves), verify it
     is ALIVE IN PRACTICE (days since it last landed anything, measured from git history
     only via ``git -C <abs repo>`` through the seam — no network), and suppress
     per-package freshness reporting ONLY for ecosystems an owner-confirmed ``covers``
     list names AND only when liveness was proven (measured) AND within its staleness
     threshold. Stale coverage suppresses nothing — the stale finding still surfaces, and
     freshness collection keeps running so drift stays visible alongside it. Config-only
     liveness (config file age with no attributable bot commit — never demonstrably ran)
     and unmeasurable liveness suppress nothing, keep freshness detection running, and
     emit a coverage candidate that reaches the report via diff() when the condition
     arises (and resolves when liveness becomes measurable again). Scope inferred from the
     tool's own config is recorded as provisional and authorises NO suppression.
     Vulnerabilities are never suppressed by coverage. Detection never turns off:
     declined, absent, malformed, dangling, stale, config-only or unprovable coverage all
     leave the uncovered collectors running.
     Coverage candidate ids include the normalized config path so two entries for the
     same tool at different paths cannot collide.

Severity rank (candidate `metric` for vulnerability candidates; higher is worse):

    critical 5 | high 4 | moderate/medium 3 | low 2 | info 1 | unknown 0

`unknown` (rank 0) means THE TOOL REPORTED NO RECOGNIZED SEVERITY — it does not mean harmless.
osv-scanner rates most advisories from OSV evidence; pip-audit (the unrated fallback) carries
no severity field at all. An advisory with `severityKnown: False` is unrated, not
low-severity; the consequence template requires saying so rather than inventing a rating.
Only a tool-reported `critical` raises the `critical-vuln` red line, which is the only
RED_LINE_KINDS member this lens emits.

Fail-closed, visibly: a tool that is missing, times out, errors, or returns unparseable
output yields `not-collected`/`partial` with a reason naming the tool — never an empty
candidate list, which the report card would render as "ran clean". A vulnerability
collector that SIGNALS findings (a metadata count, a findings exit, or non-empty raw
vulnerability entries — including transitive-only ones) but normalizes to ZERO candidates
degrades (`not-collected`) rather than reporting a clean scan (the unified contradiction
gate — see ``_vuln_contradiction``).
"""
import json
import math
import os
import re
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect as gc  # noqa: E402
import guardian_lens as gl  # noqa: E402
import guardian_tools as gt  # noqa: E402

LENS_NAME = "deps"
COLLECTOR_VERSION = "1.1.0"
DIGEST_SCHEMA = 1

# Timeouts are per tool: npm-check-updates queries the registry for every package.
FRESHNESS_TIMEOUT = 180
NPM_AUDIT_TIMEOUT = 120
PIP_AUDIT_TIMEOUT = 180
OSV_TIMEOUT = 180
GIT_TIMEOUT = 60

DEFAULT_STALE_DAYS = 90

SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "moderate": 3,
    "medium": 3,
    "low": 2,
    "info": 1,
    "informational": 1,
    "unknown": 0,
}

# Ordered so digests and candidate lists are deterministic.
ECOSYSTEM_MANIFESTS = (
    ("node", ("package.json",)),
    ("python", ("pyproject.toml", "requirements.txt", "poetry.lock", "uv.lock",
                "Pipfile.lock")),
    ("rust", ("Cargo.toml",)),
    ("go", ("go.mod",)),
)
NO_COLLECTOR_ECOSYSTEMS = ("rust", "go")
NO_COLLECTOR_REASON = (
    "no freshness or vulnerability collector ships for %s in deps collector "
    + COLLECTOR_VERSION + " — this ecosystem was NOT measured, not found clean")

NODE_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml")
PYTHON_LOCKFILES = ("poetry.lock", "uv.lock", "requirements.txt", "Pipfile.lock")

# Files that indicate a dependency-updating check exists, for provisional sensing only.
SENSE_FILES = (
    "renovate.json",
    "renovate.json5",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
)

RENOVATE_MANAGER_ECOSYSTEM = {
    "npm": "node", "pnpm": "node", "yarn": "node", "bun": "node",
    "pip_requirements": "python", "pip_setup": "python", "pipenv": "python",
    "poetry": "python", "pep621": "python", "setup-cfg": "python", "pip-compile": "python",
    "cargo": "rust",
    "gomod": "go",
}
DEPENDABOT_ECOSYSTEM = {
    "npm": "node", "yarn": "node", "pnpm": "node",
    "pip": "python", "uv": "python", "poetry": "python",
    "cargo": "rust",
    "gomod": "go", "go_modules": "go",
}

_RANGE_PREFIX = re.compile(r"^[\s\^~><=v]*")
_LEADING_INT = re.compile(r"^(\d+)")
_GHSA = re.compile(r"(GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})", re.IGNORECASE)
_DEPENDABOT_ECOSYSTEM_LINE = re.compile(
    r"^\s*-?\s*package-ecosystem\s*:\s*[\"']?([A-Za-z0-9_-]+)[\"']?", re.MULTILINE)
_REQUIREMENTS_MAX_BYTES = 1_048_576
_PIN_SCOPE_LINE_MAX = 200
_REQ_NAME_EXTRAS = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(\[[^\]]+\])?")
_REQ_SPECIFIER = re.compile(
    r"(===|==|!=|>=|<=|~=|>|<)\s*([^,;\s]+(?:\s+[^,;]+)?)")


# --------------------------------------------------------------------------- helpers

def _repo_root(ctx):
    """Repo top-level = the sweep's cwd (realpath).

    The base seam runs collectors from a neutral cwd; the repo is the ``ctx["cwd"]`` the
    shell hands us (never re-derived via ``git rev-parse`` — that would route a git spawn
    through the seam only to relocate the root). Mirrors hotspots / duplication.
    """
    cwd = (ctx or {}).get("cwd") or "."
    return os.path.realpath(cwd)


def _load_json(text):
    """(data, error). Never raises."""
    if not (text or "").strip():
        return (None, "empty output")
    try:
        return (json.loads(text), None)
    except ValueError as exc:
        return (None, "unparseable JSON (%s)" % exc)


def _payload(res, tool):
    """Normalize a run_tool result into (data, reason).

    A failed run (ok is False — exit outside the caller's ok_exits) is always
    not-collected, even when stdout happens to parse. Parseable output from a
    failed run may be mentioned in the reason as evidence, never promoted to a
    successful collection.

    When ok is True, a non-zero exit among ok_exits is success-with-findings
    (`npm audit` / `pip-audit` exit 1). What matters then is whether the tool
    handed us parseable output.
    """
    if not res.get("ok"):
        why = res.get("reason") or "failed"
        detail = (res.get("stderr") or "").strip().splitlines()
        tail = (" — " + detail[-1]) if detail else ""
        data, err = _load_json(res.get("stdout"))
        evidence = ""
        if data is not None:
            evidence = " (stdout was parseable but the run failed — not promoted)"
        elif err and err != "empty output":
            evidence = " (stdout also unparseable: %s)" % err
        return (None, "%s: %s%s%s" % (tool, why, tail, evidence))
    data, err = _load_json(res.get("stdout"))
    if err is not None:
        why = err
        detail = (res.get("stderr") or "").strip().splitlines()
        tail = (" — " + detail[-1]) if detail else ""
        return (None, "%s: %s%s" % (tool, why, tail))
    return (data, None)


def _major(spec):
    """Leading major version of a spec/range, or None when not comparable.

    Handles npm alias specs (`npm:@jsr/wei__pluralize@^8.0.2` → 8) and range operators.
    Deliberately returns None (rather than guessing) for `*`, `latest`, `workspace:*`,
    `file:../pkg2` and git URLs — a guessed major is worse than an admitted unknown.
    """
    if not isinstance(spec, str):
        return None
    s = spec.strip()
    if s.startswith("npm:"):
        s = s.rsplit("@", 1)[-1].strip()
    s = _RANGE_PREFIX.sub("", s)
    m = _LEADING_INT.match(s)
    return int(m.group(1)) if m else None


def _majors_behind(current, latest):
    cm, lm = _major(current), _major(latest)
    if cm is None or lm is None:
        return None
    return max(0, lm - cm)


def _section(status, reason=None, **extra):
    out = {"status": status, "reason": reason, "items": {}}
    out.update(extra)
    return out


def _carry_forward(prev_section, status, reason, tool):
    """A part we could not measure: carry the prior items so the next sweep sees no drift."""
    items = {}
    if isinstance(prev_section, dict) and isinstance(prev_section.get("items"), dict):
        items = prev_section["items"]
    return {
        "status": status,
        "reason": reason,
        "tool": tool,
        "items": items,
        "carriedForward": bool(items),
    }


def _prev_part(prev_digest, ecosystem, part):
    if not isinstance(prev_digest, dict):
        return None
    eco = (prev_digest.get("ecosystems") or {}).get(ecosystem)
    if not isinstance(eco, dict):
        return None
    got = eco.get(part)
    return got if isinstance(got, dict) else None


def _carry_prior_items(prev_section, items, predicate):
    """Copy prior advisory items whose ``package`` satisfies ``predicate`` into ``items``
    as carried-forward (never overwriting a fresh item), returning the carried ids.

    The carry-forward vehicle for advisories this sweep did NOT actually re-measure —
    either because the collector could not parse a signalled entry (npm, H2) or because
    the narrowed --no-deps scope never audited that package (python, H1). A carried item
    stays visible to diff() with the SAME id, so a stopped/narrowed measurement can never
    read as a `resolved` (false fixed)."""
    carried = []
    prev_items = prev_section.get("items") if isinstance(prev_section, dict) else None
    if not isinstance(prev_items, dict):
        return carried
    for cid, rec in prev_items.items():
        if cid in items or not isinstance(rec, dict):
            continue
        if predicate(rec.get("package")):
            copy = dict(rec)
            copy["carriedForward"] = True
            items[cid] = copy
            carried.append(cid)
    return carried


def _metric_of(item):
    try:
        return float(item.get("metric"))
    except (AttributeError, TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ ecosystem detection

def detect_ecosystems(repo):
    """[(ecosystem, manifest-relpath)] for repo-root manifests, in a stable order."""
    found = []
    for ecosystem, manifests in ECOSYSTEM_MANIFESTS:
        for rel in manifests:
            if os.path.isfile(os.path.join(repo, rel)):
                found.append((ecosystem, rel))
                break
    return found


# ----------------------------------------------------------------------- node collectors

def _read_package_json(repo, manifest_rel):
    try:
        with open(os.path.join(repo, manifest_rel), encoding="utf-8") as fh:
            return (json.load(fh), None)
    except (OSError, ValueError) as exc:
        return (None, "%s unreadable (%s)" % (manifest_rel, exc))


_PKG_SECTIONS = (
    "dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def _declared_ranges(pkg):
    """{name: (range, section)} across every dependency section of package.json."""
    ranges = {}
    for section in _PKG_SECTIONS:
        block = pkg.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if name not in ranges:
                ranges[name] = (spec, section)
    return ranges


def collect_node_freshness(ctx, repo, manifest_rel):
    """npm-check-updates → {id: item} of outdated packages with majors behind.

    Bin is ``npm-check-updates`` (never the ``ncu`` alias, never npx). The package file
    is passed as an ABSOLUTE ``--packageFile`` operand because the collector runs from a
    neutral cwd. An absent tool degrades to not-collected via run_tool's seam reason
    (which quotes ``guardian_tools.INSTALL_COMMANDS``).
    """
    tool = "npm-check-updates"
    pkg, err = _read_package_json(repo, manifest_rel)
    if pkg is None:
        return _section("not-collected", "%s: %s" % (tool, err), tool=tool)

    abs_manifest = os.path.join(repo, manifest_rel)
    argv = [tool, "--packageFile", abs_manifest, "--jsonUpgraded"]
    started = time.time()
    res = gc.run_tool(argv, ctx, timeout=FRESHNESS_TIMEOUT, cwd=repo)
    seconds = round(time.time() - started, 3)
    data, reason = _payload(res, tool)
    if data is None:
        return _section("not-collected", reason, tool=tool)
    if not isinstance(data, dict):
        return _section(
            "not-collected",
            "%s: expected a JSON object of upgrades, got %s" % (tool, type(data).__name__),
            tool=tool)

    ranges = _declared_ranges(pkg)
    items = {}
    unparsed = []
    for name in sorted(data):
        latest = data[name]
        current, section = ranges.get(name, (None, None))
        behind = _majors_behind(current, latest)
        cid = "deps:ncu:%s:%s" % (manifest_rel, name)
        if behind is None:
            unparsed.append(name)
            receipt = (
                "%s (%s): %s → %s; majors behind NOT computable from these specs"
                % (name, section or "unknown section", current, latest))
        else:
            receipt = (
                "%s (%s): %s → %s (%d major%s behind)"
                % (name, section or "unknown section", current, latest, behind,
                   "" if behind == 1 else "s"))
        items[cid] = {
            "id": cid,
            "package": name,
            "current": current,
            "latest": latest,
            "section": section,
            "majorsBehind": behind,
            "metric": behind if behind is not None else 0,
            "receipt": receipt,
        }
    total = sum(i["majorsBehind"] or 0 for i in items.values())
    return _section(
        "collected", None, tool=tool, items=items, manifest=manifest_rel,
        majorsBehindTotal=total, outdatedPackages=len(items),
        uncomparableSpecs=sorted(unparsed), seconds=seconds, argv=argv)


def _vuln_contradiction(tool, reported, findings_exit, raw_entries, items,
                        transitive_only):
    """The unified contradiction gate for a vulnerability collector.

    Returns a degrade reason string when the tool SIGNALLED findings — ``reported > 0``
    (metadata count) OR a findings exit (npm audit / pip-audit exit 1) OR non-empty raw
    vulnerability entries (incl. transitive-only) — but the normalized candidate count is
    ZERO. Returns None when there is no contradiction (either nothing signalled, or at
    least one candidate was normalized).

    A wholly not-collected digest is discarded by the sweep, so the measured counts have
    to live in the reason (``reportedTotal`` and the transitive-only package count) or the
    report loses them. This closes every path by which a findings-signalling tool reads
    clean — never ``collected`` with zero candidates.
    """
    signaled = bool(reported > 0 or findings_exit or raw_entries)
    if not signaled or items:
        return None
    transitive_n = len(transitive_only or ())
    if transitive_n:
        detail = (
            "%d package(s) were vulnerable only transitively (via another package's "
            "advisory) and are intentionally not surfaced as direct candidates — that "
            "is not a clean scan" % transitive_n)
    elif raw_entries:
        detail = (
            "the raw vulnerability entries were non-empty but none yielded a parseable "
            "advisory candidate")
    else:
        detail = (
            "the tool reported %d vulnerabilit%s via exit/metadata but its output "
            "carried no parseable advisory entries"
            % (reported, "y" if reported == 1 else "ies"))
    return (
        "%s signalled vulnerabilities but normalized zero advisory candidates "
        "(reportedTotal=%d, transitiveOnlyPackages=%d) — %s; refusing to report a "
        "clean scan" % (tool, reported, transitive_n, detail))


def collect_node_vulns(ctx, repo):
    """npm audit --json → {id: item}, one per (package, advisory), occurrences aggregated.

    Scoped to the repo by an ABSOLUTE ``--prefix`` (the collector runs from a neutral
    cwd). npm audit exits 1 whenever it finds a vulnerability — success-with-findings.
    """
    tool = "npm audit"
    # --registry is pinned EXPLICITLY to the public npm registry so a repo-local `.npmrc`
    # cannot redirect the audit POST (which sends the dependency set) to an attacker or
    # internal endpoint. The audit still runs against the repo's own manifest via --prefix.
    argv = ["npm", "audit", "--json", "--registry=https://registry.npmjs.org/",
            "--prefix", repo]
    started = time.time()
    res = gc.run_tool(argv, ctx, timeout=NPM_AUDIT_TIMEOUT,
                      cwd=repo, ok_exits=(0, 1))
    seconds = round(time.time() - started, 3)
    data, reason = _payload(res, tool)
    if data is None:
        return _section("not-collected", reason, tool=tool)
    if not isinstance(data, dict):
        return _section("not-collected",
                        "%s: expected a JSON object, got %s" % (tool, type(data).__name__),
                        tool=tool)
    # `npm audit` reports its own refusals in-band: no lockfile prints
    # {"error": {"code": "ENOLOCK", ...}} on stdout and exits 1. Reading
    # data["vulnerabilities"] with a default here would report a clean repo.
    if isinstance(data.get("error"), dict):
        err = data["error"]
        return _section(
            "not-collected",
            "%s refused: %s — %s" % (tool, err.get("code"), err.get("summary")),
            tool=tool)
    vulns = data.get("vulnerabilities")
    if not isinstance(vulns, dict):
        return _section(
            "not-collected",
            "%s: output carried no 'vulnerabilities' section" % tool, tool=tool)

    items = {}
    transitive_only = []
    malformed_pkgs = []
    for pkg_name in sorted(vulns):
        entry = vulns[pkg_name]
        if not isinstance(entry, dict):
            # A signalled-but-unparseable entry: record the package so a prior advisory for
            # it is carried forward (never silently dropped, never falsely resolved) even
            # when a VALID sibling entry keeps `items` truthy and clears the contradiction
            # gate below (H2).
            malformed_pkgs.append(pkg_name)
            continue
        via_list = entry.get("via")
        via_list = via_list if isinstance(via_list, list) else []
        direct = [v for v in via_list if isinstance(v, dict)]
        if not direct:
            # `via` naming other packages means this one is only an effect of another
            # advisory. Record it so it is never silently dropped.
            transitive_only.append(pkg_name)
            continue
        for via in direct:
            severity = str(via.get("severity") or entry.get("severity") or "unknown").lower()
            rank = SEVERITY_RANK.get(severity, 0)
            advisory = _npm_advisory_id(via, pkg_name, severity)
            cid = "deps:audit:node:%s:%s" % (pkg_name, advisory)
            occurrence = "%s [%s] %s (range %s)" % (
                pkg_name, severity, via.get("title") or "no title",
                via.get("range") or entry.get("range") or "unknown range")
            item = items.get(cid)
            if item is None:
                items[cid] = {
                    "id": cid,
                    "package": pkg_name,
                    "advisory": advisory,
                    "severity": severity,
                    "severityKnown": severity in SEVERITY_RANK and severity != "unknown",
                    "metric": rank,
                    "occurrences": 1,
                    "url": via.get("url"),
                    "isDirect": bool(entry.get("isDirect")),
                    "fixAvailable": bool(entry.get("fixAvailable")),
                    "receipt": occurrence,
                }
            else:
                # Same advisory id can appear twice with different affected ranges
                # (observed: brace-expansion / GHSA-3jxr-9vmj-r5cp in weekly-eats).
                # Duplicate ids are dropped as malformed by the sweep, so aggregate.
                item["occurrences"] += 1
                if rank > item["metric"]:
                    item["metric"] = rank
                    item["severity"] = severity
                    item["severityKnown"] = severity != "unknown"
                item["receipt"] += " | " + occurrence

    reported = 0
    meta = data.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("vulnerabilities"), dict):
        try:
            reported = int(meta["vulnerabilities"].get("total") or 0)
        except (TypeError, ValueError):
            reported = 0

    # THE unified contradiction gate (deliberately replaces the two prior
    # `and not transitive_only` guards): a tool that signalled findings — via a metadata
    # count, exit 1, OR non-empty raw vulnerability entries (INCLUDING transitive-only) —
    # but normalized zero candidates must NEVER read as a clean `collected`.
    # Count EVERY key of a nonempty `vulnerabilities` map, not only the dict-valued ones:
    # a malformed (non-dict) entry is skipped by normalization above, so counting only
    # dict values would let a nonempty-but-unnormalizable map slip the gate at exit 0 /
    # metadata 0 and read clean. Fail closed on schema drift — any nonempty raw map that
    # normalized to zero items is a contradiction.
    raw_entries = len(vulns)
    contradiction = _vuln_contradiction(
        tool, reported, res.get("exit") == 1, raw_entries, items, transitive_only)
    if contradiction is not None:
        return _section("not-collected", contradiction, tool=tool)

    # H2: at least one candidate normalized (the gate cleared), but a malformed sibling
    # entry was signalled and dropped. A partial disclosing the drop — carrying that
    # package's prior advisories forward, never resolving them — keeps the valid findings
    # visible while refusing to read the unparseable signal as a clean scan. A legitimately
    # empty `vulnerabilities: {}` has no malformed entries and stays `collected`.
    if malformed_pkgs:
        malformed_set = set(malformed_pkgs)
        prev_section = _prev_part((ctx or {}).get("prevDigest"), "node", "vulns")
        carried = _carry_prior_items(
            prev_section, items, lambda pkg: pkg in malformed_set)
        reason = (
            "%s returned %d malformed vulnerability entr%s (package(s): %s) that did not "
            "normalize to an advisory; their prior advisories are carried forward, never "
            "resolved — a signalled-but-unparseable entry is not a clean scan"
            % (tool, len(malformed_pkgs), "y" if len(malformed_pkgs) == 1 else "ies",
               ", ".join(sorted(malformed_set))))
        return _section(
            "partial", reason, tool=tool, items=items, reportedTotal=reported,
            transitiveOnly=transitive_only, malformedEntries=sorted(malformed_set),
            carriedForward=bool(carried), seconds=seconds, argv=argv,
            resolution="npm on PATH via the guardian seam (--prefix %s)" % repo)

    return _section(
        "collected", None, tool=tool, items=items, reportedTotal=reported,
        transitiveOnly=transitive_only, seconds=seconds, argv=argv,
        resolution="npm on PATH via the guardian seam (--prefix %s)" % repo)


def _npm_advisory_id(via, pkg_name, severity):
    """Stable advisory identity: GHSA when npm gives one, else its numeric source id.

    When neither is present, fall back to package + severity + range AND title so two
    distinct unidentified advisories that share a range (or a title) do not collapse
    into one candidate (R12). Preferring only `range or title` still merges siblings
    that collide on the preferred field.
    """
    m = _GHSA.search(str(via.get("url") or ""))
    if m:
        return m.group(1).upper()
    source = via.get("source")
    if source not in (None, ""):
        return "npm-%s" % source

    def _slug(value):
        if not isinstance(value, str) or not value.strip():
            return ""
        s = re.sub(r"\s+", "-", value.strip().lower())
        return re.sub(r"[^a-z0-9._<> =+-]", "", s)[:80]

    range_slug = _slug(via.get("range") or "")
    title_slug = _slug(via.get("title") or "")
    parts = [p for p in (range_slug, title_slug) if p]
    discriminator = "+".join(parts) if parts else "unknown"
    return "%s-%s-%s" % (pkg_name, severity, discriminator)


# --------------------------------------------------------------------- python collectors

PYTHON_FRESHNESS_POLICY_REASON = (
    "pip list --outdated requires the project's installed environment, which the sweep "
    "will not execute from inside the repository — supply-chain policy; python freshness "
    "is disclosed as NOT measured, never faked or read as clean")

PYTHON_VULN_RED_LINE_GAP_REASON = (
    "Python advisories carry no severity rating; the critical-vuln red line therefore "
    "cannot fire for those advisories")

PYTHON_VULN_NO_RESOLVE_SCOPE_REASON = (
    "osv-scanner ran with --no-resolve: only the enumerated packages in "
    "requirements.txt were audited; transitive dependencies were NOT resolved (a "
    "vulnerable transitive is invisible to this scan), so prior advisories for packages "
    "this manifest does not enumerate are carried forward, never resolved")

PYTHON_VULN_LOCKFILE_SCOPE_REASON = (
    "osv-scanner audited the full locked dependency graph (including transitive "
    "dependencies) from %s; every locked entry is exactly pinned")

PYTHON_VULN_NO_RESOLVE_COVERAGE_GAP = {
    "ecosystem": "python",
    "tool": "osv-scanner",
    "scope": "enumerated-manifest-only",
    "missing": "transitive dependency resolution — --no-resolve audits only the packages "
               "requirements.txt enumerates; a vulnerable transitive dependency is not "
               "surfaced and prior transitive advisories are not re-measured",
}

PYTHON_VULN_UNPINNED_AUDIT_NOTE = (
    "some requirements are not exactly pinned (==); osv-scanner --no-resolve audits the "
    "lowest satisfying version for ranged requirements, which may not be the deployed "
    "version — findings on those packages are reported but their prior advisories are "
    "never resolved")

PYTHON_VULN_PIP_AUDIT_RED_LINE_GAP_REASON = (
    "Python advisories carry no severity (pip-audit reports none); the "
    "critical-vuln red line therefore cannot fire for Python in this collector "
    "version")

PYTHON_VULN_PIP_AUDIT_RED_LINE_GAP = {
    "ecosystem": "python",
    "tool": "pip-audit",
    "missing": "severity ratings — critical-vuln red line cannot fire for Python",
}

PYTHON_VULN_PIP_AUDIT_NO_DEPS_SCOPE_REASON = (
    "pip-audit ran with --no-deps: only the enumerated packages in requirements.txt were "
    "audited; transitive dependencies were NOT resolved (a vulnerable transitive is "
    "invisible to this scan), so prior advisories for packages this manifest does not "
    "enumerate are carried forward, never resolved")

PYTHON_VULN_PIP_AUDIT_NO_DEPS_COVERAGE_GAP = {
    "ecosystem": "python",
    "tool": "pip-audit",
    "scope": "enumerated-manifest-only",
    "missing": "transitive dependency resolution — --no-deps audits only the packages "
               "requirements.txt enumerates; a vulnerable transitive dependency is not "
               "surfaced and prior transitive advisories are not re-measured",
}


def _prior_alias_set(rec):
    """Alias set for reconciling advisory identity across collectors and sweeps."""
    aliases = set()
    if isinstance(rec, dict):
        adv = rec.get("advisory")
        if isinstance(adv, str) and adv:
            aliases.add(adv)
        for field in ("aliases", "aliasIds"):
            for alias in rec.get(field) or []:
                if isinstance(alias, str) and alias:
                    aliases.add(alias)
    return aliases


def _osv_alias_set(group):
    aliases = set()
    if isinstance(group, dict):
        for gid in group.get("ids") or []:
            if isinstance(gid, str) and gid:
                aliases.add(gid)
        for alias in group.get("aliases") or []:
            if isinstance(alias, str) and alias:
                aliases.add(alias)
    return aliases


def _osv_preferred_id(alias_set):
    """Deterministic advisory id: CVE-* > GHSA-* > PYSEC-* > other (lexicographic)."""
    strings = sorted(a for a in alias_set if isinstance(a, str) and a)
    for prefix in ("CVE-", "GHSA-", "PYSEC-"):
        tier = sorted(a for a in strings if a.upper().startswith(prefix))
        if tier:
            return tier[0].upper()
    return strings[0].upper() if strings else "UNKNOWN"


def _osv_score_band(score):
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "moderate"
    if score > 0:
        return "low"
    return None


def _osv_parse_max_severity(value, all_withdrawn=False):
    """Parse group.max_severity into a severity band, or None when unrecognized."""
    if all_withdrawn:
        return None
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (list, dict)):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or score < 0 or score > 10:
        return None
    if score == 0:
        return None
    return _osv_score_band(score)


def _osv_group_all_withdrawn(group, byid):
    ids = group.get("ids") or []
    if not ids:
        return False
    for gid in ids:
        if not isinstance(gid, str):
            return False
        rec = byid.get(gid)
        if not isinstance(rec, dict) or not rec.get("withdrawn"):
            return False
    return True


def _osv_group_severity(group, byid):
    """Return (severity_str, rank, known_bool) from ALL recognized evidence (max rank)."""
    ranks = []
    severities = []
    for gid in group.get("ids") or []:
        if not isinstance(gid, str):
            continue
        rec = byid.get(gid)
        if not isinstance(rec, dict):
            continue
        if rec.get("withdrawn"):
            continue
        db = rec.get("database_specific")
        if not isinstance(db, dict):
            continue
        label = db.get("severity")
        if not isinstance(label, str) or not label.strip():
            continue
        sev = label.strip().lower()
        if sev == "unknown":
            continue
        rank = SEVERITY_RANK.get(sev)
        if rank is not None:
            ranks.append(rank)
            severities.append(sev)
    all_withdrawn = _osv_group_all_withdrawn(group, byid)
    band = _osv_parse_max_severity(group.get("max_severity"), all_withdrawn=all_withdrawn)
    if band is not None:
        rank = SEVERITY_RANK.get(band)
        if rank is not None:
            ranks.append(rank)
            severities.append(band)
    if not ranks:
        return ("unknown", 0, False)
    max_rank = max(ranks)
    for sev, rank in zip(severities, ranks):
        if rank == max_rank:
            return (sev, max_rank, True)
    return ("unknown", max_rank, True)


def _pep503_canonical(name):
    """PEP 503 normalized name: lowercase; collapse runs of ``-._`` to a single ``-``."""
    if not isinstance(name, str) or not name:
        return ""
    return re.sub(r"[-_.]+", "-", name.lower())


def _pin_scope_line_echo(line):
    """Bounded echo of a requirement line for pinScopeGap disclosure."""
    if not isinstance(line, str):
        return ""
    s = line.strip()
    if len(s) <= _PIN_SCOPE_LINE_MAX:
        return s
    return s[:_PIN_SCOPE_LINE_MAX - 3] + "..."


def _strip_requirement_options(fragment):
    """Drop pip option tokens (``--hash=`` etc.) from the tail of a requirement fragment."""
    parts = fragment.split()
    kept = []
    for part in parts:
        if part.startswith("--"):
            break
        kept.append(part)
    return " ".join(kept).strip()


def _split_requirement_marker(body):
    """Split ``specifiers ; marker`` without treating ``#`` inside URLs as a marker."""
    if ";" not in body:
        return (body, None)
    spec_part, marker = body.split(";", 1)
    return (spec_part.strip(), marker.strip() or None)


def _is_exact_pin_version_tail(version):
    """True when *version* (after any PEP 440 epoch prefix) is a concrete pin."""
    if not version or "*" in version:
        return False
    tail = version
    epoch = re.match(r"^\d+!", tail)
    if epoch:
        tail = tail[epoch.end():]
    if not tail:
        return False
    if any(op in tail for op in (">", "<", "!", "=", "~")):
        return False
    return True


def _is_exact_pin_specifier(operator, version):
    """True only when a single concrete version is positively provable."""
    if operator not in ("==", "==="):
        return False
    return _is_exact_pin_version_tail(version)


def _parse_requirement_specifiers(spec_part):
    """Return [(operator, version), ...] from the specifier tail of a requirement."""
    spec_part = _strip_requirement_options(spec_part)
    if not spec_part:
        return []
    out = []
    for match in _REQ_SPECIFIER.finditer(spec_part):
        op, ver = match.group(1), match.group(2).strip()
        out.append((op, ver))
    return out


def _classify_requirements_line(line):
    """Classify one logical requirements.txt line.

    Returns ``(kind, canonical_name_or_echo, version)`` where *kind* is one of
    ``skip``, ``include``, ``pin``, ``conditional``, or ``unpinned``.
    """
    raw = (line or "").strip()
    if not raw or raw.startswith("#"):
        return ("skip", None, None)

    body = raw
    hash_idx = body.find(" #")
    if hash_idx >= 0:
        body = body[:hash_idx].rstrip()

    if body.startswith(("-r", "-c", "--requirement", "--constraint")):
        return ("include", None, None)
    if body.startswith(("-e", "--editable")):
        return ("unpinned", _pin_scope_line_echo(raw), None)
    if "://" in body or body.startswith(("git+", "hg+", "svn+", "bzr+")):
        return ("unpinned", _pin_scope_line_echo(raw), None)

    name_match = _REQ_NAME_EXTRAS.match(body)
    if not name_match:
        return ("unpinned", _pin_scope_line_echo(raw), None)
    name = name_match.group(1)
    tail = body[name_match.end():].strip()
    spec_part, marker = _split_requirement_marker(tail)
    if marker:
        return ("conditional", _pin_scope_line_echo(raw), None)
    if not spec_part:
        return ("unpinned", _pin_scope_line_echo(raw), None)

    specifiers = _parse_requirement_specifiers(spec_part)
    if not specifiers:
        return ("unpinned", _pin_scope_line_echo(raw), None)
    if len(specifiers) != 1:
        return ("unpinned", _pin_scope_line_echo(raw), None)
    operator, version = specifiers[0]
    if operator in (">=", ">", "<", "<=", "~=", "!="):
        return ("unpinned", _pin_scope_line_echo(raw), None)
    if _is_exact_pin_specifier(operator, version):
        return ("pin", _pep503_canonical(name), version)
    return ("unpinned", _pin_scope_line_echo(raw), None)


def _join_requirement_lines(raw_text):
    """Join ``\\`` continuations and return logical requirement lines."""
    physical = raw_text.splitlines()
    logical = []
    buf = ""
    for line in physical:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1]
            continue
        logical.append(buf + stripped)
        buf = ""
    if buf:
        logical.append(buf)
    return logical


def _parse_requirements_pins(req_abs):
    """Parse requirements.txt into exactly-pinned vs unpinned requirement lines."""
    pins = {}
    unpinned = []
    conditional = []
    has_includes = False
    truncated = False
    try:
        with open(req_abs, "rb") as fh:
            raw_bytes = fh.read(_REQUIREMENTS_MAX_BYTES + 1)
        if len(raw_bytes) > _REQUIREMENTS_MAX_BYTES:
            truncated = True
            raw_bytes = raw_bytes[:_REQUIREMENTS_MAX_BYTES]
            last_nl = raw_bytes.rfind(b"\n")
            raw_bytes = raw_bytes[:last_nl + 1] if last_nl >= 0 else b""
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            raw_bytes = raw_bytes[3:]
        text = raw_bytes.decode("utf-8")
        if truncated:
            # Truncation can preserve a physical line ending in "\" while cutting its
            # continuation payload. Drop that incomplete final logical line.
            physical = text.splitlines()
            if physical and physical[-1].rstrip().endswith("\\"):
                cut = len(physical)
                while cut > 0 and physical[cut - 1].rstrip().endswith("\\"):
                    cut -= 1
                text = "\n".join(physical[:cut])
                if text:
                    text += "\n"
    except (OSError, ValueError) as exc:
        return {
            "pins": pins,
            "unpinned": unpinned,
            "conditional": conditional,
            "hasIncludes": has_includes,
            "truncated": truncated,
            "readError": str(exc),
        }
    for line in _join_requirement_lines(text):
        kind, name_or_line, _version = _classify_requirements_line(line)
        if kind == "pin":
            pins[name_or_line] = name_or_line
        elif kind == "conditional":
            conditional.append(name_or_line)
        elif kind == "unpinned":
            unpinned.append(name_or_line)
        elif kind == "include":
            has_includes = True
    return {
        "pins": pins,
        "unpinned": unpinned,
        "conditional": conditional,
        "hasIncludes": has_includes,
        "truncated": truncated,
    }


def _reconcile_python_vuln_id(package, alias_set, prev_section, base_id):
    """Match a current advisory to a prior item by package + alias intersection."""
    prev_items = prev_section.get("items") if isinstance(prev_section, dict) else None
    if not isinstance(prev_items, dict):
        return (base_id, None)
    pkg_key = _pep503_canonical(package)
    matches = []
    for pid, rec in prev_items.items():
        if not isinstance(rec, dict):
            continue
        if _pep503_canonical(rec.get("package")) != pkg_key:
            continue
        if alias_set & _prior_alias_set(rec):
            matches.append(pid)
    if len(matches) == 1:
        return (matches[0], None)
    if len(matches) > 1:
        return (None, "ambiguous advisory identity for package %s: prior items %s both "
                      "intersect the current alias set" % (package, ", ".join(sorted(matches))))
    return (base_id, None)


def _select_python_audit_manifest(repo):
    """Return (relpath, kind, transitive, osv_type) for the highest-precedence manifest."""
    for rel in ("poetry.lock", "uv.lock", "Pipfile.lock", "requirements.txt"):
        if os.path.isfile(os.path.join(repo, rel)):
            if rel == "requirements.txt":
                return (rel, "requirements", False, "requirements.txt")
            return (rel, "lockfile", True, rel)
    return None


_OSV_SKIP_PKG_RE = re.compile(r"^\s*Skipping\s+([^\s:]+):", re.MULTILINE)
_OSV_FILTERED_COUNT_RE = re.compile(r"Filtered\s+(\d+)\s+local/unscannable")


def _osv_skipped_packages(stderr):
    """Parse osv-scanner stderr for per-package skips and filtered counts."""
    text = stderr or ""
    names = [m.group(1).strip() for m in _OSV_SKIP_PKG_RE.finditer(text)]
    match = _OSV_FILTERED_COUNT_RE.search(text)
    filtered_count = int(match.group(1)) if match else 0
    return names, filtered_count


def _audited_scope(manifest, kind, transitive):
    """Canonical auditedScope dict for python vuln sections."""
    return {
        "manifest": manifest,
        "kind": kind,
        "transitive": bool(transitive),
    }


def _is_queryable_version(version):
    """True when a lockfile version string can be advisory-checked by osv-scanner."""
    if not isinstance(version, str) or not version:
        return False
    if not version[0].isdigit():
        return False
    for bad in ("+", "://", "@", "git", "file:"):
        if bad in version:
            return False
    return True


def _prev_audited_scope(prev_section):
    """Prior (kind, transitive, manifest) for scope-change degrade, or None."""
    if not isinstance(prev_section, dict):
        return None
    scope = prev_section.get("auditedScope")
    if isinstance(scope, dict):
        kind = scope.get("kind")
        manifest = scope.get("manifest")
        transitive = scope.get("transitive")
        if (isinstance(kind, str) and kind and isinstance(manifest, str) and manifest
                and isinstance(transitive, bool)):
            return (kind, transitive, manifest)
        return ("__malformed__", False, "__malformed__")
    items = prev_section.get("items")
    if isinstance(items, dict) and items:
        return ("requirements", False, "requirements.txt")
    return None


def _finalize_osv_python_section(items, prev_section, audited_pkgs, pin_info,
                                  seconds, argv, tool, boundary=True,
                                  ambiguity_disclosures=None, carry_all_prior=False,
                                  kind="requirements", transitive=False,
                                  manifest_rel="requirements.txt", unqueryable=(),
                                  scope_change_disclosure=None):
    """Single finalization path for every osv-scanner partial section."""
    if carry_all_prior:
        _carry_prior_items(prev_section, items, lambda _pkg: True)
    else:
        _carry_prior_items(
            prev_section, items,
            lambda pkg: _pep503_canonical(pkg or "") not in audited_pkgs)

    unrated = [i for i in items.values()
               if isinstance(i, dict) and not i.get("severityKnown")]
    if kind == "lockfile":
        reason_parts = [PYTHON_VULN_LOCKFILE_SCOPE_REASON % manifest_rel]
    else:
        reason_parts = [PYTHON_VULN_NO_RESOLVE_SCOPE_REASON]
    extra = {
        "tool": tool,
        "items": items,
        "seconds": seconds,
        "argv": argv,
        "ratedBy": tool,
        "boundary": boundary,
        "auditedScope": _audited_scope(manifest_rel, kind, transitive),
    }
    if kind == "requirements":
        extra["coverageGap"] = dict(PYTHON_VULN_NO_RESOLVE_COVERAGE_GAP)
        extra["auditCoverage"] = {
            "pinsClassified": len(pin_info.get("pins") or {}),
            "packagesAudited": len(audited_pkgs),
            "unpinnedCount": len(pin_info.get("unpinned") or []),
        }
    else:
        extra["auditCoverage"] = {
            "pinsClassified": 0,
            "packagesAudited": len(audited_pkgs),
            "unpinnedCount": 0,
        }
    if kind == "lockfile":
        if unqueryable:
            extra["pinScopeGap"] = {
                "ecosystem": "python",
                "tool": tool,
                "unqueryable": sorted(unqueryable),
                "count": len(unqueryable),
            }
            reason_parts.append(
                "VCS/path/versionless lockfile entries are not advisory-checked and their "
                "prior advisories are never resolved")
    else:
        unpinned = pin_info.get("unpinned") or []
        conditional = pin_info.get("conditional") or []
        if unpinned or conditional or pin_info.get("hasIncludes"):
            extra["pinScopeGap"] = {
                "ecosystem": "python",
                "tool": tool,
                "unpinned": list(unpinned),
                "count": len(unpinned),
                "hasIncludes": bool(pin_info.get("hasIncludes")),
            }
            if conditional:
                extra["pinScopeGap"]["conditional"] = list(conditional)
                extra["pinScopeGap"]["conditionalCount"] = len(conditional)
            if pin_info.get("truncated"):
                extra["pinScopeGap"]["truncated"] = True
            note_parts = []
            if unpinned:
                note_parts.append(PYTHON_VULN_UNPINNED_AUDIT_NOTE)
            if conditional:
                note_parts.append(
                    "some requirements carry environment markers (conditional install) and "
                    "are not exactly pinned — their prior advisories are never resolved")
            if pin_info.get("hasIncludes"):
                note_parts.append(
                    "requirements.txt contains -r/-c includes — nested requirements the scan "
                    "never saw are not audited")
            if note_parts:
                reason_parts.append("; ".join(note_parts))
    if scope_change_disclosure:
        reason_parts.append(scope_change_disclosure)
    if ambiguity_disclosures:
        reason_parts.append(
            "ambiguous advisory identity (%s) — current findings are reported under fresh "
            "ids, all prior advisories are carried forward and nothing resolves"
            % "; ".join(ambiguity_disclosures))
        extra["boundary"] = False
    if unrated:
        extra["redLineGap"] = {
            "ecosystem": "python",
            "tool": tool,
            "missing": ("%d of %d advisories carry no severity rating; the critical-vuln "
                        "red line cannot fire for those"
                        % (len(unrated), len(items) or len(unrated))),
        }
        reason_parts.insert(0, PYTHON_VULN_RED_LINE_GAP_REASON)
    carried = [cid for cid, rec in items.items()
               if isinstance(rec, dict) and rec.get("carriedForward")]
    if carried:
        extra["carriedForward"] = True
    return _section("partial", "; ".join(reason_parts), **extra)


def collect_python_freshness(ctx, repo, manifest_rel):
    """Python freshness is not collected — honest degradation, disclosed.

    ``pip list --outdated`` reports the INSTALLED environment. Under the base seam a
    project-local interpreter cannot be run (repo-local executables are rejected by
    identity), and the host interpreter's packages are not this project's dependencies.
    So python freshness is reported as not-measured rather than faked.
    """
    del ctx
    return _section(
        "not-collected", PYTHON_FRESHNESS_POLICY_REASON,
        tool="pip list --outdated", manifest=manifest_rel, boundary=True)


def collect_python_vulns_osv(ctx, repo):
    """osv-scanner scan source → {id: item}, one per vulnerability group (not per record).

    Audits the highest-precedence Python manifest (lockfile preferred) by ABSOLUTE path
    with a pinned neutral config so repo-local osv-scanner.toml cannot suppress findings.
    Successful collection is always `partial`: requirements audits only enumerated packages;
    lockfiles audit the full locked graph. A findings signal with zero normalized
    candidates degrades via the contradiction gate.
    """
    tool = "osv-scanner"
    manifest = _select_python_audit_manifest(repo)
    if manifest is None:
        return _section(
            "not-collected",
            "%s: no auditable Python manifest at the repo root (poetry.lock, uv.lock, "
            "Pipfile.lock, or requirements.txt)" % tool,
            tool=tool, boundary=True)

    manifest_rel, kind, transitive, osv_type = manifest
    manifest_abs = os.path.join(repo, manifest_rel)
    pin_info = {}
    exact_pins = {}
    if kind == "requirements":
        pin_info = _parse_requirements_pins(manifest_abs)
        if pin_info.get("readError"):
            return _section(
                "not-collected",
                "%s: requirements.txt unreadable (%s)" % (tool, pin_info["readError"]),
                tool=tool,
                boundary=False)
        exact_pins = pin_info.get("pins") or {}

    config_path = gt.neutral_tool_config(repo, tool)
    # --config is mandatory: osv-scanner auto-discovers osv-scanner.toml in the scanned
    # tree and has no --no-config flag. A repo-local [[IgnoredVulns]] entry can make an
    # affected package vanish from JSON entirely — the red line would silently never fire.
    argv = [
        tool, "scan", "source", "--format", "json", "--no-resolve", "--all-packages",
        "--config", config_path,
        "-L", "%s:%s" % (osv_type, manifest_abs),
    ]
    started = time.time()
    res = gc.run_tool(argv, ctx, timeout=OSV_TIMEOUT, cwd=repo, ok_exits=(0, 1))
    seconds = round(time.time() - started, 3)
    data, reason = _payload(res, tool)
    if data is None:
        return _section("not-collected", reason, tool=tool)
    results = data.get("results")
    if not isinstance(results, list):
        return _section(
            "not-collected",
            "%s: output carried no 'results' array" % tool, tool=tool)

    items = {}
    raw_groups = 0
    malformed = []
    malformed_packages = set()
    audited_pkgs = set()
    unqueryable = set()
    prev_section = _prev_part((ctx or {}).get("prevDigest"), "python", "vulns")
    used_ids = {}
    ambiguity_disclosures = []
    unattributed_skips = False
    if kind == "lockfile":
        skip_names, filtered_count = _osv_skipped_packages(res.get("stderr") or "")
        for skip_name in skip_names:
            unqueryable.add(skip_name)
        if filtered_count > len(skip_names):
            unattributed_skips = True

    def _mark_audited(name, version):
        pkg_key = _pep503_canonical(name)
        if kind == "lockfile":
            if _is_queryable_version(version):
                audited_pkgs.add(pkg_key)
            else:
                unqueryable.add(name)
        elif pkg_key in exact_pins:
            audited_pkgs.add(pkg_key)

    for result in results:
        if not isinstance(result, dict):
            continue
        packages = result.get("packages")
        if not isinstance(packages, list):
            continue
        for pkg_entry in packages:
            if not isinstance(pkg_entry, dict):
                continue
            pkg_info = pkg_entry.get("package")
            if not isinstance(pkg_info, dict):
                malformed.append({"package": None, "why": "missing package object"})
                continue
            name = pkg_info.get("name")
            version = pkg_info.get("version")
            if not isinstance(name, str) or not name:
                malformed.append({"package": None, "why": "missing package name"})
                continue
            has_groups = "groups" in pkg_entry
            has_vulnerabilities = "vulnerabilities" in pkg_entry
            groups = pkg_entry.get("groups")
            if not has_groups and not has_vulnerabilities:
                _mark_audited(name, version)
                continue
            if has_vulnerabilities and not has_groups:
                malformed.append({
                    "package": name,
                    "why": "vulnerabilities present without groups",
                })
                malformed_packages.add(_pep503_canonical(name))
                continue
            if not isinstance(groups, list):
                malformed.append({"package": name, "why": "non-list groups"})
                malformed_packages.add(_pep503_canonical(name))
                continue
            _mark_audited(name, version)
            byid = {}
            for rec in pkg_entry.get("vulnerabilities") or []:
                if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                    byid[rec["id"]] = rec
            for group in groups:
                raw_groups += 1
                if not isinstance(group, dict):
                    malformed.append({"package": name, "why": "group is not an object"})
                    malformed_packages.add(_pep503_canonical(name))
                    continue
                ids = group.get("ids")
                if not isinstance(ids, list) or not ids:
                    malformed.append({"package": name, "why": "group missing ids"})
                    malformed_packages.add(_pep503_canonical(name))
                    continue
                if not all(isinstance(i, str) and i for i in ids):
                    malformed.append({"package": name, "why": "group ids are not strings"})
                    malformed_packages.add(_pep503_canonical(name))
                    continue
                alias_set = _osv_alias_set(group)
                preferred = _osv_preferred_id(alias_set)
                base_id = "deps:audit:python:%s:%s" % (name, preferred)
                cid, reconcile_err = _reconcile_python_vuln_id(
                    name, alias_set, prev_section, base_id)
                if reconcile_err is not None:
                    ambiguity_disclosures.append(reconcile_err)
                    cid = base_id
                elif cid in used_ids and used_ids[cid] != alias_set:
                    ambiguity_disclosures.append(
                        "two groups reconciled to the same id %s" % cid)
                    cid = base_id
                if cid in items and cid != base_id:
                    cid = base_id
                used_ids[cid] = alias_set
                severity, rank, known = _osv_group_severity(group, byid)
                if known:
                    receipt = "%s %s: %s [%s]" % (name, version, preferred, severity)
                else:
                    receipt = (
                        "%s %s: %s [severity not recognized from osv-scanner evidence]"
                        % (name, version, preferred))
                if kind == "requirements" and _pep503_canonical(name) not in exact_pins:
                    receipt += " [audited lowest satisfying version — requirement not exactly pinned]"
                item = items.get(cid)
                if item is None:
                    items[cid] = {
                        "id": cid,
                        "package": name,
                        "installed": version,
                        "advisory": preferred,
                        "aliases": sorted(a for a in alias_set if a != preferred),
                        "aliasIds": sorted(alias_set),
                        "severity": severity,
                        "severityKnown": known,
                        "metric": rank,
                        "occurrences": 1,
                        "receipt": receipt,
                    }
                else:
                    item["occurrences"] += 1
                    if rank > item["metric"]:
                        item["metric"] = rank
                        item["severity"] = severity
                        item["severityKnown"] = known
                    item["receipt"] += " | " + receipt

    audited_pkgs -= {_pep503_canonical(n) for n in unqueryable}

    contradiction = _vuln_contradiction(
        tool, 0, res.get("exit") == 1, raw_groups, items, ())
    if contradiction is not None:
        return _section("not-collected", contradiction, tool=tool)

    cur_scope = (kind, transitive, osv_type)
    prev_scope = _prev_audited_scope(prev_section)
    scope_change_disclosure = None
    scope_changed = False
    if prev_scope is not None and prev_scope != cur_scope:
        scope_changed = True
        scope_change_disclosure = (
            "audit scope changed (%s/%s → %s/%s); all prior advisories carried forward, "
            "none resolved this sweep"
            % (prev_scope[0], prev_scope[2], kind, osv_type))
    if unattributed_skips:
        unattributed_disclosure = (
            "osv-scanner filtered %d unscannable package(s) it did not individually name; "
            "carrying all prior advisories forward" % filtered_count)
        scope_change_disclosure = (
            "%s; %s" % (scope_change_disclosure, unattributed_disclosure)
            if scope_change_disclosure else unattributed_disclosure)

    carry_all_prior = bool(ambiguity_disclosures) or scope_changed or unattributed_skips
    finalize_kw = dict(
        kind=kind, transitive=transitive, manifest_rel=manifest_rel,
        unqueryable=tuple(sorted(unqueryable)),
        scope_change_disclosure=scope_change_disclosure)
    if malformed:
        if any(m.get("package") is None for m in malformed):
            _carry_prior_items(prev_section, items, lambda _pkg: True)
            carry_all_prior = True
        else:
            malformed_set = set(malformed_packages)
            _carry_prior_items(
                prev_section, items, lambda pkg: isinstance(pkg, str)
                and _pep503_canonical(pkg) in malformed_set)
        reason = (
            "%s returned %d malformed vulnerability group(s)%s; advisories measured this "
            "run are still reported"
            % (tool, len(malformed),
               (" including at least one that could not be attributed to a package"
                if any(m.get("package") is None for m in malformed) else
                " (package(s): %s) that did not normalize to an advisory"
                % ", ".join(sorted(malformed_packages)))))
        section = _finalize_osv_python_section(
            items, prev_section, audited_pkgs, pin_info, seconds, argv, tool,
            boundary=False, ambiguity_disclosures=ambiguity_disclosures or None,
            carry_all_prior=carry_all_prior, **finalize_kw)
        section["reason"] = "%s; %s" % (reason, section["reason"])
        if not any(m.get("package") is None for m in malformed):
            section["malformedEntries"] = sorted(malformed_packages)
        return section

    return _finalize_osv_python_section(
        items, prev_section, audited_pkgs, pin_info, seconds, argv, tool,
        boundary=not ambiguity_disclosures,
        ambiguity_disclosures=ambiguity_disclosures or None,
        carry_all_prior=carry_all_prior, **finalize_kw)


def collect_python_vulns_pip_audit(ctx, repo):
    """pip-audit --format=json -r <abs requirements.txt> → {id: item}. NO severity.

    Audits the project's requirements by ABSOLUTE path (the collector runs from a neutral
    cwd). A pyproject-only project has no static manifest pip-audit can audit without
    resolving/installing it in the project environment — the sweep will not do that from
    inside the repo, so that degrades to not-collected.

    Successful collection is always `partial`: the advisories are unrated, so the
    `critical-vuln` red line cannot fire for Python. That gap must be loud
    (degradedLenses + digest redLineGap), never a silent clean collection. A findings
    signal with zero normalized candidates degrades via the contradiction gate.
    """
    tool = "pip-audit"
    req_rel = "requirements.txt"
    req_abs = os.path.join(repo, req_rel)
    if not os.path.isfile(req_abs):
        return _section(
            "not-collected",
            "%s: no requirements.txt at the repo root to audit by absolute path; "
            "auditing a pyproject.toml statically is not supported and resolving it "
            "would require the project's installed environment, which the sweep will "
            "not build from inside the repo — supply-chain policy" % tool, tool=tool)

    # --no-deps audits ONLY the pinned manifest without resolving/fetching the dependency
    # graph, so no build-backend hook runs during the sweep (supply-chain hardening). It
    # requires a fully-pinned requirements.txt; when the manifest is not pinned, pip-audit
    # exits non-zero and this degrades to not-collected honestly (via _payload) rather than
    # silently resolving the graph.
    argv = [tool, "--format=json", "--no-deps", "-r", req_abs]
    started = time.time()
    # pip-audit exits 1 when it finds vulnerabilities — that is success-with-findings.
    res = gc.run_tool(argv, ctx, timeout=PIP_AUDIT_TIMEOUT, cwd=repo, ok_exits=(0, 1))
    seconds = round(time.time() - started, 3)
    data, reason = _payload(res, tool)
    if data is None:
        return _section("not-collected", reason, tool=tool)
    if isinstance(data, dict):
        deps = data.get("dependencies")
    elif isinstance(data, list):
        deps = data
    else:
        deps = None
    if not isinstance(deps, list):
        return _section(
            "not-collected",
            "%s: output carried no 'dependencies' array" % tool, tool=tool)

    items = {}
    raw_entries = 0
    audited_pkgs = set()
    prev_section = _prev_part((ctx or {}).get("prevDigest"), "python", "vulns")
    used_ids = {}
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        name = dep.get("name")
        version = dep.get("version")
        if isinstance(name, str) and name:
            audited_pkgs.add(_pep503_canonical(name))
        for vuln in dep.get("vulns") or []:
            raw_entries += 1
            if not isinstance(vuln, dict):
                continue
            advisory = str(vuln.get("id") or "").strip().upper()
            aliases = [a for a in (vuln.get("aliases") or []) if isinstance(a, str)]
            alias_set = set(aliases)
            if advisory:
                alias_set.add(advisory)
            if not advisory:
                if aliases:
                    advisory = aliases[0].upper()
                else:
                    fixes = [f for f in (vuln.get("fix_versions") or [])
                             if isinstance(f, str)]
                    disc = ",".join(fixes) if fixes else (
                        re.sub(r"\s+", "-", str(vuln.get("description") or "unknown")
                               .strip().lower())[:40] or "unknown")
                    advisory = "%s-UNIDENTIFIED-%s" % (str(name).upper(), disc)
                    alias_set.add(advisory)
            base_id = "deps:audit:python:%s:%s" % (name, advisory)
            cid, reconcile_err = _reconcile_python_vuln_id(
                name, alias_set, prev_section, base_id)
            if reconcile_err is not None:
                return _section("not-collected", "%s: %s" % (tool, reconcile_err),
                                tool=tool)
            if cid in used_ids and used_ids[cid] != alias_set:
                return _section(
                    "not-collected",
                    "%s: ambiguous advisory identity: two advisories reconciled to the "
                    "same id %s" % (tool, cid),
                    tool=tool)
            used_ids[cid] = alias_set
            fixes = [f for f in (vuln.get("fix_versions") or []) if isinstance(f, str)]
            occurrence = "%s %s: %s%s [severity not reported by pip-audit]" % (
                name, version, advisory,
                (" (fixed in %s)" % ", ".join(fixes)) if fixes else " (no fix version)")
            item = items.get(cid)
            if item is None:
                items[cid] = {
                    "id": cid,
                    "package": name,
                    "installed": version,
                    "advisory": advisory,
                    "aliases": [a for a in aliases if a != advisory],
                    "aliasIds": sorted(alias_set),
                    "severity": "unknown",
                    "severityKnown": False,
                    "metric": SEVERITY_RANK["unknown"],
                    "occurrences": 1,
                    "fixVersions": fixes,
                    "receipt": occurrence,
                }
            else:
                item["occurrences"] += 1
                item["receipt"] += " | " + occurrence

    contradiction = _vuln_contradiction(
        tool, 0, res.get("exit") == 1, raw_entries, items, ())
    if contradiction is not None:
        return _section("not-collected", contradiction, tool=tool)

    _carry_prior_items(prev_section, items,
                       lambda pkg: _pep503_canonical(pkg or "") not in audited_pkgs)

    return _section(
        "partial",
        "%s; %s" % (
            PYTHON_VULN_PIP_AUDIT_RED_LINE_GAP_REASON,
            PYTHON_VULN_PIP_AUDIT_NO_DEPS_SCOPE_REASON),
        tool=tool, items=items, seconds=seconds, argv=argv,
        severityNote="pip-audit reports no severity field; every python advisory ranks "
                     "0 = unknown, which means unrated, NOT harmless",
        redLineGap=dict(PYTHON_VULN_PIP_AUDIT_RED_LINE_GAP),
        coverageGap=dict(PYTHON_VULN_PIP_AUDIT_NO_DEPS_COVERAGE_GAP),
        auditedScope=_audited_scope("requirements.txt", "requirements", False),
        ratedBy=tool,
        boundary=False)


def collect_python_vulns(ctx, repo):
    """Try osv-scanner first; fall back to pip-audit when the rated source degrades."""
    osv = collect_python_vulns_osv(ctx, repo)
    if osv["status"] in ("collected", "partial"):
        return osv
    osv_reason = osv.get("reason") or "osv-scanner not collected"
    req_abs = os.path.join(repo, "requirements.txt")
    structural = not os.path.isfile(req_abs)
    pip = collect_python_vulns_pip_audit(ctx, repo)
    if pip["status"] in ("collected", "partial"):
        pip = dict(pip)
        items = dict(pip.get("items") or {})
        prev_section = _prev_part((ctx or {}).get("prevDigest"), "python", "vulns")
        if isinstance(prev_section, dict) and isinstance(prev_section.get("items"), dict):
            for pid, rec in prev_section["items"].items():
                if pid in items:
                    continue
                if not isinstance(rec, dict):
                    continue
                copy = dict(rec)
                copy["carriedForward"] = True
                items[pid] = copy
        pip["items"] = items
        pip["reason"] = (
            "rated source osv-scanner was unavailable (%s); %s"
            % (osv_reason, pip.get("reason") or "pip-audit fallback"))
        pip["boundary"] = True
        return pip
    pip_reason = pip.get("reason") or "pip-audit not collected"
    return _section(
        "not-collected",
        "osv-scanner: %s; pip-audit: %s" % (osv_reason, pip_reason),
        tool="osv-scanner",
        boundary=structural)


def _partial_part_gap(ecosystem, part, section):
    """Gap text for a partial ecosystem part — derived from the section's own reason."""
    reason = section.get("reason") if isinstance(section, dict) else None
    label = "%s %s" % (ecosystem, part)
    if reason:
        return "%s: %s" % (label, reason)
    return "%s: partial" % label


def _section_cause_tokens(section):
    """Stable measurement-basis cause tokens for a partial ecosystem-part section."""
    if not isinstance(section, dict):
        return []
    tokens = []
    if section.get("coverageGap"):
        tokens.append("no-transitive-resolution")
    if section.get("pinScopeGap"):
        tokens.append("unpinned-scope")
    malformed = section.get("malformedEntries")
    if isinstance(malformed, list) and malformed:
        tokens.append("malformed-advisory")
    if section.get("boundary") is False:
        tokens.append("ambiguous-identity")
    scope = section.get("auditedScope")
    if isinstance(scope, dict) and scope.get("kind") == "lockfile":
        tokens.append("lockfile-audit")
    return sorted(set(tokens))


def _majors_behind_vital(digest):
    ecosystems = digest.get("ecosystems") if isinstance(digest, dict) else None
    if not isinstance(ecosystems, dict) or not ecosystems:
        return (None, "digest has no ecosystems to measure")
    measured = []
    gaps = []
    triples = []
    unclassifiable = False
    total = 0
    for eco in sorted(ecosystems):
        section = ecosystems.get(eco)
        if not isinstance(section, dict):
            gaps.append("%s: missing ecosystem section" % eco)
            triples.append("%s/freshness/section-missing" % eco)
            continue
        fresh = section.get("freshness")
        if not isinstance(fresh, dict):
            gaps.append("%s freshness: missing" % eco)
            triples.append("%s/freshness/part-missing" % eco)
            continue
        status = fresh.get("status")
        if status == "suppressed-by-coverage":
            gaps.append("%s freshness: suppressed-by-coverage" % eco)
            triples.append("%s/freshness/suppressed-by-coverage" % eco)
            continue
        if status == "not-collected":
            gaps.append("%s freshness: %s" % (eco, fresh.get("reason") or status))
            triples.append("%s/freshness/not-collected" % eco)
            continue
        if status == "partial":
            gaps.append(_partial_part_gap(eco, "freshness", fresh))
            tokens = _section_cause_tokens(fresh)
            if tokens:
                for cause in tokens:
                    triples.append("%s/freshness/%s" % (eco, cause))
            else:
                unclassifiable = True
            continue
        if status != "collected":
            gaps.append("%s freshness: %s" % (eco, status))
            triples.append("%s/freshness/unknown-status" % eco)
            continue
        if fresh.get("carriedForward"):
            gaps.append("%s freshness: carried forward from prior sweep" % eco)
            triples.append("%s/freshness/carried-forward" % eco)
            continue
        if "majorsBehindTotal" not in fresh:
            gaps.append("%s freshness: missing majorsBehindTotal" % eco)
            triples.append("%s/freshness/missing-total" % eco)
            continue
        try:
            total += int(fresh.get("majorsBehindTotal") or 0)
        except (TypeError, ValueError):
            gaps.append("%s freshness: majorsBehindTotal is not a number" % eco)
            triples.append("%s/freshness/total-nonnumeric" % eco)
            continue
        measured.append(eco)
    if not measured:
        return (None, "; ".join(gaps) or "no ecosystem freshness measured")
    if gaps:
        identity = None if unclassifiable else sorted(set(triples))
        return (total, "; ".join(gaps), identity)
    return (total, None)


def _vuln_count_vital(digest):
    ecosystems = digest.get("ecosystems") if isinstance(digest, dict) else None
    if not isinstance(ecosystems, dict) or not ecosystems:
        return (None, "digest has no ecosystems to measure")
    measured = []
    gaps = []
    triples = []
    unclassifiable = False
    total = 0
    for eco in sorted(ecosystems):
        section = ecosystems.get(eco)
        if not isinstance(section, dict):
            gaps.append("%s: missing ecosystem section" % eco)
            triples.append("%s/vulns/section-missing" % eco)
            continue
        vulns = section.get("vulns")
        if not isinstance(vulns, dict):
            gaps.append("%s vulns: missing" % eco)
            triples.append("%s/vulns/part-missing" % eco)
            continue
        status = vulns.get("status")
        if status == "not-collected":
            gaps.append("%s vulns: %s" % (eco, vulns.get("reason") or status))
            triples.append("%s/vulns/not-collected" % eco)
            continue
        if status not in ("collected", "partial"):
            gaps.append("%s vulns: %s" % (eco, status))
            triples.append("%s/vulns/unknown-status" % eco)
            continue
        if vulns.get("carriedForward"):
            gaps.append("%s vulns: carried forward from prior sweep" % eco)
            triples.append("%s/vulns/carried-forward" % eco)
            continue
        items = vulns.get("items")
        if not isinstance(items, dict):
            gaps.append("%s vulns: items is not an object" % eco)
            triples.append("%s/vulns/items-malformed" % eco)
            continue
        total += len(items)
        measured.append(eco)
        if status == "partial":
            gaps.append(_partial_part_gap(eco, "vulns", vulns))
            tokens = _section_cause_tokens(vulns)
            if tokens:
                for cause in tokens:
                    triples.append("%s/vulns/%s" % (eco, cause))
            else:
                unclassifiable = True
    if not measured:
        return (None, "; ".join(gaps) or "no ecosystem vulnerabilities measured")
    if gaps:
        identity = None if unclassifiable else sorted(set(triples))
        return (total, "; ".join(gaps), identity)
    return (total, None)



def _binding_entries(ctx):
    """(entries, malformed) — coverage entries for this lens with lens/tool/path present."""
    config = (ctx or {}).get("config") or {}
    raw = config.get("coverage")
    entries, malformed = [], []
    if not isinstance(raw, list):
        return (entries, malformed)
    for item in raw:
        if not isinstance(item, dict):
            malformed.append({"entry": repr(item), "why": "not an object"})
            continue
        if item.get("lens") != LENS_NAME:
            continue
        missing = [k for k in ("lens", "tool", "path")
                   if not isinstance(item.get(k), str) or not item.get(k)]
        if missing:
            malformed.append({
                "entry": repr(item),
                "why": "missing required field(s): %s — entry does not bind, "
                       "detection stays on" % ", ".join(missing),
            })
            continue
        entries.append(item)
    return (entries, malformed)


def _confirmed_covers(entry):
    """(covers, note). Only an explicit list of non-empty strings is owner-confirmed."""
    covers = entry.get("covers")
    if covers is None:
        return (None, "no `covers` recorded — scope unproven, nothing suppressed")
    if not isinstance(covers, list) or not covers or not all(
            isinstance(c, str) and c for c in covers):
        return (None, "`covers` is not a non-empty list of ecosystem names (%r) — "
                      "scope unproven, nothing suppressed" % (covers,))
    return ([c for c in covers], None)


def _stale_days(entry):
    raw = entry.get("staleDays")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_STALE_DAYS
    return val if val > 0 else DEFAULT_STALE_DAYS


def _git_epoch(ctx, repo, args):
    """A git ``%at`` epoch from history via the seam, or None.

    Routes through ``gc.run_tool(["git", "-C", <abs repo>, ...])`` — never
    ``store_core.run_git`` — so the spawn inherits the base seam's hardening. ``git -C``
    targets the repo even though the collector runs from a neutral cwd (git resolves via
    PATH; it is not a repo-local executable). A no-match ``git log`` exits 0 with empty
    stdout → None.
    """
    res = gc.run_tool(["git", "-C", repo, *args], ctx=ctx, cwd=repo, timeout=GIT_TIMEOUT)
    if not res.get("ok"):
        return None
    out = (res.get("stdout") or "").strip()
    if not out:
        return None
    try:
        return int(out.splitlines()[0])
    except (ValueError, IndexError):
        return None


def measure_liveness(ctx, repo, tool, config_rel, now=None):
    """Liveness of a covering check from git history only. No network.

    Returns a dict with `status` in {"measured", "config-only", "unmeasurable"}:

      measured     — a commit attributable to the tool (author/committer/subject)
      config-only  — only the config file's own commit date exists; that is NOT
                     evidence the check ran, so callers must not treat it as proven
                     liveness (suppresses nothing; surfaces its own finding)
      unmeasurable — git yielded no date at all

    Evidence ladder for `measured`, strongest first: a commit authored by the tool's
    bot, a commit committed by it, a commit whose subject names it and touches a
    manifest/lockfile.
    """
    now = time.time() if now is None else now
    paths = []
    for _eco, manifests in ECOSYSTEM_MANIFESTS:
        paths.extend(manifests)
    paths.extend(NODE_LOCKFILES)
    paths.extend(PYTHON_LOCKFILES)
    paths = sorted(set(paths))

    attempts = (
        (["log", "-1", "--format=%at", "--regexp-ignore-case", "--author=" + tool],
         "commit authored by a `%s` bot" % tool),
        (["log", "-1", "--format=%at", "--regexp-ignore-case", "--committer=" + tool],
         "commit committed by `%s`" % tool),
        (["log", "-1", "--format=%at", "--regexp-ignore-case", "--grep=" + tool, "--"]
         + paths,
         "manifest/lockfile commit whose message names `%s`" % tool),
    )
    for args, evidence in attempts:
        ts = _git_epoch(ctx, repo, args)
        if ts is not None:
            return {
                "status": "measured",
                "days": max(0, int((now - ts) // 86400)),
                "evidence": evidence,
            }

    ts = _git_epoch(ctx, repo, ["log", "-1", "--format=%at", "--", config_rel])
    if ts is not None:
        age = max(0, int((now - ts) // 86400))
        return {
            "status": "config-only",
            "configAgeDays": age,
            "evidence": (
                "config-only, never demonstrably ran: %s is %d days old — that is NOT "
                "evidence `%s` has landed a dependency update" % (config_rel, age, tool)),
        }
    return {
        "status": "unmeasurable",
        "reason": (
            "git history yielded no date for `%s` or for %s — liveness NOT measured"
            % (tool, config_rel)),
    }


def _infer_renovate_scope(repo, rel):
    """(managers, ecosystems) inferred from a renovate config. Provisional — never proof."""
    try:
        with open(os.path.join(repo, rel), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ([], [])
    if not isinstance(data, dict):
        return ([], [])
    managers = []
    enabled = data.get("enabledManagers")
    if isinstance(enabled, list):
        managers.extend([m for m in enabled if isinstance(m, str)])
    rules = data.get("packageRules")
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("matchManagers"), list):
                managers.extend([m for m in rule["matchManagers"] if isinstance(m, str)])
    ecosystems = sorted({RENOVATE_MANAGER_ECOSYSTEM[m] for m in managers
                         if m in RENOVATE_MANAGER_ECOSYSTEM})
    return (sorted(set(managers)), ecosystems)


def _infer_dependabot_scope(repo, rel):
    """(ecosystem keys, ecosystems) from dependabot YAML by line scan. Provisional only."""
    try:
        with open(os.path.join(repo, rel), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ([], [])
    keys = [m.group(1) for m in _DEPENDABOT_ECOSYSTEM_LINE.finditer(text)]
    ecosystems = sorted({DEPENDABOT_ECOSYSTEM[k] for k in keys if k in DEPENDABOT_ECOSYSTEM})
    return (sorted(set(keys)), ecosystems)


def _infer_scope(repo, rel):
    if os.path.basename(rel).startswith("dependabot"):
        return _infer_dependabot_scope(repo, rel)
    return _infer_renovate_scope(repo, rel)


def sense_provisional(repo, bound_paths):
    """Coverage-looking config found in the repo but NOT owner-confirmed. Never suppresses."""
    out = []
    for rel in SENSE_FILES:
        if rel in bound_paths:
            continue
        if not os.path.exists(os.path.join(repo, rel)):
            continue
        managers, ecosystems = _infer_scope(repo, rel)
        out.append({
            "path": rel,
            "tool": "dependabot" if os.path.basename(rel).startswith("dependabot")
                    else "renovate",
            "inferredManagers": managers,
            "inferredEcosystems": ecosystems,
            "confirmed": False,
            "suppresses": False,
            "note": "sensed from the repo, NOT owner-confirmed: recorded for the advisor "
                    "to confirm into a `covers` entry; suppresses nothing",
        })
    return out


def _normalize_config_path(path):
    """Stable, line-independent config path for coverage candidate ids."""
    norm = (path or "").replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _coverage_candidate_id(tool, path, kind):
    return "deps:coverage:%s:%s:%s" % (tool, _normalize_config_path(path), kind)


def _liveness_key(tool, path):
    return "%s:%s" % (tool, _normalize_config_path(path))


def evaluate_coverage(ctx, repo, detected, now=None):
    """Check-the-check. Returns (coverage-digest, candidates, reasons).

    Suppression requires proven (measured) liveness that is within its staleness
    threshold. Stale coverage, config-only (never demonstrably ran), and unmeasurable
    liveness suppress nothing and leave freshness detection running. Config-only and
    unmeasurable liveness are tracked separately so diff() can surface each when it
    arises and resolve it when the check becomes measurable again.
    """
    entries, malformed = _binding_entries(ctx)
    bound_paths = set()
    candidates = []
    reasons = []
    suppressed = {}
    liveness = {}
    missing_config = []
    unmeasurable_liveness = []
    config_only_liveness = []
    checked = []
    prev_cov = ((ctx or {}).get("prevDigest") or {})
    if not isinstance(prev_cov, dict):
        prev_cov = {}
    prev_cov = prev_cov.get("coverage") or {}
    if not isinstance(prev_cov, dict):
        prev_cov = {}
    prev_live_map = prev_cov.get("liveness") or {}
    if not isinstance(prev_live_map, dict):
        prev_live_map = {}

    for entry in entries:
        tool = entry["tool"]
        rel = entry["path"]
        norm = _normalize_config_path(rel)
        live_key = _liveness_key(tool, rel)
        bound_paths.add(rel)
        exists = os.path.exists(os.path.join(repo, rel))
        covers, covers_note = _confirmed_covers(entry)
        record = {
            "tool": tool,
            "path": rel,
            "configExists": exists,
            "covers": covers,
            "coversNote": covers_note,
            "inferredEcosystems": [],
            "inferredManagers": [],
        }

        if not exists:
            cid = _coverage_candidate_id(tool, rel, "missing-config")
            missing_config.append(cid)
            candidates.append({
                "id": cid,
                "lensKind": "coverage-missing-config",
                "tool": tool,
                "location": rel,
                "metric": 1,
                "receipt": "calibration records %s covering dependencies at %s; that "
                           "path does not exist in the repo" % (tool, rel),
                "consequenceHint": "your calibration says %s covers dependencies; its "
                                   "config is gone, so nothing is keeping them fresh"
                                   % tool,
            })
            record["suppresses"] = []
            record["suppressionReason"] = (
                "not suppressed: config path missing — coverage proves nothing")
            record["note"] = ("dangling config path: coverage proves nothing, "
                              "detection continues uncovered")
            checked.append(record)
            continue

        managers, inferred = _infer_scope(repo, rel)
        record["inferredManagers"] = managers
        record["inferredEcosystems"] = inferred

        live = measure_liveness(ctx, repo, tool, rel, now=now)
        threshold = _stale_days(entry)
        live_status = live.get("status")

        if live_status in ("unmeasurable", "config-only"):
            kind = ("liveness-config-only" if live_status == "config-only"
                    else "liveness-unmeasurable")
            evidence = live.get("evidence") or live.get("reason") or live_status
            cid = _coverage_candidate_id(tool, rel, kind)
            # Digest status: config-only is distinct; unmeasurable stays not-collected
            # so existing carry-forward / diff guards keep working.
            digest_status = ("config-only" if live_status == "config-only"
                             else "not-collected")
            live_entry = {
                "id": cid, "status": digest_status, "reason": evidence,
                "staleDays": threshold, "tool": tool, "path": norm,
            }
            if live_status == "config-only":
                live_entry["configAgeDays"] = live.get("configAgeDays")
            prev_live = prev_live_map.get(live_key) or {}
            if isinstance(prev_live, dict) and prev_live.get("status") == "collected":
                live_entry["carriedForward"] = {
                    "days": prev_live.get("days"),
                    "stale": prev_live.get("stale"),
                    "evidence": prev_live.get("evidence"),
                }
            liveness[live_key] = live_entry
            if live_status == "config-only":
                config_only_liveness.append(cid)
            else:
                unmeasurable_liveness.append(cid)
            reasons.append(evidence)
            age_note = ""
            if live_status == "config-only" and live.get("configAgeDays") is not None:
                age_note = " (config age %d days — not evidence it ran)" % live[
                    "configAgeDays"]
            candidates.append({
                "id": cid,
                "lensKind": "coverage-liveness",
                "tool": tool,
                "location": rel,
                "metric": live.get("configAgeDays") or 0,
                "days": None,
                "staleDays": threshold,
                "stale": None,
                "receipt": ("%s config exists at %s but %s%s; freshness detection "
                            "stayed on" % (tool, rel, evidence, age_note)),
                "consequenceHint": (
                    "%s's config exists at %s but the guardian cannot show it has ever "
                    "landed a dependency update; detection stayed on" % (tool, rel)),
            })
            record["suppresses"] = []
            record["suppressionReason"] = (
                "not suppressed: liveness %s — owner-confirmed covers do not "
                "suppress without proven-alive coverage" % live_status)
            record["note"] = (
                "liveness %s (%s); owner-confirmed covers do not suppress — "
                "detection continues" % (live_status, evidence))
            checked.append(record)
            continue

        days = live["days"]
        evidence = live["evidence"]
        stale = days > threshold
        # Distinct stable identities: stale and unmeasurable/config-only must never
        # share an id, or recovering to the same stale state after a gap falsely
        # clears the finding.
        cid = (_coverage_candidate_id(tool, rel, "liveness-stale") if stale else None)
        liveness[live_key] = {
            "id": cid,
            "status": "collected",
            "days": days,
            "staleDays": threshold,
            "stale": stale,
            "evidence": evidence,
            "tool": tool,
            "path": norm,
        }
        if stale:
            hint = ("%s is configured but hasn't landed a dependency update in %d "
                    "days; your dependencies are drifting behind a check that looks "
                    "alive on paper" % (tool, days))
            candidates.append({
                "id": cid,
                "lensKind": "coverage-liveness",
                "tool": tool,
                "location": rel,
                "metric": days,
                "days": days,
                "staleDays": threshold,
                "stale": True,
                "receipt": "%s: last landed activity %d days ago (%s); staleness "
                           "threshold %d days" % (tool, days, evidence, threshold),
                "consequenceHint": hint,
            })

        detected_ecos = [eco for eco, _rel in detected]
        # Suppression requires proven-alive AND within-threshold coverage (R6).
        if covers and not stale:
            hit = [c for c in covers if c in detected_ecos]
            for eco in hit:
                suppressed[eco] = {
                    "tool": tool,
                    "path": rel,
                    "why": ("owner-confirmed `covers` names %s; liveness proven alive "
                            "within threshold (%d ≤ %d days)" % (eco, days, threshold)),
                }
            record["suppresses"] = sorted(hit)
            record["suppressionReason"] = (
                "suppressed: owner-confirmed covers %s with proven liveness "
                "(%d days ≤ staleDays %d)" % (", ".join(sorted(covers)), days, threshold))
            record["note"] = ("owner-confirmed covers %s; freshness reporting suppressed "
                              "for those ecosystems only, vulnerabilities never"
                              % ", ".join(sorted(covers)))
        elif covers and stale:
            record["suppresses"] = []
            record["suppressionReason"] = (
                "not suppressed: coverage is stale (%d days > staleDays %d) — "
                "freshness detection stays on so drift stays visible alongside the "
                "stale-check finding" % (days, threshold))
            record["note"] = (
                "owner-confirmed covers %s but coverage is STALE (%d > %d days) — "
                "nothing suppressed; freshness detection continues"
                % (", ".join(sorted(covers)), days, threshold))
        else:
            record["suppresses"] = []
            record["suppressionReason"] = (
                covers_note or "not suppressed: no owner-confirmed covers")
            record["note"] = (
                "%s; inferred scope %s is PROVISIONAL and authorises no suppression — "
                "effective scope cannot be proven, so nothing is suppressed"
                % (covers_note, inferred or "unknown"))
        checked.append(record)

    provisional = sense_provisional(repo, bound_paths)
    return ({
        "entries": checked,
        "malformed": malformed,
        "suppressed": suppressed,
        "liveness": liveness,
        "missingConfig": sorted(set(missing_config)),
        "unmeasurableLiveness": sorted(set(unmeasurable_liveness)),
        "configOnlyLiveness": sorted(set(config_only_liveness)),
        "provisional": provisional,
    }, candidates, reasons)


# ------------------------------------------------------------------------------- the lens

VALIDATION_GUIDANCE = """\
Kill a dependency-freshness candidate when the repo itself says the version is a choice,
not a drift:
- the dependency is pinned deliberately — a comment at the pin, a `resolutions`/`overrides`
  entry, a constraint file, or a CLAUDE.md/ADR note saying why;
- a major is deferred for a documented reason (linked issue, migration plan, upstream
  incompatibility recorded in the repo);
- the package is already tracked by a PROVEN covered check — see the digest's
  `coverage.suppressed`. `coverage.provisional` is NOT proof: it is a sensed config the
  owner has not confirmed, so confirm with the owner before killing anything on it;
- an advisory that cannot reach a live code path in this project's declared use (dev-only
  tooling, an unused transitive surface) — say which, from the manifest, not from a guess.
Never kill a candidate merely for being one of many, and never kill a critical-severity
vulnerability for tidiness. An ecosystem or collector the digest marks not-collected is
NOT clean — do not validate it away, and do not let it be reported as if it were measured.
Python vulnerability collection is partial in this collector version: osv-scanner rates
advisories when present (so the `critical-vuln` red line can fire for Python), but
`--no-resolve` audits only enumerated requirements.txt packages — transitive dependencies
are not resolved. When osv-scanner is absent the lens falls back to unrated pip-audit and
discloses that the rated source was unavailable. See the digest's `redLineGap` when any
emitted advisory is still unrated. That is a known capability gap, not a clean bill of
health; do not treat an unrated advisory as low-severity or as already triaged. Python
freshness is not measured at all (it needs the project's installed environment, which the
sweep will not run from inside the repo) — the digest marks it not-collected; that is a
disclosed gap, never a clean bill.
"""

CONSEQUENCE_TEMPLATE = """\
Freshness is deferred cost, stated plainly and never inflated into danger:
  "your toolchain is 18 majors behind; each deferred major makes the eventual jump more
   expensive; none is a known vulnerability today"
State the not-a-vulnerability-today half explicitly ONLY when the vulnerability collector
actually ran for that ecosystem and found nothing; if it did not run, say that instead —
never let a missing collector read as a clean bill of health.
Vulnerabilities get their own sentence, in the register of present danger, and never
borrow freshness's soft framing. When severity is unrated (pip-audit fallback or
osv-scanner evidence missing for an advisory), say the severity is unrated rather than
assigning one.
Coverage findings speak about the check, not the packages:
  "Renovate is configured but hasn't landed a dependency update in 137 days; your
   dependencies are drifting behind a check that looks alive on paper."
  "your calibration says Renovate covers dependencies; its config is gone, so nothing is
   keeping them fresh."
"""


class DepsLens(object):
    """Dependency freshness + known vulnerabilities, with check-the-check for coverage."""

    name = LENS_NAME
    collector_version = COLLECTOR_VERSION
    required_facts = ()
    validation_guidance = VALIDATION_GUIDANCE
    consequence_template = CONSEQUENCE_TEMPLATE
    # Measured 2026-07-21/22 at the command line, not estimated:
    #   weekly-eats (1099 deps): npm-check-updates --jsonUpgraded 3.2s, npm audit 1.2s
    #   home-assistant/core (59 packages): osv-scanner 0.63–0.74s (queries remote OSV DB)
    #   aiogrilla: pip-audit 2.2s (pip-audit 2.9.0, unrated fallback)
    #   renovate liveness from git history: 0.02s
    cost = {
        "collectorSeconds": 6.5,
        "note": "measured on real repos 2026-07-21/22: npm-check-updates 3.2s + npm audit "
                "1.2s (weekly-eats, 1099 deps), osv-scanner 0.63–0.74s over a 59-package "
                "requirements.txt (home-assistant/core, queries remote OSV database), "
                "pip-audit 2.2s (aiogrilla, unrated fallback), git liveness 0.02s. All "
                "collectors are PATH-only through the guardian seam (no npx fetch, no "
                "repo-local interpreter). Freshness collection is skipped entirely for "
                "ecosystems an owner-confirmed `covers` list proves are covered (proven "
                "liveness within the staleness threshold required; stale coverage "
                "suppresses nothing). Python freshness is NOT measured (it needs the "
                "project's installed environment); python vulns need a repo-root "
                "requirements.txt. osv-scanner rates Python advisories when present; "
                "pip-audit is the unrated fallback when osv-scanner is absent (see digest "
                "redLineGap for any still-unrated advisories).",
    }

    # -------------------------------------------------------------------------- collect

    def collect(self, ctx):
        ctx = ctx or {}
        prev = ctx.get("prevDigest")
        repo = _repo_root(ctx)
        detected = detect_ecosystems(repo)
        detected_names = [eco for eco, _rel in detected]

        cov_digest, cov_candidates, cov_reasons = evaluate_coverage(
            ctx, repo, detected, now=ctx.get("now"))
        suppressed = cov_digest["suppressed"]

        ecosystems = {}
        candidates = list(cov_candidates)
        reasons = list(cov_reasons)
        boundary_contributors = [False] * len(cov_reasons)
        collected_any = bool(cov_candidates)
        notes = []
        red_line_gaps = []

        for ecosystem, manifest_rel in detected:
            section = {"manifest": manifest_rel}
            if ecosystem in NO_COLLECTOR_ECOSYSTEMS:
                why = NO_COLLECTOR_REASON % ecosystem
                section["status"] = "not-collected"
                section["reason"] = why
                section["freshness"] = _carry_forward(
                    _prev_part(prev, ecosystem, "freshness"), "not-collected", why, None)
                section["freshness"]["boundary"] = True
                section["vulns"] = _carry_forward(
                    _prev_part(prev, ecosystem, "vulns"), "not-collected", why, None)
                section["vulns"]["boundary"] = True
                reasons.append(why)
                boundary_contributors.append(True)
                notes.append(why)
                ecosystems[ecosystem] = section
                continue

            if ecosystem in suppressed:
                sup = suppressed[ecosystem]
                fresh = _section(
                    "suppressed-by-coverage",
                    "%s covers %s (%s); this lens does not re-report what a proven "
                    "covered check already tracks"
                    % (sup["tool"], ecosystem, sup["why"]),
                    tool=None, manifest=manifest_rel)
            elif ecosystem == "node":
                fresh = collect_node_freshness(ctx, repo, manifest_rel)
            else:
                fresh = collect_python_freshness(ctx, repo, manifest_rel)

            if ecosystem == "node":
                vulns = collect_node_vulns(ctx, repo)
            else:
                vulns = collect_python_vulns(ctx, repo)

            for part_name, part in (("freshness", fresh), ("vulns", vulns)):
                if part["status"] in ("collected", "partial"):
                    collected_any = True
                    for item in part["items"].values():
                        candidates.append(self._candidate(ecosystem, part_name, part, item))
                    if part["status"] == "partial" and part.get("reason"):
                        reasons.append(part["reason"])
                        boundary_contributors.append(part.get("boundary") is True)
                    gap = part.get("redLineGap")
                    if isinstance(gap, dict):
                        red_line_gaps.append(gap)
                elif part["status"] == "not-collected":
                    reasons.append(part["reason"])
                    boundary_contributors.append(part.get("boundary") is True)
                    merged = _carry_forward(
                        _prev_part(prev, ecosystem, part_name), "not-collected",
                        part["reason"], part.get("tool"))
                    part["items"] = merged["items"]
                    part["carriedForward"] = merged["carriedForward"]

            section["freshness"] = fresh
            section["vulns"] = vulns
            statuses = (fresh["status"], vulns["status"])
            if all(s in ("collected", "suppressed-by-coverage") for s in statuses):
                section["status"] = "collected"
                section["reason"] = None
            elif any(s in ("collected", "partial", "suppressed-by-coverage")
                     for s in statuses):
                section["status"] = "partial"
                section["reason"] = "; ".join(
                    [p["reason"] for p in (fresh, vulns)
                     if p["status"] in ("not-collected", "partial") and p.get("reason")])
            else:
                section["status"] = "not-collected"
                section["reason"] = "; ".join(
                    [p["reason"] for p in (fresh, vulns)
                     if p["status"] == "not-collected" and p.get("reason")])
            ecosystems[ecosystem] = section

        digest = {
            "schema": DIGEST_SCHEMA,
            "collectorVersion": COLLECTOR_VERSION,
            "detected": detected_names,
            "ecosystems": ecosystems,
            "coverage": cov_digest,
            "notes": notes,
        }
        if red_line_gaps:
            # One gap per ecosystem for now; keep a single object when there is one so
            # machine consumers can read digest["redLineGap"] without indexing.
            digest["redLineGap"] = (red_line_gaps[0] if len(red_line_gaps) == 1
                                    else red_line_gaps)

        # not-collected returns digest None (the base conformance contract: a degraded
        # collect must not overwrite the tracked snapshot). partial keeps the digest for
        # the portions it did measure.
        if not detected:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected(
                    "no supported dependency manifest at the repo root (looked for "
                    "package.json, pyproject.toml, requirements.txt, Cargo.toml, go.mod)"))
        if not collected_any:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected("; ".join(reasons) or "no dependency data collected"))
        if reasons:
            out = dict(candidates=candidates, digest=digest,
                        **gc.partial("; ".join(reasons)))
            if (out.get("status") == "partial" and boundary_contributors
                    and all(boundary_contributors)):
                out[gl.PERMANENT_BOUNDARY_KEY] = True
            return out
        return dict(candidates=candidates, digest=digest, **gc.collected())

    @staticmethod
    def _candidate(ecosystem, part_name, part, item):
        cand = dict(item)
        cand["lens"] = LENS_NAME
        cand["ecosystem"] = ecosystem
        cand["tool"] = part.get("tool")
        cand["lensKind"] = "freshness" if part_name == "freshness" else "vulnerability"
        return cand

    # ----------------------------------------------------------------------------- diff

    def diff(self, prev_digest, cur_digest):
        empty = {"new": [], "worsened": [], "resolved": []}
        if not isinstance(cur_digest, dict) or "ecosystems" not in cur_digest:
            # Nothing measurable to compare — claim no movement in either direction.
            return empty
        prev_digest = prev_digest if isinstance(prev_digest, dict) else {}
        prev_ecos = prev_digest.get("ecosystems") or {}
        cur_ecos = cur_digest.get("ecosystems") or {}

        new, worsened, resolved = [], [], []

        for ecosystem in sorted(cur_ecos):
            cur_section = cur_ecos[ecosystem] or {}
            prev_section = prev_ecos.get(ecosystem) or {}
            for part_name in ("freshness", "vulns"):
                cur_part = cur_section.get(part_name) or {}
                prev_part = prev_section.get(part_name) or {}
                if cur_part.get("status") not in ("collected", "partial"):
                    # Not measured this run (missing tool, suppressed, no collector):
                    # it contributes NOTHING — least of all `resolved`.
                    # `partial` IS measured (e.g. python vulns with the severity gap).
                    continue
                cur_items = cur_part.get("items") or {}
                prev_items = prev_part.get("items") or {}
                prev_measured = prev_part.get("status") in ("collected", "partial")
                for cid in sorted(cur_items):
                    if cid not in prev_items:
                        # Carried-forward prev items still count as "seen before", so a
                        # tool coming back after a failed run raises no false wave of new.
                        new.append(cid)
                    elif _metric_of(cur_items[cid]) > _metric_of(prev_items[cid]):
                        worsened.append(cid)
                if prev_measured:
                    for cid in sorted(prev_items):
                        if cid not in cur_items:
                            resolved.append(cid)

        # An ecosystem whose manifest is genuinely gone this run (absent from `detected`)
        # really is resolved; an ecosystem that is still detected but missing a section
        # was not measured, and stays silent.
        cur_detected = cur_digest.get("detected")
        if isinstance(cur_detected, list):
            for ecosystem in sorted(prev_ecos):
                if ecosystem in cur_ecos or ecosystem in cur_detected:
                    continue
                for part_name in ("freshness", "vulns"):
                    part = (prev_ecos[ecosystem] or {}).get(part_name) or {}
                    if part.get("status") not in ("collected", "partial"):
                        continue
                    resolved.extend(sorted(part.get("items") or {}))

        new_c, worsened_c, resolved_c = self._coverage_diff(prev_digest, cur_digest)
        new.extend(new_c)
        worsened.extend(worsened_c)
        resolved.extend(resolved_c)
        return {"new": sorted(set(new)), "worsened": sorted(set(worsened)),
                "resolved": sorted(set(resolved))}

    @staticmethod
    def _coverage_diff(prev_digest, cur_digest):
        new, worsened, resolved = [], [], []
        prev_cov = prev_digest.get("coverage") or {}
        cur_cov = cur_digest.get("coverage") or {}

        prev_missing = set(prev_cov.get("missingConfig") or [])
        cur_missing = set(cur_cov.get("missingConfig") or [])
        for cid in sorted(cur_missing - prev_missing):
            new.append(cid)
        for cid in sorted(prev_missing - cur_missing):
            resolved.append(cid)

        # Unmeasurable / config-only liveness surface when they arise and resolve when
        # measurable again (R7) — tracked separately so they are not discarded by the
        # collected-only liveness path below. Their ids are distinct from the stale id
        # so clearing a gap never looks like clearing a still-stale check.
        prev_unmeas = set(prev_cov.get("unmeasurableLiveness") or [])
        cur_unmeas = set(cur_cov.get("unmeasurableLiveness") or [])
        for cid in sorted(cur_unmeas - prev_unmeas):
            new.append(cid)
        for cid in sorted(prev_unmeas - cur_unmeas):
            resolved.append(cid)

        prev_cfg_only = set(prev_cov.get("configOnlyLiveness") or [])
        cur_cfg_only = set(cur_cov.get("configOnlyLiveness") or [])
        for cid in sorted(cur_cfg_only - prev_cfg_only):
            new.append(cid)
        for cid in sorted(prev_cfg_only - cur_cfg_only):
            resolved.append(cid)

        prev_live = prev_cov.get("liveness") or {}
        cur_live = cur_cov.get("liveness") or {}

        def _stale_cid(entry, key):
            if entry.get("id"):
                return entry["id"]
            tool = entry.get("tool") or key.split(":", 1)[0]
            path = entry.get("path") or (key.split(":", 1)[1] if ":" in key else key)
            return _coverage_candidate_id(tool, path, "liveness-stale")

        def _unproven(status):
            return status in ("not-collected", "config-only", "unmeasurable")

        for key in sorted(cur_live):
            cur_entry = cur_live[key] or {}
            if cur_entry.get("status") != "collected":
                continue  # unproven handled via unmeasurable/configOnly lists above
            prev_entry = prev_live.get(key) or {}
            prev_status = prev_entry.get("status")
            prev_ok = prev_status == "collected"
            carried = (prev_entry.get("carriedForward") or {}) if (
                _unproven(prev_status)) else {}
            if cur_entry.get("stale"):
                cid = _stale_cid(cur_entry, key)
                if _unproven(prev_status):
                    # Distinct identity from unmeasurable/config-only: recovering to
                    # stale after a gap always surfaces the stale id as new.
                    new.append(cid)
                elif not prev_ok or not prev_entry.get("stale"):
                    new.append(cid)
                elif (cur_entry.get("days") or 0) > (prev_entry.get("days") or 0):
                    worsened.append(cid)
            elif prev_ok and prev_entry.get("stale"):
                resolved.append(_stale_cid(prev_entry, key))
            elif _unproven(prev_status) and carried.get("stale"):
                # Was stale before the gap, now alive — the stale condition resolved.
                tool = (cur_entry.get("tool") or prev_entry.get("tool")
                        or key.split(":", 1)[0])
                path = (cur_entry.get("path") or prev_entry.get("path")
                        or (key.split(":", 1)[1] if ":" in key else key))
                resolved.append(_coverage_candidate_id(tool, path, "liveness-stale"))
        for key in sorted(prev_live):
            if key in cur_live:
                continue
            prev_entry = prev_live[key] or {}
            if prev_entry.get("status") == "collected" and prev_entry.get("stale"):
                resolved.append(_stale_cid(prev_entry, key))
        return (new, worsened, resolved)

    # -------------------------------------------------------------------------- vitals

    def vitals(self, digest):
        """→ {vital_name: (value | None, reason | None)}

        (value, None)    -> complete       — a full measurement
        (value, reason)  -> partial        — a real number over the portion measured,
                                             with `reason` naming exactly what is missing
        (None,  reason)  -> not-collected  — nothing publishable; `reason` says why
        """
        if not isinstance(digest, dict):
            reason = "digest is not an object"
            return {"majorsBehind": (None, reason), "vulnCount": (None, reason)}
        return {
            "majorsBehind": _majors_behind_vital(digest),
            "vulnCount": _vuln_count_vital(digest),
        }

    # ------------------------------------------------------------------------ red lines

    def red_lines(self, candidates):
        out = []
        for cand in candidates or []:
            if not isinstance(cand, dict):
                continue
            if cand.get("lensKind") != "vulnerability":
                continue
            if str(cand.get("severity") or "").lower() != "critical":
                continue
            out.append({
                "kind": "critical-vuln",
                "id": cand["id"],
                "detail": "%s: critical-severity advisory %s (%s)" % (
                    cand.get("package"), cand.get("advisory"),
                    cand.get("receipt") or "no receipt"),
            })
        return out

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}

    # ---------------------------------------------------------------------- conformance

    def conformance_fixture(self):
        """Minimal manifest set so collect() reaches npm audit under the injected run stub.

        ``package.json`` (so node is detected + freshness has a manifest to read) plus
        ``package-lock.json`` (so the audit is nominally scoped). The harness writes these
        into a fresh temp dir used as both ctx["cwd"] and ctx["root"].
        """
        return {
            "package.json": json.dumps({
                "name": "guardian-deps-conformance",
                "dependencies": {"left-pad": "^1.0.0"},
            }) + "\n",
            "package-lock.json": json.dumps({
                "name": "guardian-deps-conformance",
                "lockfileVersion": 3,
                "packages": {},
            }) + "\n",
        }

    def conformance_cases(self):
        """Lens-supplied ``reported-nonzero-parsed-zero`` payload (see lens-contract.md).

        This lens runs TWO node collectors under the fixture — ``npm-check-updates``
        (freshness) and ``npm audit`` (vulns). The case uses the harness's PER-argv[0]
        stdout dispatch (``stdout_by_tool`` / ``clean_stdout_by_tool``) so ONLY ``npm
        audit`` (argv[0] ``"npm"``) gets the findings payload; the co-firing ncu
        (argv[0] ``"npm-check-updates"``) always gets a CLEAN upgrade map. That isolation
        is what makes the vuln contradiction gate LOAD-BEARING in conformance: with a
        single shared stdout the ncu run would degrade the whole lens on exit 1 regardless
        of the vuln gate, so deleting ``_vuln_contradiction`` would still pass. With the
        dispatch, ncu collects cleanly and the ONLY thing that can degrade the findings
        probe is the vuln gate — delete it and the deps conformance case fails.

        npm-audit declares dual success exits (``exit=1`` findings, ``clean_exit=0`` clean):

        - clean probe: npm audit gets zero-vuln JSON (metadata total 0) at exit 0 and ncu
          gets ``{}`` (an empty upgrade map) at exit 0 → whole-lens ``collected``.
        - findings probe: npm audit gets JSON that REPORTS vulnerabilities (metadata total
          3) but normalizes to zero candidates (empty ``vulnerabilities`` object) at exit 1
          → the vuln contradiction gate degrades ``npm audit`` to ``not-collected``; ncu
          collects a clean empty map → whole-lens ``partial``. It must never read as
          ``collected``.

        ``stdout`` / ``clean_stdout`` remain as the single-stdout fallback (backward
        compatible with lenses that declare no per-tool maps).
        """
        clean = json.dumps({
            "auditReportVersion": 2,
            "vulnerabilities": {},
            "metadata": {"vulnerabilities": {
                "info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0,
                "total": 0}},
        })
        reported = json.dumps({
            "auditReportVersion": 2,
            "vulnerabilities": {},
            "metadata": {"vulnerabilities": {
                "info": 0, "low": 0, "moderate": 0, "high": 3, "critical": 0,
                "total": 3}},
        })
        empty_upgrades = json.dumps({})  # ncu --jsonUpgraded clean = no upgrades
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": reported,
                "clean_stdout": clean,
                "exit": 1,
                "clean_exit": 0,
                # npm audit (argv[0] "npm") is the target; ncu gets a clean upgrade map.
                "stdout_by_tool": {"npm": reported},
                "clean_stdout_by_tool": {"npm-check-updates": empty_upgrades},
            },
        }

    def conformance_prev_digest(self):
        """A schema-valid prior digest carrying ONE recognizable node-vuln sentinel, plus
        the same digest re-measured clean, for the conformance non-vacuity check.

        The harness first asserts ``diff(prev, cleared)`` RESOLVES the sentinel (proving the
        lens's diff actually tracks it — otherwise "resolved must be empty" on the findings
        probe would be vacuous), then asserts the degraded findings probe resolves nothing.
        """
        sentinel_id = "deps:audit:node:sentinel-pkg:GHSA-sent-sent-sent"
        vuln_item = {
            "id": sentinel_id,
            "package": "sentinel-pkg",
            "advisory": "GHSA-sent-sent-sent",
            "severity": "high",
            "severityKnown": True,
            "metric": SEVERITY_RANK["high"],
            "occurrences": 1,
            "receipt": "sentinel-pkg [high] conformance sentinel advisory",
        }

        def _digest(vuln_items):
            return {
                "schema": DIGEST_SCHEMA,
                "collectorVersion": COLLECTOR_VERSION,
                "detected": ["node"],
                "ecosystems": {
                    "node": {
                        "manifest": "package.json",
                        "status": "partial",
                        "reason": None,
                        "freshness": {"status": "collected",
                                      "tool": "npm-check-updates", "items": {}},
                        "vulns": {"status": "collected", "tool": "npm audit",
                                  "items": vuln_items},
                    },
                },
                "coverage": {},
                "notes": [],
            }

        return {
            "prev": _digest({sentinel_id: vuln_item}),
            "cleared": _digest({}),
            "sentinelIds": [sentinel_id],
        }


LENS = DepsLens()
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
