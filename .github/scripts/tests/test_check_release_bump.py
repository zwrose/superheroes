from __future__ import annotations

import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = os.path.join(_HERE, "..", "check_release_bump.py")
_spec = importlib.util.spec_from_file_location("check_release_bump", _M)
RB = importlib.util.module_from_spec(_spec)
sys.modules["check_release_bump"] = RB
_spec.loader.exec_module(RB)

Commit = RB.Commit

_CONFIG_PATH = os.path.join(_HERE, "..", "..", "..", "release-please-config.json")
with open(_CONFIG_PATH) as _fh:
    _REAL_CONFIG = json.load(_fh)
_RELEASING = RB.releasing_types(_REAL_CONFIG)
_BUMP_MINOR_PRE_MAJOR = _REAL_CONFIG["packages"]["plugins/superheroes"]["bump-minor-pre-major"]


def _sha(short: str) -> str:
    return (short + "0" * 40)[:40]


def _c(sha_short, subject, *, touches_package=True, zero_file=False, body=""):
    return Commit(
        sha=_sha(sha_short),
        subject=subject,
        body=body,
        touches_package=touches_package,
        zero_file=zero_file,
    )


def _changelog_line(description: str, sha_short: str, full_sha: str | None = None) -> str:
    full = full_sha or _sha(sha_short)
    return (
        f"* **superheroes:** {description} "
        f"([#1](https://github.com/zwrose/superheroes/issues/1)) "
        f"([{sha_short[:7]}](https://github.com/zwrose/superheroes/commit/{full}))"
    )


def _evaluate(commits, last_version, release_pr=None, exclusions=None, exclusion_errors=None):
    return RB.evaluate(
        commits,
        last_version,
        release_pr,
        exclusions or {},
        exclusion_errors or [],
        _RELEASING,
        _BUMP_MINOR_PRE_MAJOR,
        f"superheroes-v{last_version}",
    )


# --- Incident 2 window (2026-07-31 pre-cut) ---

_INC2_COMMITS = [
    _c("868dce5b", "chore: release re-statement of #726 and #716 — two commits the release-please parser silently dropped from 0.23.0 (#739)", zero_file=True, touches_package=False),
    _c("2d197b78", "fix(superheroes): charter hygiene 8 part B — config-surface fall-opens become named refusals (#699 riders 7-12) [PARKED — rework tripwire fired] (#732)"),
    _c("c115e8a3", "feat(superheroes)!: remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal (#724) (#730)"),
    _c("c48b5f6c", "fix(superheroes): test-pilot execution calibration teeth — accessible-name selection, pointer events, aria-disabled, N/N procedure-suspicion (#728)"),
    _c("62f88552", "chore(superheroes): extend the boundary sync guard to the named cross-lane invariants (#721) (#727)"),
    _c("4d884197", "feat(superheroes): supervised dispatch — write verb, durable journaling, reviewer retrofit (#702 lean rebuild) (#726)"),
    _c("da90558e", "feat(superheroes): the check-runner seat + \"a review seat never changes the repository, and never claims a run it did not make\" (#719) (#731)"),
    _c("ed29199f", "feat(superheroes): vet-receipt doctrine — spine + triggered fields, owner-half verdict write, collector reconciliation (#672 ratified) (#729)"),
    _c("2a6ac6a7", "chore(superheroes): charter hygiene 8 — part A of #699 (riders 1-6, 13, 14, 15) (#716)"),
    _c("1925eb5f", "feat(superheroes): PR-body doctrine — owner half + build record, show-it wayfinding, omission floor (#661 ratified) (#715)"),
    _c("4e1f0bf2", "feat(superheroes): three-lane build doctrine (full/light/micro) — review-discipline + charters, micro hard-line named (#709)"),
    _c("0d918cfc", "chore(superheroes): PHILOSOPHY amendment — approval/execution distinction (owner-ratified) + covenant note removal + LEDGERS R3 resolution (#708)"),
    _c("b1e4904f", "docs: ROADMAP — split the concatenated 0.21.1/0.21.2 cut-record rows (#707)", touches_package=False),
    _c("6249bbf0", "fix(superheroes): config gates fail closed on an unreadable core.md — one (prefs, status) accessor (#701)"),
    _c("e7006ecb", "fix(superheroes): seat_map verify() violations drive the certification shape — per-seat excusal evidence (#680) (#700)"),
    _c("e2419ec1", "chore(superheroes): charter hygiene 7 — four riders (#685) (#698)"),
    _c("721ca00a", "chore(superheroes): retire the orphaned pr-body model tier role (#692) (#696)"),
    _c("4f1b9628", "feat(superheroes): orchestration doctrine — LEDGERS §4 + covenant merge-line repair + R1–R5 charter text (#697)"),
    _c("25d0863c", "docs: ROADMAP — 0.21.2 + 0.22.0 cut records (#690)", touches_package=False),
]

