"""Tests for PR body staging in sanitized_view (#609)."""
import os
import stat
import subprocess
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import sanitized_view as sv


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: base)
    yield
    for name in os.listdir(base):
        if name.startswith(sv.SANITIZED_VIEW_DIR_PREFIX):
            sv.destroy_sanitized_view(os.path.join(base, name))


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path, *, files=None):
    path = str(path)
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    for rel, content in (files or {"README.md": "hello\n"}).items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    _git(path, "add", "-A")
    _git(
        path,
        "-c",
        "user.email=test@test.local",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
    )
    return path


def _leftover_views(tmp_base):
    return [
        name
        for name in os.listdir(tmp_base)
        if name.startswith(sv.SANITIZED_VIEW_DIR_PREFIX)
    ]


def test_pr_body_staged_happy_path(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    body_path = tmp_path / "pr-body.md"
    body_text = "## Summary\n\nStaged PR body.\n"
    body_path.write_text(body_text, encoding="utf-8")
    view = sv.build_sanitized_view(repo, pr_body_path=str(body_path))
    try:
        assert view["prBodyPath"] == sv.PR_BODY_FILE_NAME
        assert view["prBodyBytes"] == len(body_text.encode("utf-8"))
        staged = os.path.join(view["path"], sv.PR_BODY_FILE_NAME)
        assert os.path.isfile(staged)
        with open(staged, "rb") as fh:
            assert fh.read() == body_text.encode("utf-8")
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_pr_body_not_requested(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    view = sv.build_sanitized_view(repo, pr_body_path=None)
    try:
        assert view["prBodyPath"] is None
        assert view["prBodyBytes"] is None
        assert not os.path.exists(os.path.join(view["path"], sv.PR_BODY_FILE_NAME))
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_pr_body_refuse_missing(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=str(tmp_path / "missing.md"))
    assert exc.value.detail == "sanitized-view-pr-body-missing"
    assert _leftover_views(fake_tmp) == []


def test_pr_body_refuse_unreadable(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    body_path = tmp_path / "secret.md"
    body_path.write_text("hidden\n", encoding="utf-8")
    body_path.chmod(0)
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    try:
        with pytest.raises(sv.SanitizedViewError) as exc:
            sv.build_sanitized_view(repo, pr_body_path=str(body_path))
        assert exc.value.detail == "sanitized-view-pr-body-unreadable"
        assert _leftover_views(fake_tmp) == []
    finally:
        body_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_pr_body_refuse_empty(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    body_path = tmp_path / "empty.md"
    body_path.write_bytes(b"")
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=str(body_path))
    assert exc.value.detail == "sanitized-view-pr-body-empty"
    assert _leftover_views(fake_tmp) == []


def test_pr_body_refuse_too_large(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    body_path = tmp_path / "huge.md"
    body_path.write_bytes(b"x" * (sv.PR_BODY_MAX_BYTES + 1))
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=str(body_path))
    assert exc.value.detail == "sanitized-view-pr-body-too-large"
    assert _leftover_views(fake_tmp) == []


def test_pr_body_refuse_readback_mismatch(tmp_path, monkeypatch):
    import builtins

    repo = _init_repo(tmp_path / "repo")
    body_path = tmp_path / "body.md"
    body_path.write_text("content\n", encoding="utf-8")
    real_open = builtins.open
    readback_calls = [0]

    def _open_hook(path, *args, **kwargs):
        if (
            isinstance(path, str)
            and path.endswith(sv.PR_BODY_FILE_NAME)
            and args == ("rb",)
        ):
            readback_calls[0] += 1
            if readback_calls[0] == 1:

                class _BadRead:
                    def read(self, size=-1):
                        return b"drift"

                    def __enter__(self):
                        return self

                    def __exit__(self, *exc):
                        return False

                return _BadRead()
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _open_hook)
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=str(body_path))
    assert exc.value.detail == "sanitized-view-pr-body-readback-mismatch"
    assert _leftover_views(fake_tmp) == []


def test_pr_body_refuse_name_collision_tracked_file(tmp_path):
    repo = _init_repo(
        tmp_path / "collision",
        files={
            sv.PR_BODY_FILE_NAME: "repo-owned body\n",
            "keep.txt": "k\n",
        },
    )
    body_path = tmp_path / "external.md"
    body_path.write_text("external\n", encoding="utf-8")
    fake_tmp = str(tmp_path / "sanitized-temp-base")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=str(body_path))
    assert exc.value.detail == "sanitized-view-pr-body-name-collision"
    assert _leftover_views(fake_tmp) == []


def test_pr_body_refuse_name_collision_review_patch_source(tmp_path):
    view_root = tmp_path / "view"
    view_root.mkdir()
    patch_path = view_root / sv.REVIEW_DIFF_FILE_NAME
    patch_path.write_text("diff content\n", encoding="utf-8")
    body_path = tmp_path / "body.md"
    body_path.write_text("body\n", encoding="utf-8")
    # Point pr_body_path at the already-staged review patch via hard link.
    linked = tmp_path / "linked-patch"
    os.link(patch_path, linked)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(str(view_root), str(linked))
    assert exc.value.detail == "sanitized-view-pr-body-name-collision"
