#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_coupling.py
"""The Guardian coupling lens — a data-gatherer with a high findings bar.

Stdlib-only. One lens object, `coupling`, covering BOTH ecosystems in a single
`collect()` — dependency-cruiser for JS/TS and a stdlib AST import census for
Python — exported as `LENSES = (LENS,)` for registration (mirrors the deps
multi-ecosystem-in-one-lens shape).

**Why one lens.** Main's production roster registers one name per module entry;
both ecosystems share one digest, one diff, and one status. A flat/unanalyzable
Python side while JS collected is `partial` (reason names what degraded); a
healthy JS side never implies Python was clean — per-ecosystem status lives in
the digest. Nothing collectable (no sources, or every side degraded) is
`not-collected` with `digest=None`.

**Why the bar is structural.** Both hands-on boundary candidates in this project's
history died in adjudication as conventionally-sanctioned code. So loud-but-sanctioned
edges are *data*, not findings: non-qualifying edges land in the digest and can never
reach `candidates`. Declared boundary vocabulary (a dependency-cruiser ruleset, an
import-linter contract) is **owner-deferred**: this lens never reads, parses, sanitizes,
or passes repository configuration to any collector. Without that vocabulary the lens
surfaces **nothing** and collects data only — guessing walls from folder names is
exactly the plausible-but-wrong rule derivation this project rejected. The digest records
the deferral honestly (`declaredVocabulary` / `deferredCapabilities`); it does not claim
the repo was checked and found clean.

**Tool seam.** dependency-cruiser is invoked only through `guardian_collect.run_tool`
(→ `guardian_tools.invoke` in production). Always `--no-config`, absolute repo operands
in argv. Never pass repo config. TypeScript pin provisioning is deferred; the
module-count-collapse tripwire is the compensating control when depcruise resolves
TypeScript ≥6 and silently drops to ~2 modules.

**Why `required_facts = ()`.** A lens that requires `stack-tags` is degraded by the
sweep *before* `collect()` runs (guardian_sweep.collect → `_unsatisfied_facts`), and
`verify_config` on this very repo returns `stack-tags → absent`. Ecosystem detection is
therefore lens-owned: a recursive source/manifest census, because the sweep's
`_manifest_tags` looks only at the repo root and misses nested workspaces.
"""
import json
import os
import re
import stat
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect as gc                  # noqa: E402
import guardian_coupling_adapters as adapters  # noqa: E402
import store_core                              # noqa: E402

# --- identity + normalization (SSOT for the ids this lens mints) ---------------------
# Ledger grammar: lens:tool:rule:normalized-location. The lens family token is
# `coupling`; the tool token disambiguates ecosystem (depcruise vs import-linter id).
# The declared rule is part of identity so two rules crossing the same cluster pair
# never merge under one id, and a rule swap at constant edge count still diffs as
# resolved+new.
LENS_FAMILY = "coupling"
LENS_NAME = "coupling"
ID_GRAMMAR = "coupling:<tool>:<rule>:<normalized-location>"
ID_SEP = ":"
EDGE_ARROW = "->"
TOOL_TOKEN_JS = "depcruise"
TOOL_TOKEN_PY = "import-linter"
COLLECTOR_VERSION = "1.0.0"

# Cluster normalization, stated once so identity is auditable:
#   - separator: forward slash, always (Windows backslashes are folded)
#   - case: lower-cased, so a case-only rename on a case-insensitive filesystem does
#     not mint a second identity for the same wall
#   - scope: the cluster is the file's containing directory, repo-relative, capped at
#     CLUSTER_MAX_DEPTH segments *below its workspace root* and then re-prefixed with the
#     workspace. Repo-relative and workspace-qualified fall out of one string, so no
#     separator has to be invented and no two workspaces can collide. The cap keeps the
#     matrix folder-level (and KB-scale) on deeply nested trees.
#
# Rename-stability boundary (explicit, because unstable ids create false churn):
#   PRESERVED  — any line-level edit; renaming or adding files inside a cluster; moving
#                a file between subdirectories that share the same cluster prefix.
#   NOT PRESERVED — renaming/moving the cluster directory itself, renaming the workspace,
#                or moving a file across a cluster boundary. That is deliberate: in those
#                cases the wall itself moved, so the finding genuinely is a new one, and
#                a ledger disposition against the old wall should not silently transfer.
CLUSTER_SEP = "/"
CLUSTER_MAX_DEPTH = 3
ROOT_WORKSPACE = "."

# --- digest shape --------------------------------------------------------------------
DIGEST_SCHEMA_VERSION = 1
# DoD: the digest is KB-scale, never the full tool report (a real graph is thousands of
# edges / tens of MB). The matrix is folder-level and capped; the hash is computed over
# the *full* matrix so truncation can never hide drift.
DIGEST_MAX_BYTES = 64 * 1024
MAX_MATRIX_CELLS = 300

# --- collapse tripwire thresholds ----------------------------------------------------
# Primary signal is a PER-LANGUAGE, PER-WORKSPACE census: TS sources on disk vs TS
# modules parsed, JS vs JS, separately. A total-vs-total census is NOT safe — measured,
# a pinned run on a real repo parsed 3,324 vendored .js modules alongside its TS, so a
# total would stay healthy while every TypeScript file collapsed. That is precisely the
# false-clean this lens exists to prevent.
COLLAPSE_MIN_SOURCES = 5
COLLAPSE_RATIO = 0.1
# Secondary signal: a cliff vs the prior digest. A genuine repo shrink drops sources too,
# so the current source census is what distinguishes shrink from parser collapse.
CLIFF_RATIO = 0.5

# --- language census -----------------------------------------------------------------
JS_EXT_LANG = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "ts", ".tsx": "ts", ".mts": "ts", ".cts": "ts",
}
PY_EXT_LANG = {".py": "py", ".pyi": "py"}

JS_MANIFEST = "package.json"
PY_MANIFESTS = ("pyproject.toml", "setup.cfg", "setup.py")

# --- declared boundary vocabulary + check-the-check --------------------------------
# OWNER-ORDERED FALLBACK (issue #538 follow-up): after four confirmed RCE escapes on
# the config-reading surface, declared-vocabulary surfacing and check-the-check
# liveness verification are deferred to a follow-up issue with a dedicated security
# design. This lens no longer discovers, parses, sanitizes, or passes any repository
# configuration to collectors. Do not re-add config reading here.
VOCABULARY_DEFERRED_NOTE = (
    "declared-vocabulary surfacing deferred by owner decision — requires a dedicated "
    "security design (follow-up issue; advisor files the number)")
CHECK_THE_CHECK_DEFERRED_NOTE = (
    "check-the-check liveness verification deferred by owner decision — requires a "
    "dedicated security design (follow-up issue; advisor files the number)")
CHECK_DEFERRED = "deferred"

# --- the findings bar: conservative deterministic eligibility filter ------------------
# Every reason below is a DIGEST row, never a candidate. Ordered — the first match wins,
# which keeps the excluded-by-bar counters deterministic.
EXCLUSION_DECLARATION = "declaration-file"
EXCLUSION_TYPE_ONLY = "type-only-import"
EXCLUSION_TEST_PLUMBING = "test-plumbing"
EXCLUSION_GENERATED = "generated-or-vendored"
EXCLUSION_WRAPPER = "lib-wrapper-target"
EXCLUSION_INTRA_CLUSTER = "intra-cluster"
EXCLUSION_REASONS = (
    EXCLUSION_DECLARATION, EXCLUSION_TYPE_ONLY, EXCLUSION_TEST_PLUMBING,
    EXCLUSION_GENERATED, EXCLUSION_WRAPPER, EXCLUSION_INTRA_CLUSTER,
)

TEST_PATH_SEGMENTS = frozenset((
    "test", "tests", "__tests__", "spec", "specs", "fixture", "fixtures",
    "__fixtures__", "mock", "mocks", "__mocks__", "testdata", "e2e", "stories",
    "conftest", "testing",
))
TEST_FILE_RE = re.compile(
    r"(^test_|_test$|\.test$|\.spec$|^conftest$|_spec$|\.stories$)")
