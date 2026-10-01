# WO-D #1554 bite-proof record: `seat_map compose` author family is the implementation engine's family

Single test node (`pytest <file>::<name> -q -p no:xdist`), neutralized by a targeted edit and restored by the inverse edit.

## Guarded element: `seat_map.py` `main()` author-family resolution for `--implementation-engine claude` (test_cli_compose_claude_impl_openai_host_author_is_anthropic)

Axis: the author family is the engine's family, not the host's.

Neutralization: in `lib/seat_map.py` `main()`, replaced the single `author_family = model_registry.family_for("code-fixer", impl_engine)` line with
`if impl_engine == "claude": author_family = host_fam or claude_host_fam` / `else: author_family = model_registry.family_for("code-fixer", impl_engine)`.

Red:

```
>       assert receipt["authorFamily"] == "anthropic"
E       AssertionError: assert 'openai' == 'anthropic'
E         - anthropic
E         + openai
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_cli_compose_claude_impl_openai_host_author_is_anthropic
1 failed in 0.29s
```

Restore: the inverse edit removed the `if impl_engine == "claude":` branch; the line
`            author_family = model_registry.family_for("code-fixer", impl_engine)` followed by `            if author_family is None:` sits at lines 1369-1370 again.

Green:

```
.                                                                        [100%]
1 passed in 1.68s
```
