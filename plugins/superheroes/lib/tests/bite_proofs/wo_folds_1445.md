# WO-2b bite-proof — v1/v2 folds (#1445, layer 4d-2)

**FU4 (test-harness default):** adds no production detector; no bite-proof owed.

## BP-v1 — full-oid allowlist in `_require_explicit_commit_sha`

- **Guarded element:** `review_diff_bytes.py:6` — `_require_explicit_commit_sha`.
- **Axis:** `run_git_diff_three_dot` refuses any base/head that is not a 40- or 64-char hex oid before invoking git.
- **Neutralization:** replaced the function body with the prior denylist only:

```python
    if not isinstance(sha, str) or not sha.strip():
        raise ValueError("%s must be an explicit commit" % label)
    if sha.strip().upper() == "HEAD":
        raise ValueError("%s must be an explicit commit" % label)
```

- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/claude-501/wo2b-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_v1_explicit_commit_guard_rejects_non_full_oid -p no:xdist -q`
- **Raw red:** `16 failed, 8 passed in 29.15s`. For `'@'`, `'HEAD~0'`, `'ORIG_HEAD'`, `'main'`, `'abc1234'`, 39-char, 41-char, and 40-char-plus-space refs (base and head parametrization): **`AssertionError: subprocess.run must not be called`** — guard did not raise `ValueError` before `run_git_diff_three_dot` reached git. Representative:

```
_______ test_v1_explicit_commit_guard_rejects_non_full_oid['@'-base_sha] _______
...
        with pytest.raises(ValueError, match="explicit commit"):
>           rdb.run_git_diff_three_dot(**kwargs)
...
>       raise AssertionError("subprocess.run must not be called")
E       AssertionError: subprocess.run must not be called
```

Short summary lists the same sixteen parametrized nodes (`'@'`, `'HEAD~0'`, `'ORIG_HEAD'`, `'main'`, `'abc1234'`, three wrong-length `a…` ids × base_sha/head_sha). No `Failed: DID NOT RAISE` on those cases in this run.
- **Restore:** reinstated full-oid allowlist body (see restore receipt).
- **Restore receipt:**

```python
def _require_explicit_commit_sha(sha, label):
    if not isinstance(sha, str):
        raise ValueError("%s must be an explicit commit" % label)
    if len(sha) not in (40, 64):
        raise ValueError("%s must be an explicit commit" % label)
    for ch in sha:
        if ch not in "0123456789abcdefABCDEF":
            raise ValueError("%s must be an explicit commit" % label)
```

- **Green command:** same node as red.
- **Raw green:** `24 passed in 39.70s`

## BP-v2 — `except ValueError` mapping in `_derive_panel_diff_at_head`

- **Guarded element:** `round_driver.py:4385-4386` — `except ValueError as exc:` / `return None, str(exc)` around `run_git_diff_three_dot`.
- **Axis:** non-explicit `head_sha` surfaces as `(None, detail)` instead of an uncaught `ValueError`.
- **Neutralization:** deleted the two lines `except ValueError as exc:` and `return None, str(exc)`.
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/claude-501/wo2b-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_v2_derive_panel_diff_maps_head_value_error -p no:xdist -q`
- **Raw red:**

```
FAILED ...::test_v2_derive_panel_diff_maps_head_value_error
...
>       diff_text, detail = RD._derive_panel_diff_at_head(cfg, "HEAD")
...
>           raise ValueError("%s must be an explicit commit" % label)
E           ValueError: head_sha must be an explicit commit
1 failed in 11.15s
```

- **Restore:** re-inserted `except ValueError as exc:` / `return None, str(exc)` before `if proc.returncode != 0`.
- **Restore receipt:**

```python
    except ValueError as exc:
        return None, str(exc)
```

- **Green command:** same node as red.
- **Raw green:** `1 passed in 8.32s`

## BP-v1-base — base resolution in `_derive_panel_diff_at_head`

- **Guarded element:** `round_driver.py:4379-4380` — pass `verified_base` (not raw `baseRef`) into `run_git_diff_three_dot`.
- **Axis:** short symbolic `baseRef` is rev-parsed to a full oid before the producer runs.
- **Neutralization:** `run_git_diff_three_dot(repo_root, base, head_sha, …)` instead of `verified_base`.
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/claude-501/wo2b-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_v1_derive_panel_diff_resolves_short_base_ref -p no:xdist -q`
- **Raw red:**

```
>       assert err is None
E       AssertionError: assert 'base_sha must be an explicit commit' is None
1 failed in 9.14s
```

- **Restore:** `verified_base` restored as diff base argument.
- **Restore receipt:**

```python
        proc = review_diff_bytes.run_git_diff_three_dot(
            repo_root, verified_base, head_sha, timeout=120)
```

- **Green command:** same node as red.
- **Raw green:** `1 passed in 6.23s`

## BP-v1-caller — handback base resolution

- **Guarded element:** `handback_gate.py:1005` — `_recompute_diff_sha256(verified_base, …)` after rev-parse of sidecar `baseSha`.
- **Axis:** short pinned `baseSha` in the sidecar still yields a matching diff digest (full oid passed to producer).
- **Neutralization:** `_recompute_diff_sha256(pinned_base, cwd, head_sha)` instead of `verified_base`.
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/claude-501/wo2b-pyc -m pytest plugins/superheroes/lib/tests/test_handback_gate.py::test_short_base_sha_in_sidecar_still_recomputes_diff -p no:xdist -q`
- **Raw red:**

```
>       assert result["decision"] == "allow"
E       AssertionError: assert 'refuse' == 'allow'
E         
E         - allow
E         + refuse
1 failed in 4.22s
```

- **Restore:** `verified_base` restored as first argument to `_recompute_diff_sha256`.
- **Restore receipt:**

```python
    recomputed_diff = _recompute_diff_sha256(verified_base, cwd, head_sha)
```

- **Green command:** same node as red.
- **Raw green:** `1 passed in 4.96s`

- **Post-restore `git status --porcelain`:** (empty)