GENERATED_PATH_SEGMENTS = frozenset((
    "generated", "__generated__", "gen", "codegen", "vendor", "vendored",
    "third_party", "thirdparty", "node_modules", "dist", "build", ".next",
    "migrations", "proto",
))
# "lib wrapper" targets — the #475 adjudication class: conventionally-sanctioned shared
# plumbing that is loud in a graph and never a real architectural finding.
WRAPPER_SEGMENTS = frozenset((
    "lib", "libs", "util", "utils", "helper", "helpers", "common", "shared",
    "vendor", "internal", "types", "typings", "constants", "config",
))
DECLARATION_SUFFIX = ".d.ts"
TYPE_ONLY_DEP_TYPE = "type-only"

# A candidate the model cannot check is a candidate that should not have been raised, so
# every candidate carries representative concrete source->import paths (capped).
MAX_CANDIDATE_PATHS = 5
# Total bound on the model-bound candidate payload. Unbounded distinct walls would
# cross the structured→LLM→structured boundary in one pass with no fidelity guarantee;
# overflowing this cap degrades rather than pretending validation is complete.
MAX_CANDIDATES = 40

# --- model-/report-bound repo-text hygiene ------------------------------------------
# Repo-controlled file and directory *names* flow into degraded reasons, digest fields,
# and ultimately report.md (markdown). A committed name containing newlines and
# `## heading` can forge report structure or smuggle instruction-shaped text toward
# the validating model. This is the single choke point for that class — not process
# execution, but injection into text a model and a human read.
REPO_TEXT_MAX = 200
# Control chars + C1 controls (includes \\n, \\r, \\t). Collapsed, never passed through.
_REPO_TEXT_CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")
# Markdown-structural characters. report.md is markdown — a bare `#` at line start is
# a heading; `*`, backticks, brackets, and `|` similarly forge structure. Neutralised
# here. Angle brackets are handled separately below so EDGE_ARROW (`->`) survives.
_REPO_TEXT_MD = str.maketrans({
    "#": "_",
    "*": "_",
    "`": "'",
    "[": "(",
    "]": ")",
    "|": "_",
})
# Placeholder used while neutralizing HTML angle brackets so EDGE_ARROW is preserved.
_ARROW_PLACEHOLDER = "\x00ARROW\x00"
# Characters that must be percent-encoded in identity fragments so encoding is
# reversible, collision-free, and carries no active markdown/HTML markup. `%` itself
# is included so a literal `%23` cannot collide with an encoded `#`.
_IDENTITY_ESCAPE_RE = re.compile(
    r"[\x00-\x1f\x7f-\x9f#*`\[\]|<>%\\]")

# --- Python AST census I/O bounds ---------------------------------------------------
# `_python_edges` must not hang or OOM on committed content alone. A symlink to
# `/dev/zero` reads forever; a FIFO blocks; a multi-GB `.py` exhausts memory. Caps are
# hard: hitting either degrades honestly — silent truncation would feed the collapse
# tripwire a partial census and could manufacture a false collapse (or mask a real one).
PY_SOURCE_MAX_BYTES = 1 * 1024 * 1024
PY_CENSUS_MAX_BYTES = 16 * 1024 * 1024


# ======================================================================================
# small path helpers
# ======================================================================================

def _safe_repo_text(text, max_len=REPO_TEXT_MAX):
    """Clamp/collapse/neutralise a repo-derived string for model-visible surfaces.

    Defends against: a committed directory or file name containing newlines and
    markdown headings (e.g. ``\\n## forged``) forging structure in ``report.md``, or
    smuggling instruction-shaped text toward the validating model. Also neutralises
    HTML angle-bracket tags (``<script>``, ``<img ...>``) while preserving the lens's
    EDGE_ARROW (`->`) grammar. Call this at every site where a repo-controlled string
    enters a reason, a digest free-text field, or the report — do not scatter ad-hoc
    escaping at call sites. Identity/join keys use ``_encode_identity_*`` instead.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = _REPO_TEXT_CTRL.sub(" ", text)
    text = " ".join(text.split())
    text = text.translate(_REPO_TEXT_MD)
    # Neutralize HTML tags / angle brackets without destroying EDGE_ARROW (`->`).
    text = text.replace(EDGE_ARROW, _ARROW_PLACEHOLDER)
    text = text.replace("<", "(").replace(">", ")")
    text = text.replace(_ARROW_PLACEHOLDER, EDGE_ARROW)
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def _encode_identity_fragment(text, max_len=REPO_TEXT_MAX * 2):
    """Lossless, injection-safe encoding for one identity fragment (cluster, rule, …).

    Percent-escapes control / markdown / HTML-significant characters so distinct
    inputs stay distinct (unlike lossy ``_safe_repo_text``) while carrying no active
    markup. Reversible for the escaped alphabet; does not collapse whitespace.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    def _esc(match):
        return "%%%02X" % ord(match.group(0))

    encoded = _IDENTITY_ESCAPE_RE.sub(_esc, text)
    if len(encoded) > max_len:
        encoded = encoded[: max_len - 3] + "..."
    return encoded


