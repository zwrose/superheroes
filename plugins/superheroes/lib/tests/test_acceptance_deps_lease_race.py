# plugins/superheroes/lib/tests/test_acceptance_deps_lease_race.py
#
# premortem-001 (Failure-Mode / concurrency/race): the acceptance harness's lease
# acquisition was check-then-act TOCTOU — `real_reclaim_probe` read the lease and
# returned `proceed` when it found none, but the lease was only WRITTEN later (a
# separate, non-atomic `os.replace`), so two invocations could both observe "no lease"
# and both proceed, each spawning a live showrunner (violating UFR-4) and the second
# lease write silently clobbering the first (breaking UFR-8 record accounting).
#
# The fix folds probe + acquire into one atomic `O_CREAT|O_EXCL` create
# (`acceptance_deps._try_acquire_lease`, the same race-free primitive `file_lock.acquire`
# uses) so a genuine no-prior-lease race can only ever be won by exactly one invocation.
import os
import pytest
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps


def _isolated_root(monkeypatch, tmp_store):
    """Point control_plane's store root at a throwaway tempdir and give the harness a
    real (or real-enough) `root` to key its checkout dir off of."""
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", tmp_store)


def test_try_acquire_lease_only_one_of_two_concurrent_callers_wins(monkeypatch):
    """The core TOCTOU fix: simulate two invocations racing to acquire the lease for the
    first time. Exactly one must win the atomic create; the other must observe it already
    exists (False), never both winning."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        stamp_a = "accept-harness-aaaa1111"
        stamp_b = "accept-harness-bbbb2222"

        first = deps._try_acquire_lease(tmp_root, stamp_a)
        second = deps._try_acquire_lease(tmp_root, stamp_b)

        assert first is True
        assert second is False
        # The lease on disk reflects the WINNER's stamp only — never silently overwritten
        # by the loser (the exact UFR-8 record-accounting break the finding calls out).
        lease = deps._read_lease(tmp_root)
        assert lease["stamp"] == stamp_a
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_real_reclaim_probe_two_concurrent_calls_only_one_proceeds(monkeypatch):
    """End-to-end at the `real_reclaim_probe` seam: two invocations calling
    `reclaim_probe` back-to-back with distinct reserved stamps (no lease exists yet) must
    NOT both come back `in_flight: False` — only the winner may report no-in-flight; the
    loser must see the winner's lease and be forced through the liveness path instead of
    silently sailing through with its own reservation."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        stamp_a = "accept-harness-cccc3333"
        stamp_b = "accept-harness-dddd4444"

        state_a, liveness_a = deps.real_reclaim_probe(tmp_root, reserved_stamp=stamp_a)
        state_b, liveness_b = deps.real_reclaim_probe(tmp_root, reserved_stamp=stamp_b)

        # The first caller wins the atomic acquire outright.
        assert state_a["in_flight"] is False
        assert state_a.get("lease_acquired") is True

        # The second caller must NOT also get a clean "nothing in flight" -- it has to
        # observe caller A's now-live lease and go through liveness classification,
        # which (since A's own pid is alive) reports "alive" -> the reclaim decider
        # would refuse it. This is the crux of the fix: it is impossible for both probes
        # to return `in_flight: False`.
        assert not (state_a["in_flight"] is False and state_b["in_flight"] is False)
        assert state_b["in_flight"] is True
        assert liveness_b == "alive"
        assert state_b["stamp"] == stamp_a

        # The lease on disk still names only the winner's stamp.
        lease = deps._read_lease(tmp_root)
        assert lease["stamp"] == stamp_a
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_real_materialize_does_not_rewrite_lease_when_already_acquired(monkeypatch):
    """When `real_reclaim_probe` already won the atomic acquire, `real_materialize` must
    reuse that lease as-is (no second, non-atomic write) -- pins that the fixed lifecycle
    never re-introduces a second write step for the winning path."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        import acceptance_fixture as af
        # Minimal committed fixture triple the real materialize() copies.
        for doc in ("spec.md", "plan.md", "tasks.md"):
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)

        stamp = "accept-harness-eeee5555"
        recorded_state, liveness = deps.real_reclaim_probe(tmp_root, reserved_stamp=stamp)
        assert recorded_state.get("lease_acquired") is True
        lease_before = dict(deps._read_lease(tmp_root))

        stamped = deps.real_materialize(
            fixture_dir, tmp_root, reserved_stamp=stamp,
            lease_acquired=recorded_state.get("lease_acquired", False),
        )
        lease_after = deps._read_lease(tmp_root)

        assert stamped["stamp"] == stamp
        # acquiredAt / pid / host / bootId all unchanged -- materialize did not rewrite it.
        assert lease_after == lease_before
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_build_wires_reclaim_probe_and_materialize_to_the_same_reserved_stamp(monkeypatch):
    """`build()` mints exactly one reserved stamp shared by `reclaim_probe` and the first
    `materialize()` call -- the fix's actual wiring, not just the underlying primitive."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        for doc in ("spec.md", "plan.md", "tasks.md"):
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)

        built = deps.build(fixture_dir, tmp_root)
        recorded_state, liveness = built["reclaim_probe"]()
        assert recorded_state["in_flight"] is False
        assert recorded_state.get("lease_acquired") is True

        stamped = built["materialize"]()
        lease = deps._read_lease(tmp_root)
        assert lease["stamp"] == stamped["stamp"]
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_real_materialize_lands_where_definition_doc_resolves(monkeypatch):
    """0.10.0 qualification finding: a fixture materialized into the harness control-plane
    dir is invisible to preflight's spec-approved probe and every spine phase reader.
    The materialized triple must land exactly where definition_doc resolves the
    work-item -- pinned by resolving through the same seam the consumers use."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        import definition_doc
        for doc in ("spec.md", "plan.md", "tasks.md"):
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)
        stamp = "accept-harness-cafe1234"
        deps.real_materialize(fixture_dir, tmp_root, reserved_stamp=stamp)
        resolved = definition_doc.resolve_work_item_dir(stamp, root=tmp_root, cwd=tmp_root)
        assert os.path.isfile(os.path.join(resolved, "spec.md")), (
            "materialized fixture is not where definition_doc resolves the work-item")
        # and NOT (only) in the harness control-plane dir, which no consumer reads.
        assert not os.path.isfile(
            os.path.join(deps._harness_dir(tmp_root), stamp, "spec.md"))
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_reap_removes_the_docs_located_fixture(monkeypatch):
    """Companion teardown guarantee for the docs-located materialize: reap must remove the
    fixture from the definition-docs location (found live: run 3 left both stamped dirs
    behind). The stamp-suffix guard keeps this from ever touching a real work-item."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        import definition_doc
        for doc in ("spec.md", "plan.md", "tasks.md"):
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)
        stamp = "accept-harness-dead0001"
        deps.real_materialize(fixture_dir, tmp_root, reserved_stamp=stamp)
        resolved = definition_doc.resolve_work_item_dir(stamp, root=tmp_root, cwd=tmp_root)
        assert os.path.isfile(os.path.join(resolved, "spec.md"))
        reap = deps.real_reap(tmp_root, lambda: stamp)
        result = reap({"reap": [{"kind": "store-dir", "name": resolved}],
                       "leave_behind": []})
        assert not os.path.isdir(resolved), "reap left the docs-located fixture behind"
        assert resolved in result["cleaned_up"]  # the removal is REPORTED, not silent
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_discover_lists_stranded_fixture_dirs_from_both_locations(monkeypatch):
    """Review fix (PR #244 premortem): a run that dies between materialize and reap must
    not strand a phantom pre-approved work-item — discovery lists stamped fixture DIRS
    (legacy harness location and the docs-resolved location) so plan()/reap() reclaim
    them like branches and PRs."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        import definition_doc
        for doc in ("spec.md", "plan.md", "tasks.md"):
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)
        stamp = "accept-harness-feed0002"
        deps.real_materialize(fixture_dir, tmp_root, reserved_stamp=stamp)
        resolved = definition_doc.resolve_work_item_dir(stamp, root=tmp_root, cwd=tmp_root)
        monkeypatch.setattr(deps, "_run", lambda argv, cwd=None: (0, "", ""))
        discover = deps.real_discover_artifacts(tmp_root)
        arts = discover(None)  # discovery mode: no pinned stamp (dead-run reclaim)
        dir_names = [a["name"] for a in arts if a["kind"] == "store-dir"]
        assert resolved in dir_names
        import acceptance_cleanup
        planned = acceptance_cleanup.plan(arts, run_stamp=None)
        assert {"kind": "store-dir", "name": resolved} in planned["reap"]
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_reap_store_dir_failure_is_left_behind_not_silently_dropped(monkeypatch):
    """Review fix (PR #244 premortem, detectability): a failed fixture-dir removal must
    land in left_behind — never report a teardown that did not happen."""
    def fail_rmtree(path):
        raise OSError("held file")
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "rmtree", fail_rmtree)
    tmp = tempfile.mkdtemp()
    victim = os.path.join(tmp, "accept-harness-dead0003")
    os.makedirs(victim)
    try:
        reap = deps.real_reap(tmp, lambda: None)
        result = reap({"reap": [{"kind": "store-dir", "name": victim}], "leave_behind": []})
        assert result["cleaned_up"] == []
        assert result["left_behind"] and result["left_behind"][0]["name"] == victim
    finally:
        import shutil as _sh
        monkeypatch.undo()
        _sh.rmtree(tmp, ignore_errors=True)


def test_reap_store_dir_refuses_non_identity_stamp_basename(monkeypatch):
    """Security hardening (PR #244): the rmtree guard is identity, not embedded-match —
    a dir whose basename merely CONTAINS a stamp is refused and surfaced."""
    tmp = tempfile.mkdtemp()
    victim = os.path.join(tmp, "evil-accept-harness-abc")
    os.makedirs(victim)
    try:
        reap = deps.real_reap(tmp, lambda: None)
        result = reap({"reap": [{"kind": "store-dir", "name": victim}], "leave_behind": []})
        assert os.path.isdir(victim), "guard must refuse a non-identity basename"
        assert result["left_behind"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_real_materialize_rejects_non_bare_stamp(monkeypatch):
    """Security hardening (PR #244): reserved_stamp must BE a bare valid stamp —
    an embedded/prefixed value is refused before any write."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        with pytest.raises(ValueError):
            deps.real_materialize(fixture_dir, tmp_root,
                                  reserved_stamp="evil-accept-harness-abc")
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_real_materialize_partial_failure_removes_partial_docs_dir(monkeypatch):
    """Review fix (PR #244): a mid-write materialize failure must not strand a partial
    fixture in the consumer-visible docs location (invoke's except path tears down with
    stamp=None, which skips artifact cleanup)."""
    tmp_store = tempfile.mkdtemp()
    tmp_root = tempfile.mkdtemp()
    fixture_dir = tempfile.mkdtemp()
    try:
        _isolated_root(monkeypatch, tmp_store)
        import definition_doc, acceptance_fixture as af
        for doc in ("spec.md", "plan.md"):  # tasks.md MISSING -> materialize raises mid-write
            with open(os.path.join(fixture_dir, doc), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\nwork_item: PLACEHOLDER\n" % doc)
        stamp = "accept-harness-feed0004"
        with pytest.raises(Exception):
            deps.real_materialize(fixture_dir, tmp_root, reserved_stamp=stamp)
        resolved = definition_doc.resolve_work_item_dir(stamp, root=tmp_root, cwd=tmp_root)
        assert not os.path.isdir(resolved), "partial fixture stranded in docs location"
    finally:
        shutil.rmtree(tmp_store, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fixture_dir, ignore_errors=True)
