# WO-5 (#2459) bite-proof — `test_prove_a_layer_rebuilt_from_its_vetted_tree_after_a_rebase_conflict`

Bite proof for the one test added to `plugins/superheroes/lib/tests/test_stack_linear.py`. It exercises the rebuild step that `skills/showrunner/reference/merge-train.md` § Merging a stack, item 4 (d) prescribes, on a real throwaway repo.

**Register:** 1 guarded element, declared by the order: the rebuild step the prose prescribes (`git commit-tree <vetted head>^{tree} -p <parent> -m ...`), as the test exercises it (`test_stack_linear.py:974`). Axis: a straightening rebase conflict is cleared by rebuilding the layer as one commit that carries its vetted tree, and `prove` accepts that layer.

**Provenance:** claude (Claude Sonnet 5.5).

**Commands.** *Red* (the test alone):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo5 -m pytest plugins/superheroes/lib/tests/test_stack_linear.py -q -p no:cacheprovider --tb=short -k "rebuilt"
```

*Green* (the whole file, after the restore):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo5 -m pytest plugins/superheroes/lib/tests/test_stack_linear.py -q -p no:cacheprovider --tb=short
```

Every capture omits the one leading line `warning: The UV_NATIVE_TLS environment variable is deprecated ...`, which is uv's own notice. Nothing else is filtered or redacted (no secrets, tokens or private URLs appear). The `detail` text in the red capture is cut by pytest's own assertion-message elision (the `...` is pytest's), not by this record.

## R1 — the rebuild step

**neutralization:** in the test, the single line

```python
    n1 = _git(repo, "commit-tree", v1 + "^{tree}", "-p", base, "-m", "layer 1")
```

was replaced by an automatic replay that resolves the conflict on its own, whose head becomes `N1`:

```python
    _git(repo, "checkout", "-q", "--detach", v1)  # bite-proof
    _git(repo, "rebase", "-q", "-X", "theirs", "--onto", base, base, v1)  # bite-proof
    n1 = _head(repo)  # bite-proof
    _git(repo, "checkout", "-q", "main")  # bite-proof
```

**first attempt, disclosed:** the first red run failed earlier than the order expected, on an extra line of my own that compared the rebuilt commit's tree to the vetted tree (`assert 'e46973293511...7a025225dd44a' == '849ad56e2d5d...1f9f52c94e541'` at `test_stack_linear.py:979`). That line was redundant with `prove`'s own tree check, so I removed it from the test, so that the red comes from `prove` as the order specified. I also added the result dict as the assertion message on the proven assertion, so the red names the refusal reason. The red below is the run after both changes.

**raw red** (`-k "rebuilt"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_prove_a_layer_rebuilt_from_its_vetted_tree_after_a_rebase_conflict ____
/home/user/wt-2459-wo5/plugins/superheroes/lib/tests/test_stack_linear.py:991: in test_prove_a_layer_rebuilt_from_its_vetted_tree_after_a_rebase_conflict
    assert result["ok"] is True and result["proven"] is True and result["reason"] is None, result
E   AssertionError: {'ok': False, 'proven': False, 'reason': 'tree-changed', 'detail': 'layer layer-1: new head 2f662b876960dd938b67724300...a but the vetted head 67cc24611407bc38b5f9bfca2502c065709e5eb9 has tree 849ad56e2d5d3750b455342d0601f9f52c94e541', ...}
E   assert (False is True)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_a_layer_rebuilt_from_its_vetted_tree_after_a_rebase_conflict
1 failed, 178 deselected in 0.77s
```

`prove` refused `tree-changed` naming `layer-1`: the replay kept the layer commit's line, not the vetted resolution.

**restore:** the four neutralized lines were replaced by the inverse edit (the Edit tool, no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line quoted back from `test_stack_linear.py:974`; a grep for `bite-proof` over the test file returns no match):
```python
    n1 = _git(repo, "commit-tree", v1 + "^{tree}", "-p", base, "-m", "layer 1")
```

**raw green** (whole file):
```
........................................................................ [ 40%]
........................................................................ [ 80%]
...................................                                      [100%]
179 passed in 2.64s
```