def _encode_identity_key(text, max_len=REPO_TEXT_MAX * 2):
    """Encode an identity key that may contain EDGE_ARROW separators.

    Cluster segments are encoded; the ``->`` arrow grammar is preserved as the
    separator (encode segments, not the arrow). Also safe for candidate ids /
    wallKeys that embed a ``from->to`` location.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    parts = text.split(EDGE_ARROW)
    return EDGE_ARROW.join(
        _encode_identity_fragment(p, max_len=max_len) for p in parts)


def _posix(path):
    return path.replace("\\", CLUSTER_SEP)


def _rel_posix(repo, path):
    """Repo-relative, forward-slash path — ORIGINAL case (safe for filesystem open)."""
    p = _posix(path)
    if os.path.isabs(p) and repo:
        try:
            p = _posix(os.path.relpath(p, repo))
        except ValueError:
            pass
    while p.startswith("./"):
        p = p[2:]
    if p == ".":
        p = ""
    return p


def _norm_rel(repo, path):
    """Repo-relative, forward-slash, lower-cased path. Identity / cluster normalization."""
    return _rel_posix(repo, path).lower()


def _segments(rel_path):
    return [s for s in rel_path.split(CLUSTER_SEP) if s and s != "."]


def _stem(rel_path):
    base = _segments(rel_path)[-1] if _segments(rel_path) else rel_path
    if base.endswith(DECLARATION_SUFFIX):
        return base[:-len(DECLARATION_SUFFIX)]
    return os.path.splitext(base)[0]



def _repo_root(ctx):
    """Repo top-level = the sweep's cwd (realpath).

    The base seam runs collectors from a neutral cwd; the repo is the ``ctx["cwd"]`` the
    shell hands us (never re-derived via ``git rev-parse`` — that would route a git spawn
    through the seam only to relocate the root). Mirrors deps / hotspots / deadcode.
    """
    cwd = (ctx or {}).get("cwd") or "."
    return os.path.realpath(cwd)



def _is_excluded_dir(name):
    return name in adapters.EXCLUDED_DIR_NAMES


def _is_regular_file(path):
    """True only for non-symlink regular files (lstat — never follow links).

    Symlinks (incl. to `/dev/zero`), FIFOs, devices, and sockets must not be opened
    by the Python census — any of those hang or OOM the sweep from committed content.
    """
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)


# ======================================================================================
# census — lens-owned ecosystem detection (recursive; the sweep's is root-only)
# ======================================================================================

def census(repo, ecosystem):
    """Walk the repo → {"workspaces": [...], "sources": {ws: {lang: n}}, "files": {...}}.

    Workspaces are manifest-rooted (nested `package.json` / `pyproject.toml` etc.), with
    the repo root always present, and each file is attributed to its NEAREST enclosing
    workspace so one collapsed workspace cannot hide inside a healthy repo-wide total.

    For the Python ecosystem, only regular non-symlink files are censused — a committed
    symlink or FIFO must never reach `_python_edges` open().
    """
    ext_lang = JS_EXT_LANG if ecosystem == "js" else PY_EXT_LANG
    manifests = (JS_MANIFEST,) if ecosystem == "js" else PY_MANIFESTS
    workspaces = {ROOT_WORKSPACE}
    files = []
    skipped_non_regular = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if not _is_excluded_dir(d))
        # Preserve on-disk case for filesystem access; normalize only at identity sites.
        rel_dir = _rel_posix(repo, os.path.relpath(dirpath, repo))
        rel_dir = "" if rel_dir in (".", "") else rel_dir
        if rel_dir and any(m in filenames for m in manifests):
            workspaces.add(rel_dir)
        for fn in sorted(filenames):
            lang = ext_lang.get(_ext_of(fn))
            if not lang:
                continue
            rel_file = rel_dir + CLUSTER_SEP + fn if rel_dir else fn
            abs_path = os.path.join(dirpath, fn)
            # Python census: skip non-regular/symlinks (JS collector has its own walk).
            if ecosystem == "py" and not _is_regular_file(abs_path):
                skipped_non_regular.append(rel_file)
                continue
            files.append((rel_file, lang))
    ws_sorted = sorted(workspaces, key=lambda w: (-len(_norm_rel("", w)), _norm_rel("", w)))
    sources = {}
    attributed = []
    for rel_file, lang in files:
        ws = _owning_workspace(rel_file, ws_sorted)
        sources.setdefault(ws, {}).setdefault(lang, 0)
        sources[ws][lang] += 1
        attributed.append((ws, rel_file, lang))
    return {
        "workspaces": sorted(workspaces, key=lambda w: _norm_rel("", w)),
        "sources": sources,
        "files": attributed,
        "total": len(files),
        "skippedNonRegular": skipped_non_regular,
    }


def _ext_of(filename):
    low = filename.lower()
    if low.endswith(DECLARATION_SUFFIX):
        return ".ts"
    return os.path.splitext(low)[1]


def _owning_workspace(rel_path, workspaces_longest_first):
    """Attribute a file to its nearest enclosing workspace (case-insensitive match)."""
    rel_n = _norm_rel("", rel_path)
    for ws in workspaces_longest_first:
        if ws == ROOT_WORKSPACE:
            continue
        ws_n = _norm_rel("", ws)
        if rel_n == ws_n or rel_n.startswith(ws_n + CLUSTER_SEP):
            return ws
    return ROOT_WORKSPACE


def cluster_key(rel_path, workspace):
    """Workspace-qualified, repo-relative cluster key. See the normalization note above."""
    rel = _norm_rel("", rel_path)
    ws_n = _norm_rel("", workspace) if workspace != ROOT_WORKSPACE else ROOT_WORKSPACE
    inner = rel
    if ws_n != ROOT_WORKSPACE and rel.startswith(ws_n + CLUSTER_SEP):
        inner = rel[len(ws_n) + 1:]
    segs = _segments(inner)[:-1]  # drop the filename
    segs = segs[:CLUSTER_MAX_DEPTH]
    if ws_n != ROOT_WORKSPACE:
        segs = _segments(ws_n) + segs
    return CLUSTER_SEP.join(segs) if segs else ROOT_WORKSPACE


# ======================================================================================
# the findings bar
# ======================================================================================

def exclusion_reason(from_path, to_path, dep_types=(), from_cluster=None, to_cluster=None):
    """None → eligible. A string → a DIGEST row that can never become a candidate."""
    f, t = _norm_rel("", from_path), _norm_rel("", to_path)
    if f.endswith(DECLARATION_SUFFIX) or t.endswith(DECLARATION_SUFFIX):
        return EXCLUSION_DECLARATION
    if TYPE_ONLY_DEP_TYPE in (dep_types or ()):
        return EXCLUSION_TYPE_ONLY
    if _is_test_path(f) or _is_test_path(t):
        return EXCLUSION_TEST_PLUMBING
    if _has_segment(f, GENERATED_PATH_SEGMENTS) or _has_segment(t, GENERATED_PATH_SEGMENTS):
        return EXCLUSION_GENERATED
    if _is_wrapper_target(t):
        return EXCLUSION_WRAPPER
    if from_cluster is not None and from_cluster == to_cluster:
        return EXCLUSION_INTRA_CLUSTER
    return None


def _has_segment(rel_path, vocabulary):
    return any(s in vocabulary for s in _segments(rel_path))


def _is_test_path(rel_path):
    if _has_segment(rel_path, TEST_PATH_SEGMENTS):
        return True
    return bool(TEST_FILE_RE.search(_stem(rel_path)))


def _is_wrapper_target(rel_path):
    segs = _segments(rel_path)
    if not segs:
        return False
    if any(s in WRAPPER_SEGMENTS for s in segs[:-1]):
        return True
    return _stem(rel_path) in WRAPPER_SEGMENTS


# ======================================================================================
# declared boundary vocabulary (owner-deferred) + check-the-check (owner-deferred)
# ======================================================================================

def deferred_vocabulary():
    """Always-absent vocabulary record — honest that surfacing is deferred, not checked.

    Conservative findings bar: no declared vocabulary ⇒ surface nothing, collect data
    only. `deferred: True` distinguishes this from "we looked and the repo declared
    nothing," which would imply a clean check we did not perform.
    """
    return {
        "declared": False,
        "deferred": True,
        "config": None,
        "configRel": None,
        "note": VOCABULARY_DEFERRED_NOTE,
    }


def deferred_check_the_check():
    """Placeholder digest row for the deferred check-the-check DoD item."""
    return {
        "status": CHECK_DEFERRED,
        "config": None,
        "detail": CHECK_THE_CHECK_DEFERRED_NOTE,
        "unenforced": 0,
    }


def deferred_capabilities_list():
    """Digest-level entries for owner-deferred coupling capabilities.

    Recorded on every successful digest so a zero-candidate collect (vocabulary
    deferred) is never indistinguishable from a fully verified clean measurement.
    Human-report / funnel surfacing of this list is a deferred follow-up.
    """
    return [
        {"capability": "declared-vocabulary", "note": VOCABULARY_DEFERRED_NOTE},
        {"capability": "check-the-check", "note": CHECK_THE_CHECK_DEFERRED_NOTE},
    ]


# ======================================================================================
# collapse tripwires
# ======================================================================================

def detect_collapse(source_census, parsed_census):
    """Per-language, per-workspace collapse detection. Returns a list of findings.

    `parsed_census` mirrors `source_census["sources"]`: {workspace: {lang: count}}.

    Zero parsed modules against any on-disk sources is always a collapse — the
    COLLAPSE_MIN_SOURCES threshold applies only to nonzero ratio judgments (a
    partially-engaged parser on a small workspace). A one-file TypeScript workspace
    where dependency-cruiser parsed nothing must never write an empty clean baseline.
    """
    hits = []
    for ws in sorted(source_census.get("sources") or {}):
        by_lang = source_census["sources"][ws]
        for lang in sorted(by_lang):
            sources = by_lang[lang]
            if sources <= 0:
                continue
            parsed = ((parsed_census or {}).get(ws) or {}).get(lang, 0)
            if parsed == 0:
                hits.append({"workspace": ws, "language": lang,
                             "sources": sources, "parsed": parsed})
                continue
            if sources >= COLLAPSE_MIN_SOURCES and parsed <= sources * COLLAPSE_RATIO:
                hits.append({"workspace": ws, "language": lang,
                             "sources": sources, "parsed": parsed})
    return hits


def detect_cliff(prev_digest, parsed_total, sources_total):
    """Prior-digest cliff, with a genuine repo shrink excluded.

    A real shrink drops SOURCES too; a broken collector drops only parsed modules. So the
    cliff fires only when the module count fell off a cliff while the source census did
    not follow it down.
    """
    prev = (prev_digest or {}).get("counters") or {}
    prev_modules = prev.get("modulesParsed")
    prev_sources = prev.get("sourcesCensused")
    if not isinstance(prev_modules, int) or prev_modules <= 0:
        return None
    if parsed_total >= prev_modules * CLIFF_RATIO:
        return None
    if isinstance(prev_sources, int) and prev_sources > 0 and \
            sources_total < prev_sources * CLIFF_RATIO:
        return None  # genuine shrink — sources fell too
    return {"priorModules": prev_modules, "modules": parsed_total,
            "priorSources": prev_sources, "sources": sources_total}


# ======================================================================================
# digest assembly
# ======================================================================================

def build_matrix(edge_rows):
    """Folder-level coupling matrix {"<from>-><to>": weight} over ALL edges (data)."""
    matrix = {}
    for row in edge_rows:
        key = row["fromCluster"] + EDGE_ARROW + row["toCluster"]
        matrix[key] = matrix.get(key, 0) + 1
    return matrix


def matrix_hash(matrix):
    return store_core.short_hash(json.dumps(matrix, sort_keys=True))


def _truncate_matrix(matrix):
    if len(matrix) <= MAX_MATRIX_CELLS:
        return dict(matrix), False
    top = sorted(matrix.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_MATRIX_CELLS]
    return dict(top), True


def make_id(tool_token, from_cluster, to_cluster, rule=None):
    """Mint a candidate id. `rule` is part of identity when present (see ID_GRAMMAR)."""
    location = from_cluster + EDGE_ARROW + to_cluster
    if rule:
        return ID_SEP.join((LENS_FAMILY, tool_token, rule, location))
    return ID_SEP.join((LENS_FAMILY, tool_token, location))


def make_wall_key(tool_token, rule, from_cluster, to_cluster):
    """Deterministic key for the architectural wall an edge crosses.

    A SEAM ONLY. Recurrence tracking (repeated violation of the same wall) needs the
    dispositions ledger and belongs to #539 — building a recurrence store here would be a
    pipeline ahead of its consumer.
    """
    return ID_SEP.join(
        (tool_token, rule or "declared-wall", from_cluster + EDGE_ARROW + to_cluster))

# ======================================================================================
# the lens
# ======================================================================================

VALIDATION_GUIDANCE = """\
Check each candidate edge against the repo's DECLARED conventions \
(CLAUDE.md / CONVENTIONS / spec'd designs) using the representative \
source->import paths on the candidate. Surface it only if the edge crosses \
a boundary the project itself declared and the crossing is not sanctioned \
there. Conventionally-sanctioned coupling — shared lib wrappers, type-only \
or .d.ts imports, test plumbing — is data, not a finding; reject it. If the \
declared conventions do not cover the edge, reject: an unverifiable \
candidate is a candidate that should not have been raised. Tool-config \
vocabulary surfacing is owner-deferred; this lens currently collects data \
only and surfaces no coupling candidates from collector rules.
"""

CONSEQUENCE_TEMPLATE = """\
One plain sentence naming what the crossing costs: \
"<from-cluster> reaches into <to-cluster>, so <concrete consequence>." \
Price the effort from the measured edge count on the candidate, never from a \
severity tier.
"""


class CouplingLens(object):
    """Coupling matrix for JS/TS (dependency-cruiser) + Python (AST census) in one lens."""

    name = LENS_NAME
    collector_version = COLLECTOR_VERSION
    required_facts = ()
    validation_guidance = VALIDATION_GUIDANCE
    consequence_template = CONSEQUENCE_TEMPLATE
    cost = {
        "collectorSeconds": 7.0,
        "note": (
            "Ephemeral dependency-cruiser over first-party JS/TS plus a stdlib AST "
            "import census for Python; node_modules/vendored trees are never followed. "
            "Degrades (never returns empty candidates as a false clean) when the tool "
            "is absent, an ecosystem is unparseable, or the module census collapses. "
            "Declared-vocabulary surfacing is owner-deferred — candidates stay empty; "
            "the digest records the deferral."),
    }

    def collect(self, ctx):
        ctx = ctx or {}
        repo = _repo_root(ctx)
        prev = ctx.get("prevDigest") if isinstance(ctx.get("prevDigest"), dict) else None

        js_census = census(repo, "js")
        py_census = census(repo, "py")

        if js_census["total"] == 0 and py_census["total"] == 0:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected(
                    "no JS/TS or Python sources found in this repo — coupling needs "
                    "first-party sources to measure; nothing was scanned this sweep"))

        vocabulary = deferred_vocabulary()
        check = deferred_check_the_check()
        ecosystems = {}
        all_rows = []
        reasons = []
        any_collected = False
        versions = {}
        per_workspace = {}
        total_parsed = 0
        total_sources = 0

        if js_census["total"] > 0:
            js = self._measure_js(ctx, repo, js_census, prev)
            ecosystems["js"] = js["section"]
            if js["status"] in ("collected", "partial"):
                any_collected = True
                all_rows.extend(js.get("rows") or [])
                total_parsed += js.get("parsed_total") or 0
                total_sources += js_census["total"]
                versions["js"] = js.get("versions") or {}
                per_workspace.update(js.get("per_workspace") or {})
            if js.get("reason"):
                reasons.append(js["reason"])
        # else: ecosystem absent — not a degradation

        if py_census["total"] > 0:
            py = self._measure_py(ctx, repo, py_census, prev)
            ecosystems["py"] = py["section"]
            if py["status"] in ("collected", "partial"):
                any_collected = True
                all_rows.extend(py.get("rows") or [])
                total_parsed += py.get("parsed_total") or 0
                total_sources += py_census["total"]
                versions["py"] = py.get("versions") or {}
                per_workspace.update(py.get("per_workspace") or {})
            if py.get("reason"):
                reasons.append(py["reason"])

        if not any_collected:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected("; ".join(reasons) or "no coupling data collected"))

        candidates = self._candidates_from_rows(all_rows, vocabulary, {}, check)
        if isinstance(candidates, dict) and candidates.get("status") == "not-collected":
            return candidates

        digest = self._build_digest(
            ecosystems, all_rows, candidates, vocabulary, check, versions,
            per_workspace, total_parsed, total_sources,
            js_census if js_census["total"] else None,
            py_census if py_census["total"] else None)

        size = len(json.dumps(digest, sort_keys=True).encode("utf-8"))
        if size > DIGEST_MAX_BYTES:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected(
                    "%s: %s — serialized digest is %d bytes (cap %d). Refusing to "
                    "persist an over-cap digest that the advertised bound claimed to "
                    "prevent." % (
                        self.name, adapters.OUTCOMES["digest-over-cap"][1],
                        size, DIGEST_MAX_BYTES)))

        safe_candidates = self._sanitize_candidates(candidates)
        out = dict(candidates=safe_candidates, digest=digest)
        if reasons:
            out.update(gc.partial("; ".join(reasons)))
        else:
            out.update(gc.collected())
        return out

    def diff(self, prev_digest, cur_digest):
        """Diff over the eligible index ONLY.

        Load-bearing: guardian_sweep.collect unions diff()'s new+worsened into the
        surfacing set and FABRICATES a bare `{"id": cid}` placeholder for any id with
        no matching candidate. So an id here for a digest-only edge would leak past the
        findings bar as a placeholder finding. Every returned id is therefore taken from
        — and finally re-filtered against — the current eligible index.
        """
        if not isinstance(cur_digest, dict):
            return {"new": [], "worsened": [], "resolved": []}
        prev = _eligible_index(prev_digest)
        cur = _eligible_index(cur_digest)
        new = [cid for cid in sorted(cur) if cid not in prev]
        worsened = [
            cid for cid in sorted(cur)
            if cid in prev and _num(cur[cid]) is not None
            and _num(prev[cid]) is not None and _num(cur[cid]) > _num(prev[cid])
        ]
        resolved = [cid for cid in sorted(prev) if cid not in cur]
        return {
            "new": [cid for cid in new if cid in cur],
            "worsened": [cid for cid in worsened if cid in cur],
            "resolved": resolved,
        }

    def red_lines(self, candidates):
        """No coupling red-lines while check-the-check is owner-deferred."""
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}

    # ------------------------------------------------------------------ JS measure

    def _measure_js(self, ctx, repo, src_census, prev):
        """Run depcruise via run_tool; return a structured ecosystem result."""
        before_cache = adapters.cache_paths_present(repo)
        targets = _js_targets(repo, src_census)
        try:
            abs_targets = adapters.absolute_repo_operands(repo, targets)
        except ValueError as exc:
            reason = "%s js: bad cruise targets (%s)" % (self.name, exc)
            return self._eco_fail("js", reason)

        argv = adapters.depcruise_argv(abs_targets)
        res = gc.run_tool(argv, ctx, timeout=adapters.COLLECT_TIMEOUT, cwd=repo,
                          ok_exits=(0,))
        after_cache = adapters.cache_paths_present(repo)
        wrote = set(after_cache) - set(before_cache)
        if wrote:
            reason = "%s js: %s (%s)" % (
                self.name, adapters.OUTCOMES["repo-write"][1],
                ", ".join(sorted(wrote)))
            return self._eco_fail("js", reason)

        if not res.get("ok"):
            why = res.get("reason") or "dependency-cruiser failed"
            detail = (res.get("stderr") or "").strip().splitlines()
            tail = (" — " + detail[-1]) if detail else ""
            # Evidence-only parse of stdout (never promote a failed run to collected).
            parsed = adapters.parse_depcruise_json(
                res.get("stdout") or "", returncode=res.get("exit") or 1)
            evidence = ""
            if adapters.is_ok(parsed.get("outcome")):
                evidence = " (stdout was parseable but the run failed — not promoted)"
            reason = "%s js: %s%s%s" % (self.name, why, tail, evidence)
            return self._eco_fail("js", reason)

        parsed = adapters.parse_depcruise_json(
            res.get("stdout") or "", returncode=res.get("exit") or 0)
        outcome = parsed.get("outcome")
        klass, default_reason = adapters.classify(outcome)
        if klass == adapters.DEGRADED:
            reason = "%s js: %s%s" % (
                self.name, default_reason or outcome,
                (" — " + parsed["detail"]) if parsed.get("detail") else "")
            return self._eco_fail("js", reason)

        payload = parsed.get("payload") or {}
        versions = adapters.depcruise_versions(payload)
        parsed_paths = adapters.depcruise_parsed_modules(payload)
        parsed_census = _parsed_census(repo, parsed_paths, src_census, JS_EXT_LANG)
        collapse = detect_collapse(src_census, parsed_census)
        if collapse:
            reason = _collapse_reason(
                self.name + " js", src_census, collapse, versions)
            return self._eco_fail("js", reason)

        cliff = detect_cliff(_eco_prev_digest(prev, "js"), len(parsed_paths),
                             src_census["total"])
        if cliff:
            reason = (
                "%s js: %s — %d modules parsed vs %s in the prior sweep while the "
                "source census held at %d (a genuine shrink drops sources too)"
                % (self.name, adapters.OUTCOMES["module-count-cliff"][1],
                   cliff["modules"], cliff["priorModules"], cliff["sources"]))
            return self._eco_fail("js", reason)

        rows = _classify_edges(
            repo, adapters.depcruise_edges(payload), src_census["workspaces"])
        # Tag rows with tool token for candidate minting later.
        for row in rows:
            row["toolToken"] = TOOL_TOKEN_JS
            row["tool"] = adapters.DEPCRUISE_TOOL

        per_ws = {
            _safe_repo_text(ws): {
                "sources": dict(src_census["sources"].get(ws) or {}),
                "modules": dict((parsed_census or {}).get(ws) or {}),
            }
            for ws in src_census["workspaces"]
        }
        return {
            "status": "collected",
            "reason": None,
            "rows": rows,
            "versions": versions,
            "parsed_total": len(parsed_paths),
            "per_workspace": per_ws,
            "section": {
                "status": "collected",
                "reason": None,
                "tool": adapters.DEPCRUISE_TOOL,
                "outcome": outcome,
                "sourcesCensused": src_census["total"],
                "modulesParsed": len(parsed_paths),
                "argv": argv,
            },
        }

    # ----------------------------------------------------------------- Python measure

    def _measure_py(self, ctx, repo, src_census, prev):
        del ctx  # AST census is tool-free; prevDigest used for cliff only
        skipped = src_census.get("skippedNonRegular") or []
        if src_census["total"] == 0 and skipped:
            samples = ", ".join(_safe_repo_text(p) for p in skipped[:5])
            more = len(skipped) - 5
            if more > 0:
                samples += ", …+%d more" % more
            reason = (
                "%s py: Python census found %d non-regular or symlink source(s) "
                "and no readable regular files — %s. Refusing to treat a "
                "symlink/FIFO/device tree as an empty clean repo."
                % (self.name, len(skipped), samples))
            return self._eco_fail("py", reason)
        if skipped:
            samples = ", ".join(_safe_repo_text(p) for p in skipped[:5])
            more = len(skipped) - 5
            if more > 0:
                samples += ", …+%d more" % more
            reason = (
                "%s py: Python census skipped %d non-regular or symlink source(s) "
                "— %s. A partial census that silently drops hang/OOM vectors is "
                "not a clean collect." % (self.name, len(skipped), samples))
            return self._eco_fail("py", reason)

        packaged, why = _python_is_packaged(repo, src_census)
        if not packaged:
            reason = (
                "%s py: %s — %s. Reporting honestly rather than faking a clean result."
                % (self.name, adapters.OUTCOMES["flat-layout"][1], why))
            return self._eco_fail("py", reason)

        edges = _python_edges(repo, src_census)
        if edges.get("capped"):
            reason = "%s py: %s" % (self.name, edges.get("capDetail") or (
                "Python source census hit a byte cap — refusing to silently "
                "truncate (a truncated census feeds the collapse tripwire)"))
            return self._eco_fail("py", reason)
        if edges.get("nonRegular"):
            samples = ", ".join(
                _safe_repo_text(p) for p in edges["nonRegular"][:5])
            more = len(edges["nonRegular"]) - 5
            if more > 0:
                samples += ", …+%d more" % more
            reason = (
                "%s py: Python census refused %d non-regular or symlink source(s) "
                "— %s. Open() on a symlink/FIFO/device is a hang/OOM vector."
                % (self.name, len(edges["nonRegular"]), samples))
            return self._eco_fail("py", reason)
        if edges.get("parseFailures"):
            samples = ", ".join(
                "%s (%s)" % (_safe_repo_text(p["path"]),
                             _safe_repo_text(p["error"], max_len=120))
                for p in edges["parseFailures"][:5])
            more = len(edges["parseFailures"]) - 5
            if more > 0:
                samples += ", …+%d more" % more
            reason = (
                "%s py: %d first-party Python source(s) could not be opened or parsed "
                "— %s. A partial census is a broken collector, never a clean repo."
                % (self.name, len(edges["parseFailures"]), samples))
            return self._eco_fail("py", reason)

        rows = _classify_edges(repo, edges["edges"], src_census["workspaces"])
        for row in rows:
            row["toolToken"] = TOOL_TOKEN_PY
            row["tool"] = adapters.IMPORT_LINTER_TOOL

        parsed_census = edges["parsedCensus"]
        collapse = detect_collapse(src_census, parsed_census)
        if collapse:
            reason = _collapse_reason(self.name + " py", src_census, collapse, None)
            return self._eco_fail("py", reason)

        parsed_total = sum(sum(v.values()) for v in parsed_census.values())
        cliff = detect_cliff(_eco_prev_digest(prev, "py"), parsed_total,
                             src_census["total"])
        if cliff:
            reason = (
                "%s py: %s — %d modules parsed vs %s in the prior sweep while the "
                "source census held at %d (a genuine shrink drops sources too)"
                % (self.name, adapters.OUTCOMES["module-count-cliff"][1],
                   cliff["modules"], cliff["priorModules"], cliff["sources"]))
            return self._eco_fail("py", reason)

        versions = {
            "tool": adapters.IMPORT_LINTER_TOOL,
            "toolVersionPinned": adapters.IMPORT_LINTER_PIN,
            "toolVersionResolved": None,
            "typescriptVersionPinned": None,
            "typescriptVersionResolved": None,
            "parseMode": "ast-census-only",
        }
        per_ws = {
            _safe_repo_text(ws): {
                "sources": dict(src_census["sources"].get(ws) or {}),
                "modules": dict((parsed_census or {}).get(ws) or {}),
            }
            for ws in src_census["workspaces"]
        }
        return {
            "status": "collected",
            "reason": None,
            "rows": rows,
            "versions": versions,
            "parsed_total": parsed_total,
            "per_workspace": per_ws,
            "section": {
                "status": "collected",
                "reason": None,
                "tool": adapters.IMPORT_LINTER_TOOL,
                "outcome": "no-declared-vocabulary",
                "sourcesCensused": src_census["total"],
                "modulesParsed": parsed_total,
                "parseMode": "ast-census-only",
            },
        }

    @staticmethod
    def _eco_fail(ecosystem, reason):
        return {
            "status": "not-collected",
            "reason": _safe_repo_text(reason, max_len=max(REPO_TEXT_MAX * 4, 800)),
            "rows": [],
            "versions": {},
            "parsed_total": 0,
            "per_workspace": {},
            "section": {
                "status": "not-collected",
                "reason": _safe_repo_text(reason, max_len=max(REPO_TEXT_MAX * 4, 800)),
                "tool": (adapters.DEPCRUISE_TOOL if ecosystem == "js"
                         else adapters.IMPORT_LINTER_TOOL),
            },
        }

    # --------------------------------------------------------------- candidates/digest

    def _candidates_from_rows(self, rows, vocabulary, violations, check):
        """Eligible rows → candidates. No declared vocabulary ⇒ data only (binding).

        With vocabulary owner-deferred, `vocabulary["declared"]` is always False and
        this returns []. Kept as the single findings-bar gate so restoring vocabulary
        later reuses the same path. `check` is accepted for call-site stability but is
        never turned into a candidate while check-the-check is deferred.
        """
        del check
        candidates = []
        if not vocabulary.get("declared"):
            return candidates
        by_wall = {}
        for row in rows:
            if row["exclusion"] is not None:
                continue
            tool_token = row.get("toolToken") or TOOL_TOKEN_JS
            tool = row.get("tool") or adapters.DEPCRUISE_TOOL
            rules = violations.get((row["from"], row["to"])) or []
            if isinstance(rules, str):
                rules = [rules]
            if not rules:
                continue
            for rule in rules:
                if not rule:
                    continue
                cid = make_id(
                    tool_token, row["fromCluster"], row["toCluster"], rule=rule)
                entry = by_wall.setdefault(cid, {
                    "id": cid,
                    "lensFamily": LENS_FAMILY,
                    "tool": tool,
                    "rule": rule,
                    "fromCluster": row["fromCluster"],
                    "toCluster": row["toCluster"],
                    "wallKey": make_wall_key(
                        tool_token, rule, row["fromCluster"], row["toCluster"]),
                    "metric": 0,
                    "paths": [],
                })
                entry["metric"] += 1
                if len(entry["paths"]) < MAX_CANDIDATE_PATHS:
                    entry["paths"].append({"from": row["from"], "to": row["to"]})
        candidates.extend(sorted(by_wall.values(), key=lambda c: c["id"]))
        if len(candidates) > MAX_CANDIDATES:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected(
                    "%s: candidate payload exceeds the model-bound total cap "
                    "(%d > %d) — refusing to send an unbounded structured→LLM→structured "
                    "pass that cannot guarantee one disposition per id"
                    % (self.name, len(candidates), MAX_CANDIDATES)))
        return candidates

    def _build_digest(self, ecosystems, rows, candidates, vocabulary, check, versions,
                      per_workspace, parsed_total, sources_total, js_census, py_census):
        full_matrix = build_matrix(rows)
        # Identity keys (matrix / matrixHash) use lossless encoding — lossy
        # _safe_repo_text would collapse a#->b and a*->b onto one cell and mask drift.
        safe_full = {
            _encode_identity_key(k, max_len=REPO_TEXT_MAX * 2): v
            for k, v in full_matrix.items()
        }
        matrix, truncated = _truncate_matrix(safe_full)
        excluded = {}
        eligible_rows = 0
        for row in rows:
            if row["exclusion"] is None:
                eligible_rows += 1
            else:
                excluded[row["exclusion"]] = excluded.get(row["exclusion"], 0) + 1
        deferred = deferred_capabilities_list()
        workspaces = []
        if js_census:
            workspaces.extend(js_census["workspaces"])
        if py_census:
            for w in py_census["workspaces"]:
                if w not in workspaces:
                    workspaces.append(w)
        safe_candidates = self._sanitize_candidates(candidates)
        return {
            "schemaVersion": DIGEST_SCHEMA_VERSION,
            "lens": self.name,
            "tool": adapters.DEPCRUISE_TOOL,
            "outcome": "ok",
            "note": "",
            "idGrammar": ID_GRAMMAR,
            "clusterMaxDepth": CLUSTER_MAX_DEPTH,
            "workspaces": [_safe_repo_text(w) for w in workspaces],
            "ecosystems": ecosystems,
            "matrix": matrix,
            "matrixTruncated": truncated,
            "matrixHash": matrix_hash(safe_full),
            "eligible": {c["id"]: c["metric"] for c in safe_candidates},
            "counters": {
                "edges": len(rows),
                "eligible": eligible_rows,
                "surfaced": len(safe_candidates),
                "excludedByBar": len(rows) - eligible_rows,
                "modulesParsed": parsed_total,
                "sourcesCensused": sources_total,
            },
            "excludedByReason": excluded,
            "perWorkspace": per_workspace,
            "declaredVocabulary": {
                "declared": bool(vocabulary.get("declared")),
                "deferred": bool(vocabulary.get("deferred")),
                "config": (_safe_repo_text(vocabulary["configRel"])
                           if vocabulary.get("configRel") else None),
                "note": vocabulary.get("note") or VOCABULARY_DEFERRED_NOTE,
            },
            "checkTheCheck": check,
            "deferredCapabilities": list(deferred),
            "versions": versions,
        }

    @staticmethod
    def _sanitize_candidates(candidates):
        safe_candidates = []
        for c in candidates or []:
            sc = dict(c)
            # Ledger-join / eligible keys: lossless identity encoding (not lossy clamp).
            if "id" in sc:
                sc["id"] = _encode_identity_key(
                    sc["id"], max_len=REPO_TEXT_MAX * 2)
            for key in ("fromCluster", "toCluster", "wallKey", "rule"):
                if key in sc and isinstance(sc[key], str):
                    max_len = (REPO_TEXT_MAX * 2 if key != "rule"
                               else REPO_TEXT_MAX)
                    if key in ("fromCluster", "toCluster", "rule"):
                        sc[key] = _encode_identity_fragment(
                            sc[key], max_len=max_len)
                    else:
                        sc[key] = _encode_identity_key(
                            sc[key], max_len=max_len)
            # Free-text path evidence stays on the lossy display clamp.
            if "paths" in sc:
                sc["paths"] = [
                    {"from": _safe_repo_text(p.get("from") or ""),
                     "to": _safe_repo_text(p.get("to") or "")}
                    for p in (sc.get("paths") or [])
                    if isinstance(p, dict)
                ]
            safe_candidates.append(sc)
        return safe_candidates

    # ---------------------------------------------------------------------- conformance

    def conformance_fixture(self):
        """Minimal JS/TS workspace so collect() reaches the depcruise argv under the stub.

        ``package.json`` + a ``.ts`` file make the JS census non-empty; no Python sources
        so the AST path does not co-fire. The harness writes these into a temp dir used as
        both ctx["cwd"] and ctx["root"].
        """
        return {
            "package.json": json.dumps({
                "name": "guardian-coupling-conformance",
            }) + "\n",
            "src/app.ts": "export const ok = true;\n",
        }

    def conformance_cases(self):
        """Lens-supplied ``reported-nonzero-parsed-zero`` payload (see lens-contract.md).

        Under the JS-only fixture the single injected stdout drives ``depcruise``. This
        lens declares ``ok_exits=(0,)`` — a findings exit is never promoted:

        - clean probe: schema-valid report that parses the fixture module at exit 0 →
          whole-lens ``collected`` (vocabulary deferred ⇒ candidates stay ``[]``, but
          the matrix was measured).
        - findings probe: a report that lists modules but yields no first-party edges at
          a non-ok exit → ``run_tool`` returns ok=False → JS degrades → whole-lens
          ``not-collected``. Must never read as ``collected``.
        """
        clean = json.dumps({
            "modules": [{
                "source": "src/app.ts",
                "dependencies": [],
            }],
            "summary": {
                "violations": [],
                "environment": {
                    "version": "18.0.0",
                    "transpilersFound": [{
                        "name": "typescript",
                        "available": True,
                        "currentVersion": "5.9.3",
                    }],
                },
            },
        })
        # Modules present (tool reported something) but none are first-party parseable
        # edges — external-only sources so the bar / edge extract yields nothing useful.
        # Paired with a non-ok exit so the run is not promoted.
        reported = json.dumps({
            "modules": [{
                "source": "lodash",
                "coreModule": False,
                "dependencies": [{
                    "module": "lodash/fp",
                    "resolved": "lodash/fp",
                    "dependencyTypes": ["npm"],
                    "rules": [],
                }],
            }],
            "summary": {
                "violations": [{"from": "lodash", "to": "lodash/fp",
                                "rule": {"name": "no-orphans"}}],
                "environment": {
                    "version": "18.0.0",
                    "transpilersFound": [],
                },
            },
        })
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": reported,
                "clean_stdout": clean,
                "exit": 1,
                "clean_exit": 0,
                "stdout_by_tool": {"depcruise": reported},
                "clean_stdout_by_tool": {"depcruise": clean},
            },
        }

    def conformance_prev_digest(self):
        """Prior digest with one eligible sentinel that diff() resolves against cleared."""
        sentinel_id = "coupling:depcruise:sentinel-rule:src/a->src/b"

        def _digest(eligible):
            return {
                "schemaVersion": DIGEST_SCHEMA_VERSION,
                "lens": self.name,
                "ecosystems": {"js": {"status": "collected"}},
                "matrix": {},
                "matrixHash": matrix_hash({}),
                "eligible": eligible,
                "counters": {
                    "edges": 0, "eligible": len(eligible), "surfaced": len(eligible),
                    "excludedByBar": 0, "modulesParsed": 1, "sourcesCensused": 1,
                },
                "declaredVocabulary": {
                    "declared": False, "deferred": True, "config": None,
                    "note": VOCABULARY_DEFERRED_NOTE,
                },
                "deferredCapabilities": deferred_capabilities_list(),
            }

        return {
            "prev": _digest({sentinel_id: 1}),
            "cleared": _digest({}),
            "sentinelIds": [sentinel_id],
        }


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _eligible_index(digest):
    idx = (digest or {}).get("eligible")
    return dict(idx) if isinstance(idx, dict) else {}


def _eco_prev_digest(prev, ecosystem):
    """Shape a prior digest for detect_cliff from one ecosystem's section counters.

    Uses ``ctx["prevDigest"]`` (authoritative prior injected by the sweep) — never a
    store re-read. Falls back to top-level counters when the prior predates the
    ecosystems map (should not happen for this collector version).
    """
    if not isinstance(prev, dict):
        return None
    section = (prev.get("ecosystems") or {}).get(ecosystem)
    if isinstance(section, dict) and (
            section.get("modulesParsed") is not None
            or section.get("sourcesCensused") is not None):
        return {"counters": {
            "modulesParsed": section.get("modulesParsed"),
            "sourcesCensused": section.get("sourcesCensused"),
        }}
    return prev

def _census_has_lang(src_census, lang):
    """True when any workspace in the source census has a nonzero count for `lang`."""
    for by_lang in (src_census.get("sources") or {}).values():
        if (by_lang or {}).get(lang, 0) > 0:
            return True
    return False

def collapse_outcome(src_census, collapse):
    """Which closed-table row a collapse belongs to.

    A collapse confined to some workspaces is `workspace-collapse` — the case a repo-wide
    total would have hidden; a collapse everywhere is `module-count-collapse`.
    """
    hit_workspaces = {h["workspace"] for h in collapse}
    all_workspaces = {ws for ws, langs in (src_census.get("sources") or {}).items()
                      if sum(langs.values())}
    if hit_workspaces and hit_workspaces < all_workspaces:
        return "workspace-collapse"
    return "module-count-collapse"


def _collapse_reason(lens_name, src_census, collapse, versions):
    parts = ", ".join(
        "%s/%s %d parsed of %d sources" % (
            _safe_repo_text(h["workspace"]), h["language"], h["parsed"],
            h["sources"])
        for h in collapse)
    ver = ""
    if versions:
        ver = " (tool=%s, typescript=%s, parseMode=%s, pinHeld=%s)" % (
            versions.get("toolVersionResolved"),
            versions.get("typescriptVersionResolved"),
            versions.get("parseMode"), versions.get("pinHeld"))
    outcome = collapse_outcome(src_census, collapse)
    return ("%s: %s — module-count collapse: %s%s. A collapsed collector is a broken "
            "collector, never a clean repo."
            % (lens_name, adapters.OUTCOMES[outcome][1], parts, ver))


def _js_targets(repo, src_census):
    """First-party directories to cruise. Vendored trees are never targets."""
    tops = set()
    for _ws, rel_file, _lang in src_census["files"]:
        segs = _segments(rel_file)
        tops.add(segs[0] if len(segs) > 1 else ".")
    if "." in tops:
        return ["."]  # sources sit at the repo root; --exclude keeps vendored trees out
    real = sorted(t for t in tops if os.path.isdir(os.path.join(repo, t)))
    return real or ["."]


def _parsed_census(repo, parsed_paths, src_census, ext_lang):
    """Attribute parsed module paths to (workspace, language), mirroring the source census."""
    ws_sorted = sorted(src_census["workspaces"],
                       key=lambda w: (-len(_norm_rel("", w)), _norm_rel("", w)))
    out = {}
    for path in parsed_paths:
        rel = _norm_rel(repo, path)
        lang = ext_lang.get(_ext_of(rel))
        if not lang:
            continue
        ws = _owning_workspace(rel, ws_sorted)
        out.setdefault(ws, {}).setdefault(lang, 0)
        out[ws][lang] += 1
    return out


def _classify_edges(repo, edges, workspaces):
    """Normalize raw tool edges into rows carrying clusters + the bar's verdict."""
    ws_sorted = sorted(workspaces, key=lambda w: (-len(_norm_rel("", w)), _norm_rel("", w)))
    rows = []
    for edge in edges:
        f = _norm_rel(repo, edge["from"])
        t = _norm_rel(repo, edge["to"])
        fc = cluster_key(f, _owning_workspace(f, ws_sorted))
        tc = cluster_key(t, _owning_workspace(t, ws_sorted))
        rows.append({
            "from": f,
            "to": t,
            "fromCluster": fc,
            "toCluster": tc,
            "types": list(edge.get("types") or []),
            "exclusion": exclusion_reason(f, t, edge.get("types") or [], fc, tc),
        })
    return rows

