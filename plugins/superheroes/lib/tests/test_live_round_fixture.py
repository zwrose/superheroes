import json
from pathlib import Path


def test_live_wf17_round6_fixture_contains_modern_severityless_findings():
    path = Path(__file__).parent / "fixtures" / "live-round-records-wf17d83964-review-code.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    round6 = next(r for r in records if r.get("round") == 6)
    malformed = [
        f for f in round6.get("findings", [])
        if f.get("file") and f.get("line") and f.get("severity") is None and f.get("title") is None
    ]
    assert len(malformed) >= 3
