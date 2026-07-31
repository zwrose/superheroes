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
_PKG_CFG = _REAL_CONFIG["packages"]["plugins/superheroes"]
_PARSE_TYPES = RB.parseable_types(_REAL_CONFIG, _PKG_CFG)
_RELEASING = RB.releasing_types(_REAL_CONFIG, _PKG_CFG)
_BUMP_MINOR_PRE_MAJOR = _PKG_CFG["bump-minor-pre-major"]


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


def _release_changelog(version: str, body: str) -> str:
    return f"## [{version}](https://github.com/zwrose/superheroes/compare)\n\n{body}\n"


def _evaluate(commits, last_version, release_pr=None, exclusions=None, exclusion_errors=None):
    return RB.evaluate(
        commits,
        last_version,
        release_pr,
        exclusions or {},
        exclusion_errors or [],
        _RELEASING,
        _PARSE_TYPES,
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
      parsed = RB.parse_subject(c.subject, _PARSE_TYPES)
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
        "changelog_text": _release_changelog(
            "0.21.3",
            "\n".join(
                [
                    _changelog_line("one", "fi000001"),
                    _changelog_line("two", "fi000002"),
                ]
            ),
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
        "changelog_text": _release_changelog("0.23.0", _inc2_changelog_present_only()),
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
    changelog = _release_changelog(
        "0.23.0",
        _inc2_changelog_present_only()
        + "\n"
        + _changelog_line("restated 726", repl1[:7], repl1)
        + "\n"
        + _changelog_line("restated 716", repl2[:7], repl2),
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
    changelog = _release_changelog(
        "0.23.0",
        _inc2_changelog_present_only()
        + "\n"
        + _changelog_line("restated 726", repl1[:7], repl1),
    )
    exclusions = {
        "4d88419716b7b7054660a7943b061420bd804ed8": (repl1, "2026-07-31", "parser crash"),
    }
    release_pr = {"number": 100, "proposed_version": "0.23.0", "changelog_text": changelog}
    result = _evaluate(_INC2_COMMITS, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is False
    joined = "\n".join(result.failures)
    assert "2a6ac6a" in joined
    assert "4d884197" not in joined
    assert any(n.startswith("acknowledged exclusion:") for n in result.notices)


def test_incident2_acknowledged_but_replacement_absent():
    repl1 = _sha("rep00001")
    exclusions = {
        "4d88419716b7b7054660a7943b061420bd804ed8": (repl1, "2026-07-31", "parser crash"),
    }
    release_pr = {
        "number": 100,
        "proposed_version": "0.23.0",
        "changelog_text": _release_changelog("0.23.0", _inc2_changelog_present_only()),
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


def test_hidden_docs_ci_not_in_completeness_but_in_floor():
    commits = [
        _c("dc000001", "docs: readme tweak"),
        _c("ci000001", "ci: workflow only"),
    ]
    assert RB.completeness_population(commits, _RELEASING, _PARSE_TYPES) == []
    assert len(RB.floor_population(commits, _PARSE_TYPES)) == 2


def test_feat_touching_only_non_package_files_not_eligible():
    commits = [_c("np000001", "feat(superheroes): root only", touches_package=False)]
    assert RB.completeness_population(commits, _RELEASING, _PARSE_TYPES) == []
    assert RB.floor_population(commits, _PARSE_TYPES) == []


def test_zero_file_feat_restatement_eligible_and_fails_if_missing():
    sha = _sha("868dce5b")
    commits = [
        Commit(
            sha=sha,
            subject=(
                "chore: release re-statement of #726 and #716 — two commits the "
                "release-please parser silently dropped from 0.23.0 (#739)"
            ),
            zero_file=True,
            touches_package=False,
        )
    ]
    assert RB.completeness_population(commits, _RELEASING, _PARSE_TYPES)
    result = _evaluate(
        commits,
        "0.22.0",
        {
            "number": 1,
            "proposed_version": "0.23.0",
            "changelog_text": _release_changelog("0.23.0", ""),
        },
    )
    assert result.ok is False


def test_release_cut_requires_manifest_touch():
    cut = Commit(
        sha=_sha("rc000001"),
        subject="chore(main): release superheroes 0.23.0 (#705)",
        touches_package=True,
        touches_manifest=True,
    )
    shaped = Commit(
        sha=_sha("rc000002"),
        subject="chore(superheroes): release 9.9.9",
        touches_package=True,
        touches_manifest=False,
    )
    assert RB.completeness_population([cut], _RELEASING, _PARSE_TYPES) == []
    assert RB.floor_population([cut], _PARSE_TYPES) == []
    assert shaped in RB.floor_population([shaped], _PARSE_TYPES)
    assert shaped in RB.completeness_population([shaped], _RELEASING, _PARSE_TYPES)


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
    changelog = _release_changelog(
        "0.23.1",
        _changelog_line("ok", "ok000001") + "\n" + _changelog_line("restated", "stale00", orig),
    )
    exclusions = {orig: (repl, "2026-01-01", "old")}
    release_pr = {
        "number": 1,
        "proposed_version": "0.23.1",
        "changelog_text": changelog,
    }
    result = _evaluate(commits, "0.23.0", release_pr, exclusions=exclusions)
    assert result.ok is True
    assert any("stale acknowledgement" in n for n in result.notices)


def test_abbrev_sha_no_false_match_inside_full_sha():
    """7-char prefix must not match as substring inside another commit's full SHA."""
    sha_a = "0123456789abcdef0123456789abcdef01234567"
    sha_b = "cdef012" + "0" * 33
    assert sha_b[:7] == "cdef012"
    assert "cdef012" in sha_a
    bullet = (
        f"* **superheroes:** other commit "
        f"([{sha_a}](https://github.com/zwrose/superheroes/commit/{sha_a}))"
    )
    # Bare substring would falsely match; word-boundary matching must not.
    assert "cdef012" in bullet.lower()
    carries, _ = RB._bullet_carries_sha(bullet, sha_b)
    assert carries is False


def test_abbrev_only_presence_notice():
    sha = _sha("abb00001")
    commits = [
        Commit(sha=sha, subject="fix(superheroes): abbrev match", touches_package=True)
    ]
    changelog = (
        f"* **superheroes:** abbrev match "
        f"([{sha[:7]}](https://github.com/zwrose/superheroes/commit/{sha[:7]}))"
    )
    release_pr = {
        "number": 1,
        "proposed_version": "0.23.1",
        "changelog_text": _release_changelog("0.23.1", changelog),
    }
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is True
    assert any("abbreviated SHA only" in n for n in result.notices)


# --- B2. Pre-code review findings ---


def test_hidden_breaking_raises_floor_not_changelog():
    hidden = _c("hb000001", "refactor(superheroes)!: delete legacy path")
    fix = _c("fx000001", "fix(superheroes): small fix")
    commits = [hidden, fix]
    assert hidden not in RB.completeness_population(commits, _RELEASING, _PARSE_TYPES)
    assert hidden in RB.floor_population(commits, _PARSE_TYPES)
    release_pr = {
        "number": 1,
        "proposed_version": "0.23.1",
        "changelog_text": _release_changelog(
            "0.23.1", _changelog_line("small fix", "fx000001")
        ),
    }
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is False
    assert any("minimum" in f for f in result.failures)


def test_hidden_non_breaking_only_no_release_pr_fails():
    commits = [_c("hn000001", "refactor(superheroes): internal cleanup")]
    result = _evaluate(commits, "0.23.0")
    assert result.ok is False
    assert any("changelog-hidden types" in f for f in result.failures)
    assert any("no open release PR" in f for f in result.failures)


def test_sha_only_failure_distinguishes_from_absent():
    sha = _sha("shaonly1")
    commits = [
        Commit(sha=sha, subject="feat(superheroes): real title", touches_package=True)
    ]
    changelog = (
        f"* **superheroes:** unrelated body fragment "
        f"([{sha[:7]}](https://github.com/zwrose/superheroes/commit/{sha}))"
    )
    release_pr = {
        "number": 1,
        "proposed_version": "0.24.0",
        "changelog_text": _release_changelog("0.24.0", changelog),
    }
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
        "feat(superheroes)!: remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal (#724) (#730)",
        _PARSE_TYPES,
    ) == ("feat", "superheroes", True, "remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal (#724) (#730)")
    assert RB.parse_subject(
        "feat(superheroes): supervised dispatch — write verb, durable journaling, reviewer retrofit (#702 lean rebuild) (#726)",
        _PARSE_TYPES,
    )[0:3] == ("feat", "superheroes", False)
    assert RB.parse_subject("not a conventional commit at all", _PARSE_TYPES) is None


def test_is_release_commit_real_subjects():
    """Table over measured release-please cut vs non-cut subjects from repo history."""
    cut_subjects = [
        "chore(main): release superheroes 0.23.0 (#705)",
        "chore(main): release superheroes 0.22.0 (#669)",
        "chore(main): release superheroes 0.21.2 (#645)",
    ]
    non_cut_subjects = [
        "feat(superheroes): supervised dispatch — write verb, durable journaling, reviewer retrofit (release re-statement of #726) (#740)",
        "chore(superheroes): charter hygiene 8 — part A of #699, riders 1-6 and 13-15 (release re-statement of #716) (#741)",
        "chore: release re-statement of #726 and #716 — two commits the release-please parser silently dropped from 0.23.0 (#739)",
        "feat(superheroes)!: Claude 5 model refresh + cursor first-party family merge (release re-statement of #653) (#673)",
    ]
    for subject in cut_subjects:
        assert RB.is_release_commit(subject), f"expected cut: {subject!r}"
    for subject in non_cut_subjects:
        assert not RB.is_release_commit(subject), f"expected non-cut: {subject!r}"


def test_incident2_completeness_population_includes_restatement():
    pop = RB.completeness_population(_INC2_COMMITS, _RELEASING, _PARSE_TYPES)
    assert len(pop) == 17
    assert any(c.sha.startswith("868dce5b") for c in pop)


def test_releasing_types_from_config_not_hardcoded():
    got = RB.releasing_types(_REAL_CONFIG, _PKG_CFG)
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
        "changelog_text": _release_changelog(
            "0.24.0", _changelog_line("title without bang", "bd000001")
        ),
    }
    result = _evaluate(commits, "0.23.0", release_pr)
    assert result.ok is True
    assert any("body declares BREAKING CHANGE" in n for n in result.notices)
    assert any("eyeball the proposed bump" in n for n in result.notices)


def test_body_breaking_with_exclamation_in_title_still_notices():
    commits = [
        Commit(
            sha=_sha("bd000002"),
            subject="feat(superheroes): remove old API!",
            body="BREAKING CHANGE: removed API",
            touches_package=True,
        )
    ]
    release_pr = {
        "number": 1,
        "proposed_version": "0.24.0",
        "changelog_text": _release_changelog(
            "0.24.0", _changelog_line("remove old API!", "bd000002")
        ),
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


def test_parse_exclusions_wider_column_separator():
    """Separator must accept \\s{2,}, not exactly two spaces."""
    orig = "4d88419716b7b7054660a7943b061420bd804ed8"
    repl = "868dce5b11111111111111111111111111111111"
    three_spaces = (
        f"{orig}   {repl}   2026-07-31   parser crash on squash body"
    )
    wide_run = (
        f"{orig}     {repl}     2026-07-31     parser crash on squash body"
    )
    for text in (three_spaces, wide_run):
        mapping, errors = RB.parse_exclusions(text)
        assert not errors
        assert mapping[orig] == (repl, "2026-07-31", "parser crash on squash body")


_CONFIG_ONLY_TYPE = {
    "changelog-sections": [
        {"type": "feat", "section": "Features"},
        {"type": "spdx", "section": "License"},
    ],
    "packages": {
        "plugins/superheroes": {
            "component": "superheroes",
        }
    },
}
_CONFIG_ONLY_PKG = _CONFIG_ONLY_TYPE["packages"]["plugins/superheroes"]

_HIDDEN_CONFIG_ONLY_TYPE = {
    "changelog-sections": [
        {"type": "feat", "section": "Features"},
        {"type": "spdx", "section": "License", "hidden": True},
    ],
    "packages": {
        "plugins/superheroes": {
            "component": "superheroes",
        }
    },
}
_HIDDEN_CONFIG_ONLY_PKG = _HIDDEN_CONFIG_ONLY_TYPE["packages"]["plugins/superheroes"]

_PKG_OVERRIDE_ROOT = {
    "changelog-sections": [
        {"type": "feat", "section": "Features"},
        {"type": "docs", "section": "Documentation", "hidden": True},
    ],
    "packages": {
        "plugins/superheroes": {
            "component": "superheroes",
            "changelog-sections": [
                {"type": "tooling", "section": "Tooling"},
                {"type": "docs", "section": "Docs"},
            ],
        }
    },
}
_PKG_OVERRIDE_PKG = _PKG_OVERRIDE_ROOT["packages"]["plugins/superheroes"]


def test_parseable_types_includes_config_only_type():
    parse_types = RB.parseable_types(_CONFIG_ONLY_TYPE, _CONFIG_ONLY_PKG)
    assert "spdx" in parse_types
    assert "spdx" not in RB.TYPES
    commits = [_c("sp000001", "spdx(superheroes): refresh SPDX headers")]
    assert RB.parse_subject(commits[0].subject, parse_types) is not None
    assert commits[0] in RB.floor_population(commits, parse_types)
    assert commits[0] in RB.completeness_population(
        commits, RB.releasing_types(_CONFIG_ONLY_TYPE, _CONFIG_ONLY_PKG), parse_types
    )


def test_hidden_config_only_type_parseable_not_releasing():
    parse_types = RB.parseable_types(_HIDDEN_CONFIG_ONLY_TYPE, _HIDDEN_CONFIG_ONLY_PKG)
    releasing = RB.releasing_types(_HIDDEN_CONFIG_ONLY_TYPE, _HIDDEN_CONFIG_ONLY_PKG)
    assert "spdx" in parse_types
    assert "spdx" not in releasing
    assert "spdx" not in RB.TYPES
    commits = [_c("sp000002", "spdx(superheroes): refresh SPDX headers")]
    assert RB.parse_subject(commits[0].subject, parse_types) is not None
    assert commits[0] in RB.floor_population(commits, parse_types)
    assert commits[0] not in RB.completeness_population(commits, releasing, parse_types)


def test_package_level_changelog_sections_override():
    root_parse = RB.parseable_types(_PKG_OVERRIDE_ROOT)
    root_releasing = RB.releasing_types(_PKG_OVERRIDE_ROOT)
    pkg_parse = RB.parseable_types(_PKG_OVERRIDE_ROOT, _PKG_OVERRIDE_PKG)
    pkg_releasing = RB.releasing_types(_PKG_OVERRIDE_ROOT, _PKG_OVERRIDE_PKG)

    assert "tooling" in pkg_parse
    assert "tooling" not in root_parse
    assert "docs" not in root_releasing
    assert "docs" in pkg_releasing
    assert "tooling" in pkg_releasing

    commits = [
        _c("tl000001", "tooling(superheroes): refresh lint config"),
        _c("dc000002", "docs(superheroes): clarify override"),
    ]
    assert RB.parse_subject(commits[0].subject, pkg_parse) is not None
    assert RB.parse_subject(commits[1].subject, pkg_parse) is not None
    assert commits[0] in RB.floor_population(commits, pkg_parse)
    assert commits[1] in RB.floor_population(commits, pkg_parse)
    assert commits[0] in RB.completeness_population(commits, pkg_releasing, pkg_parse)
    assert commits[1] in RB.completeness_population(commits, pkg_releasing, pkg_parse)


def test_belongs_to_package_zero_file():
    c = Commit(sha=_sha("zf000001"), subject="chore: empty", zero_file=True, touches_package=False)
    assert RB.belongs_to_package(c)


def test_changelog_presence_absent():
    presence, _ = RB.changelog_presence(_sha("xx000001"), "desc", "* nothing here")
    assert presence == "absent"


# --- E. Review round 1 regression tests ---


def test_extract_release_section_newest_first():
    """Mirror release-please output: proposed version first, older sections below."""
    changelog = (
        "## [0.23.1](https://github.com/zwrose/superheroes/compare)\n\n"
        "* **superheroes:** proposed bullet\n"
        "## [0.23.0](https://github.com/zwrose/superheroes/compare)\n\n"
        "* **superheroes:** older bullet\n"
        "## [0.22.0](https://github.com/zwrose/superheroes/compare)\n\n"
        "* **superheroes:** ancient bullet\n"
    )
    section = RB.extract_release_section(changelog, "0.23.1")
    assert "proposed bullet" in section
    assert "older bullet" not in section
    assert "ancient bullet" not in section


def test_extract_release_section_absent_version():
    changelog = (
        "## [0.23.0](https://github.com/zwrose/superheroes/compare)\n\n"
        "* **superheroes:** only older\n"
    )
    assert RB.extract_release_section(changelog, "0.23.1") == ""


def test_ack_replacement_only_in_prior_release_section_fails():
    """Replacement SHA in an older ## [version] section must not suppress failure."""
    dropped = _sha("drop0001")
    old_repl = _sha("oldrepl1")
    commits = [
        Commit(
            sha=dropped,
            subject="feat(superheroes): dropped commit",
            touches_package=True,
        )
    ]
    changelog = (
        "## [0.23.0](https://github.com/zwrose/superheroes/compare)\n\n"
        + _changelog_line("something else", "oth0001")
        + "\n## [0.22.0](https://github.com/zwrose/superheroes/compare)\n\n"
        + _changelog_line("shipped earlier", old_repl[:7], old_repl)
    )
    exclusions = {dropped: (old_repl, "2026-07-31", "parser crash")}
    release_pr = {"number": 100, "proposed_version": "0.23.0", "changelog_text": changelog}
    result = _evaluate(commits, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is False
    assert any("acknowledgement unsatisfied" in f for f in result.failures)


def test_prose_sha_mention_does_not_satisfy_acknowledgement():
    """A later bullet that mentions a SHA in prose must not suppress acknowledgement."""
    dropped = _sha("drop0002")
    repl = _sha("repl0002")
    mentioner = _sha("ment0002")
    commits = [
        Commit(sha=dropped, subject="feat(superheroes): dropped", touches_package=True),
    ]
    changelog = _release_changelog(
        "0.23.0",
        _changelog_line(
            f"context in https://github.com/zwrose/superheroes/commit/{repl}",
            mentioner[:7],
            mentioner,
        ),
    )
    exclusions = {dropped: (repl, "2026-07-31", "parser crash")}
    release_pr = {"number": 1, "proposed_version": "0.23.0", "changelog_text": changelog}
    result = _evaluate(commits, "0.22.0", release_pr, exclusions=exclusions)
    assert result.ok is False
    assert any("acknowledgement unsatisfied" in f for f in result.failures)


def test_deps_type_in_floor_population():
    commits = [_c("dp000001", "deps(superheroes): update dependency")]
    assert commits[0] in RB.floor_population(commits, _PARSE_TYPES)
    assert RB.completeness_population(commits, _RELEASING, _PARSE_TYPES) == [commits[0]]


def test_hidden_body_breaking_on_refactor_counts_for_floor():
    hidden = Commit(
        sha=_sha("hb000002"),
        subject="refactor(superheroes): remove legacy",
        body="BREAKING CHANGE: API removed",
        touches_package=True,
    )
    assert hidden in RB.floor_population([hidden], _PARSE_TYPES)
    assert hidden not in RB.completeness_population([hidden], _RELEASING, _PARSE_TYPES)


def test_release_shaped_title_without_manifest_not_cut():
    shaped = Commit(
        sha=_sha("rs000001"),
        subject="chore(superheroes): release 9.9.9",
        touches_package=True,
        touches_manifest=False,
    )
    result = _evaluate(
        [shaped],
        "0.23.0",
        release_pr=None,
    )
    assert result.ok is False
    assert any("no open release PR" in f for f in result.failures)


def test_gh_read_retry_wrapper_retries_transient_failure(monkeypatch):
    attempts = {"n": 0}

    def flaky_read(repo, path, ref):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("gh api failed (502)")
        return "ok"

    monkeypatch.setattr(RB, "_gh_read_file_content", flaky_read)
    assert RB._gh_read_file_content_retry("r/o", "p", "sha", retries=3, delay_s=0) == "ok"
    assert attempts["n"] == 2


def test_main_contents_reads_pin_pr_head_sha(tmp_path, monkeypatch):
    import shutil
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    pkg = repo / "plugins" / "superheroes"
    pkg.mkdir(parents=True)
    (pkg / "marker.txt").write_text("touch\n")
    (repo / ".release-please-manifest.json").write_text(
        json.dumps({"plugins/superheroes": "0.23.0"})
    )
    shutil.copy(_CONFIG_PATH, repo / "release-please-config.json")
    (repo / ".github").mkdir()
    (repo / ".github" / "release-exclusions.txt").write_text("# empty\n")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: bootstrap"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "tag", "superheroes-v0.23.0"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (pkg / "marker.txt").write_text("touch2\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix(superheroes): small fix"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_sha = head.stdout.strip()

    pinned_sha = "deadbeef" * 5
    content_calls: list[str] = []

    def fake_gh(args):
        if args[0].startswith("repos/example/superheroes/pulls"):
            return [
                {
                    "number": 99,
                    "head": {
                        "ref": "release-please--branches--main--components--superheroes",
                        "sha": pinned_sha,
                        "repo": {"full_name": "example/superheroes"},
                    },
                    "base": {"ref": "main"},
                }
            ]
        if "contents/" in args[0]:
            content_calls.append(args[0])
            if "manifest.json" in args[0]:
                return {
                    "content": __import__("base64")
                    .b64encode(json.dumps({"plugins/superheroes": "0.23.1"}).encode())
                    .decode()
                }
            body = _release_changelog(
                "0.23.1", _changelog_line("small fix", commit_sha[:7], commit_sha)
            )
            return {
                "content": __import__("base64").b64encode(body.encode()).decode()
            }
        raise AssertionError(f"unexpected gh api call: {args}")

    monkeypatch.setattr(RB, "_run_gh", fake_gh)
    exit_code = RB.main(
        [
            "--repo",
            "example/superheroes",
            "--repo-root",
            str(repo),
        ]
    )
    assert exit_code == 0
    assert len(content_calls) == 2
    for url in content_calls:
        assert f"ref={pinned_sha}" in url, f"contents read not pinned to PR head: {url}"


def test_find_release_pr_rejects_fork_pr():
    fork_pr = {
        "number": 1,
        "head": {
            "ref": "release-please--branches--main--components--superheroes",
            "sha": "abc",
            "repo": {"full_name": "attacker/fork"},
        },
        "base": {"ref": "main"},
    }

    def fake_gh(args):
        return [fork_pr]

    orig = RB._run_gh
    RB._run_gh = fake_gh
    try:
        assert RB._find_release_pr("zwrose/superheroes", "superheroes", retries=1) is None
    finally:
        RB._run_gh = orig


def test_empty_releasing_types_config_fails(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    pkg = repo / "plugins" / "superheroes"
    pkg.mkdir(parents=True)
    (pkg / "marker.txt").write_text("x\n")
    (repo / ".release-please-manifest.json").write_text(
        json.dumps({"plugins/superheroes": "0.23.0"})
    )
    cfg = {
        "packages": {
            "plugins/superheroes": {
                "component": "superheroes",
                "changelog-sections": [{"type": "docs", "hidden": True}],
            }
        }
    }
    (repo / "release-please-config.json").write_text(json.dumps(cfg))
    (repo / ".github").mkdir()
    (repo / ".github" / "release-exclusions.txt").write_text("# empty\n")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: bootstrap"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "tag", "superheroes-v0.23.0"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    exit_code = RB.main(
        [
            "--repo",
            "example/superheroes",
            "--repo-root",
            str(repo),
        ]
    )
    assert exit_code == 1


def test_notice_uses_github_warning_annotation(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    result = RB.EvaluateResult(ok=True, status="pass", notices=["soft signal"])
    RB._print_report(result)
    out = capsys.readouterr().out
    assert "::warning::soft signal" in out
    assert "notice: soft signal" not in out


def test_notice_plain_stdout_locally(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    result = RB.EvaluateResult(ok=True, status="pass", notices=["local hint"])
    RB._print_report(result)
    out = capsys.readouterr().out
    assert "notice: local hint" in out
    assert "::warning::" not in out


def test_main_integration_omitted_commit_fails(tmp_path, monkeypatch):
    import shutil
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    pkg = repo / "plugins" / "superheroes"
    pkg.mkdir(parents=True)
    (pkg / "marker.txt").write_text("touch\n")
    (repo / ".release-please-manifest.json").write_text(
        json.dumps({"plugins/superheroes": "0.23.0"})
    )
    shutil.copy(_CONFIG_PATH, repo / "release-please-config.json")
    (repo / ".github").mkdir()
    (repo / ".github" / "release-exclusions.txt").write_text("# empty\n")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: bootstrap"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "tag", "superheroes-v0.23.0"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (pkg / "marker.txt").write_text("touch2\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "deps(superheroes): bump pinned action hash"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    pinned_sha = "deadbeef" * 5

    def fake_gh(args):
        if args[0].startswith("repos/example/superheroes/pulls"):
            return [
                {
                    "number": 99,
                    "head": {
                        "ref": "release-please--branches--main--components--superheroes",
                        "sha": pinned_sha,
                        "repo": {"full_name": "example/superheroes"},
                    },
                    "base": {"ref": "main"},
                }
            ]
        if "contents/.release-please-manifest.json" in args[0]:
            assert f"ref={pinned_sha}" in args[0]
            return {
                "content": __import__("base64")
                .b64encode(json.dumps({"plugins/superheroes": "0.23.1"}).encode())
                .decode()
            }
        if "contents/plugins/superheroes/CHANGELOG.md" in args[0]:
            assert f"ref={pinned_sha}" in args[0]
            body = _release_changelog("0.23.1", "")
            return {
                "content": __import__("base64").b64encode(body.encode()).decode()
            }
        raise AssertionError(f"unexpected gh api call: {args}")

    monkeypatch.setattr(RB, "_run_gh", fake_gh)
    exit_code = RB.main(
        [
            "--repo",
            "example/superheroes",
            "--repo-root",
            str(repo),
        ]
    )
    assert exit_code == 1
