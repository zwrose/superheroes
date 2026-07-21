import guardian_report as gr


def _sample_bundle():
    return {
        "committed": "uncommitted",
        "surfaced": [{"id": "a", "lens": "fixture"}],
        "ledgerStatus": [{"id": "b", "lens": "fixture", "line": "filed as #9, verification pending"}],
        "vitalsDelta": {},
        "funnel": {
            "raised": {"fixture": 2},
            "killedByDrift": [{"id": "c", "lens": "fixture", "reason": "no-drift"}],
            "killedByLedger": [{"id": "d", "lens": "fixture", "disposition": "accepted"}],
            "degradedLenses": [],
        },
    }


def _sample_dispositions():
    return [
        {
            "id": "a",
            "verdict": "validated",
            "consequence": "Refactor the module.",
            "receipt": "complexity=120",
            "effort": "2 days",
            "ledgerJoin": "a",
        },
        {"id": "x", "verdict": "rejected"},
    ]


def test_render_contains_standing_instructions():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_STANDING_INSTRUCTIONS in md
    assert "Verify each finding against its receipt" in md


def test_render_validated_finding_fields():
    md = gr.render(_sample_bundle(), _sample_dispositions(), {"byId": {}})
    assert gr.HEADER_VALIDATED in md
    assert "Refactor the module." in md
    assert "complexity=120" in md
    assert "2 days" in md


def test_render_filed_status_line():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_TRACKED in md
    assert "filed as #9, verification pending" in md


def test_render_vitals_section():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_VITALS in md


def test_render_funnel_buckets_use_constants():
    md = gr.render(_sample_bundle(), _sample_dispositions(), {"byId": {}})
    assert gr.HEADER_FUNNEL in md
    assert gr.FUNNEL_RAISED in md
    assert gr.FUNNEL_KILLED_DRIFT in md
    assert gr.FUNNEL_KILLED_LEDGER in md
    assert gr.FUNNEL_DEGRADED in md
    assert gr.FUNNEL_REJECTED in md
    assert gr.FUNNEL_VALIDATED in md
    assert "fixture: 2" in md
    assert "no-drift" in md
    assert "accepted" in md
