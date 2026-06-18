import os

import band_lib
import readout

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_SCRUB = os.path.join(_REPO, "plugins", "test-pilot", "lib", "pr_comment.py")


def test_scrub_uses_test_pilot_when_present(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target", lambda *a, **k: _SCRUB)
    scrubbed, ok = readout.scrub("Authorization: Bearer abcdef0123456789")
    assert ok is True and "abcdef0123456789" not in scrubbed


def test_scrub_fails_closed_when_scrubber_absent(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target", lambda *a, **k: None)
    scrubbed, ok = readout.scrub("Authorization: Bearer secret")
    assert ok is False and "secret" not in scrubbed and "omitted" in scrubbed


def test_build_readout_has_merge_is_yours_and_ci_line():
    body = readout.build_readout({"pr_url": "http://x/pr/1", "ci_status": "CI not detected"})
    assert "Merge is yours" in body
    assert "CI not detected" in body
    assert "http://x/pr/1" in body


def test_build_readout_scrubs_every_freetext_field(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target", lambda *a, **k: _SCRUB)
    body = readout.build_readout({
        "ci_status": "red",
        "raw_ci_excerpt": "token=supersecretvalue123",
        "test_results": "ran with Authorization: Bearer leakybeaker0000",
        "built_vs_acceptance": "set password=hunter2hunter2 during setup",
    })
    assert "supersecretvalue123" not in body   # raw_ci_excerpt scrubbed
    assert "leakybeaker0000" not in body        # test_results scrubbed
    assert "hunter2hunter2" not in body          # built_vs_acceptance scrubbed