# --- Python: packaging check + stdlib import census ----------------------------------

def _python_is_packaged(repo, src_census):
    """Is there an importable package? Flat layouts have no root for a graph."""
    for _ws, rel_file, _lang in src_census["files"]:
        if _segments(rel_file)[-1] == "__init__.py":
            return True, ""
    return False, ("no __init__.py under any Python source root (flat layout — "
                   "not analyzable as an importable package graph)")


def _python_edges(repo, src_census):
    """Stdlib `ast` import census → first-party module→module edges + a parsed census.

    import-linter is a contract *checker*, not a graph dumper — it emits no machine-
    readable graph — so the folder-level matrix the digest owes comes from this census.
    Files that fail to parse are recorded in `parseFailures`; the caller must degrade
    rather than treat a partial census as a clean collect.

    Non-regular files and symlinks are refused (never opened). Per-file and aggregate
    byte caps are hard: hitting either sets `capped` so the caller degrades — silent
    truncation would feed the collapse tripwire a partial census.
    """
    import ast
    ws_sorted = sorted(src_census["workspaces"], key=lambda w: (-len(_norm_rel("", w)),
                                                                _norm_rel("", w)))
    # dotted name → list of (workspace, rel_file) so same-workspace resolution wins
    # over a cross-workspace collision on a shared package name.
    by_module = {}
    for ws, rel_file, _lang in src_census["files"]:
        for mod in _path_to_modules(rel_file, workspace=ws):
            by_module.setdefault(mod, []).append((ws, rel_file))
    parsed_census = {}
    edges = []
    seen_edges = set()
    parse_failures = []
    non_regular = []
    bytes_read = 0
    for ws, rel_file, lang in src_census["files"]:
        abs_path = os.path.join(repo, rel_file)
        if not _is_regular_file(abs_path):
            non_regular.append(rel_file)
            continue
        try:
            size = os.lstat(abs_path).st_size
        except OSError as exc:
            parse_failures.append({
                "path": rel_file,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            continue
        if size > PY_SOURCE_MAX_BYTES:
            return {
                "edges": edges,
                "parsedCensus": parsed_census,
                "parseFailures": parse_failures,
                "nonRegular": non_regular,
                "capped": True,
                "capDetail": (
                    "Python source %s is %d bytes (per-file cap %d) — refusing to "
                    "silently truncate; a truncated census feeds the collapse tripwire"
                    % (_safe_repo_text(rel_file), size, PY_SOURCE_MAX_BYTES)),
            }
        if bytes_read + size > PY_CENSUS_MAX_BYTES:
            return {
                "edges": edges,
                "parsedCensus": parsed_census,
                "parseFailures": parse_failures,
                "nonRegular": non_regular,
                "capped": True,
                "capDetail": (
                    "Python census aggregate read would exceed %d bytes at %s "
                    "(already read %d) — refusing to silently truncate; a truncated "
                    "census feeds the collapse tripwire"
                    % (PY_CENSUS_MAX_BYTES, _safe_repo_text(rel_file), bytes_read)),
            }
        try:
            # Bound the read even if st_size lied (sparse/race): never pull more than
            # the per-file cap + 1 into memory.
            with open(abs_path, "rb") as fh:
                raw = fh.read(PY_SOURCE_MAX_BYTES + 1)
            if len(raw) > PY_SOURCE_MAX_BYTES:
                return {
                    "edges": edges,
                    "parsedCensus": parsed_census,
                    "parseFailures": parse_failures,
                    "nonRegular": non_regular,
                    "capped": True,
                    "capDetail": (
                        "Python source %s exceeded per-file cap %d during read — "
                        "refusing to silently truncate"
                        % (_safe_repo_text(rel_file), PY_SOURCE_MAX_BYTES)),
                }
            text = raw.decode("utf-8", errors="replace")
            bytes_read += len(raw)
            tree = ast.parse(text, filename=rel_file)
        except (OSError, SyntaxError, ValueError) as exc:
            parse_failures.append({
                "path": rel_file,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            continue
        owning = _owning_workspace(rel_file, ws_sorted)
        parsed_census.setdefault(owning, {}).setdefault(lang, 0)
        parsed_census[owning][lang] += 1
        for target in _imported_modules(ast, tree, rel_file, workspace=owning):
            hit = _resolve_module(target, by_module, from_workspace=owning)
            if hit and hit != rel_file:
                key = (rel_file, hit)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append({"from": rel_file, "to": hit, "types": [], "rules": []})
    return {
        "edges": edges,
        "parsedCensus": parsed_census,
        "parseFailures": parse_failures,
        "nonRegular": non_regular,
        "capped": False,
        "capDetail": "",
    }


def _imported_modules(ast, tree, rel_file, workspace=ROOT_WORKSPACE):
    out = []
    pkg = _import_package_segments(rel_file, workspace=workspace)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod:
                out.append(mod)
                # Also try symbol-qualified names; _resolve_module longest-prefix
                # matches them onto the real module, and _python_edges dedupes.
                out.extend("%s.%s" % (mod, a.name) for a in node.names)
    return out


def _src_layout_strip(segs):
    """Strip a `src/` layout root from path segments when present.

    `src/mypkg/api.py` and `packages/service/src/mypkg/api.py` both import as
    `mypkg.api`, not `src.mypkg.api` / `packages.service.src.mypkg.api`.
    """
    if "src" not in segs:
        return segs
    idx = segs.index("src")
    after = segs[idx + 1:]
    return after if after else segs


def _module_path_aliases(rel_file, workspace=ROOT_WORKSPACE):
    """Repo-relative paths whose dotted form may be how the file is imported.

    Includes the full repo-relative path, a src-layout-stripped form, and — when the
    file sits under a nested workspace — the workspace-relative form so
    `packages/service/mypkg/api.py` resolves as `mypkg.api`.
    """
    out = []
    seen = set()

    def _add(path):
        if path and path not in seen:
            seen.add(path)
            out.append(path)

    _add(rel_file)
    segs = _segments(rel_file)
    stripped = _src_layout_strip(segs)
    if stripped != segs:
        _add(CLUSTER_SEP.join(stripped))
    if workspace and workspace != ROOT_WORKSPACE:
        ws_n = _norm_rel("", workspace)
        rel_n = _norm_rel("", rel_file)
        n_ws = len(_segments(ws_n))
        if rel_n == ws_n or rel_n.startswith(ws_n + CLUSTER_SEP):
            inner_segs = _segments(rel_file)[n_ws:]
            if inner_segs:
                inner = CLUSTER_SEP.join(inner_segs)
                _add(inner)
                inner_stripped = _src_layout_strip(inner_segs)
                if inner_stripped != inner_segs:
                    _add(CLUSTER_SEP.join(inner_stripped))
    return out


def _path_to_modules(rel_file, workspace=ROOT_WORKSPACE):
    """All dotted module names a source file may be imported as.

    Returns path-derived names plus src-layout and workspace-relative aliases so
    `mypkg.api` resolves against both `src/mypkg/api.py` and
    `packages/service/mypkg/api.py`.
    """
    names = []
    for candidate in _module_path_aliases(rel_file, workspace=workspace):
        mod = _path_to_module(candidate)
        if mod and mod not in names:
            names.append(mod)
    return names


def _path_to_module(rel_file):
    segs = _segments(rel_file)
    if not segs or not segs[-1].endswith(".py"):
        return None
    stem = segs[-1][:-3]
    if stem == "__init__":
        segs = segs[:-1]
    else:
        segs = segs[:-1] + [stem]
    return ".".join(segs) if segs else None


def _import_package_segments(rel_file, workspace=ROOT_WORKSPACE):
    """Package segments for relative-import resolution, honouring workspace + src-layout."""
    segs = _segments(rel_file)[:-1]
    if workspace and workspace != ROOT_WORKSPACE:
        ws_segs = _segments(_norm_rel("", workspace))
        n_ws = len(ws_segs)
        if len(segs) >= n_ws and _segments(_norm_rel("", CLUSTER_SEP.join(segs[:n_ws]))) == ws_segs:
            segs = segs[n_ws:]
    return _src_layout_strip(segs)


def _resolve_module(dotted, by_module, from_workspace=None):
    """Longest-prefix match of a dotted import onto a first-party module path.

    Prefer a hit in `from_workspace` when the same dotted name is registered under
    multiple workspaces; otherwise take the first registration (deterministic census
    order). Cross-workspace shared packages therefore resolve locally first.
    """
    parts = dotted.split(".")
    while parts:
        hits = by_module.get(".".join(parts))
        if hits:
            if from_workspace is not None:
                for ws, rel in hits:
                    if ws == from_workspace:
                        return rel
            return hits[0][1]
        parts = parts[:-1]
    return None


def _module_to_path(repo, dotted, src_census):
    by_module = {}
    for ws, rel_file, _lang in src_census["files"]:
        for mod in _path_to_modules(rel_file, workspace=ws):
            by_module.setdefault(mod, []).append((ws, rel_file))
    return _resolve_module(dotted or "", by_module) or _norm_rel("", (dotted or "")
                                                                .replace(".", CLUSTER_SEP))


LENS = CouplingLens()
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
