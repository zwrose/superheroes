import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LIB = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "live-round-records-wf17d83964-review-code.json"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CB = _load("circuit_breaker")
LS = _load("loop_synthesis")
PT = _load("panel_tally")
BLOCKING = {"Critical", "Important"}

ROUND6_SUMMARIES = {
    ("plugins/superheroes/skills/acceptance/SKILL.md", 39): (
        "SKILL.md nesting-refusal path is buried under acceptance setup",
        "Important",
    ),
    ("plugins/superheroes/lib/acceptance_deps.py", 40): (
        "orphan-record worktree directory is reused without validation",
        "Important",
    ),
    ("plugins/superheroes/lib/acceptance_run.py", 158): (
        "PIPELINE_PHASES skips review-code so acceptance never exercises the review loop",
        "Critical",
    ),
}


def _records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _round6():
    return next(r for r in _records() if r.get("round") == 6)


def _round6_modern_dimension_results():
    dims = json.loads(json.dumps(_round6()["dimensions"]))
    raw_findings = []
    for dim in dims.values():
        for finding in dim.get("findings") or []:
            key = (finding.get("file"), finding.get("line"))
            if key not in ROUND6_SUMMARIES:
                continue
            assert finding.get("title") is None
            assert finding.get("severity") is None
            finding["summary"] = ROUND6_SUMMARIES[key][0]
            raw_findings.append(finding)
    assert len(raw_findings) == 3
    return dims, raw_findings


def _verdicts(raw_findings):
    out = []
    for finding in raw_findings:
        summary, severity = ROUND6_SUMMARIES[(finding["file"], finding["line"])]
        out.append({
            "id": f"{finding['file']}::{CB.normalize_title(summary)}",
            "action": "keep",
            "reason": "replayed live synthesis verdict",
            "severity": severity,
        })
    return out


def _assert_replay_output(out):
    survivors = out["findings"]
    assert len(survivors) == 3
    assert out["drops"] == []
    assert sorted(f.get("severity") for f in survivors) == ["Critical", "Important", "Important"]
    assert all(f.get("severity") for f in survivors)
    assert sum(1 for f in survivors if f.get("severity") in BLOCKING) == 3


def test_live_wf17_round6_fixture_contains_modern_severityless_findings():
    round6 = _round6()
    malformed = [
        f for f in round6.get("findings", [])
        if f.get("file") and f.get("line") and f.get("severity") is None and f.get("title") is None
    ]
    assert len(malformed) >= 3


def test_live_wf17_round6_replays_synthesis_as_three_blockers_python_twin():
    round_findings, raw_findings = _round6_modern_dimension_results()
    identities = [CB.finding_identity(f) for f in raw_findings]
    assert all(identity and not identity.endswith("::") for identity in identities)

    merged = PT.compile_dimension_results(round_findings)
    out = LS.consume(merged, _verdicts(raw_findings))

    _assert_replay_output(out)


def test_live_wf17_round6_replays_synthesis_as_three_blockers_js_twin():
    round_findings, raw_findings = _round6_modern_dimension_results()
    verdicts = _verdicts(raw_findings)
    script = """
const fs = require('fs')
const payload = JSON.parse(fs.readFileSync(0, 'utf8'))
const panelTally = require('./plugins/superheroes/lib/panel_tally.js')
const loopSynthesis = require('./plugins/superheroes/lib/loop_synthesis.js')
const circuitBreaker = require('./plugins/superheroes/lib/circuit_breaker.js')
const merged = panelTally.compileDimensionResults(payload.roundFindings)
const out = loopSynthesis.consume(merged, payload.verdicts)
const identities = payload.rawFindings.map((f) => circuitBreaker.findingIdentity(f))
process.stdout.write(JSON.stringify({ out, identities }))
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        input=json.dumps({
            "roundFindings": round_findings,
            "rawFindings": raw_findings,
            "verdicts": verdicts,
        }),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    replay = json.loads(result.stdout)

    assert all(identity and not identity.endswith("::") for identity in replay["identities"])
    _assert_replay_output(replay["out"])
