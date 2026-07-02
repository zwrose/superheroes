# plugins/superheroes/lib/tests/test_store_sweep.py
"""Orphan report + sweep over store_root()/projects/ (provenance-aware, fail-closed).

Class contract: `real` = live content (docs/ with files, git commits, any state file)
OR a recorded sourcePath that still exists; `orphan` = sourcePath recorded but gone and
no real content; `unknown` = no sourcePath and no real content (pre-provenance). Sweep
deletes orphans only; `unknown` requires the explicit opt-in; `real` is never deleted.
"""
import json
import os
import subprocess
import sys

import control_plane as cp
import mode_registry as mr
import store_sweep as ss

_BOOKKEEPING = {"meta.json": '{"schemaVersion": 1}',
                "config.lock": "",
                "doc-policy.json": "{}",
                "registry.json": "{}"}


def _mk_store(root, key, files=None, git_init=False):
    d = os.path.join(str(root), "projects", key)
    os.makedirs(d, exist_ok=True)
    for rel, text in (files or {}).items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
    if git_init:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
    return d


def _meta(source_path):
    return json.dumps({"schemaVersion": 1, "sourcePath": source_path})


def _classes(root):
    return {s["key"]: s["class"] for s in ss.report(root=str(root))["stores"]}


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


# --- classification -------------------------------------------------------


def test_docs_with_files_is_real_even_without_source_path(tmp_path):
    files = dict(_BOOKKEEPING)
    files["docs/some-work-item/spec.md"] = "# spec"
    _mk_store(tmp_path, "aaaa000000000001", files=files, git_init=True)
    assert _classes(tmp_path) == {"aaaa000000000001": "real"}


def test_git_commits_are_real_content(tmp_path):
    d = _mk_store(tmp_path, "aaaa000000000002", files=dict(_BOOKKEEPING), git_init=True)
    subprocess.run(["git", "-C", d, "add", "-f", "meta.json"], check=True)
    subprocess.run(["git", "-C", d, "-c", "user.email=a@b.c", "-c", "user.name=a",
                    "commit", "-qm", "seed"], check=True)
    assert _classes(tmp_path) == {"aaaa000000000002": "real"}


def test_existing_source_path_is_real_even_when_store_is_empty(tmp_path):
    src = tmp_path / "live-project"
    src.mkdir()
    files = dict(_BOOKKEEPING)
    files["meta.json"] = _meta(str(src))
    _mk_store(tmp_path, "aaaa000000000003", files=files, git_init=True)
    assert _classes(tmp_path) == {"aaaa000000000003": "real"}


def test_missing_source_path_and_no_content_is_orphan(tmp_path):
    files = dict(_BOOKKEEPING)
    files["meta.json"] = _meta(str(tmp_path / "gone-repo"))
    _mk_store(tmp_path, "aaaa000000000004", files=files, git_init=True)
    assert _classes(tmp_path) == {"aaaa000000000004": "orphan"}


def test_no_source_path_and_no_content_is_unknown(tmp_path):
    _mk_store(tmp_path, "aaaa000000000005", files=dict(_BOOKKEEPING), git_init=True)
    assert _classes(tmp_path) == {"aaaa000000000005": "unknown"}


def test_corrupt_meta_is_unknown_not_orphan(tmp_path):
    files = dict(_BOOKKEEPING)
    files["meta.json"] = "{not json"
    _mk_store(tmp_path, "aaaa000000000006", files=files)
    assert _classes(tmp_path) == {"aaaa000000000006": "unknown"}


def test_missing_source_path_but_unrecognized_file_is_real(tmp_path):
    # fail-closed: ANY file the classifier does not recognize counts as content
    files = dict(_BOOKKEEPING)
    files["meta.json"] = _meta(str(tmp_path / "gone-repo"))
    files["checkpoint.json"] = "{}"
    _mk_store(tmp_path, "aaaa000000000007", files=files)
    assert _classes(tmp_path) == {"aaaa000000000007": "real"}


def test_store_minted_by_ensure_project_store_classifies_by_source_liveness(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo, "git@github.com:o/sweepme.git")
    root = tmp_path / "store"
    d = mr.ensure_project_store(str(repo), root=str(root))
    assert d is not None
    assert _classes(root)[mr.config_key(str(repo))] == "real"   # source still exists
    key = mr.config_key(str(repo))
    import shutil
    shutil.rmtree(str(repo))
    assert _classes(root)[key] == "orphan"                       # source gone, no content