# Fix the two commits that need real full SHAs
_INC2_COMMITS[5] = Commit(
    sha="4d88419716b7b7054660a7943b061420bd804ed8",
    subject="feat(superheroes): supervised dispatch — write verb, durable journaling, reviewer retrofit (#702 lean rebuild) (#726)",
    touches_package=True,
)
_INC2_COMMITS[8] = Commit(
    sha="2a6ac6a7259146083deb62f18171fd10c9312754",
    subject="chore(superheroes): charter hygiene 8 — part A of #699 (riders 1-6, 13, 14, 15) (#716)",
    touches_package=True,
)


def _inc2_changelog_present_only() -> str:
  lines = []
  for c in _INC2_COMMITS:
      if c.sha in (
          "4d88419716b7b7054660a7943b061420bd804ed8",
          "2a6ac6a7259146083deb62f18171fd10c9312754",
      ):
          continue
      if not RB.belongs_to_package(c):
          continue
      parsed = RB.parse_subject(c.subject)
      if parsed is None:
          continue
      _, _, _, desc = parsed
      if parsed[0] not in _RELEASING:
          continue
      lines.append(_changelog_line(desc, c.sha[:7], c.sha))
  return "\n".join(lines)


# --- A. Real incidents ---


def test_incident1_version_floor_shape():
    feat_sha = _sha("fe000001")
    commits = [
        _c("fi000001", "fix(superheroes): one"),
        _c("fi000002", "fix(superheroes): two"),
        Commit(
            sha=feat_sha,
            subject="feat(superheroes)!: breaking feature dropped by parser",
            touches_package=True,
        ),
    ]
    release_pr = {
        "number": 99,
        "proposed_version": "0.21.3",
        "changelog_text": "\n".join(
            [
                _changelog_line("one", "fi000001"),
                _changelog_line("two", "fi000002"),
            ]
        ),
    }
    result = _evaluate(commits, "0.21.2", release_pr)
    assert result.ok is False
    floor_msgs = [f for f in result.failures if "minimum" in f]
    assert floor_msgs
    assert "0.22.0" in floor_msgs[0]
    assert feat_sha[:7] in "\n".join(result.failures)


def test_incident2_changelog_only_shape():
    release_pr = {
        "number": 100,
        "proposed_version": "0.23.0",
        "changelog_text": _inc2_changelog_present_only(),
    }
    result = _evaluate(_INC2_COMMITS, "0.22.0", release_pr)
    assert result.ok is False
    version_failures = [f for f in result.failures if "minimum" in f or "below minimum" in f]
    assert not version_failures
    completeness_failures = [
        f
        for f in result.failures
        if f != RB.REMEDIATION
        and ("changelog" in f.lower() or "SHA" in f or "title" in f)
    ]
    assert len(completeness_failures) == 2
    joined = "\n".join(result.failures)
    assert "4d88419" in joined
    assert "2a6ac6a" in joined


