"""The advisor's vet reads the review record: the section's field names are the record's, and the retired checks stay gone.

The six fixtures are PRs as a vet sees them, each with the record the writer builds for it. They hold
no verdict. Run this module as a script to rewrite them from the accounts below.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_findings_schema  # noqa: E402
import review_record as rr  # noqa: E402
from test_review_record import GOOD_RUN, Fake, account, finding, reviewer  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(_LIB)
_SHOWRUNNER = os.path.join(_PLUGIN_ROOT, "skills", "showrunner")
_VET_RECEIPT = os.path.join(_SHOWRUNNER, "reference", "vet-receipt.md")
_FIXTURES = os.path.join(_HERE, "fixtures", "vet_record_checks")
_HEADING = "## The review record checks"
_FIXED_WRITTEN_AT = "2026-01-01T00:00:00Z"

_RECORD_FIELDS = ("finalCommit.sha", "finalCommit.source", "ci.state", "ci.sha", "ci.source", "missingReviews",
                  "goAhead", "parked", "findings", "title", "body", "consequence", "outcome", "reason",
                  "leftForOwner", "status", "whatIsMissing")
_ROW_NON_FIELDS = frozenset({"read", "green", "craft", "ruling"})
_TOKEN = re.compile(r"^[a-z][A-Za-z]*(\.[A-Za-z]+)*$")
_ENTRY_KEYS = {"goAhead": "missingReviews", "title": "findings", "body": "findings", "consequence": "findings",
               "outcome": "findings", "reason": "findings"}
_OUTCOMES_IN_SECTION = ("craft", "ruling", "left-for-owner", "fixed", "shown-wrong")
_RETIRED = ("certified-loop", "certified loop", "seat-provenance parity")

_FIXTURE_NAMES = ("pr-a", "pr-b", "pr-c", "pr-d", "pr-e", "pr-f")
_WROTE = "a" * 40
_MOVED = "b" * 40
_HEAD = "c" * 40


def _run(head):
    return ({**GOOD_RUN, "viewHeadSha": head}, None)


def _readers(head, runs):
    fake = Fake(meta={"head": head, "body": "", "issues": []}, runs=runs)
    return fake.readers()


def _pr(head, names_record=True, accepting=()):
    return {"number": 7, "head": head, "ciOnHead": "green", "buildRecordNamesRecord": names_record,
            "ownerHalf": {"whatWeAreAccepting": list(accepting)}}


def _one(head, findings, extra_reviewers=()):
    acct = account(finalCommit=head, laneReason="a plain reason", reviewers=[reviewer(), *extra_reviewers],
                   findings=findings)
    return acct, _readers(head, {"/run/code-reviewer": _run(head)})


def _scenarios():
    """name -> (account, readers, PR as the vet sees it); the account is None where no record exists."""
    out = {"pr-a": (None, None, _pr(_HEAD, names_record=False))}
    fixed = finding("code-null-guard", title="A null guard was missing", outcome="fixed", reason="fixed in 1a2b3c4")
    acct, rd = _one(_WROTE, [fixed])
    out["pr-b"] = (acct, rd, _pr(_MOVED))
    craft = finding("code-retry-double-charge", title="Retry can charge twice",
                    consequence="a customer can be charged twice when the retry fires",
                    outcome="craft", reason="style preference")
    acct, rd = _one(_HEAD, [craft])
    out["pr-c"] = (acct, rd, _pr(_HEAD))
    security = reviewer("security-reviewer", ran=False, runDir="")
    acct, rd = _one(_HEAD, [fixed], extra_reviewers=[security])
    acct["goAheads"] = []
    out["pr-d"] = (acct, rd, _pr(_HEAD))
    left = finding("code-retry-window", title="The retry window is too long",
                   consequence="a customer waits minutes before a failed payment is retried",
                   outcome="left-for-owner", reason="needs the owner's call on the retry window")
    acct, rd = _one(_HEAD, [fixed, left])
    out["pr-e"] = (acct, rd, _pr(_HEAD, accepting=[f"{left['id']}: {left['title']}"]))
    drops = finding("code-account-delete-invoices", title="Deleting an account drops its invoices",
                    body="Invoices are deleted along with the account and there is no way to restore them.",
                    consequence=None, outcome="craft", reason="minor cleanup")
    acct, rd = _one(_HEAD, [drops])
    out["pr-f"] = (acct, rd, _pr(_HEAD))
    return out


def _rebuild(name):
    acct, rd, _ = _scenarios()[name]
    if acct is None:
        return None
    return {**rr.build_record(acct, rd), "writtenAt": _FIXED_WRITTEN_AT}


def _fixture(name):
    with open(os.path.join(_FIXTURES, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _write_fixtures():
    os.makedirs(_FIXTURES, exist_ok=True)
    for name in _FIXTURE_NAMES:
        body = {"name": name, "pr": _scenarios()[name][2], "record": _rebuild(name)}
        with open(os.path.join(_FIXTURES, f"{name}.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(body, indent=2, sort_keys=True) + "\n")


def _without_written_at(record):
    return {k: v for k, v in record.items() if k != "writtenAt"}


def _section():
    with open(_VET_RECEIPT, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    assert _HEADING in lines, f"vet-receipt.md has no heading {_HEADING!r}"
    start = lines.index(_HEADING)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _resolves(record, path):
    if path in _ENTRY_KEYS:
        entries = record.get(_ENTRY_KEYS[path])
        return isinstance(entries, list) and any(isinstance(e, dict) and path in e for e in entries)
    node = record
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _retired_hits(texts):
    return [(rel, needle) for rel, text in sorted(texts.items()) for needle in _RETIRED if needle in text.lower()]


def _showrunner_texts():
    texts = {}
    for base, _dirs, files in os.walk(_SHOWRUNNER):
        for name in files:
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as fh:
                texts[os.path.relpath(path, _SHOWRUNNER)] = fh.read()
    return texts


def test_fixture_records_match_the_writer():
    # axis: a stored fixture drifting from the record the writer builds for the same account
    for name in _FIXTURE_NAMES:
        stored = _fixture(name)["record"]
        if name == "pr-a":
            assert stored is None
            continue
        assert _without_written_at(stored) == _without_written_at(_rebuild(name)), name


def test_fixtures_carry_the_facts_they_stand_for():
    # axis: a fixture that no longer holds the fact its row of the section is graded against
    f = {name: _fixture(name) for name in _FIXTURE_NAMES}
    b = f["pr-b"]
    assert b["record"]["finalCommit"]["sha"] != b["pr"]["head"] and b["record"]["ci"]["state"] == "green"
    c = f["pr-c"]["record"]
    assert any(x["consequence"] is not None and x["outcome"] == "craft" for x in c["findings"])
    assert c["status"] == "reviewed"
    d = f["pr-d"]["record"]
    assert any(m["goAhead"] is None for m in d["missingReviews"]) and d["parked"] is True
    e = f["pr-e"]
    assert e["record"]["finalCommit"]["sha"] == e["pr"]["head"] and e["record"]["ci"]["state"] == "green"
    assert e["record"]["parked"] is False and e["record"]["leftForOwner"]
    accepting = e["pr"]["ownerHalf"]["whatWeAreAccepting"]
    assert all(any(n in s for s in accepting) for n in e["record"]["leftForOwner"])
    assert e["record"]["status"] == "not-reviewed"
    g = f["pr-f"]["record"]
    assert any(x["consequence"] is None and x["outcome"] == "craft" for x in g["findings"])
    assert g["status"] == "reviewed"


def test_record_checks_section_names_real_record_fields():
    # axis: a row of the section naming a field the record does not have
    section = _section()
    record = _rebuild("pr-d")
    for path in _RECORD_FIELDS:
        assert f"`{path}`" in section, f"the section does not name `{path}` in backticks"
        assert _resolves(record, path), f"`{path}` is not a field of a record the writer builds"
    rows = [line for line in section.split("\n") if line.startswith("| **")]
    assert rows, "the section has no table body rows"
    tokens = {t for row in rows for t in re.findall(r"`([^`]+)`", row) if _TOKEN.match(t)} - _ROW_NON_FIELDS
    for token in sorted(tokens):
        assert _resolves(record, token), f"a row names `{token}`, which is not a field of a record the writer builds"


def test_record_checks_section_outcomes_are_the_schema_spellings():
    # axis: an outcome spelled in the section that the findings schema does not have
    section = _section()
    for outcome in _OUTCOMES_IN_SECTION:
        assert f"`{outcome}`" in section, f"the section does not name `{outcome}`"
        assert outcome in review_findings_schema.OUTCOMES, outcome


def test_retired_vet_checks_absent_from_showrunner_skill():
    # axis: a retired vet check name returning anywhere under skills/showrunner/
    texts = _showrunner_texts()
    assert texts, "no files found under skills/showrunner/"
    assert _retired_hits(texts) == []


def test_negative_retired_name_is_caught():
    assert _retired_hits({"x.md": "the Certified-Loop check"})


def test_negative_unknown_field_does_not_resolve():
    record = _rebuild("pr-d")
    assert not _resolves(record, "finalCommit.shaa")
    assert not _resolves(record, "missingReview")
    assert not _resolves({"missingReviews": []}, "goAhead")


if __name__ == "__main__":
    _write_fixtures()
