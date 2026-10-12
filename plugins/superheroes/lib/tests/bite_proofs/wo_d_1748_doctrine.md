# Bite-proof: wave-watch verb-list drift check after the anchor change

Guarded element (one): `test_wave_watch_verbs_in_wave_watch_doc` in `plugins/superheroes/lib/tests/test_ssot_drift.py`, which compares the verbs `wave-watch.md` lists after `It has three verbs:` with the sub-commands `wave_watch.py` registers. Axis: the documented verb list matches the CLI after the anchor literal changed from `It has two verbs:` to `It has three verbs:`.

## Neutralization

In `plugins/superheroes/skills/showrunner/reference/wave-watch.md`, deleted the whole `note-answered` bullet from the verb list (the four lines from `- **`note-answered`** — not a watch: ...` to `... or `store-unresolvable`.`).

## Red

Command: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_ssot_drift.py::test_wave_watch_verbs_in_wave_watch_doc" -q -p no:cacheprovider`

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_wave_watch_verbs_in_wave_watch_doc ____________________
E       AssertionError: wave-watch.md verb vocabulary drift from wave_watch CLI — missing from doc: ['note-answered']; present in doc but not in home: []
E       assert (not ['note-answered'])

plugins/superheroes/lib/tests/test_ssot_drift.py:599: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_wave_watch_verbs_in_wave_watch_doc
1 failed in 0.72s
```

(The source lines the runner echoed between the header and the `E` lines are the test body and are omitted here; the full output is in the dispatch return.)

## Restore

Inverse edit: put the four-line `note-answered` bullet back directly after the `run` bullet's last line (`  waiting, then prints one JSON line on stdout and exits. It does **not** re-arm.`). Restored lines:

```
- **`note-answered`** — not a watch: `--repo-root` and `--comment-id N` record a builder note's
  comment as answered, so `builder-note` stops surfacing it. It prints one JSON line on stdout and
  exits 1 on a refusal: `comment-id-invalid`, `note-answers-unreadable` (the record is never
  overwritten), or `store-unresolvable`.
```

## Green

Same command:

```
.                                                                        [100%]
1 passed in 3.01s
```
