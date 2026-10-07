#!/usr/bin/env python3
"""superheroes (architect): definition-doc location + frontmatter helper (CONVENTIONS §3, §6.1).

Resolution is mode-aware (CONVENTIONS §2.3/§3.3): global mode → the I1 project
store (`projects/<config-key>/docs/<work-item>/…`); in-repo mode → the location
configured by the project's doc-policy. The doc-policy (where definition-docs live
and whether they are committed or gitignored) is owned by `architect_config.py`
and set up by `architect-init`.

Two jobs:
  - mint + locate: freeze a `<work-item>` slug (§6.1, via the vendored
    identifiers) and resolve the on-disk path for each doc-type.
  - frontmatter: build + render the §3.1 shared additive header so a skill never
    hand-writes (and never invalidates) the machine-read linkage. The body prose
    is authored separately (the `writing-specs` skill); the renderer here owns
    only the `---`-fenced frontmatter block.

Run as a script from this directory; the sibling `identifiers` module imports
directly because the script dir is on sys.path (same convention as test-pilot's
engine.py). We also insert the lib dir explicitly so importing this module by
path (the conformance test) still resolves `identifiers`.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import identifiers  # noqa: E402  (sibling import; see module docstring)

SCHEMA_VERSION = 1
DOC_TYPES = ("spec", "plan", "tasks")
# The in-repo default docs location, kept in lock-step with architect_config.DEFAULT_LOCATION
# (a connascence-of-value guard test asserts they match). Defined here too, rather than
# imported, so these pure path helpers stay import-light (no module-load dependency on the
# policy/mode stack — the deferred-import design).
DEFAULT_LOCATION = "docs/superheroes"
CANON_FILE = "canon.md"


def _plugin_version():
    """Read this plugin's version from its manifest, so `producedBy` has one source."""
    manifest = os.path.join(_LIB_DIR, "..", ".claude-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as fh:
        return json.load(fh)["version"]


def produced_by():
    return f"the-architect@{_plugin_version()}"


# --- mint + locate ---------------------------------------------------------

def mint_work_item(title, nonce=None):
    """Freeze a `<work-item>` slug for `title` (§6.1).

    The slug is minted ONCE per work-item and never re-derived. `nonce` is the
    creation nonce that disambiguates same-titled items; callers normally omit
    it and we draw a fresh random one (the resulting slug is what gets frozen).
    Tests pass an explicit nonce for determinism.
    """
    if nonce is None:
        nonce = os.urandom(8).hex()
    return identifiers.work_item_slug(title, nonce)


def work_item_dir(work_item, root=".", location=DEFAULT_LOCATION):
    return os.path.join(root, *location.split("/"), work_item)


def doc_path(work_item, doc_type, root=".", location=DEFAULT_LOCATION):
    if doc_type not in DOC_TYPES:
        raise ValueError(f"unknown docType {doc_type!r}; expected one of {DOC_TYPES}")
    return os.path.join(work_item_dir(work_item, root, location), f"{doc_type}.md")


def _in_repo_candidate(work_item, root, cwd, store_root=None):
    import architect_config
    pol = architect_config.read_policy(cwd, store_root)
    location = pol["location"] if pol else architect_config.DEFAULT_LOCATION
    return work_item_dir(work_item, root, location)


def _global_candidate(work_item, cwd, store_root):
    import mode_registry
    return os.path.join(mode_registry.project_store_dir(cwd, store_root), "docs", work_item)


def resolve_work_item_dir(work_item, *, root, cwd, store_root=None):
    """Mode-aware, spec-anchored directory for a work-item's definition-docs.
    Propagates mode_registry.UnknownSchemaVersion (UFR-7 — caller halts)."""
    import mode_registry
    in_repo = _in_repo_candidate(work_item, root, cwd, store_root)
    global_dir = _global_candidate(work_item, cwd, store_root)
    # Spec-anchor (UFR-2): an existing work-item lives wherever its spec is — keep docs together.
    for cand in (in_repo, global_dir):
        if os.path.isfile(os.path.join(cand, "spec.md")):
            return cand
    # No existing doc → the recorded mode decides (raises UnknownSchemaVersion if newer).
    mode = mode_registry.resolve(cwd, store_root)["mode"]
    return in_repo if mode == mode_registry.IN_REPO else global_dir


class CanonLookupError(RuntimeError):
    """The default-branch copy of Canon could not be probed (git missing or slow, no resolvable
    default ref on a repo with an origin remote, or a tree read that failed for a reason other
    than the path being absent). The lookup fails closed: an unprobed default branch is never
    read as one with no Canon. The single arg names the cause; `remedy`, when set, is the one
    action that fixes that cause and is set only where such an action exists."""

    def __init__(self, message, *, remedy=None):
        super().__init__(message)
        self.remedy = remedy


_CANON_REMEDY = "run `git remote set-head origin --auto` (or fetch origin) and retry"


def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                              timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CanonLookupError("git could not be run (%s: %s)" % (type(exc).__name__, exc))


def _default_branch_ref(root):
    """The default-branch ref name for `root` (e.g. `origin/main`), read from origin/HEAD only; a
    name guess (origin/main, origin/master) is never accepted. Returns None ONLY when the
    repository has no origin remote, which only git's own answer establishes: `git remote get-url
    origin` exits 2, or `git config --get remote.origin.url` exits 1 with nothing on stderr. Any
    other failure raises CanonLookupError, as does git that cannot be run or an origin remote whose
    origin/HEAD does not resolve."""
    got = _git(root, "remote", "get-url", "origin")
    if got.returncode == 2:
        return None
    if got.returncode != 0:
        cfg = _git(root, "config", "--get", "remote.origin.url")
        if cfg.returncode == 1 and not cfg.stderr.strip():
            return None
        raise CanonLookupError("could not probe the origin remote: %s"
                               % (got.stderr.strip() or "git exit %d" % got.returncode))
    proc = _git(root, "rev-parse", "--abbrev-ref", "origin/HEAD")
    ref = proc.stdout.strip()
    if proc.returncode == 0 and ref and ref != "origin/HEAD":
        return ref
    raise CanonLookupError("origin/HEAD does not resolve, so the default branch is unknown",
                           remedy=_CANON_REMEDY)


def _exists_at_ref(root, ref, relpath):
    """True iff `relpath` (forward slashes) exists in the tree at `ref`, False when the path is
    absent there; raises CanonLookupError on any other failure (the tree could not be read)."""
    proc = _git(root, "ls-tree", "--name-only", ref, "--", relpath)
    if proc.returncode != 0:
        raise CanonLookupError("could not read %s at %s: %s"
                               % (relpath, ref, proc.stderr.strip() or "git exit %d" % proc.returncode))
    return bool(proc.stdout.strip())


def resolve_canon(*, root, cwd=None, store_root=None):
    """Locate the project's Canon file. Returns {path, home, gitRoot, exists, defaultRef}:
    an existing Canon (in the repo on disk, in the repo at the default-branch ref, or in the
    project store on disk, in that order) wins over the recorded storage mode; with none, an
    in-repo mode and a committed policy give the repo, anything else the project store. Read-only:
    creates and writes nothing, and records no registry backfill. Propagates
    mode_registry.UnknownSchemaVersion when the mode is needed and undeterminable, and
    CanonLookupError when the default branch cannot be probed (it fails closed)."""
    import architect_config
    import mode_registry
    import store_core
    try:
        top = store_core.repo_root(os.path.abspath(root))
    except store_core.RepoRootUnavailable as exc:
        raise CanonLookupError("could not resolve the repository root: %s" % exc)
    if os.path.realpath(root) != top:
        root = top
    cwd = cwd if cwd is not None else root
    pol = architect_config.read_policy(cwd, store_root) or architect_config.analyze_repo(root)
    committed = pol["visibility"] == architect_config.COMMITTED
    root_abs = os.path.abspath(root)
    in_repo = os.path.join(root_abs, *pol["location"].split("/"), CANON_FILE)
    store_dir = mode_registry.project_store_dir(cwd, store_root)
    store = os.path.join(store_dir, "docs", CANON_FILE)
    default_ref = _default_branch_ref(root) if committed else None
    if committed and os.path.isfile(in_repo):
        home = "repo"
    elif committed and default_ref and _exists_at_ref(
            root, default_ref, "/".join([*pol["location"].split("/"), CANON_FILE])):
        home = "repo"
    elif os.path.isfile(store):
        home = "project-store"
    else:
        mode = mode_registry.resolve(cwd, store_root, persist_backfill=False)["mode"]
        home = "repo" if committed and mode == mode_registry.IN_REPO else "project-store"
    if home == "repo":
        path, git_root = in_repo, root_abs
    else:
        path, git_root, default_ref = store, store_dir, None
    return {"path": os.path.abspath(path), "home": home, "gitRoot": git_root,
           "exists": os.path.isfile(path), "defaultRef": default_ref}


class GroundingBaseError(RuntimeError):
    """The grounding base (a detached worktree at the default branch's tip) could not be made.
    `reason` is the refusal token; the single arg is the detail."""

    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason


def _git_step(top, *args):
    """Run git for the grounding base: (CompletedProcess, None), or (None, the failure text) when
    git could not be run or timed out. Its own 60 s timeout, apart from the Canon lookup's `_git`."""
    try:
        # The checkout hooks are switched off (the pair engine_dispatch._git_scrubbed uses): a
        # project's post-checkout hook must neither fail nor dirty the grounding worktree.
        return subprocess.run(["git", "-C", top, "-c", "core.hooksPath=/dev/null",
                               "-c", "core.fsmonitor=", *args], capture_output=True, text=True,
                              timeout=60), None
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


def grounding_base(*, root, dest):
    """Fetch the project's default branch and materialize a detached worktree at its tip in the
    new directory `dest`. Returns {ok, ref, sha, path}; raises GroundingBaseError (with a refusal
    token) and creates nothing on any refusal. The dest checks run before the fetch."""
    import store_core
    try:
        top = store_core.repo_root(os.path.abspath(root))
    except store_core.RepoRootUnavailable as exc:
        raise GroundingBaseError("grounding-base-not-a-repo",
                                 "could not resolve the repository root: %s" % exc)
    try:
        ref = _default_branch_ref(top)
    except CanonLookupError as exc:
        remedy = "; %s" % exc.remedy if exc.remedy else ""
        raise GroundingBaseError("grounding-base-default-unknown", "%s%s" % (exc, remedy))
    if ref is None:
        raise GroundingBaseError("grounding-base-no-origin",
                                 "the repository has no origin remote, so there is no default "
                                 "branch to ground against")
    dest_abs = os.path.abspath(dest)
    if os.path.lexists(dest_abs):
        raise GroundingBaseError("grounding-base-dest-exists", "%s already exists" % dest_abs)
    dest_real = os.path.join(os.path.realpath(os.path.dirname(dest_abs)),
                             os.path.basename(dest_abs))
    top_real = os.path.realpath(top)
    if dest_real == top_real or dest_real.startswith(top_real + os.sep):
        raise GroundingBaseError("grounding-base-dest-inside-repo",
                                 "%s is inside the repository at %s" % (dest_abs, top_real))
    branch = ref.split("/", 1)[1]
    fetched, failure = _git_step(top, "fetch", "--quiet", "origin",
                                 "+refs/heads/%s:refs/remotes/%s" % (branch, ref))
    if failure is not None or fetched.returncode != 0:
        raise GroundingBaseError("grounding-base-fetch-failed",
                                 failure or fetched.stderr.strip() or "git exit %d" % fetched.returncode)
    parsed, failure = _git_step(top, "rev-parse", "--verify", "%s^{commit}" % ref)
    if failure is not None or parsed.returncode != 0:
        raise GroundingBaseError("grounding-base-fetch-failed",
                                 failure or parsed.stderr.strip() or "git exit %d" % parsed.returncode)
    sha = parsed.stdout.strip()
    added, failure = _git_step(top, "worktree", "add", "--detach", dest_abs, sha)
    if failure is not None or added.returncode != 0:
        raise GroundingBaseError("grounding-base-worktree-failed",
                                 failure or added.stderr.strip() or "git exit %d" % added.returncode)
    return {"ok": True, "ref": ref, "sha": sha, "path": os.path.realpath(dest_abs)}


class IgnoreCoverageError(RuntimeError):
    """A kept-local (gitignored) docs location could not be kept out of version control
    (already tracked or .gitignore unwritable) — UFR-8; the write must be refused. The
    offending location is the exception's single arg."""


def resolve_write_path(work_item, doc_type, *, root, cwd=None, store_root=None):
    """Resolve the mode-aware write path for a definition-doc and prepare it for writing:
    ensure ignore coverage for a kept-local (gitignored) policy, record an
    analysis-informed PROVISIONAL policy when none exists (UFR-1, only after the ignore
    gate passes), and create the target directory. Returns the resolved `<doc>.md` path.

    Raises mode_registry.UnknownSchemaVersion when the storage mode is undeterminable
    (UFR-7) and IgnoreCoverageError when a gitignored location can't be kept untracked
    (UFR-8). The `resolve-write` CLI verb is a thin wrapper over this."""
    import architect_config
    cwd = cwd if cwd is not None else root
    d = resolve_work_item_dir(work_item, root=root, cwd=cwd, store_root=store_root)
    pol = architect_config.read_policy(cwd, store_root)
    is_new = pol is None
    if is_new:
        pol = {**architect_config.analyze_repo(root), "confirmed": False}
    root_abs = os.path.abspath(root)
    d_abs = os.path.abspath(d)
    is_inrepo = d_abs == root_abs or d_abs.startswith(root_abs + os.sep)
    if is_inrepo and pol.get("visibility") == architect_config.GITIGNORED:
        if not architect_config.ensure_ignored(root, pol["location"]):
            raise IgnoreCoverageError(pol["location"])
    if is_new:
        architect_config.write_policy(cwd, pol)  # provisional (UFR-1); store contention is non-fatal
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, doc_type + ".md")


