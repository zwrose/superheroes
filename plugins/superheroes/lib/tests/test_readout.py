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


def test_readout_post_guard_requires_ctx_or_reason(tmp_path, monkeypatch):
    # Defensive guard: a caller passing neither --ctx nor --reason must exit non-zero
    # with a clear JSON error, not silently record an empty hand-back.
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode != 0, "must exit non-zero when neither --ctx nor --reason given"
    out = json.loads(r.stdout)
    assert "requires --ctx or --reason" in out.get("error", "")


def test_readout_post_malformed_ctx_exits_nonzero(tmp_path, monkeypatch):
    # Fail-closed guard: a malformed --ctx JSON must exit non-zero with a clear error,
    # not silently coerce to {} and record an empty hand-back (mirrors required-args guard).
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi", "--ctx", "not-valid-json{{{"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode != 0, "must exit non-zero when --ctx is malformed JSON"
    out = json.loads(r.stdout)
    assert "malformed --ctx JSON" in out.get("error", "")
    assert out.get("posted") is False
    assert out.get("recorded") is False


def test_readout_post_builds_structured_ctx(tmp_path, monkeypatch):
    # FR-6/FR-7 teeth: --ctx must build (and durably record) a hand-back carrying the PR link,
    # built-vs-asked, the spot-check list, the "never merges" statement, AND the FR-7 integration note.
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))  # isolate the store (never the real one)
    sys.path.insert(0, LIB_R)
    import control_plane
    ctx = {"pr_url": "https://x/pr/7", "ci_status": "green — all required checks pass",
           "built_vs_acceptance": "all FRs met", "smoke": ["confirm catch-up", "review the diff"],
           "integration_note": "the final head carries post-review base integration"}
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi", "--ctx", json.dumps(ctx)],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out.get("recorded") is True or out.get("posted") is True
    # no --pr -> recorded to the store; read the structured hand-back back and assert the FR-6/FR-7 elements
    body = open(control_plane.paths(str(tmp_path), "wi")["resume_brief"]).read()
    assert "https://x/pr/7" in body                          # FR-6: PR link
    assert "all FRs met" in body                             # FR-6: built-vs-asked
    assert "confirm catch-up" in body                        # FR-6: spot-check list
    assert "Merge is yours" in body                          # FR-6: never-merges statement
    assert "post-review base integration" in body            # FR-7: integration note


def test_readout_post_discloses_real_permission_denials(tmp_path, monkeypatch):
    # UFR-3 end-to-end: readout_post reads the RUN'S OWN events.jsonl (not a caller-supplied stub)
    # and folds any permission_denied events into the posted hand-back — a build step or reviewer
    # probe the 15-min timeout denied must be visible, never silently absorbed.
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    sys.path.insert(0, LIB_R)
    import control_plane, journal
    paths = control_plane.paths(str(tmp_path), "wi-denied")
    journal.append(paths["events"], "permission_denied", step="build:task-3",
                   detail={"command": "python3 -c x"})
    journal.append(paths["events"], "permission_denied", step="review:security-reviewer",
                   detail="probe denied")
    ctx = {"pr_url": "https://x/pr/9", "ci_status": "green"}
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi-denied", "--ctx", json.dumps(ctx)],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode == 0, r.stderr
    body = open(paths["resume_brief"]).read()
    assert "Permission denials" in body
    assert "build:task-3" in body
    assert "review:security-reviewer" in body


def test_readout_post_caller_supplied_permission_denials_wins(tmp_path, monkeypatch):
    # An explicit ctx.permissionDenials (test/override input) must not be silently overwritten by
    # the real journal read — the caller-supplied value wins.
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    sys.path.insert(0, LIB_R)
    import control_plane, journal
    paths = control_plane.paths(str(tmp_path), "wi-override")
    journal.append(paths["events"], "permission_denied", step="build:real-step")
    ctx = {"pr_url": "https://x/pr/10", "ci_status": "green",
           "permissionDenials": [{"step": "explicit-override"}]}
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi-override", "--ctx", json.dumps(ctx)],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode == 0, r.stderr
    body = open(paths["resume_brief"]).read()
    assert "explicit-override" in body
    assert "build:real-step" not in body


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
