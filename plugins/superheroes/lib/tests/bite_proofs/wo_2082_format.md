# #2082 bite-proof — implementer orders carry the bite-proof record format inline

**Provenance:** the light-lane builder session for #2082 (claude, opus 5.5), orchestrator-typed;
every run below is that session's own, in detached probe worktrees of its own under session
scratch (never the build tree).

**Heads.** BP-1..7 were run at `ca101136b`; BP-8..11 at `da01e4380`, the final code head. The only
change between the two heads is two comment lines in `engine_dispatch.py` and `native_engine.py`;
`lib/bite_proof_format.py` and every test file are byte-identical across them (`git diff --quiet
da01e4380 -- lib/bite_proof_format.py lib/tests` exit 0). Every green below was re-run on
`da01e4380`.

**Method.** One neutralization live at a time, applied and reverted through the host's edit action
by the exact inverse edit; the probe tree's `git diff` was printed before every red run and showed
exactly that edit. Tests selected by exact node id. Red output is quoted as its decisive lines
(the `>`/`E` lines and the count); nothing else was elided. Greens were made together on the
clean trees after every restore (`git status --porcelain` empty in both probe trees), disclosed
here as one green run covering every element.

Command shape (in the probe tree):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node id> -q -p no:cacheprovider
```

## Declared guarded elements

| id | element | axis | detector |
|---|---|---|---|
| BP-1 | `bite_proof_format.py` `RECORD_END` cut | drift: every record field reaches the inserted text | `test_drift_every_record_field_appears_verbatim` |
| BP-2 | `DISCLOSURE_END` cut | drift: every cannot-produce shape reaches the inserted text | `test_drift_every_cannot_produce_shape_appears_verbatim` |
| BP-3 | `format_text` reads the given rubric file | source: generated from the file, never a kept copy | `test_generated_text_follows_the_rubric_file` |
| BP-4 | `asks_for_record` masks the implementer template | mapping: only authored text asks | `test_template_copy_alone_never_asks` |
| BP-5 | `_ASKS` matches both spellings | mapping: `bite proof` asks too | `test_asks_on_either_spelling_and_not_otherwise` |
| BP-6 | `block_for` refuses when the format cannot be cut | refusal | `test_unreadable_rubric_refuses_*` (unit), the two chokepoint refusal tests |
| BP-7 | `_cut` start-marker uniqueness | refusal: a doubled marker never guesses | `test_unreadable_rubric_refuses_when_a_marker_is_missing_or_doubled` |
| BP-8 | `engine_dispatch._open_write_run` inserts the block | insertion | `test_write_run_stages_the_bite_proof_format_after_an_order_that_asks` |
| BP-9 | `_open_write_run` returns the refusal | refusal | `test_write_run_refuses_an_order_that_asks_when_the_rubric_is_unreadable` |
| BP-10 | `native_engine._cmd_open` writes the block | insertion | `test_open_records_the_bite_proof_format_after_an_order_that_asks` |
| BP-11 | `_cmd_open` refuses | refusal | `test_open_refuses_an_order_that_asks_when_the_rubric_is_unreadable` |

## Records

**BP-1.** Neutralization: `RECORD_END = "**Where each part lives"` → `RECORD_END = "- **raw green**"`.
Red: `E assert '- **raw green** — output after restore.' in "## Bite-proof record format ..."` /
`1 failed`. Restore: inverse edit; restored line `RECORD_END = "**Where each part lives"`.

**BP-2.** Neutralization: `DISCLOSURE_END = "\n## "` → `DISCLOSURE_END = "\n**Unrunnable here.**"`.
Red: `E assert '**Unrunnable here.** The detector is expected to bite, ...' in "## Bite-proof record
format ..."` / `1 failed`. Restore: inverse edit; restored line `DISCLOSURE_END = "\n## "`.

**BP-3.** Neutralization: `with open(path or RUBRIC_PATH, ...)` → `with open(RUBRIC_PATH, ...)`.
Red: `E assert '- **novel field** — planted by this test.' in "## Bite-proof record format ..."` /
`1 failed`. Restore: inverse edit; restored line `with open(path or RUBRIC_PATH, encoding="utf-8") as fh:`.

**BP-4.** Neutralization: `masked, _ = order_lint.mask_template(order_text)` → `masked = order_text`.
Red: `E AssertionError: assert ('## Bite-pro...ipt**.', None) == ('', None)`. Restore: inverse edit;
restored line `masked, _ = order_lint.mask_template(order_text)`.

**BP-5.** Neutralization: `r"bite[- ]proof"` → `r"bite-proof"`. Red: `E assert False` /
`E + where False = <built-in method startswith ...>(...)` on `''.startswith` / `1 failed`.
Restore: inverse edit; restored line `_ASKS = re.compile(r"bite[- ]proof", re.IGNORECASE)`.

**BP-6.** Neutralization: in `block_for`, `return None, REASON_UNREADABLE` → `return "", None`.
Red (4 detectors, one run): `test_unreadable_rubric_refuses_an_order_that_asks` `E AssertionError:
assert ('', None) == (None, 'bite-...t-unreadable')`; `..._missing_or_doubled` the same;
`test_write_run_refuses_...` `E AssertionError: assert (True, '', 'R... met none.\n') == (False,
'bite...adable', None)`; `test_open_refuses_...` `E assert 0 == 1` / `4 failed`. Restore: inverse
edit; restored line `return None, REASON_UNREADABLE`.

**BP-7.** Neutralization: `if i < 0 or text.find(start, i + 1) >= 0:` → `if i < 0:`. Red:
`> assert BPF.block_for("Return a bite-proof record.", path=str(path)) == (` / `E AssertionError:
assert ('## Bite-pro...ipt**.', None) == (None, 'bite-...t-unreadable')` / `1 failed` — the
doubled-marker case (the missing-marker case still refuses on its absent end marker). Restore:
inverse edit; restored line `if i < 0 or text.find(start, i + 1) >= 0:`.

**BP-8.** Neutralization: `if bite_proof_block:` → `if False:` (the `prefix + bite_proof_block`
guard in `_open_write_run`). Red: `> assert staged.startswith(head)` / `E assert False` /
`1 failed`. Restore: inverse edit; restored line `if bite_proof_block:`.

**BP-9.** Neutralization: `if bite_proof_reason:` → `if False:` in `_open_write_run`. Red:
`E AssertionError: assert (True, '', 'R... met none.\n') == (False, 'bite...adable', None)` /
`1 failed`. Restore: inverse edit; restored line `if bite_proof_reason:`.

**BP-10.** Neutralization: `if bite_proof_block:` → `if False:` before the native prompt's block
write. Red: `> assert prompt.endswith("**who owns the outstanding receipt**.\n")` /
`E AssertionError: assert False` / `1 failed`. Restore: inverse edit; restored line
`if bite_proof_block:`.

**BP-11.** Neutralization: `if bite_proof_reason:` → `if False:` in `_cmd_open`. Red:
`> assert code == 1` / `E assert 0 == 1` / `1 failed`. Restore: inverse edit; restored line
`if bite_proof_reason:`.

## Restore receipt and green

`git status --porcelain` empty in both probe trees after the last restore (`ca101136b` and
`da01e4380`). Green on `da01e4380`, all 13 node ids of the three detector groups:
`13 passed in 6.71s`.
