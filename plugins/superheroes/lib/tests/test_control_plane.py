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


# --- #121 Part B: store-root rename (workhorse → superheroes) + auto-migrate ---

def test_store_root_prefers_new_falls_back_to_legacy(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    new = tmp_path / "superheroes"
    old = tmp_path / "workhorse"
    monkeypatch.setattr(cp, "DEFAULT_STORE_ROOT", str(new))
    monkeypatch.setattr(cp, "LEGACY_STORE_ROOT", str(old))
    # neither holds a store → the new default
    assert cp.store_root() == os.path.realpath(str(new))
    # only legacy holds a store → back-compat fallback (don't strand the existing store)
    (old / "projects").mkdir(parents=True)
    assert cp.store_root() == os.path.realpath(str(old))
    # new holds a store → prefer new even if legacy also lingers
    (new / "projects").mkdir(parents=True)
    assert cp.store_root() == os.path.realpath(str(new))


def test_store_root_does_not_strand_legacy_behind_an_empty_new_root(monkeypatch, tmp_path):
    # /code-review #6: an EMPTY new root (created by anything other than the rename) must NOT
    # strand a populated legacy — "a store" means it holds the projects/ tree, not mere existence.
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    new = tmp_path / "superheroes"
    old = tmp_path / "workhorse"
    monkeypatch.setattr(cp, "DEFAULT_STORE_ROOT", str(new))
    monkeypatch.setattr(cp, "LEGACY_STORE_ROOT", str(old))
    (old / "projects").mkdir(parents=True)   # populated legacy
    new.mkdir()                               # empty new (not from the rename)
    assert cp.store_root() == os.path.realpath(str(old))   # legacy still wins
    res = cp.migrate_store_root()                          # and migration still reconciles it
    assert res["migrated"] is True
    assert (new / "projects").is_dir() and not old.exists()


def test_store_root_env_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "wh"))
    assert cp.store_root() == os.path.realpath(str(tmp_path / "wh"))  # legacy env still honored
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "sh"))
    assert cp.store_root() == os.path.realpath(str(tmp_path / "sh"))  # new env wins


def test_migrate_store_root_renames_legacy_atomically(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    new = tmp_path / "claude" / "superheroes"
    old = tmp_path / "claude" / "workhorse"
    (old / "projects").mkdir(parents=True)
    (old / "projects" / "marker").write_text("calibration")
    monkeypatch.setattr(cp, "DEFAULT_STORE_ROOT", str(new))
    monkeypatch.setattr(cp, "LEGACY_STORE_ROOT", str(old))
    res = cp.migrate_store_root()
    assert res["migrated"] is True
    assert not old.exists()
    assert (new / "projects" / "marker").read_text() == "calibration"
    # idempotent — second call is a no-op
    assert cp.migrate_store_root()["migrated"] is False


def test_migrate_store_root_noops_on_env_or_nothing(monkeypatch, tmp_path):
    new = tmp_path / "superheroes"
    old = tmp_path / "workhorse"
    monkeypatch.setattr(cp, "DEFAULT_STORE_ROOT", str(new))
    monkeypatch.setattr(cp, "LEGACY_STORE_ROOT", str(old))
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    assert cp.migrate_store_root()["migrated"] is False  # nothing to migrate
    old.mkdir()
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "pinned"))
    assert cp.migrate_store_root()["migrated"] is False  # pinned via env → leave it
    assert old.exists()  # untouched