# --- frontmatter (§3.1) ----------------------------------------------------

def frontmatter(doc_type, work_item, *, size, issue=None,
                created=None, updated=None, status="draft", review="pending",
                approved=None):
    """Build the §3.1 frontmatter dict, enforcing the review/status/approved invariants.

    The §3.1 header is a FLAT field set: a definition-doc carries no linkage to
    another doc (there is no `parent` field). We fail closed on an unknown docType,
    and on any `status` / `gates.review` / `approved` combination the contract
    forbids, rather than emit a doc that violates it.
    """
    if doc_type not in DOC_TYPES:
        raise ValueError(f"unknown docType {doc_type!r}; expected one of {DOC_TYPES}")
    # `set_gate` is the sole writer that mints an approved date; this emitter only round-trips
    # a caller-supplied value and synthesises nothing.
    if approved is not None and review != "passed":
        raise ValueError("approved may be set only when gates.review is passed (§3.1)")
    if review == "passed" and approved is None:
        raise ValueError("gates.review passed requires an approved date (§3.1)")
    if status != _STATUS_FOR_REVIEW[review]:
        raise ValueError(
            f"status {status!r} contradicts gates.review {review!r} (§3.1)")
    if approved is not None:
        try:
            parsed = datetime.date.fromisoformat(approved)
        except ValueError:
            raise ValueError(f"approved must be a canonical ISO date, got {approved!r}")
        if parsed.isoformat() != approved:
            raise ValueError(f"approved must be a canonical ISO date, got {approved!r}")
    today = datetime.date.today().isoformat()
    fm = {
        "superheroes": "doc",
        "schemaVersion": SCHEMA_VERSION,
        "docType": doc_type,
        "workItem": work_item,
        "issue": issue,
        "size": size,
        "status": status,
        "gates": {"review": review},
        "producedBy": produced_by(),
        "created": created or today,
        "updated": updated or today,
    }
    if approved is not None:
        fm["approved"] = approved
    return fm


