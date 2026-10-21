# Bite-proof record: WO-A (#2022), the hook offer saves the detected inputs on either answer

Declared guarded-element set (from the order): G1, G2, G3. One neutralization and one red each.
Every run used `scripts/pinned-python -B -X pycache_prefix=<scratchpad>/pyc -m pytest <target> -k <test> -q -p no:cacheprovider`
from the worktree. Nothing in the captures needed redaction. Captures are trimmed to the decisive
lines (the `UV_NATIVE_TLS` deprecation warning and the unchanged test body echo are elided).

## G1 — set-up.md § 6, the dependency hook offer paragraph

- **Guarded element and axis:** `skills/configure/reference/set-up.md` paragraph `**The dependency hook offer.**`;
  the item 18 save is unconditional on the owner's answer to the hook offer. Detector:
  `test_the_hook_offer_saves_the_detected_inputs_on_either_answer` in
  `lib/tests/test_cloud_setup_sitting_text.py`.
- **Neutralization:** replaced the new sentences with the base sentence:
  "When the owner says yes and the offer's `inputsSource` is `detected`, first save the offer's
  `inputs` as item 18 (the JSON list), and go on only when the result is `written` or `noop`; item 19
  alone would leave the hook watching nothing."
- **Raw red:**
  ```
  >       assert any("Whatever the owner answers" in s for s in saves), (
  E       AssertionError: the item 18 save is not stated for whatever the owner answers: ["When the owner says yes and the offer's `inputsSource` is `detected`, first save the offer's `inputs` as item 18 (the JSON list), and go on only when the result is `written` or `noop`; item 19 alone would leave the hook watching nothing"]
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_hook_offer_saves_the_detected_inputs_on_either_answer
  1 failed, 12 deselected in 0.16s
  ```
- **Restore:** the inverse edit, putting the new sentences back.
- **Restore receipt (restored lines quoted back, set-up.md lines 544-549):**
  ```
  A refusal means there is nothing to offer: skip the offer. Whatever the owner answers, when the
  offer's `inputsSource` is `detected`, first save the offer's `inputs` as item 18 (the JSON list),
  and go on only when the result is `written` or `noop`. On yes, item 19 alone would leave the hook
  watching nothing; on no, the files would stay out of the setup text's stamp, so a change to one
  would never make the cloud check ask for new setup text, as the offer tells the owner it will.
  Leave an item 18 the owner already stored as it is.
  ```
  `git diff --stat -- set-up.md` after restore: ` set-up.md | 8 +++++---` / `1 file changed, 5 insertions(+), 3 deletions(-)`
  (the intended change only; the diff hunk matches the new text above).
- **Raw green:** `1 passed, 12 deselected in 0.15s`

## G2 — view-and-tune.md, the item 19 tune row

- **Guarded element and axis:** `skills/configure/reference/view-and-tune.md` bullet
  `**Keep cloud dependencies current with a hook (item 19)**`; the item 18 save is unconditional on
  the owner's answer in the item 19 tune row. Detector:
  `test_the_item_19_tune_row_saves_the_detected_inputs_on_either_answer`.
- **Neutralization:** restored "write only item 19" and the base last sentence ("Run the offer
  first (set-up § 6) so the owner hears the cost before choosing.").
- **Raw red:**
  ```
  >       assert "write only item 19" not in bullet, "the item 19 row still says to write only item 19"
  E       AssertionError: the item 19 row still says to write only item 19
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_item_19_tune_row_saves_the_detected_inputs_on_either_answer
  1 failed, 12 deselected in 1.25s
  ```
- **Restore:** the inverse edit, putting "write item 19" and the new last sentence back.
- **Restore receipt:** `git diff -- view-and-tune.md` after restore shows exactly the intended hunk:
  ```
  -- **Keep cloud dependencies current with a hook (item 19)** → write only item 19, `true` to add the
  +- **Keep cloud dependencies current with a hook (item 19)** → write item 19, `true` to add the
  ...
  -  first (set-up § 6) so the owner hears the cost before choosing.
  +  first (set-up § 6) so the owner hears the cost before choosing, and on either answer save its
  +  detected inputs as item 18 before item 19, as set-up § 6 says.
  ```
- **Raw green:** `1 passed, 12 deselected in 0.14s`

## G3 — the stamp's hook-off input leg, `lib/cloud_setup_text.py` `_view_for`

- **Guarded element and axis:** `cloud_setup_text.py:484` (`# axis: the input files join the stamp
  only with commands, stored inputs and no hook`); a decline that saved the offered inputs puts them
  in the stamp, so a lockfile change reads stale. Detector:
  `test_declining_the_offer_after_saving_its_inputs_makes_a_lockfile_change_ask_for_a_re_paste` in
  `lib/tests/test_cloud_dependency_hook_2009.py`.
- **Neutralization (transient, shipped source):** line 484
  `return _stamp_view(files, commands, _inputs_view_for(cwd, commands, inputs))` changed to
  `return _stamp_view(files, commands, _inputs_view_for(cwd, commands, None))`.
- **Raw red:**
  ```
  >       assert _stamp(w) != before
  E       AssertionError: assert 'sha256:46c6989041195a2203c8dd7c9d8f40232b81834cb9063a987c37645dad1d257f' != 'sha256:46c6989041195a2203c8dd7c9d8f40232b81834cb9063a987c37645dad1d257f'
  FAILED plugins/superheroes/lib/tests/test_cloud_dependency_hook_2009.py::test_declining_the_offer_after_saving_its_inputs_makes_a_lockfile_change_ask_for_a_re_paste
  1 failed, 106 deselected in 1.28s
  ```
- **Restore:** the inverse edit, `None` back to `inputs`.
- **Restore receipt:** `git diff --stat -- plugins/superheroes/lib/cloud_setup_text.py` after restore
  printed nothing (no change to the file).
- **Raw green:** `1 passed, 106 deselected in 1.34s`
