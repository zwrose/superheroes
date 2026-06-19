# plugins/workhorse/lib/tests/test_devserver_reclaim.py
import devserver


def test_poll_healthy_true_when_opener_succeeds():
    class R:
        status = 200
    assert devserver.poll_healthy("http://x", timeout=0.2, interval=0.01,
                                  opener=lambda u: R()) is True


def test_poll_healthy_false_at_deadline():
    def boom(u):
        raise OSError("refused")
    assert devserver.poll_healthy("http://x", timeout=0.1, interval=0.01,
                                  opener=boom) is False


def test_reclaim_corroborates_then_adopts(tmp_path, monkeypatch):
    monkeypatch.setattr(devserver.hostinfo, "boot_id", lambda: "boot-A")
    monkeypatch.setattr(devserver.readout, "scrub", lambda t, root=None: (t, True))
    sc = str(tmp_path / "devserver.json")
    devserver.write_sidecar(sc, {"pid": 4242, "port": 3000}, "npm run dev", root=str(tmp_path))
    h = devserver.reclaim(sc, 3000, "npm run dev", root=str(tmp_path))
    assert h and h["pid"] == 4242 and h["port"] == 3000


def test_reclaim_refuses_on_boot_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(devserver.readout, "scrub", lambda t, root=None: (t, True))
    monkeypatch.setattr(devserver.hostinfo, "boot_id", lambda: "boot-A")
    sc = str(tmp_path / "devserver.json")
    devserver.write_sidecar(sc, {"pid": 4242, "port": 3000}, "npm run dev", root=str(tmp_path))
    monkeypatch.setattr(devserver.hostinfo, "boot_id", lambda: "boot-B")   # rebooted
    assert devserver.reclaim(sc, 3000, "npm run dev", root=str(tmp_path)) is None


def test_reclaim_refuses_on_port_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(devserver.hostinfo, "boot_id", lambda: "boot-A")
    monkeypatch.setattr(devserver.readout, "scrub", lambda t, root=None: (t, True))
    sc = str(tmp_path / "devserver.json")
    devserver.write_sidecar(sc, {"pid": 4242, "port": 3000}, "npm run dev", root=str(tmp_path))
    assert devserver.reclaim(sc, 9999, "npm run dev", root=str(tmp_path)) is None