def test_report_shape_and_counts(tmp_path):
    files_orphan = dict(_BOOKKEEPING)
    files_orphan["meta.json"] = _meta(str(tmp_path / "gone"))
    _mk_store(tmp_path, "bbbb000000000001", files=files_orphan)
    _mk_store(tmp_path, "bbbb000000000002", files=dict(_BOOKKEEPING))
    rep = ss.report(root=str(tmp_path))
    assert rep["projectsRoot"] == os.path.join(str(tmp_path), "projects")
    assert rep["counts"] == {"real": 0, "orphan": 1, "unknown": 1}
    by_key = {s["key"]: s for s in rep["stores"]}
    assert by_key["bbbb000000000001"]["sourcePath"] == str(tmp_path / "gone")
    assert by_key["bbbb000000000002"]["sourcePath"] is None
    for s in rep["stores"]:
        assert s["reasons"]  # every classification is explained


def test_report_on_missing_projects_dir_is_empty(tmp_path):
    rep = ss.report(root=str(tmp_path / "nowhere"))
    assert rep["stores"] == [] and rep["counts"] == {"real": 0, "orphan": 0, "unknown": 0}


# --- sweep ----------------------------------------------------------------


def _three_class_fixture(tmp_path):
    real_files = dict(_BOOKKEEPING)
    real_files["docs/wi/spec.md"] = "# spec"
    real = _mk_store(tmp_path, "cccc000000000001", files=real_files)
    orphan_files = dict(_BOOKKEEPING)
    orphan_files["meta.json"] = _meta(str(tmp_path / "gone"))
    orphan = _mk_store(tmp_path, "cccc000000000002", files=orphan_files, git_init=True)
    unknown = _mk_store(tmp_path, "cccc000000000003", files=dict(_BOOKKEEPING), git_init=True)
    return real, orphan, unknown


def test_sweep_deletes_orphans_only_by_default(tmp_path):
    real, orphan, unknown = _three_class_fixture(tmp_path)
    result = ss.sweep(root=str(tmp_path))
    assert result["deleted"] == [orphan]
    assert os.path.isdir(real) and os.path.isdir(unknown) and not os.path.exists(orphan)


def test_sweep_include_unknown_deletes_unknown_too_but_never_real(tmp_path):
    real, orphan, unknown = _three_class_fixture(tmp_path)
    result = ss.sweep(root=str(tmp_path), include_unknown=True)
    assert sorted(result["deleted"]) == sorted([orphan, unknown])
    assert os.path.isdir(real)


def test_sweep_never_deletes_store_whose_source_path_exists(tmp_path):
    src = tmp_path / "live"
    src.mkdir()
    files = dict(_BOOKKEEPING)
    files["meta.json"] = _meta(str(src))
    d = _mk_store(tmp_path, "cccc000000000004", files=files, git_init=True)
    result = ss.sweep(root=str(tmp_path), include_unknown=True)
    assert result["deleted"] == [] and os.path.isdir(d)


def test_sweep_on_missing_projects_dir_is_a_noop(tmp_path):
    result = ss.sweep(root=str(tmp_path / "nowhere"))
    assert result["deleted"] == []


# --- CLI ------------------------------------------------------------------


def _run_cli(root, *args):
    env = dict(os.environ, SUPERHEROES_STORE_ROOT=str(root))
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "store_sweep.py")
    r = subprocess.run([sys.executable, script, *args],
                       capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_cli_report_and_sweep_print_json(tmp_path):
    real, orphan, unknown = _three_class_fixture(tmp_path)
    rep = _run_cli(tmp_path, "report")
    assert rep["counts"] == {"real": 1, "orphan": 1, "unknown": 1}
    swept = _run_cli(tmp_path, "sweep")
    assert swept["deleted"] == [orphan]
    assert os.path.isdir(real) and os.path.isdir(unknown)
    swept2 = _run_cli(tmp_path, "sweep", "--include-unknown")
    assert swept2["deleted"] == [unknown]


def test_cli_respects_root_flag_over_env(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    files = dict(_BOOKKEEPING)
    files["meta.json"] = _meta(str(tmp_path / "gone"))
    _mk_store(a, "dddd000000000001", files=files)
    env = dict(os.environ, SUPERHEROES_STORE_ROOT=str(b))
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "store_sweep.py")
    r = subprocess.run([sys.executable, script, "report", "--root", str(a)],
                       capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["counts"]["orphan"] == 1
