import json

from test_pilot_acceptance import (
    _commit_checkout,
    _conformance_fixture,
    _run_conformance,
)


def test_report_stamps_cwd_head_when_git_dir_points_elsewhere(tmp_path, monkeypatch):
    # bite-axis: checkout identity — an inherited GIT_DIR cannot redirect the report stamp.
    checkout, policy_root = _conformance_fixture(tmp_path)
    expected_head = _commit_checkout(checkout)
    other_checkout = tmp_path / "other"
    other_checkout.mkdir()
    (other_checkout / "marker.txt").write_text("other checkout\n", encoding="utf-8")
    other_head = _commit_checkout(other_checkout)
    assert other_head != expected_head
    monkeypatch.setenv("GIT_DIR", str(other_checkout / ".git"))

    proc = _run_conformance(checkout, policy_root, "--project", "demo")

    assert proc.returncode in (0, 1), proc.stderr
    assert json.loads(proc.stdout)["reference"]["commit"] == expected_head