def test_incident2_both_acknowledged_with_replacements_present():
    repl1 = _sha("rep00001")
    repl2 = _sha("rep00002")
    changelog = (
        _inc2_changelog_present_only()
        + "\n"
        + _changelog_line("restated 726", repl1[:7], repl1)
        + "\n"
        + _changelog_line("restated 716", repl2[:7], repl2)
    )
    exclusions = {
        "4d88419716b7b7054660a7943b061420bd804ed8": (repl1, "2026-07-31", "parser crash"),
        "2a6ac6a7259146083deb62f18171fd10c9312754": (repl2, "2026-07-31", "parser crash"),
    }
    release_pr = {"number": 100, "proposed_version": "0.23.0", "changelog_text": changelog}
    result = _evaluate(_INC2_COMMITS, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is True
    ack_notices = [n for n in result.notices if n.startswith("acknowledged exclusion:")]
    assert len(ack_notices) == 2


def test_incident2_only_one_acknowledged():
    repl1 = _sha("rep00001")
    changelog = (
        _inc2_changelog_present_only()
        + "\n"
        + _changelog_line("restated 726", repl1[:7], repl1)
    )
    exclusions = {
        "4d88419716b7b7054660a7943b061420bd804ed8": (repl1, "2026-07-31", "parser crash"),
    }
    release_pr = {"number": 100, "proposed_version": "0.23.0", "changelog_text": changelog}
    result = _evaluate(_INC2_COMMITS, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is False
    joined = "\n".join(result.failures)
    assert "2a6ac6a" in joined
    assert "4d884197" not in joined or "acknowledged" in "\n".join(result.notices)


def test_incident2_acknowledged_but_replacement_absent():
    repl1 = _sha("rep00001")
    exclusions = {
        "4d88419716b7b7054660a7943b061420bd804ed8": (repl1, "2026-07-31", "parser crash"),
    }
    release_pr = {
        "number": 100,
        "proposed_version": "0.23.0",
        "changelog_text": _inc2_changelog_present_only(),
    }
    result = _evaluate(_INC2_COMMITS, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is False
    joined = "\n".join(result.failures)
    assert "4d88419" in joined
    assert "acknowledgement unsatisfied" in joined


# --- B. Tolerances and edges ---


def test_empty_floor_population_passes():
    result = _evaluate([], "0.23.0")
    assert result.ok is True
    assert any("no eligible commits" in n for n in result.notices)


def test_nonempty_floor_no_release_pr_fails():
    commits = [_c("aa000001", "fix(superheroes): something")]
    result = _evaluate(commits, "0.23.0", release_pr=None)
    assert result.ok is False
    assert any("no open release PR" in f for f in result.failures)


def test_hidden_docs_ci_not_in_populations():
    commits = [
        _c("dc000001", "docs: readme tweak"),
        _c("ci000001", "ci: workflow only"),
    ]
    assert RB.completeness_population(commits, _RELEASING) == []
    assert RB.floor_population(commits, _RELEASING) == []


def test_feat_touching_only_non_package_files_not_eligible():
    commits = [_c("np000001", "feat(superheroes): root only", touches_package=False)]
    assert RB.completeness_population(commits, _RELEASING) == []


def test_zero_file_feat_restatement_eligible_and_fails_if_missing():
    sha = _sha("868dce5b")
    commits = [
        Commit(
            sha=sha,
            subject="feat(superheroes): release re-statement of dropped commit (#739)",
            zero_file=True,
            touches_package=False,
        )
    ]
    assert RB.completeness_population(commits, _RELEASING)
    result = _evaluate(
        commits,
        "0.22.0",
        {"number": 1, "proposed_version": "0.23.0", "changelog_text": ""},
    )
    assert result.ok is False


def test_release_commit_not_eligible():
    commits = [_c("rc000001", "chore(main): release superheroes 0.23.0 (#705)")]
    assert RB.completeness_population(commits, _RELEASING) == []
    assert RB.floor_population(commits, _RELEASING) == []


def test_malformed_ledger_line_fails():
    _, errors = RB.parse_exclusions("deadbeef\n")
    result = _evaluate([], "0.23.0", exclusion_errors=errors)
    assert result.ok is False
    assert errors


def test_missing_ledger_passes_with_notice_via_empty_mapping():
    result = _evaluate([], "0.23.0")
    assert result.ok is True


def test_stale_acknowledgement_notice_still_passes():
    orig = _sha("stale001")
    repl = _sha("stale002")
    commits = [_c("ok000001", "fix(superheroes): ok")]
    changelog = _changelog_line("ok", "ok000001") + "\n" + _changelog_line("restated", "stale00", orig)
    exclusions = {orig: (repl, "2026-01-01", "old")}
    release_pr = {"number": 1, "proposed_version": "0.23.1", "changelog_text": changelog}
    result = _evaluate(commits, "0.23.0", release_pr, exclusions=exclusions)
    assert result.ok is True
    assert any("stale acknowledgement" in n for n in result.notices)


def test_abbrev_only_presence_notice():
    sha = _sha("abb00001")
    commits = [
        Commit(sha=sha, subject="fix(superheroes): abbrev match", touches_package=True)
    ]
    changelog = (
        f"* **superheroes:** abbrev match "
        f"([{sha[:7]}](https://github.com/zwrose/superheroes/commit/{sha[:7]}))"
    )
    release_pr = {"number": 1, "proposed_version": "0.23.1", "changelog_text": changelog}
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is True
    assert any("abbreviated SHA only" in n for n in result.notices)


# --- B2. Pre-code review findings ---


def test_hidden_breaking_raises_floor_not_changelog():
    hidden = _c("hb000001", "refactor(superheroes)!: delete legacy path")
    fix = _c("fx000001", "fix(superheroes): small fix")
    commits = [hidden, fix]
    assert hidden not in RB.completeness_population(commits, _RELEASING)
    assert hidden in RB.floor_population(commits, _RELEASING)
    release_pr = {
        "number": 1,
        "proposed_version": "0.23.1",
        "changelog_text": _changelog_line("small fix", "fx000001"),
    }
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is False
    assert any("minimum" in f for f in result.failures)


def test_hidden_non_breaking_only_commit_passes():
    commits = [_c("hn000001", "refactor(superheroes): internal cleanup")]
    result = _evaluate(commits, "0.23.0")
    assert result.ok is True


def test_sha_only_failure_distinguishes_from_absent():
    sha = _sha("shaonly1")
    commits = [
        Commit(sha=sha, subject="feat(superheroes): real title", touches_package=True)
    ]
    changelog = (
        f"* **superheroes:** unrelated body fragment "
        f"([{sha[:7]}](https://github.com/zwrose/superheroes/commit/{sha}))"
    )
    release_pr = {"number": 1, "proposed_version": "0.24.0", "changelog_text": changelog}
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is False
    assert any("none matches this commit's title" in f for f in result.failures)
    assert not any("no changelog entry carries" in f and "title" not in f for f in result.failures if "none matches" not in f)


def test_normalize_entry_flattens_markdown_links():
    title = "three-lane build doctrine (full/light/micro) — review-discipline + charters, micro hard-line named ([#709](https://github.com/zwrose/superheroes/issues/709))"
    bullet = (
        "* **superheroes:** three-lane build doctrine (full/light/micro) — "
        "review-discipline + charters, micro hard-line named "
        "([#709](https://github.com/zwrose/superheroes/issues/709)) "
        "([4e1f0bf](https://github.com/zwrose/superheroes/commit/4e1f0bf20e0f14f31de58626ec0d58ca03d9f6da))"
    )
    presence, _ = RB.changelog_presence(
        "4e1f0bf20e0f14f31de58626ec0d58ca03d9f6da",
        title.split(": ", 1)[1] if ": " in title else title,
        bullet,
    )
    assert presence == "entry"
    assert RB.normalize_entry("([#709](https://x))") == "(#709)"


# --- C. Bump arithmetic ---


def test_expected_minimum_pre_major_breaking_minor():
    assert RB.expected_minimum((0, 21, 2), "major", True) == (0, 22, 0)


def test_expected_minimum_pre_major_breaking_major():
    assert RB.expected_minimum((0, 21, 2), "major", False) == (1, 0, 0)


def test_expected_minimum_post_major_breaking():
    assert RB.expected_minimum((1, 2, 3), "major", True) == (2, 0, 0)


def test_expected_minimum_feat_minor():
    assert RB.expected_minimum((0, 21, 2), "minor", True) == (0, 22, 0)


def test_expected_minimum_fix_patch():
    assert RB.expected_minimum((0, 21, 2), "patch", True) == (0, 21, 3)


def test_parse_version_rejects_invalid():
    import pytest

    for bad in ("1.2", "v1.2.3", "1.2.3-rc1", ""):
        with pytest.raises(ValueError):
            RB.parse_version(bad)


# --- D. Parsing ---


def test_parse_subject_real_titles():
    assert RB.parse_subject(
        "feat(superheroes)!: remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal (#724) (#730)"
    ) == ("feat", "superheroes", True, "remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal (#724) (#730)")
    assert RB.parse_subject(
        "feat(superheroes): supervised dispatch — write verb, durable journaling, reviewer retrofit (#702 lean rebuild) (#726)"
    )[0:3] == ("feat", "superheroes", False)
    assert RB.parse_subject("not a conventional commit at all") is None


def test_is_release_commit():
    assert RB.is_release_commit("chore(main): release superheroes 0.23.0 (#705)")
    assert RB.is_release_commit("chore: release superheroes 0.1.0")
    assert not RB.is_release_commit("chore(superheroes): extend boundary (#721)")


def test_releasing_types_from_config_not_hardcoded():
    got = RB.releasing_types(_REAL_CONFIG)
    assert got == frozenset({"feat", "fix", "perf", "deps", "revert", "chore"})
    assert "docs" not in got


def test_body_declares_breaking_notice_not_failure():
    commits = [
        Commit(
            sha=_sha("bd000001"),
            subject="feat(superheroes): title without bang",
            body="BREAKING CHANGE: removed API",
            touches_package=True,
        )
    ]
    release_pr = {
        "number": 1,
        "proposed_version": "0.24.0",
        "changelog_text": _changelog_line("title without bang", "bd000001"),
    }
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is True
    assert any("body declares BREAKING CHANGE" in n for n in result.notices)


def test_non_conventional_subject_notice():
    commits = [
        Commit(sha=_sha("nc000001"), subject="WIP: messy squash subject", touches_package=True)
    ]
    result = _evaluate(commits, "0.23.0")
    assert any("non-conventional" in n for n in result.notices)


def test_parse_exclusions_valid_line():
    text = (
        "4d88419716b7b7054660a7943b061420bd804ed8  "
        "868dce5b11111111111111111111111111111111  "
        "2026-07-31  parser crash on squash body"
    )
    mapping, errors = RB.parse_exclusions(text)
    assert not errors
    assert "4d88419716b7b7054660a7943b061420bd804ed8" in mapping


def test_belongs_to_package_zero_file():
    c = Commit(sha=_sha("zf000001"), subject="chore: empty", zero_file=True, touches_package=False)
    assert RB.belongs_to_package(c)


def test_changelog_presence_absent():
    presence, _ = RB.changelog_presence(_sha("xx000001"), "desc", "* nothing here")
    assert presence == "absent"
