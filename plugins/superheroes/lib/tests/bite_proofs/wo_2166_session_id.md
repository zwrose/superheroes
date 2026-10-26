# Bite-proof record: #2166 `cloud_relay.py compose` refuses a session id where it needs the name

Detector under proof: the two tests added in `plugins/superheroes/lib/tests/test_cloud_relay.py`,
`test_compose_refuses_a_session_id_and_names_where_to_read_the_name` and
`test_compose_still_accepts_a_name_and_every_other_value`.
Guarded code: `plugins/superheroes/lib/cloud_relay.py` `compose`, the line
`if session.startswith(SESSION_ID_PREFIX):`.
Base: `895bf507` (the axis-line commit). Every neutralization was a targeted edit through the
host's edit tool, undone by the inverse edit before the next element. No `git checkout`,
`restore`, `reset` or `stash` was used. The detector was not edited.
Command for every run below (worktree root):
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest plugins/superheroes/lib/tests/test_cloud_relay.py -q -p no:cacheprovider -k "session_id or every_other_value"`.
Captures are trimmed to their decisive lines (the progress line, failure heads, the summary); the
uv deprecation warning line is dropped. Nothing was redacted.

## G1 refusal: a `session_` id is refused

- **Guarded element:** the `compose` guard line; axis: a value opening with `session_` refuses
  `session-id-not-name` (with `session` and `message`) and writes no state.
- **Neutralization:** `    if session.startswith(SESSION_ID_PREFIX):` →
  `    if False and session.startswith(SESSION_ID_PREFIX):`.
- **Raw red:**

```
F.....                                                                   [100%]
>       assert out["ok"] is False and out["reason"] == "session-id-not-name"
E       assert (True is False)
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_compose_refuses_a_session_id_and_names_where_to_read_the_name
1 failed, 5 passed, 102 deselected in 0.61s
```

- **Restore:** the inverse edit, back to `    if session.startswith(SESSION_ID_PREFIX):`.
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/cloud_relay.py` printed
  nothing (exit 0).
- **Raw green:** `6 passed, 102 deselected in 0.59s`

## G2 boundary: the match is case-sensitive and needs the underscore

- **Guarded element:** the same guard line; axis: only the exact, case-sensitive `session_`
  prefix refuses, so `Session_x` and a bare `session` still compose.
- **Neutralization:** `    if session.startswith(SESSION_ID_PREFIX):` →
  `    if session.lower().startswith(SESSION_ID_PREFIX[:-1]):`.
- **Raw red:**

```
E       assert False is True
E       assert False is True
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_compose_still_accepts_a_name_and_every_other_value[Session_x]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_compose_still_accepts_a_name_and_every_other_value[session]
2 failed, 4 passed, 102 deselected in 1.46s
```

- **Restore:** the inverse edit, back to `    if session.startswith(SESSION_ID_PREFIX):`.
- **Restore receipt:** `git status --porcelain plugins/superheroes/lib/cloud_relay.py` printed
  nothing (exit 0).
- **Raw green:** `6 passed, 102 deselected in 0.53s`

## G3 boundary: only a leading `session_` refuses

- **Guarded element:** the same guard line; axis: a `session_` inside the value (`my-session_1`)
  still composes.
- **Neutralization:** `    if session.startswith(SESSION_ID_PREFIX):` →
  `    if SESSION_ID_PREFIX in session:`.
- **Raw red:**

```
E       assert False is True
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_compose_still_accepts_a_name_and_every_other_value[my-session_1]
1 failed, 5 passed, 102 deselected in 0.55s
```

- **Restore:** the inverse edit, back to `    if session.startswith(SESSION_ID_PREFIX):`.
- **Restore receipt:** `git status --porcelain` over the worktree printed nothing (exit 0).
- **Raw green:** `6 passed, 102 deselected in 0.49s`

The `issue-2166-3fa9c1d2` and `builder-1748` cases are the plain acceptance rows; each of the three
neutralizations leaves them green, and no neutralization makes them the only red, so they are
covered by the composing path the original test file already exercises, not by a proof of their own.