def render_frontmatter(fm):
    """Render the frontmatter dict as a deterministic `---`-fenced YAML block.

    We emit the fixed §3.1 field set in schema order and quote the values that a
    YAML reader would otherwise coerce (dates → date objects; `producedBy` holds
    `@`). The constrained fields (slugs, enums) are safe bare scalars.
    """
    issue = fm["issue"]
    issue_str = "null" if issue is None else str(issue)
    lines = [
        "---",
        "superheroes: doc",
        f"schemaVersion: {fm['schemaVersion']}",
        f"docType: {fm['docType']}",
        f"workItem: {fm['workItem']}",
        f"issue: {issue_str}",
        f"size: {fm['size']}",
        f"status: {fm['status']}",
    ]
    if fm.get("approved") is not None:
        lines.append(f'approved: "{fm["approved"]}"')
    lines.extend([
        f"gates: {{review: {fm['gates']['review']}}}",
        f'producedBy: "{fm["producedBy"]}"',
        f'created: "{fm["created"]}"',
        f'updated: "{fm["updated"]}"',
        "---",
    ])
    return "\n".join(lines) + "\n"


# --- review gate (§3.1) ----------------------------------------------------

REVIEW_STATES = ("pending", "passed", "changes-requested")
# `status` is DERIVED from gates.review (§3.1): approved iff review == passed.
_STATUS_FOR_REVIEW = {"passed": "approved", "changes-requested": "in-review", "pending": "draft"}
_GATES_RE = re.compile(r"^gates:\s*\{\s*review:\s*([a-z-]+)\s*\}\s*$")
_STATUS_RE = re.compile(r"^status:\s*[a-z-]+\s*$")
_UPDATED_RE = re.compile(r'^updated:\s*".*"\s*$')
_APPROVED_KEY_RE = re.compile(r"^(?:approved|'approved'|\"approved\")[ \t]*:")
_APPROVED_CANONICAL_RE = re.compile(r'^approved:\s*"(\d{4}-\d{2}-\d{2})"\s*$')
# The closed set of frontmatter fields `set_gate` rewrites, and the canonical line forms this
# module writes for them — reused (never restated) as the definition of "canonical", so a change
# to a writer's shape moves the check with it.
_MANAGED_FIELDS = ("status", "gates", "updated", "approved")
_MANAGED_KEY_RE = re.compile(
    r"^((?:%s)|'(?:%s)'|\"(?:%s)\")[ \t]*:" % ((("|".join(_MANAGED_FIELDS)),) * 3))
