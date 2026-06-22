# plugins/superheroes/lib/tests/test_recover_front_half.py
import recover

OK_WORLD = {"store_ok": True, "current_content_hash": None, "pr": None, "seeded_empty": True}


def test_front_half_none_hash_no_branch_continues():
    ckpt = {"workItem": "wi", "lastGoodStep": "2"}  # no branch -> front-half
    assert recover.reconcile(ckpt, OK_WORLD)["action"] == "continue"


def test_back_half_none_hash_with_branch_still_gates():
    ckpt = {"workItem": "wi", "branch": "superheroes/wi-abc123", "lastGoodStep": "5"}
    assert recover.reconcile(ckpt, OK_WORLD)["action"] == "gate"
