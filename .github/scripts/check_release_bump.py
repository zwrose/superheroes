#!/usr/bin/env python3
"""Fail-closed CI tripwire: release-please can silently drop squash commits from
version calculation and the changelog when its conventional-commit parser crashes
on PR-body punctuation. This script compares the commit window since the last cut
tag against the open release PR's proposed version and changelog.

Pure functions are testable without git, gh, or network; main() is a thin IO layer.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Load TYPES from the sibling conventional-commit checker (not a package).
_SCRIPTS = Path(__file__).resolve().parent
_cc_spec = importlib.util.spec_from_file_location(
    "check_conventional_commit", _SCRIPTS / "check_conventional_commit.py"
)
_cc_mod = importlib.util.module_from_spec(_cc_spec)
_cc_spec.loader.exec_module(_cc_mod)
TYPES: tuple[str, ...] = _cc_mod.TYPES

_SUBJECT_CAPTURE_RE = re.compile(
    r"^(" + "|".join(TYPES) + r")"
    r"(?:\(([^()\n]+)\))?"
    r"(!)?"
    r": (.+)$"
)

_RELEASE_COMMIT_RE = re.compile(
    r"^chore\([^()\n]+\): release (?:\S+ )?\d+\.\d+\.\d+(?: \(#\d+\))?$"
)
_BODY_BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_EXCLUSION_LINE_RE = re.compile(
    r"^([0-9a-f]{40})\s{2,}([0-9a-f]{40})\s{2,}(\d{4}-\d{2}-\d{2})\s{2,}(.+)$"
)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPHASIS_RE = re.compile(r"[*_]+")

REMEDIATION = (
    "Remediation (issue #674): re-state each dropped commit with an empty commit "
    "carrying a clean conventional title (the #673 pattern), open it as a normal PR, "
    "and let release-please regenerate the release PR. Never hand-edit version.txt, "
    "plugin.json, or the manifest. Record each originally-dropped SHA in "
    ".github/release-exclusions.txt — the re-statement commit is a new commit and never "
    "restores the original commit's changelog entry."
)


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str = ""
    touches_package: bool = False
    zero_file: bool = False


@dataclass
class EvaluateResult:
    ok: bool
    status: str  # "pass" | "skip" | "fail"
    failures: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    tag: str = ""
    last_version: str = ""
    eligible_count: int = 0
    proposed_version: str | None = None
    release_pr_number: int | None = None
    floor_population: list[Commit] = field(default_factory=list)
    completeness_population: list[Commit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "failures": self.failures,
            "notices": self.notices,
            "tag": self.tag,
            "last_version": self.last_version,
            "eligible_count": self.eligible_count,
            "proposed_version": self.proposed_version,
            "release_pr_number": self.release_pr_number,
        }


def parse_subject(subject: str) -> tuple[str, str | None, bool, str] | None:
    """Parse a Conventional Commit subject into (type, scope, breaking, description)."""
    first = subject.splitlines()[0] if subject else ""
    m = _SUBJECT_CAPTURE_RE.match(first)
    if not m:
        return None
    typ, scope, bang, desc = m.group(1), m.group(2), m.group(3), m.group(4)
    return typ, scope, bang == "!", desc


def is_release_commit(subject: str) -> bool:
    first = subject.splitlines()[0] if subject else ""
    return _RELEASE_COMMIT_RE.match(first) is not None


def releasing_types(config_dict: dict[str, Any]) -> frozenset[str]:
    sections = config_dict.get("changelog-sections", [])
    return frozenset(
        s["type"] for s in sections if s.get("hidden") is not True
    )


def belongs_to_package(commit: Commit) -> bool:
    return commit.touches_package or commit.zero_file


def completeness_population(
    commits: list[Commit], releasing: frozenset[str]
) -> list[Commit]:
    out: list[Commit] = []
    for c in commits:
        if not belongs_to_package(c):
            continue
        if is_release_commit(c.subject):
            continue
        parsed = parse_subject(c.subject)
        if parsed is None:
            continue
        typ, _, _, _ = parsed
        if typ not in releasing:
            continue
        out.append(c)
    return out


def floor_population(commits: list[Commit], releasing: frozenset[str]) -> list[Commit]:
    base = {c.sha: c for c in completeness_population(commits, releasing)}
    for c in commits:
        if not belongs_to_package(c):
            continue
        if is_release_commit(c.subject):
            continue
        parsed = parse_subject(c.subject)
        if parsed is None:
            continue
        _, _, breaking, _ = parsed
        if breaking:
            base[c.sha] = c
    return list(base.values())


def bump_severity(floor_pop: list[Commit]) -> str | None:
    has_breaking = False
    has_feat = False
    has_other = False
    for c in floor_pop:
        parsed = parse_subject(c.subject)
        if parsed is None:
            continue
        typ, _, breaking, _ = parsed
        if breaking:
            has_breaking = True
        elif typ == "feat":
            has_feat = True
        else:
            has_other = True
    if has_breaking:
        return "major"
    if has_feat:
        return "minor"
    if has_other:
        return "patch"
    return None


def body_declares_breaking(body: str) -> bool:
    return _BODY_BREAKING_RE.search(body) is not None


def parse_version(text: str) -> tuple[int, int, int]:
    m = _VERSION_RE.match(text.strip())
    if not m:
        raise ValueError(f"not a strict SemVer triple: {text!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def expected_minimum(
    current: tuple[int, int, int],
    severity: str | None,
    bump_minor_pre_major: bool,
) -> tuple[int, int, int] | None:
    if severity is None:
        return None
    major, minor, patch = current
    if severity == "major":
        if bump_minor_pre_major and major == 0:
            return (0, minor + 1, 0)
        return (major + 1, 0, 0)
    if severity == "minor":
        return (major, minor + 1, 0)
    if severity == "patch":
        return (major, minor, patch + 1)
    raise ValueError(f"unknown severity: {severity!r}")


def parse_exclusions(
    text: str,
) -> tuple[dict[str, tuple[str, str, str]], list[str]]:
    mapping: dict[str, tuple[str, str, str]] = {}
    errors: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _EXCLUSION_LINE_RE.match(line)
        if not m:
            errors.append(f"malformed exclusion ledger line {lineno}: {raw!r}")
            continue
        orig, repl, date, reason = m.group(1), m.group(2), m.group(3), m.group(4)
        mapping[orig] = (repl, date, reason)
    return mapping, errors


def normalize_entry(text: str) -> str:
    flat = _MD_LINK_RE.sub(r"\1", text)
    flat = _EMPHASIS_RE.sub("", flat)
    flat = re.sub(r"\s+", " ", flat).strip()
    return flat.casefold()


def changelog_bullets(changelog_text: str) -> list[str]:
    return [ln for ln in changelog_text.splitlines() if ln.startswith("* ")]


def _bullet_carries_sha(bullet: str, sha: str) -> tuple[bool, bool]:
    """Return (carries_sha, abbrev_only)."""
    full = sha.lower()
    abbrev = sha[:7].lower()
    lower = bullet.lower()
    has_full = full in lower
    has_abbrev = re.search(r"\b" + re.escape(abbrev) + r"\b", lower) is not None
    if not has_full and not has_abbrev:
        return False, False
    return True, has_abbrev and not has_full


def changelog_presence(
    sha: str, description: str, changelog_text: str
) -> tuple[str, bool]:
    """Return (presence, abbrev_only) where presence is entry|sha-only|absent."""
    norm_desc = normalize_entry(description)
    sha_bullets: list[str] = []
    abbrev_only_match = False
    for bullet in changelog_bullets(changelog_text):
        carries, abbrev_only = _bullet_carries_sha(bullet, sha)
        if carries:
            sha_bullets.append(bullet)
            if abbrev_only:
                abbrev_only_match = True
    if not sha_bullets:
        return "absent", False
    for bullet in sha_bullets:
        if norm_desc in normalize_entry(bullet):
            _, abbrev_only = _bullet_carries_sha(bullet, sha)
            return "entry", abbrev_only
    return "sha-only", abbrev_only_match


def _version_lt(a: str, b: tuple[int, int, int]) -> bool:
    return parse_version(a) < b


def _format_version(v: tuple[int, int, int]) -> str:
    return f"{v[0]}.{v[1]}.{v[2]}"


def evaluate(
    commits: list[Commit],
    last_version: str,
    release_pr: dict[str, Any] | None,
    exclusions: dict[str, tuple[str, str, str]],
    exclusion_errors: list[str],
    releasing: frozenset[str],
    bump_minor_pre_major: bool,
    tag: str,
) -> EvaluateResult:
    result = EvaluateResult(ok=True, status="pass", tag=tag, last_version=last_version)

    if exclusion_errors:
        result.status = "fail"
        result.failures.extend(exclusion_errors)
        result.ok = False
        return result

    floor_pop = floor_population(commits, releasing)
    complete_pop = completeness_population(commits, releasing)
    result.floor_population = floor_pop
    result.completeness_population = complete_pop
    result.eligible_count = len(floor_pop)

    window_shas = {c.sha for c in commits}

    for c in commits:
        if not belongs_to_package(c):
            continue
        if is_release_commit(c.subject):
            continue
        if parse_subject(c.subject) is None:
            result.notices.append(
                f"non-conventional commit subject (excluded from populations): "
                f"{c.sha[:7]} {c.subject!r}"
            )
        elif body_declares_breaking(c.body) and "!" not in c.subject.splitlines()[0]:
            result.notices.append(
                f"body declares BREAKING CHANGE but title lacks '!': {c.sha[:7]} — "
                f"version floor is derived from titles only; eyeball the proposed bump"
            )

    if not floor_pop:
        result.status = "pass"
        result.notices.insert(
            0, f"no eligible commits since {tag} — no release is expected"
        )
        result.ok = True
        return result

    if release_pr is None:
        subjects = [f"  {c.sha[:7]} {c.subject}" for c in floor_pop]
        result.status = "fail"
        result.failures.append(
            f"{len(floor_pop)} eligible commits since {tag} but no open release PR:\n"
            + "\n".join(subjects)
        )
        result.ok = False
        return result

    proposed = release_pr["proposed_version"]
    changelog_text = release_pr.get("changelog_text", "")
    result.proposed_version = proposed
    result.release_pr_number = release_pr.get("number")

    severity = bump_severity(floor_pop)
    current = parse_version(last_version)
    minimum = expected_minimum(current, severity, bump_minor_pre_major)
    if minimum is not None and _version_lt(proposed, minimum):
        drivers = [f"  {c.sha[:7]} {c.subject}" for c in floor_pop if parse_subject(c.subject)]
        result.failures.append(
            f"proposed version {proposed} is below minimum {_format_version(minimum)} "
            f"(severity {severity}) — commits driving severity:\n" + "\n".join(drivers)
        )

    for c in complete_pop:
        parsed = parse_subject(c.subject)
        if parsed is None:
            continue
        _, _, _, desc = parsed
        presence, abbrev_only = changelog_presence(c.sha, desc, changelog_text)

        if presence == "entry":
            if abbrev_only:
                result.notices.append(
                    f"changelog entry matched by abbreviated SHA only: {c.sha[:7]}"
                )
            continue

        ack = exclusions.get(c.sha)
        if ack is not None:
            repl_sha, _date, reason = ack
            repl_presence, _ = changelog_presence(repl_sha, "", changelog_text)
            if repl_presence != "absent":
                result.notices.append(
                    f"acknowledged exclusion: {c.sha} — re-stated as {repl_sha} — {reason}"
                )
                continue
            if presence == "absent":
                result.failures.append(
                    f"no changelog entry carries this commit's SHA: {c.sha[:7]} "
                    f"{c.subject!r} — acknowledgement unsatisfied because replacement "
                    f"commit {repl_sha} is not in this release"
                )
            else:
                result.failures.append(
                    f"an entry carries this SHA but none matches this commit's title: "
                    f"{c.sha[:7]} {c.subject!r} — acknowledgement unsatisfied because "
                    f"replacement commit {repl_sha} is not in this release"
                )
            continue

        if presence == "absent":
            result.failures.append(
                f"no changelog entry carries this commit's SHA: {c.sha[:7]} {c.subject!r}"
            )
        else:
            result.failures.append(
                f"an entry carries this SHA but none matches this commit's title: "
                f"{c.sha[:7]} {c.subject!r}"
            )

    for orig_sha, (repl_sha, _date, reason) in exclusions.items():
        orig_presence, _ = changelog_presence(orig_sha, "", changelog_text)
        if orig_presence != "absent":
            result.notices.append(
                f"stale acknowledgement: {orig_sha} is present in changelog "
                f"(replacement {repl_sha}, {reason})"
            )
        elif orig_sha not in window_shas:
            result.notices.append(
                f"aged-out acknowledgement: {orig_sha} is outside the current window "
                f"(replacement {repl_sha}, {reason})"
            )

    if result.failures:
        result.status = "fail"
        result.failures.append(REMEDIATION)
    result.ok = not result.failures
    return result


def _run_git(args: list[str], *, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def _run_gh(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", "api", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"gh api {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return json.loads(proc.stdout)


def _parse_remote_repo(url: str) -> str | None:
    url = url.strip()
    m = re.match(r"git@github\.com:(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    m = re.match(r"https://github\.com/(.+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1)
    return None


def _read_json(path: Path) -> dict[str, Any]:
    with open(path) as fh:
        return json.load(fh)


def _load_commits_since_tag(
    tag: str, package: str, repo_root: Path
) -> list[Commit]:
    raw = _run_git(
        ["log", "--format=%H%x1f%s", f"{tag}..HEAD"],
        cwd=repo_root,
    )
    commits: list[Commit] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, subject = line.split("\x1f", 1)
        body = _run_git(["log", "-1", "--format=%b", sha], cwd=repo_root).rstrip("\n")
        pkg_files = _run_git(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                sha,
                "--",
                package,
            ],
            cwd=repo_root,
        ).splitlines()
        all_files = _run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            cwd=repo_root,
        ).splitlines()
        commits.append(
            Commit(
                sha=sha,
                subject=subject,
                body=body,
                touches_package=bool(pkg_files),
                zero_file=len(all_files) == 0,
            )
        )
    return commits


def _find_release_pr(
    repo: str,
    component: str,
    *,
    retries: int = 3,
    delay_s: float = 5.0,
) -> dict[str, Any] | None:
    prefix = "release-please--branches--"
    suffix = f"--components--{component}"
    for attempt in range(retries):
        pulls = _run_gh([f"repos/{repo}/pulls?state=open&per_page=100"])
        matches = [
            pr
            for pr in pulls
            if pr.get("head", {}).get("ref", "").startswith(prefix)
            and pr.get("head", {}).get("ref", "").endswith(suffix)
        ]
        if len(matches) > 1:
            nums = [str(m["number"]) for m in matches]
            raise RuntimeError(
                f"ambiguous release PRs for {component}: {', '.join(nums)}"
            )
        if len(matches) == 1:
            pr = matches[0]
            return {
                "number": pr["number"],
                "head_ref": pr["head"]["ref"],
            }
        if attempt < retries - 1:
            time.sleep(delay_s)
    return None


def _gh_read_file_content(repo: str, path: str, ref: str) -> str:
    data = _run_gh([f"repos/{repo}/contents/{path}?ref={ref}"])
    if not isinstance(data, dict) or "content" not in data:
        raise RuntimeError(f"missing .content in gh response for {path}@{ref}")
    raw = base64.b64decode(data["content"]).decode("utf-8")
    return raw


def _print_report(result: EvaluateResult) -> None:
    pr_part = (
        str(result.release_pr_number) if result.release_pr_number is not None else "—"
    )
    proposed = result.proposed_version if result.proposed_version is not None else "—"
    print(
        f"check_release_bump: tag={result.tag} last={result.last_version} "
        f"eligible={result.eligible_count} proposed={proposed} pr=#{pr_part}"
    )
    for msg in result.failures:
        print(f"FAIL: {msg}")
    for msg in result.notices:
        print(f"notice: {msg}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release-please bump tripwire")
    parser.add_argument("--repo", default=None)
    parser.add_argument("--config", default="release-please-config.json")
    parser.add_argument("--manifest", default=".release-please-manifest.json")
    parser.add_argument("--package", default="plugins/superheroes")
    parser.add_argument("--exclusions", default=".github/release-exclusions.txt")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args(argv)

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(top.stdout.strip())
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"error: cannot resolve repo root: {e}\n")
            return 1

    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )
            repo = _parse_remote_repo(remote.stdout)
        except subprocess.CalledProcessError:
            repo = None
    if not repo:
        sys.stderr.write("error: cannot resolve GitHub repository\n")
        return 1

    try:
        config = _read_json(repo_root / args.config)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"error: cannot read config {args.config}: {e}\n")
        return 1

    packages = config.get("packages", {})
    if args.package not in packages:
        sys.stderr.write(f"error: package key {args.package!r} missing from config\n")
        return 1
    pkg_cfg = packages[args.package]
    component = pkg_cfg.get("component")
    if not component:
        sys.stderr.write(f"error: component missing for package {args.package!r}\n")
        return 1
    changelog_rel = pkg_cfg.get("changelog-path", "CHANGELOG.md")
    bump_minor_pre_major = bool(pkg_cfg.get("bump-minor-pre-major", False))
    releasing = releasing_types(config)

    try:
        manifest = _read_json(repo_root / args.manifest)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"error: cannot read manifest {args.manifest}: {e}\n")
        return 1
    if args.package not in manifest:
        sys.stderr.write(f"error: package key {args.package!r} missing from manifest\n")
        return 1
    try:
        last_version = manifest[args.package]
        parse_version(last_version)
    except ValueError as e:
        sys.stderr.write(f"error: invalid manifest version: {e}\n")
        return 1

    tag = f"{component}-v{last_version}"
    try:
        _run_git(["rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"], cwd=repo_root)
        tag_exists = True
    except RuntimeError:
        tag_exists = False

    if not tag_exists:
        try:
            listed = _run_git(["tag", "--list", f"{component}-v*"], cwd=repo_root).strip()
        except RuntimeError as e:
            sys.stderr.write(f"error: {e}\n")
            return 1
        if not listed:
            print(
                f"check_release_bump: no {component} release tags yet — bootstrap skip"
            )
            return 0
        sys.stderr.write(
            f"error: tag {tag!r} missing while other {component} tags exist\n"
        )
        return 1

    try:
        commits = _load_commits_since_tag(tag, args.package, repo_root)
    except RuntimeError as e:
        sys.stderr.write(f"error: {e}\n")
        return 1

    exclusions_path = repo_root / args.exclusions
    exclusion_notice: str | None = None
    if exclusions_path.exists():
        try:
            exclusion_text = exclusions_path.read_text()
        except OSError as e:
            sys.stderr.write(f"error: cannot read exclusions file: {e}\n")
            return 1
    else:
        exclusion_text = ""
        exclusion_notice = f"exclusions ledger missing ({args.exclusions}) — treating as empty"

    exclusions, exclusion_errors = parse_exclusions(exclusion_text)

    release_pr: dict[str, Any] | None = None
    floor_pop = floor_population(commits, releasing)
    if floor_pop:
        try:
            pr_meta = _find_release_pr(repo, component)
        except RuntimeError as e:
            sys.stderr.write(f"error: {e}\n")
            return 1
        if pr_meta is not None:
            try:
                manifest_text = _gh_read_file_content(
                    repo, args.manifest, pr_meta["head_ref"]
                )
                pr_manifest = json.loads(manifest_text)
                if args.package not in pr_manifest:
                    raise RuntimeError(
                        f"package {args.package!r} missing from release PR manifest"
                    )
                proposed_version = pr_manifest[args.package]
                parse_version(proposed_version)
                changelog_text = _gh_read_file_content(
                    repo,
                    f"{args.package}/{changelog_rel}",
                    pr_meta["head_ref"],
                )
                release_pr = {
                    "number": pr_meta["number"],
                    "proposed_version": proposed_version,
                    "changelog_text": changelog_text,
                }
            except (RuntimeError, json.JSONDecodeError, ValueError) as e:
                sys.stderr.write(f"error: release PR data: {e}\n")
                return 1

    result = evaluate(
        commits,
        last_version,
        release_pr,
        exclusions,
        exclusion_errors,
        releasing,
        bump_minor_pre_major,
        tag,
    )
    if exclusion_notice:
        result.notices.insert(0, exclusion_notice)

    _print_report(result)
    if args.emit_json:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
