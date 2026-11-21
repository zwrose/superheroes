# Bite-proof record: wo3_2587_leftover_surfaces

Detectors: `plugins/superheroes/lib/tests/test_leftover_surfaces_2587.py` (G1-G3) and
`plugins/superheroes/lib/tests/test_decision_point_census.py` (G4).

Each neutralization is one targeted edit made with the edit tool and undone by the inverse edit
(never `git checkout`, `restore`, `reset` or `stash`). Every run was
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo3-2587-pyc -m pytest <file> -q`. Raw captures are
trimmed to the decisive lines (the `UV_NATIVE_TLS` warning line, the repeated source listing of each
failing test and tmp-path noise are elided); nothing in them needed redaction. Absolute tmp paths are
shortened with `...`.

The restore receipt for all four is the restored lines quoted back from the final tree (quoted after
G4's green run):

- `lib/session_context.py:352`: `            _Rec("Leftover settings copies", leftover_settings_notice(cwd), "/superheroes:configure"),`
- `lib/configure_route.py:81`: `    if files:`
- `lib/configure_view.py:659`: `    if leftovers and leftovers.get("files"):`
- `skills/configure/reference/fix.md:142`: `<!-- /decision-point: id=configure-fix-retire-leftovers -->`

## G1 - the session-start record (`session_context.assemble`)

- **Axis:** a project with leftover settings copies gets a `### Leftover settings copies` section in the bootstrap block, and a broken probe leaves a stderr breadcrumb only.
- **Neutralization:** the `_Rec("Leftover settings copies", ...)` line in `assemble` replaced by `# NEUTRALIZED _Rec(...)` (commented out).
- **Raw red:** `3 failed, 3 passed`. Failures:
  - `test_global_leftovers_reach_all_three_surfaces`: `assert '### Leftover settings copies' in "## Superheroes session bootstrap ..."` (AssertionError, `_assert_surfaces_list`).
  - `test_in_repo_leftovers_reach_all_three_surfaces`: the same assertion.
  - `test_raising_probe_prints_nothing_and_routing_continues`: `assert 'superheroes bootstrap: Leftover settings copies — RuntimeError' in ''` (no breadcrumb, since the probe is never called).
- **Restore:** the inverse edit put the original `_Rec` line back.
- **Raw green:** `6 passed in 4.26s`.

## G2 - the route's leftover step (`configure_route.route`, step 5)

- **Axis:** with no structural signal, a project with leftover copies routes to `fix` with the leftover reason.
- **Neutralization:** `    if files:` replaced by `    if files and False:  # NEUTRALIZED`.
- **Raw red:** `2 failed, 4 passed`. Failures: `test_global_leftovers_reach_all_three_surfaces` and `test_in_repo_leftovers_reach_all_three_surfaces`, each `assert routed["path"] == "fix"` -> `AssertionError: assert 'view' == 'fix'`.
- **Restore:** the inverse edit put `    if files:` back.
- **Raw green:** `6 passed in 4.24s`.

## G3 - the view section (`configure_view.render`)

- **Axis:** the one-screen view shows a `## Leftover settings copies` block when any exist.
- **Neutralization:** `    if leftovers and leftovers.get("files"):` replaced by `    if False and leftovers and leftovers.get("files"):  # NEUTRALIZED`.
- **Raw red:** `2 failed, 4 passed`. Failures: `test_global_leftovers_reach_all_three_surfaces` and `test_in_repo_leftovers_reach_all_three_surfaces`, each `assert VIEW_HEADING in view` -> `AssertionError: assert '## Leftover settings copies' in '# superheroes — project calibration ...'`.
- **Restore:** the inverse edit put the original condition back.
- **Raw green:** `6 passed in 4.44s`.

## G4 - the fix page's decision-point block (`skills/configure/reference/fix.md`)

- **Axis:** the `configure-fix-retire-leftovers` gate is a well-formed decision-point block the census enforces.
- **Neutralization:** the closing marker line `<!-- /decision-point: id=configure-fix-retire-leftovers -->` deleted.
- **Raw red** (`test_decision_point_census.py` alone): `1 failed, 21 passed`.
  ```
  FAILED plugins/superheroes/lib/tests/test_decision_point_census.py::test_decision_blocks_well_formed
  E       AssertionError: #1144 decision block well-formedness violations. Every hit:
  E         skills/configure/reference/fix.md:122: unmatched decision-point open id='configure-fix-retire-leftovers'
  ```
- **Restore:** the inverse edit put the closing marker line back (between `Follow-up: ` and `**Read the result`).
- **Raw green:** `22 passed in 0.48s`.

## Not guarded by a neutralization

`test_structural_fix_outranks_the_leftover_step` (a structural signal still wins over the leftover step) and `test_no_leftovers_leaves_every_surface_as_it_was` (byte-identical surfaces with nothing left over) were not given a neutralization of their own: the order's declared guarded-element set is G1-G4 only. Their protection is therefore unproven by this record.
