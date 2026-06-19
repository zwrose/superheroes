import json
import os
import textwrap

import reset


def test_plan_reset_no_lock_cleans():
    status = {"entries": [{"branch": "feat/x"}], "lock": None, "lockStale": False}
    assert reset.plan_reset(status)[0] == "clean"


def test_plan_reset_stale_lock_unlocks_then_cleans():
    status = {"entries": [], "lock": {"pid": 9}, "lockStale": True}
    assert reset.plan_reset(status)[0] == "unlock_then_clean"


def test_plan_reset_live_lock_gates():
    status = {"entries": [], "lock": {"pid": 9}, "lockStale": False}
    action, reason = reset.plan_reset(status)
    assert action == "gate" and "held" in reason


def test_plan_reset_unreadable_status_fails_closed():
    assert reset.plan_reset(None)[0] == "gate"


def test_verify_empty():
    assert reset.verify_empty({"entries": []}) is True
    assert reset.verify_empty({"entries": [{"branch": "x"}]}) is False
    assert reset.verify_empty(None) is False


def test_engine_json_round_trips_with_a_fake_engine(tmp_path):
    fake = tmp_path / "engine.py"
    fake.write_text(textwrap.dedent("""\
        import json, sys
        print(json.dumps({"ok": True, "command": "status",
                          "entries": [], "lock": None, "lockStale": False}))
    """))
    rc, obj = reset.engine_json(str(fake), ["status"])
    assert rc == 0 and obj["entries"] == []