_CANONICAL_LINE_RES = (_STATUS_RE, _GATES_RE, _UPDATED_RE, _APPROVED_CANONICAL_RE)


def _unrewritten_managed_keys(lines, end):
    """Return [(index, key-as-written)] for managed-field keys left in non-canonical form.

    Axis: refusal — `set_gate` must never report success while a top-level managed key it did
    not rewrite survives in the frontmatter, because the doc would then disagree with the
    result the caller was handed.

    Detects, within `lines[1:end]` (the `---`-fenced frontmatter only): a key token that is one
    of the four managed fields — `status`, `gates`, `updated`, `approved` — written at the top
    level with **no leading whitespace**, bare or `'single'`- or `"double"`-quoted, with optional
    spaces/tabs before the colon, on a line matching none of this module's canonical forms.

    Does NOT detect: keys nested inside block or flow mappings (any indented key belongs to its
    parent field, not to `set_gate`), keys spanning multiple lines, YAML anchors or aliases,
    escaped or unicode-escaped spellings, and managed keys in the document body below the
    closing fence. This is a closed-variant line scan, not a YAML reader.
    """
    offenders = []
    for i in range(1, end):
        m = _MANAGED_KEY_RE.match(lines[i])
        if m and not any(rx.match(lines[i]) for rx in _CANONICAL_LINE_RES):
            offenders.append((i, m.group(1)))
    return offenders


