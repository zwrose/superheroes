"""An uncited tagged parameterized test must block removal clearance."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import audits  # noqa: E402


def test_uncited_tagged_each_test_blocks_removal_clearance():
    # axis: removing a cited wording pin together with an uncited tagged test must refuse discharge.
    path = "tests/example.test.ts"
    source = (
        "test('wording', () => expect(formatError()).toBe('Exact wording'));\n"
        "test.each`\n"
        "  input | expected\n"
        "  ${1}  | ${2}\n"
        "`('doubles $input', ({ input, expected }) => {\n"
        "  expect(double(input)).toBe(expected);\n"
        "});\n"
    )
    lines = source.splitlines()
    delta = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        "+++ /dev/null",
        f"@@ -1,{len(lines)} +0,0 @@",
    ] + ["-" + line for line in lines]
    target = {
        "id": "t0", "file": path, "line": 1, "title": "Remove wording pin",
        "dimension": "Test", "taxonomy": "wording-pin",
        "body": "The first test pins error wording that is not a contract.",
        "auditorVendor": "codex", "fixerDelta": delta,
        "fixerRemoval": {"files": [{
            "path": path, "removed": [[1, len(lines)]], "added": False,
            "testOpenings": audits.test_openings(path, source),
        }]},
        # Freshness is fixed here to isolate recognition of uncited test openings.
        "citationFresh": True,
    }
    checks = {
        name: {"answer": "yes", "why": "The auditor accepted this check."}
        for name in audits.CHECK_NAMES
    }
    checks["testWouldFail"]["answer"] = audits.WORTHLESS_TEST_REMOVED
    result = {
        "id": "t0", "ruling": "discharged",
        "reason": "The cited wording test was removed.", "checks": checks,
    }
    outcome = audits.apply_audit_results(
        [target], [result], collection_manifest={"t0": "codex"}
    )
    assert outcome["discharged"] == []
    assert outcome["notDischarged"] == ["t0"]
    assert outcome["testRemovalRefused"] == ["t0"]
