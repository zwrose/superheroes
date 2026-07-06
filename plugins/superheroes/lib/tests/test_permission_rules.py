# Courier allow-rules generator/applier (issue #255 classifier-block mitigation).
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import permission_rules as pr


def test_generate_shapes_are_project_scoped():
    rules = pr.generate("/proj", worktrees_root="/wt", cache_base="/cache/")
    assert "Bash(cd '/proj' && python3 *)" in rules
    assert "Bash(cd '/wt/'*)" in rules            # separator-anchored: '/wt-evil' never matches
    assert "Bash(python3 /cache/*)" in rules
    assert "Bash(python3 - <<'__SR_EOF__'*)" in rules
    # No blanket verb grants: every rule is rooted, marker-anchored, or path-prefixed.
    assert not any(r in ("Bash(python3 *)", "Bash(rm *)", "Bash(git *)") for r in rules)
    assert rules == sorted(rules)


def test_merge_adds_to_both_gates_and_preserves_unrelated_keys():
    rules = pr.generate("/proj", "/wt", "/cache/")
    existing = {"permissions": {"allow": ["Workflow"], "deny": ["Bash(rm -rf *)"]},
                "model": "opus"}
    merged, added = pr.merge(existing, rules)
    assert added == 2 * len(rules)
    assert merged["permissions"]["allow"][0] == "Workflow"          # order preserved
    assert merged["permissions"]["deny"] == ["Bash(rm -rf *)"]      # untouched
    assert merged["model"] == "opus"                                 # untouched
    assert all(r in merged["autoMode"]["allow"] for r in rules)      # classifier gate


def test_merge_preserves_preexisting_automode_rules():
    rules = pr.generate("/proj", "/wt", "/cache/")
    existing = {"autoMode": {"allow": ["SomePriorRule"], "environment": ["x"]}}
    merged, _ = pr.merge(existing, rules)
    assert merged["autoMode"]["allow"][0] == "SomePriorRule"     # order preserved
    assert all(r in merged["autoMode"]["allow"] for r in rules)
    assert merged["autoMode"]["environment"] == ["x"]            # untouched


def test_merge_is_idempotent():
    rules = pr.generate("/proj", "/wt", "/cache/")
    once, _ = pr.merge({}, rules)
    twice, added = pr.merge(once, rules)
    assert added == 0
    assert twice == once


def test_apply_roundtrip_and_idempotence(tmp_path):
    root = str(tmp_path)
    out = pr.apply(root, "local", worktrees_root="/wt", cache_base="/cache/")
    assert out["ok"] and out["added"] > 0
    assert out["path"].endswith(".claude/settings.local.json")
    again = pr.apply(root, "local", worktrees_root="/wt", cache_base="/cache/")
    assert again == {"ok": True, "path": out["path"], "added": 0, "already": True}
    data = json.loads(open(out["path"]).read())
    assert data["permissions"]["allow"] == data["autoMode"]["allow"]


def test_apply_in_repo_mode_targets_committed_settings(tmp_path):
    out = pr.apply(str(tmp_path), "in-repo", worktrees_root="/wt", cache_base="/cache/")
    assert out["ok"] and out["path"].endswith(".claude/settings.json")


def test_apply_fails_closed_on_unparseable_settings(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.local.json").write_text("{not json")
    out = pr.apply(str(tmp_path), "local")
    assert out["ok"] is False and "not clobbering" in out["reason"]
    assert (d / "settings.local.json").read_text() == "{not json"   # untouched


def test_apply_fails_closed_on_non_object_settings(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.local.json").write_text("[1,2]")
    out = pr.apply(str(tmp_path), "local")
    assert out["ok"] is False


def test_cli_emit_and_apply(tmp_path, capsys):
    assert pr.main(["emit", "--root", str(tmp_path)]) == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["ok"] and any("__SR_EOF__" in r for r in emitted["rules"])
    assert pr.main(["apply", "--root", str(tmp_path), "--mode", "local"]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["ok"] and applied["added"] > 0


def test_headless_tier_is_superset_with_floor_bounded_verbs():
    scoped = pr.generate("/proj", "/wt", "/cache/")
    headless = pr.generate_headless("/proj", "/wt", "/cache/")
    assert set(scoped) <= set(headless)
    assert "Bash(python3 *)" in headless and "Bash(git *)" in headless
    # Never the gated-verb surface as a bare grant (enforcer floor is the backstop,
    # but the tier itself must not name owner-authority verbs).
    assert not any("merge" in r or "release" in r or "push" in r for r in headless)
    assert headless == sorted(headless)


def test_apply_headless_tier_writes_verb_rules(tmp_path):
    out = pr.apply(str(tmp_path), "local", worktrees_root="/wt", cache_base="/cache/",
                   tier="headless")
    assert out["ok"]
    import json as _json
    data = _json.loads(open(out["path"]).read())
    assert "Bash(git *)" in data["autoMode"]["allow"]
    # apply()'s parameter default is the scoped tier — a flipped default would
    # silently widen every configure-offer write, so pin it directly.
    scoped_only = pr.apply(str(tmp_path / "other"), "local", worktrees_root="/wt",
                           cache_base="/cache/")
    data2 = _json.loads(open(scoped_only["path"]).read())
    assert "Bash(git *)" not in data2["permissions"]["allow"]
