# Bite-proof — WO-6, panel-channel census sees the wave-aware recorder (issue 2218, C2)

Detector changed: `plugins/superheroes/lib/tests/test_round_driver.py::test_panel_round_channels_are_all_accounted_for`
(the census now counts `_record_round_wave` calls in `_fold_panel` like `_record_round` calls).

Declared guarded-element set: **E1** only — the wrapper branch of the census (`node.func.id in ("_record_round", "_record_round_wave")`).

## E1 — wrapper branch of the census

- **Axis:** a key passed to `_record_round_wave` inside `_fold_panel` must be a string literal so the census can enumerate it.
- **Neutralization** (targeted edit in `plugins/superheroes/lib/round_driver.py`, `_fold_panel`, ~line 3759):

  before:
  ```
          _record_round_wave(state, "vacuousSeats", list(vacuous_dims), later)
  ```
  after:
  ```
          _e1_key = "vacuousSeats"
          _record_round_wave(state, _e1_key, list(vacuous_dims), later)
  ```

- **Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_round_driver.py -q -n auto -p no:cacheprovider -k test_panel_round_channels_are_all_accounted_for`

- **Raw red** (detector unedited, source neutralized; pytest's own failure display, as printed):

  ```
  F                                                                        [100%]
  =================================== FAILURES ===================================
  _______________ test_panel_round_channels_are_all_accounted_for ________________
  [gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpPCRq2c/bin/python
  ...
          tree, ast_mod = _round_driver_ast()
          fold = _fn_node(tree, ast_mod, "_fold_panel")
          recorded = set()
          for node in ast_mod.walk(fold):
              if not (isinstance(node, ast_mod.Call) and isinstance(node.func, ast_mod.Name)
                      and node.func.id in ("_record_round", "_record_round_wave")):
                  continue
              assert len(node.args) >= 2, "%s must be called with (state, key, value)" % node.func.id
              key = node.args[1]
  >           assert isinstance(key, ast_mod.Constant) and isinstance(key.value, str), (
                  "a _record_round key must be a string LITERAL so the census can enumerate it")
  E           AssertionError: a _record_round key must be a string LITERAL so the census can enumerate it
  E           assert (False)
  E            +  where False = isinstance(<ast.Name object at 0x7f4ca25e4d90>, <class 'ast.Constant'>)
  E            +    where <class 'ast.Constant'> = <module 'ast' from '/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/ast.py'>.Constant

  /home/user/wt-2218-wo6/plugins/superheroes/lib/tests/test_round_driver.py:3260: AssertionError
  =========================== short test summary info ============================
  FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_panel_round_channels_are_all_accounted_for
  1 failed in 2.96s
  ```
  (Elided: the test docstring echo between the header and `tree, ast_mod = ...`, shown as `...`; nothing else. No secrets in the capture.)

- **Restore** (inverse targeted edit): the two lines above were replaced by the original single line.
  Restored line quoted back from the file:
  ```
          _record_round_wave(state, "vacuousSeats", list(vacuous_dims), later)
  ```
  Supplementary `git diff --stat` after restore (round_driver.py absent = no residue):
  ```
   plugins/superheroes/lib/tests/test_round_driver.py | 5 +++--
   1 file changed, 3 insertions(+), 2 deletions(-)
  ```

- **Raw green** (same command, after restore):
  ```
  .                                                                        [100%]
  1 passed in 1.46s
  ```
