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


def test_build_readout_scrubs_pr_url_secret():
    # Pattern 3: key=value query/form params (token=...)
    secret = "supersecretvalue123"
    body = readout.build_readout({
        "pr_url": "http://example.com/pr/1?token=%s" % secret,
        "ci_status": "green",
    })
    assert secret not in body
    assert "token=[REDACTED]" in body


def test_build_readout_scrubs_dev_url_secret():
    # URI userinfo credentials: scheme://user:pass@host
    secret = "hunter2pass"
    body = readout.build_readout({
        "dev_url": "https://user:%s@dev.example.com" % secret,
        "ci_status": "green",
    })
    assert secret not in body
    assert "[REDACTED]@dev.example.com" in body


def test_build_readout_scrubs_ci_status_secret():
    # Pattern 1b: mid-line x-api-key (key: value form)
    secret = "sk-live-abc123def456"
    body = readout.build_readout({
        "ci_status": "x-api-key: %s" % secret,
    })
    assert secret not in body
    assert "x-api-key: [REDACTED]" in body


def test_build_readout_scrubs_smoke_item_secret():
    # Pattern 2: Bearer tokens
    secret = "abcdef0123456789"
    body = readout.build_readout({
        "ci_status": "green",
        "smoke": ["verify Authorization: Bearer %s" % secret],
    })
    assert secret not in body
    assert "Bearer [REDACTED]" in body


def test_build_readout_scrubs_permission_denial_step_secret():
    # Pattern 1b: mid-line x-api-key (key: value form)
    secret = "plantedsecret123"
    body = readout.build_readout({
        "ci_status": "green",
        "permissionDenials": [{"step": "deploy x-api-key: %s" % secret, "detail": ""}],
    })
    assert secret not in body
    assert "x-api-key: [REDACTED]" in body


def test_build_readout_exempt_courier_retry_count_renders():
    body = readout.build_readout({
        "ci_status": "green",
        "courierRetries": {"retried": 5},
    })
    assert "5 retried" in body


def test_build_readout_ordinary_url_unchanged():
    url = "http://x/pr/1"
    body = readout.build_readout({"pr_url": url, "ci_status": "green"})
    assert url in body


def test_build_readout_smoke_coerces_non_string_item():
    # Pattern 4: colon-separator (dict str) form after coercion of a non-string smoke item
    secret = "supersecretvalue123"
    body = readout.build_readout({
        "ci_status": "green",
        "smoke": [{"token": secret}],
    })
    assert secret not in body
    assert "'token': [REDACTED]" in body


def test_build_readout_skips_non_dict_permission_denial():
    body = readout.build_readout({
        "ci_status": "green",
        "permissionDenials": ["not-a-dict", {"step": "ok", "detail": ""}],
    })
    assert "not-a-dict" not in body
    assert "**ok**" in body


def test_build_readout_permission_denial_unknown_step_default_scrubbed():
    body = readout.build_readout({
        "ci_status": "green",
        "permissionDenials": [{"detail": "timed out"}],
    })
    assert "**unknown step**" in body
    assert "timed out" in body


def test_build_readout_permission_denial_detail_coerces_non_string():
    # Pattern 4: colon-separator (dict str) form after coercion of a non-string detail
    secret = "supersecretvalue123"
    body = readout.build_readout({
        "ci_status": "green",
        "permissionDenials": [{"step": "build", "detail": {"token": secret}}],
    })
    assert secret not in body
    assert "'token': [REDACTED]" in body


def test_build_readout_egress_fails_closed_when_scrubber_raises(monkeypatch):
    monkeypatch.setattr(readout.pr_comment, "scrub",
                        lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    body = readout.build_readout({
        "pr_url": "http://example.com/pr/1?token=leakysecret123",
        "ci_status": "green",
    })
    assert "leakysecret123" not in body
    assert "omitted" in body
