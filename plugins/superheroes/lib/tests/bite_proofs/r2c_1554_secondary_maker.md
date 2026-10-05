# R2-C #1554 bite-proof record: secondary maker family excluded from panel seats

Single test node (`pytest <file>::<name> -q -p no:xdist`), neutralized by a targeted edit and restored by the inverse edit.

## Guarded element: `seat_map.py` `build()` maker filter at line ~690 (secondary-maker exclusion)

Axis: a lens seat never carries the secondary maker family while another family is live.

Neutralization: removed the merge of `extra_maker_families` into `excluded_makers` so the filter excludes only `author_family`:

```python
            excluded_makers = {author_family}
```

(the `if extra_maker_families: excluded_makers |= extra_maker_families` block removed).

Red:

```
>           assert fam not in ("anthropic", "openai"), (seat, fam)
E           AssertionError: ('premortem-reviewer', 'openai')
E           assert 'openai' not in ('anthropic', 'openai')

FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_cli_compose_claude_impl_openai_host_author_is_anthropic
1 failed in 0.36s
```

Restore: re-added:

```python
            if extra_maker_families:
                excluded_makers |= extra_maker_families
```

after `excluded_makers = {author_family}`.

Green:

```
.                                                                        [100%]
1 passed in 0.19s
```
