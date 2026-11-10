"""A replacement heartbeat cannot make an old handback current."""
import heartbeat as hb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _BATCH, _NoteGh
from test_wave_watch_cloud import repo  # noqa: F401
from test_wave_watch_local_resume_2410 import _local_lane, _scan


def test_replacement_does_not_lend_its_timestamp_to_an_old_handback(repo, monkeypatch):
    # axis: the reopened-lane freshness guard must reject a pre-basis handback even
    # when a working heartbeat replaces it before the watcher finishes checking it.
    _local_lane(repo)
    _scan(monkeypatch, (4242, False))
    folded = ll.fold(ll.read(repo, create=False)["records"])
    basis = folded["launches"]["local-a"]["terminalTs"]
    stamped = hb.stamp(
        repo, launch_id="local-a", state="handback", phase="finished", now=basis - 1,
    )
    assert stamped.get("ok") is True, stamped
    original_read = hb.read_heartbeat
    published = False

    def read_then_publish_resume(repo_root, launch_id, **kwargs):
        nonlocal published
        snapshot = original_read(repo_root, launch_id, **kwargs)
        if launch_id == "local-a" and not published:
            # Ordering pin: publish immediately after the first snapshot is read.
            # This forces one legal writer/reader interleaving; other schedules
            # and filesystem latency remain untested. Reads and stamps stay real.
            published = True
            replacement = hb.stamp(
                repo_root, launch_id=launch_id, state="working", phase="resumed",
                now=basis + 1,
            )
            assert replacement.get("ok") is True, replacement
        return snapshot

    monkeypatch.setattr(hb, "read_heartbeat", read_then_publish_resume)
    result = ww.run(repo, _BATCH, gh_run=_NoteGh())
    assert published
    assert result.get("ok") is True, result
    assert result["event"] != ww.EVENT_LANE_TERMINAL, result
