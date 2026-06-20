# plugins/superheroes/lib/tests/test_control_plane.py
import os
import subprocess
import control_plane as cp


def _git_init(d):
    subprocess.run(["git", "-C", d, "init", "-q"], check=True)


def test_checkout_key_is_stable_16hex(tmp_path):
    _git_init(str(tmp_path))
    k1 = cp.checkout_key(str(tmp_path))
    k2 = cp.checkout_key(str(tmp_path))
    assert k1 == k2 and len(k1) == 16 and all(c in "0123456789abcdef" for c in k1)


def test_checkout_key_distinct_per_worktree(tmp_path):
    main = tmp_path / "main"; main.mkdir(); _git_init(str(main))
    (main / "f").write_text("x"); subprocess.run(["git", "-C", str(main), "add", "f"], check=True)
    subprocess.run(["git", "-C", str(main), "-c", "user.email=a@b.c", "-c", "user.name=a",
                    "commit", "-qm", "x"], check=True)
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
    # §4.2: the control-plane key MUST differ between a clone's linked worktrees
    assert cp.checkout_key(str(main)) != cp.checkout_key(str(wt))


def test_paths_shape(tmp_path):
    p = cp.paths(str(tmp_path), "my-item", root=str(tmp_path / "store"))
    assert p["checkpoint"].endswith("/issues/my-item/checkpoint.json")
    assert p["events"].endswith("/issues/my-item/events.jsonl")
    assert p["resume_brief"].endswith("/issues/my-item/resume-brief.md")
    assert p["devserver"].endswith("/issues/my-item/devserver.json")


def test_ensure_store_creates_git_repo_and_meta(tmp_path):
    _git_init(str(tmp_path))
    d = cp.ensure_store(str(tmp_path), root=str(tmp_path / "store"))
    assert d is not None
    assert os.path.isdir(os.path.join(d, ".git"))
    assert os.path.isfile(os.path.join(d, "meta.json"))


def test_atomic_write_roundtrip(tmp_path):
    f = str(tmp_path / "sub" / "x.json")
    cp.atomic_write(f, '{"a":1}')
    assert open(f).read() == '{"a":1}'


def test_paths_has_review_result_and_provenance_keys(tmp_path):
    p = cp.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))
    assert p["review_result"].endswith("/review-result.json")
    assert p["provenance"].endswith("/provenance.json")
    assert p["review_result"].startswith(p["issue_dir"])
    assert p["provenance"].startswith(p["issue_dir"])
