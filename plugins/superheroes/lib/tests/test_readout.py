import json, os, subprocess, sys
import readout

LIB_R = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_scrub_uses_test_pilot_when_present():
    # pr_comment is a same-tree sibling now — scrub calls it directly (no resolution).
    scrubbed, ok = readout.scrub("Authorization: Bearer abcdef0123456789")
    assert ok is True and "abcdef0123456789" not in scrubbed


def test_scrub_fails_closed_when_scrubber_raises(monkeypatch):
    # Equivalence note: the old "scrubber absent / subprocess non-zero / subprocess raises"
    # tests are collapsed into this one. In one tree pr_comment can't be absent and there is
    # no subprocess; the SAME fail-closed posture (scrub error -> DROP, never leak) is now
    # exercised by making pr_comment.scrub itself raise.
    monkeypatch.setattr(readout.pr_comment, "scrub",
                        lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    scrubbed, ok = readout.scrub("Authorization: Bearer secret")
    assert ok is False and "secret" not in scrubbed and "omitted" in scrubbed


def test_build_readout_has_merge_is_yours_and_ci_line():
    body = readout.build_readout({"pr_url": "http://x/pr/1", "ci_status": "CI not detected"})
    assert "Merge is yours" in body
    assert "CI not detected" in body
    assert "http://x/pr/1" in body


def test_build_readout_scrubs_every_freetext_field():
    body = readout.build_readout({
        "ci_status": "red",
        "raw_ci_excerpt": "token=supersecretvalue123",
        "test_results": "ran with Authorization: Bearer leakybeaker0000",
        "built_vs_acceptance": "set password=hunter2hunter2 during setup",
    })
    assert "supersecretvalue123" not in body   # raw_ci_excerpt scrubbed
    assert "leakybeaker0000" not in body        # test_results scrubbed
    assert "hunter2hunter2" not in body          # built_vs_acceptance scrubbed


def test_build_readout_renders_courier_retry_pressure():
    # B5 (#315): a run with courier retries surfaces a "Couriers: N retried" line.
    body = readout.build_readout({
        "ci_status": "green",
        "courierRetries": {"retried": 3, "byLabel": {"read startup state": 2, "post readout": 1}},
    })
    assert "Couriers" in body and "3 retried" in body


def test_build_readout_omits_courier_line_when_no_retries():
    body = readout.build_readout({"ci_status": "green", "courierRetries": {"retried": 0, "byLabel": {}}})
    assert "Couriers" not in body
    # and absent entirely (byte-compatible with a clean run)
    assert "Couriers" not in readout.build_readout({"ci_status": "green"})