def _unrewritten_managed_key_refusal(offenders):
    """The named refusal for `_unrewritten_managed_keys` hits — 1-based line numbers, as written."""
    detail = ", ".join("%s (line %d)" % (key, i + 1) for i, key in offenders)
    return {
        "ok": False,
        "reason": "unrewritten-managed-key",
        "detail": "frontmatter key(s) not rewritten to canonical form: " + detail,
    }


def _frontmatter_bounds(text, path):
    """Return (lines, end) where the frontmatter is lines[1:end] (between the two `---`)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing opening '---' frontmatter fence")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError(f"{path}: unterminated frontmatter (no closing '---')")
    return lines, end


def _apply_approved_pass(lines, end, review, current_review):
    """Second pass: sole writer of the `approved:` frontmatter line (§3.1)."""
    approved_indices = [i for i in range(1, end) if _APPROVED_KEY_RE.match(lines[i])]
    kept_date = None
    if review == "passed" and current_review == "passed" and approved_indices:
        dates = []
        all_canonical = True
        for i in approved_indices:
            m = _APPROVED_CANONICAL_RE.match(lines[i])
            if not m:
                all_canonical = False
                break
            captured = m.group(1)
            try:
                parsed = datetime.date.fromisoformat(captured)
            except ValueError:
                all_canonical = False
                break
            # Cross-version guard: permissive fromisoformat (3.11+) can admit values the
            # regex matched but that are not canonical YYYY-MM-DD.
            if parsed.isoformat() != captured:
                all_canonical = False
                break
            dates.append(captured)
        if all_canonical and len(set(dates)) == 1:
            kept_date = dates[0]
    for i in sorted(approved_indices, reverse=True):
        del lines[i]
        end -= 1
    if review != "passed":
        return None
    date = kept_date or datetime.date.today().isoformat()
    insert_at = None
    for i in range(1, end):
        if _STATUS_RE.match(lines[i]):
            insert_at = i + 1
            break
    if insert_at is None:
        for i in range(1, end):
            if _GATES_RE.match(lines[i]):
                insert_at = i + 1
                break
    lines.insert(insert_at, f'approved: "{date}"')
    return date


def read_frontmatter(path):
    """Parse a definition-doc's §3.1 frontmatter into (frontmatter_dict, body) — the reader paired
    with `render_frontmatter` (the writer), co-located so the two sides change in lockstep. Every
    §3.1 field is a scalar, and reads back as one. This is the canonical frontmatter→dict reader
    (e.g. for the §6.3 content-hash); callers must not re-implement it.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines, end = _frontmatter_bounds(text, path)
    fm = {}
    for ln in lines[1:end]:
        m = re.match(r"([A-Za-z]+):\s*(.+)$", ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        fm[key] = val
    return fm, "\n".join(lines[end + 1:])


def content_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _atomic_replace(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".definition-doc-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}


def read_gate(path):
    """Return the definition-doc's gates.review value, parsed from the frontmatter.

    Reads from the `---`-fenced frontmatter only (so a body line can't spoof it),
    and gives a clear error if the gates line is absent or malformed — more robust
    than a skill grepping the raw file.
    """
    with open(path, encoding="utf-8") as fh:
        lines, end = _frontmatter_bounds(fh.read(), path)
    for ln in lines[1:end]:
        m = _GATES_RE.match(ln)
        if m:
            return m.group(1)
    raise ValueError(f"{path}: no parseable 'gates: {{review: …}}' line in frontmatter")


def set_gate(path, review, *, expected_hash=None, run_id=None, lease=None):
    """Set gates.review in place (and derive status, bump updated) — §3.1.

    Fenced write: ``expected_hash`` must match the on-disk content hash captured
    for the reviewed artifact snapshot; ``run_id`` is required. Stale or unreadable
    state is refused without touching the doc.

    ``expected_hash="current"`` stamps the doc as it is on disk NOW — for callers in the
    Workflow sandbox, where every read is an LLM courier and a hash computed from courier
    prose (e.g. a chatty missing-file answer) poisons the fence. The runtime makes no
    decision between its doc re-read and this write, so the sentinel loses only the
    detection of a same-window concurrent edit, which the run lease already excludes
    (courier text must never enter an integrity decision).
    """
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if not expected_hash:
        return {"ok": False, "reason": "missing-expected-hash"}
    if review not in REVIEW_STATES:
        raise ValueError(f"unknown review state {review!r}; expected one of {REVIEW_STATES}")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {"ok": False, "reason": "unreadable", "detail": str(exc)}
    if expected_hash != "current" and content_hash(text) != expected_hash:
        return {"ok": False, "reason": "stale"}
    lines, end = _frontmatter_bounds(text, path)
    status = _STATUS_FOR_REVIEW[review]
    today = datetime.date.today().isoformat()
    found = False
    current_review = None
    for i in range(1, end):
        m = _GATES_RE.match(lines[i])
        if m:
            current_review = m.group(1)
            lines[i] = f"gates: {{review: {review}}}"
            found = True
        elif _STATUS_RE.match(lines[i]):
            lines[i] = f"status: {status}"
        elif _UPDATED_RE.match(lines[i]):
            lines[i] = f'updated: "{today}"'
    if not found:
        # A doc whose only `gates` key is non-canonical never sets `found`: refuse by name
        # rather than raise, so the caller gets the reason. Nothing was written either way.
        offenders = _unrewritten_managed_keys(lines, end)
        if offenders:
            return _unrewritten_managed_key_refusal(offenders)
        raise ValueError(f"{path}: no 'gates: {{review: …}}' line to update")
    approved_date = _apply_approved_pass(lines, end, review, current_review)
    prospective = "\n".join(lines)
    # Verify the PROSPECTIVE state (an `approved` spelling the pass already deleted is not an
    # offender), and recompute the bound: `_apply_approved_pass` deletes and inserts lines but
    # decrements only its own local `end`, so the one bound above is stale here.
    _, prospective_end = _frontmatter_bounds(prospective, path)
    offenders = _unrewritten_managed_keys(lines, prospective_end)
    if offenders:
        return _unrewritten_managed_key_refusal(offenders)
    result = _atomic_replace(path, prospective)
    if not result.get("ok"):
        return result
    out = {"ok": True, "review": review, "status": status, "runId": run_id}
    if approved_date is not None:
        out["approved"] = approved_date
    if lease:
        out["lease"] = lease
    return out


# --- CLI -------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(description="the-architect definition-doc helper (§3, §6.1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mint", help="freeze a <work-item> slug for a title (§6.1)")
    m.add_argument("--title", required=True)
    m.add_argument("--nonce", default=None)

    pa = sub.add_parser("path", help="resolve the on-disk path for a definition-doc")
    pa.add_argument("--work-item", required=True)
    pa.add_argument("--doc", required=True, choices=DOC_TYPES)
    pa.add_argument("--root", default=".")

    d = sub.add_parser("dir", help="resolve the work-item directory")
    d.add_argument("--work-item", required=True)
    d.add_argument("--root", default=".")

    f = sub.add_parser("frontmatter", help="render the §3.1 frontmatter block")
    f.add_argument("--doc", required=True, choices=DOC_TYPES)
    f.add_argument("--work-item", required=True)
    f.add_argument("--size", required=True, choices=["small", "medium", "large"])
    f.add_argument("--issue", type=int, default=None)
    f.add_argument("--created", default=None)
    f.add_argument("--updated", default=None)

    ch = sub.add_parser("content-hash", help="SHA-256 content hash of a file (empty file if absent)")
    ch.add_argument("--path", required=True)

    sg = sub.add_parser("set-gate", help="record gates.review on a definition-doc (derives status)")
    sg.add_argument("--work-item", required=True)
    sg.add_argument("--doc", required=True, choices=DOC_TYPES)
    sg.add_argument("--review", required=True, choices=list(REVIEW_STATES))
    sg.add_argument("--root", default=".")
    sg.add_argument("--expected-hash", required=True)
    sg.add_argument("--run-id", required=True)
    sg.add_argument("--lease", default=None)

    rg = sub.add_parser("read-gate", help="print a definition-doc's gates.review value")
    rg.add_argument("--work-item", required=True)
    rg.add_argument("--doc", required=True, choices=DOC_TYPES)
    rg.add_argument("--root", default=".")
    rg.add_argument("--json", action="store_true",
                    help="emit {\"review\": <state>} on stdout (errors stay on stderr/non-zero)")

    rw = sub.add_parser("resolve-write",
                        help="resolve the mode-aware write path, ensuring ignore coverage")
    rw.add_argument("--work-item", required=True)
    rw.add_argument("--doc", required=True, choices=DOC_TYPES)
    rw.add_argument("--root", default=".")
    rw.add_argument("--cwd", default=None)

    cn = sub.add_parser("canon", help="locate the project's Canon file (read-only)")
    cn.add_argument("--root", default=".")

    gb = sub.add_parser("grounding-base",
                        help="fetch the default branch and add a detached worktree at its tip")
    gb.add_argument("--root", default=".")
    gb.add_argument("--dest", required=True)
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "mint":
        sys.stdout.write(mint_work_item(args.title, args.nonce) + "\n")
        return 0
    if args.cmd == "content-hash":
        try:
            with open(args.path, encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            text = ""
        except OSError as exc:
            sys.stderr.write(f"definition_doc error: {exc}\n")
            return 1
        sys.stdout.write(content_hash(text) + "\n")
        return 0
    if args.cmd == "resolve-write":
        import mode_registry
        try:
            path = resolve_write_path(args.work_item, args.doc,
                                      root=args.root, cwd=args.cwd or args.root)
        except mode_registry.UnknownSchemaVersion as exc:
            sys.stderr.write("definition_doc: storage mode could not be determined (%s) — "
                             "repair the mode record first; refusing to guess.\n" % exc)
            return 1
        except IgnoreCoverageError:
            sys.stderr.write("definition_doc: refusing to write — the kept-local docs "
                             "location could not be kept out of version control "
                             "(already tracked or .gitignore unwritable). Resolve it "
                             "before writing.\n")
            return 1
        sys.stdout.write(path + "\n")
        return 0
    if args.cmd == "frontmatter":
        fm = frontmatter(
            args.doc, args.work_item, size=args.size,
            issue=args.issue, created=args.created, updated=args.updated)
        sys.stdout.write(render_frontmatter(fm))
        return 0
    if args.cmd == "grounding-base":
        try:
            result = grounding_base(root=args.root, dest=args.dest)
        except GroundingBaseError as exc:
            sys.stdout.write(json.dumps({"ok": False, "reason": exc.reason,
                                         "detail": str(exc)}) + "\n")
            return 1
        sys.stdout.write(json.dumps(result) + "\n")
        return 0
    try:
        if args.cmd == "canon":
            try:
                result = resolve_canon(root=args.root)
            except CanonLookupError as exc:
                remedy = "; %s" % exc.remedy if exc.remedy else ""
                sys.stderr.write("definition_doc: canon lookup refused — %s%s. Refusing to "
                                 "guess a Canon home.\n" % (exc, remedy))
                return 1
            sys.stdout.write(json.dumps(result) + "\n")
            return 0
        if args.cmd in ("path", "dir", "read-gate", "set-gate"):
            d = resolve_work_item_dir(args.work_item, root=args.root, cwd=args.root)
            if args.cmd == "path":
                sys.stdout.write(os.path.join(d, f"{args.doc}.md") + "\n")
                return 0
            if args.cmd == "dir":
                sys.stdout.write(d + "\n")
                return 0
            if args.cmd == "set-gate":
                result = set_gate(
                    os.path.join(d, f"{args.doc}.md"), args.review,
                    expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
                sys.stdout.write(json.dumps(result) + "\n")
                return 0 if result.get("ok") else 1
            if args.cmd == "read-gate":
                review = read_gate(os.path.join(d, f"{args.doc}.md"))
                if getattr(args, "json", False):   # the cmdRunner JSON bridge (errors stay stderr/non-zero)
                    sys.stdout.write(json.dumps({"review": review}) + "\n")
                else:
                    sys.stdout.write(review + "\n")
                return 0
    except __import__("mode_registry").UnknownSchemaVersion as exc:
        sys.stderr.write(
            "definition_doc: storage mode could not be determined (%s) — repair the "
            "project's mode record before continuing; refusing to guess a location.\n" % exc)
        return 1
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"definition_doc error: {exc}\n")
        sys.exit(1)
