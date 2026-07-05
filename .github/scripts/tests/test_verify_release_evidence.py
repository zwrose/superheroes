import importlib.util, json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "verify_release_evidence", os.path.join(_HERE, "..", "verify_release_evidence.py"))
V = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(V)

HEAD = "a" * 40
BUNDLE = "b" * 64  # a plausible sha256 of the released bundle


def _comment(instruments, release_sha=HEAD):
    obj = {"schemaVersion": 1, "releaseSha": release_sha, "instruments": instruments}
    return "some preamble\n```release-eval-evidence\n" + json.dumps(obj) + "\n```\nfooter"


# --- fenced-block parsing / entry pooling -------------------------------------------------

def test_collect_entries_extracts_fenced_block():
    e = V.collect_entries([_comment([{"instrument": "benchmark", "verdict": "pass"}])])
    assert e[0]["instrument"] == "benchmark"

def test_entries_inherit_block_release_sha():
    e = V.collect_entries([_comment([{"instrument": "benchmark", "verdict": "pass"}], HEAD)])
    assert e[0]["releaseSha"] == HEAD

def test_entry_level_release_sha_kept_over_block():
    c = _comment([{"instrument": "benchmark", "verdict": "pass", "releaseSha": "z" * 40}], HEAD)
    e = V.collect_entries([c])
    assert e[0]["releaseSha"] == "z" * 40

def test_collect_entries_pools_across_comments():
    a = _comment([{"instrument": "acceptance", "verdict": "pass", "bundleSha256": BUNDLE}])
    b = _comment([{"instrument": "benchmark", "verdict": "pass"}])
    e = V.collect_entries([a, b])
    kinds = {x["instrument"] for x in e}
    assert kinds == {"acceptance", "benchmark"}

def test_collect_entries_skips_malformed_block():
    bad = "```release-eval-evidence\n{not json,,,}\n```"
    good = _comment([{"instrument": "benchmark", "verdict": "pass"}])
    assert len(V.collect_entries([bad, good])) == 1
    assert V.collect_entries([bad]) == []

def test_collect_entries_ignores_non_evidence_fences():
    assert V.collect_entries(["```json\n{\"instrument\":\"benchmark\"}\n```"]) == []

def test_collect_entries_empty():
    assert V.collect_entries([]) == []
    assert V.collect_entries([None, 5]) == []


# --- per-instrument verification ----------------------------------------------------------

def test_benchmark_pass_bound_to_head_verifies():
    e = [{"instrument": "benchmark", "verdict": "pass", "releaseSha": HEAD}]
    ok, _ = V.verify_instrument("benchmark", e, HEAD, BUNDLE)
    assert ok

def test_benchmark_bound_to_other_sha_fails():
    e = [{"instrument": "benchmark", "verdict": "pass", "releaseSha": "c" * 40}]
    ok, reason = V.verify_instrument("benchmark", e, HEAD, BUNDLE)
    assert not ok and "bound to" in reason

def test_benchmark_missing_evidence_fails():
    ok, reason = V.verify_instrument("benchmark", [], HEAD, BUNDLE)
    assert not ok and "no benchmark evidence" in reason

def test_acceptance_requires_matching_bundle_sha():
    e = [{"instrument": "acceptance", "verdict": "pass", "bundleSha256": BUNDLE, "releaseSha": HEAD}]
    ok, _ = V.verify_instrument("acceptance", e, HEAD, BUNDLE)
    assert ok

def test_acceptance_wrong_bundle_sha_fails():
    e = [{"instrument": "acceptance", "verdict": "pass", "bundleSha256": "d" * 64, "releaseSha": HEAD}]
    ok, reason = V.verify_instrument("acceptance", e, HEAD, BUNDLE)
    assert not ok and "does not match" in reason

def test_acceptance_unreadable_head_bundle_fails():
    e = [{"instrument": "acceptance", "verdict": "pass", "bundleSha256": BUNDLE, "releaseSha": HEAD}]
    ok, reason = V.verify_instrument("acceptance", e, HEAD, None)
    assert not ok and "could not read" in reason

def test_verdict_not_pass_fails():
    e = [{"instrument": "benchmark", "verdict": "fail", "releaseSha": HEAD}]
    ok, reason = V.verify_instrument("benchmark", e, HEAD, BUNDLE)
    assert not ok and "not \"pass\"" in reason

def test_a_valid_entry_wins_over_a_stale_one():
    # a stale entry (old release SHA) plus a fresh valid one -> satisfied
    e = [
        {"instrument": "benchmark", "verdict": "pass", "releaseSha": "old" + "0" * 37},
        {"instrument": "benchmark", "verdict": "pass", "releaseSha": HEAD},
    ]
    ok, _ = V.verify_instrument("benchmark", e, HEAD, BUNDLE)
    assert ok


# --- whole-check summary ------------------------------------------------------------------

def test_summary_neither_is_green_and_owes_nothing():
    owed = {"class": "neither", "owed": [], "spine_hits": [], "reviewer_hits": []}
    s = V.build_summary(owed, [], HEAD, BUNDLE)
    assert s["ok"] and s["owed"] == [] and s["missing"] == []

def test_summary_owed_but_no_evidence_is_red():
    owed = {"class": "spine-carrying", "owed": ["acceptance"],
            "spine_hits": [], "reviewer_hits": []}
    s = V.build_summary(owed, [], HEAD, BUNDLE)
    assert not s["ok"] and s["missing"] == ["acceptance"]

def test_summary_both_owed_one_satisfied_is_red():
    e = V.collect_entries([_comment([{"instrument": "benchmark", "verdict": "pass"}])])
    owed = {"class": "spine-carrying+reviewer-touching", "owed": ["acceptance", "benchmark"],
            "spine_hits": [], "reviewer_hits": []}
    s = V.build_summary(owed, e, HEAD, BUNDLE)
    assert not s["ok"]
    assert s["satisfied"] == ["benchmark"] and s["missing"] == ["acceptance"]

def test_summary_all_satisfied_across_two_comments_is_green():
    e = V.collect_entries([
        _comment([{"instrument": "acceptance", "verdict": "pass", "bundleSha256": BUNDLE}]),
        _comment([{"instrument": "benchmark", "verdict": "pass"}]),
    ])
    owed = {"class": "spine-carrying+reviewer-touching", "owed": ["acceptance", "benchmark"],
            "spine_hits": [], "reviewer_hits": []}
    s = V.build_summary(owed, e, HEAD, BUNDLE)
    assert s["ok"] and s["missing"] == []
    assert s["bundleSha256"] == BUNDLE and s["releaseSha"] == HEAD


# --- owed comment carries the marker + machine block --------------------------------------

def test_owed_comment_has_marker_and_json():
    owed = {"class": "spine-carrying", "owed": ["acceptance"],
            "spine_hits": [], "reviewer_hits": []}
    s = V.build_summary(owed, [], HEAD, BUNDLE)
    body = V.render_owed_comment(s)
    assert V.OWED_MARKER in body
    assert "release-eval-evidence" in body  # tells the reader the fence to post
    assert "```json" in body and '"owed"' in body


# --- bundle hashing -----------------------------------------------------------------------

def test_sha256_file_roundtrip(tmp_path):
    import hashlib
    p = tmp_path / "b.js"
    p.write_bytes(b"spine")
    assert V.sha256_file(str(p)) == hashlib.sha256(b"spine").hexdigest()

def test_sha256_missing_file_is_none():
    assert V.sha256_file("/no/such/bundle.js") is None
