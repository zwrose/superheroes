"""#1272 layer 4a: the orders manifest names each panel seat's delivery channel."""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load_round_driver():
    spec = importlib.util.spec_from_file_location(
        "round_driver", os.path.join(_LIB, "round_driver.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_l4a_manifest_emits_channel_for_claude_and_codex_panel_seats(tmp_path):
    RD = _load_round_driver()
    spec = importlib.util.spec_from_file_location(
        "round_records", os.path.join(_LIB, "round_records.py"))
    RR = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RR)

    DIFF = "diff --git a/a.py b/a.py\n"
    session_dir = str(tmp_path / "manifest-channel")
    os.makedirs(session_dir, exist_ok=True)
    seat_map = {
        "seats": {
            RD.DIMENSIONS[0]: {"vendor": "codex", "model": "gpt", "engine": "codex"},
            RD.DIMENSIONS[1]: {"vendor": "claude", "model": "sonnet", "engine": "claude"},
        }
    }
    out = RD.cmd_next(session_dir, {
        "leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
        "fixerVendor": "claude", "verifyCommand": "none", "seatMap": seat_map,
    })
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    pend = state["pending"]
    manifest_path = RD._orders_manifest_path(
        session_dir, pend["round"], RD.P_PANEL, pend["attempt"])
    manifest, err = RR.read_json(manifest_path)
    assert err is None, err
    channels = {}
    for entry in manifest["seats"].values():
        channels[entry["seat"]] = entry.get("channel")
    assert channels[RD.DIMENSIONS[0]] == RD.CHANNEL_STDOUT
    assert channels[RD.DIMENSIONS[1]] == RD.CHANNEL_FILE
