---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: codex-and-cursor-as-review-and-build-engines-5b60ca
issue: 38
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-30"
updated: "2026-07-01"
---
# Codex and Cursor as review and build engines — Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase — **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: large`. Advance to Build
> only once `gates.review: passed`.

**Goal:** Add an owner-chosen, per-role engine axis — a reviewer engine and an implementation engine, each `claude`/`codex`/`cursor`, chosen independently, default `claude` — layered *above* the existing model-tier resolver: review runs on the chosen reviewer engine (read-only, standard findings form), while the build and the mechanical fixes (including review-code's own auto-fix) run on the chosen implementation engine (verify-gated, audited, isolated to the managed worktree), with the whole axis failing open to Claude.

**Architecture:** A leaf-adapter swap *above* `model_tier`, spine byte-unchanged. `engine_pref` (py + js twin) resolves which engine + what effort a role runs at, fail-open to claude; `core.md`'s machine block persists `enginePreferences {reviewer, implementation}` (schemaVersion 1→2). `engine_adapter.py` deterministically builds each CLI's argv, parses its structured output (scrubbing external free-text at that trust boundary), and is the *sole committer* for external writes (Task-Id-trailered, per-dispatch preSHA fold). `engine_dispatch.js` is the single spine leaf that shells the external CLI via the existing command-runner, journals every `external_dispatch`, and returns the *same result shape* the native worker returns — so `reviewPanel`, `build_phase`, the verify-gate, and the journal are reused unchanged. `configure` onboards availability detection, the per-role preference, the owner-granted write authorization (shown, never applied), and a test dispatch.

**Tech Stack:** Python 3 stdlib only; Node for the JS twins + bundled spine + parity harness; pytest + Node smoke tests; git for the effectful commit-discipline tests. External CLIs: Codex (`codex exec`, reasoning-effort tiers) and Cursor (`cursor-agent`, composer). This is a dogfooding change to superheroes' own plugin code.

## Global Constraints

Verbatim project-wide rules every task in this doc must honor:

- **Conventional Commits, scoped to `superheroes`:** most commits are `feat(superheroes): …` (this is a user-facing feature); a test-only or docs-only task may use `test(superheroes): …` / `docs(superheroes): …` as appropriate. The scope is always `superheroes`. CI gates the PR *title* (a single `feat(superheroes): …`), and the per-task commits are squashed at merge.
- **Do NOT hand-edit the plugin version.** `plugins/superheroes/.claude-plugin/plugin.json` `version` is advanced only by release-please through the release PR — never touch it in a feature task.
- **Python stdlib only.** No new third-party dependencies. (`jsonschema` is already a test dep; do not add others.)
- **Fail-OPEN engine *selection* / fail-CLOSED external *result*.** `resolve_engine` / `resolve_effort` / `resolve_timeout` / `load_engine_prefs` / `engine_detect.probe` / `implementation_dispatch_allowed` never raise — a bad/absent/unavailable engine silently degrades to claude. A *completed* external result that is unsound (verify-fail, unauditable, unreadable) fails closed — but that gating lives in the JS dispatch/build tasks (Tasks 10-11); these resolvers only return the structured signals those tasks key on.
- **Module naming:** the argv/parse core is `engine_adapter.py` (test `test_engine_adapter.py`), NOT `engine_cli.py` — `lib/engine.py` + `lib/tests/test_engine_cli.py` are test-pilot's manifest system and must not be reused.
- **CI (run all before pushing):**
  ```
  python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_hosts.py && python3 .github/scripts/validate_skills.py && python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
  ```
- **Test loading idiom:** `plugins/superheroes/lib/tests/conftest.py` already inserts `lib/` onto `sys.path`, so lib tests `import engine_pref` (etc.) directly; run pytest with cwd anywhere the conftest is discovered. Effectful git tests mirror `test_buildtree_effectful.py`.
- **Repo root** for all commands below: `/path/to/home/superheroes/.claude/worktrees/adoring-lehmann-b2cf0b`.

---

---

### Task 1

`engine_pref.py` — the pure fail-open resolvers (`resolve_engine`, `resolve_effort`, `resolve_timeout`) + the `engine_pref.js` twin + parity fixtures + registration + unit tests. Mirrors `model_tier`'s parity-locked pattern exactly.

**Files:**
- Create: `plugins/superheroes/lib/engine_pref.py`
- Create: `plugins/superheroes/lib/engine_pref.js`
- Create: `plugins/superheroes/lib/tests/test_engine_pref.py`
- Create: `plugins/superheroes/lib/tests/parity/engine_pref/resolveEngine/*.json` (fixtures)
- Create: `plugins/superheroes/lib/tests/parity/engine_pref/resolveEffort/*.json` (fixtures)
- Create: `plugins/superheroes/lib/tests/parity/engine_pref/resolveTimeout/*.json` (fixtures — M4)
- Modify: `plugins/superheroes/lib/tests/test_parity.py` — register `engine_pref` in `PARITY_TWINS` (three rows: resolveEngine, resolveEffort, resolveTimeout) and `PARITY_TARGET_MODULES` (lines 22-52).

**Interfaces:**
- Produces (Python, `engine_pref.py`):
  - `resolve_engine(role_kind, prefs) -> "claude"|"codex"|"cursor"` — `role_kind ∈ {"review","build","fix"}`; `review`→`prefs["reviewer"]`, `build`|`fix`→`prefs["implementation"]`. Missing/unknown/malformed/non-dict `prefs`, or a resolved value not in the engine set → `"claude"` (fail-open, never raises).
  - `resolve_effort(engine, role_kind, overrides=None) -> str|None` — defaults: `codex`→`"high"` for `review`/`build`, `"low"` for `fix`; `cursor`→`"composer"` (all roles); `claude`→`None`. `overrides = {role_kind: effort_token}`; a valid non-empty str override for `role_kind` wins; malformed→default. Never raises.
  - `resolve_timeout(overrides=None) -> int` — `DEFAULT_STALL_LIMIT_SECONDS = 300`; `overrides={"timeout": int}`; a valid positive int wins; else default. Always finite, never raises.
  - Module constants: `ENGINES = ("claude", "codex", "cursor")`, `DEFAULT_STALL_LIMIT_SECONDS = 300`.
- Produces (JS, `engine_pref.js`): `resolveEngine(roleKind, prefs)`, `resolveEffort(engine, roleKind, overrides)`, `resolveTimeout(overrides)` — own-key membership via `hasOwn` (mirror `model_tier.js`); also exports `DEFAULT_STALL_LIMIT_SECONDS`. Parity fns = `resolveEngine`, `resolveEffort`, `resolveTimeout` (M4: the duplicated 300s default is twin-guarded).
- Consumes: nothing (pure leaf).

**Steps:**

- [ ] **Step 1:** Write the failing test file `plugins/superheroes/lib/tests/test_engine_pref.py`:
   ```python
   import importlib.util
   import json
   import os

   _HERE = os.path.dirname(os.path.abspath(__file__))


   def _load():
       spec = importlib.util.spec_from_file_location(
           "engine_pref", os.path.join(_HERE, "..", "engine_pref.py"))
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod


   EP = _load()


   def test_resolve_engine_maps_role_to_key():
       prefs = {"reviewer": "codex", "implementation": "cursor"}
       assert EP.resolve_engine("review", prefs) == "codex"
       assert EP.resolve_engine("build", prefs) == "cursor"
       assert EP.resolve_engine("fix", prefs) == "cursor"   # fix follows implementation


   def test_resolve_engine_mixed_reviewer_ne_implementation():
       prefs = {"reviewer": "codex", "implementation": "cursor"}
       assert EP.resolve_engine("review", prefs) == "codex"
       assert EP.resolve_engine("build", prefs) == "cursor"


   def test_resolve_engine_falls_open_to_claude():
       assert EP.resolve_engine("review", {}) == "claude"                    # absent key
       assert EP.resolve_engine("review", {"reviewer": "bogus"}) == "claude" # unknown engine
       assert EP.resolve_engine("review", {"reviewer": 7}) == "claude"        # non-str
       assert EP.resolve_engine("review", "not-a-dict") == "claude"           # non-dict prefs
       assert EP.resolve_engine("review", None) == "claude"
       assert EP.resolve_engine("bogus-role", {"reviewer": "codex"}) == "claude"  # unknown role


   def test_resolve_effort_defaults():
       assert EP.resolve_effort("codex", "review") == "high"
       assert EP.resolve_effort("codex", "build") == "high"
       assert EP.resolve_effort("codex", "fix") == "low"
       assert EP.resolve_effort("cursor", "review") == "composer"
       assert EP.resolve_effort("cursor", "fix") == "composer"
       assert EP.resolve_effort("claude", "build") is None
       assert EP.resolve_effort("bogus", "build") is None   # unknown engine → None


   def test_resolve_effort_override_wins_else_default():
       assert EP.resolve_effort("codex", "review", {"review": "medium"}) == "medium"
       assert EP.resolve_effort("codex", "review", {"review": ""}) == "high"    # empty → default
       assert EP.resolve_effort("codex", "review", {"review": 7}) == "high"      # non-str → default
       assert EP.resolve_effort("codex", "review", "not-a-dict") == "high"
       assert EP.resolve_effort("codex", "review", ["review"]) == "high"         # list (non-dict) → default


   def test_resolve_timeout_default_and_override():
       assert EP.resolve_timeout() == EP.DEFAULT_STALL_LIMIT_SECONDS == 300
       assert EP.resolve_timeout({"timeout": 5}) == 5
       assert EP.resolve_timeout({"timeout": 0}) == 300       # non-positive → default
       assert EP.resolve_timeout({"timeout": -1}) == 300
       assert EP.resolve_timeout({"timeout": "5"}) == 300      # non-int → default
       assert EP.resolve_timeout("not-a-dict") == 300


   def test_never_raises_on_garbage():
       assert EP.resolve_engine(None, None) == "claude"
       assert EP.resolve_effort(None, None, None) is None
       assert EP.resolve_timeout(None) == 300
   ```
- [ ] **Step 2:** Run it to see it FAIL (module does not exist yet):
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py -q
   ```
   Expected: collection error / `ModuleNotFoundError: No module named 'engine_pref'` (or spec load error) — RED.
- [ ] **Step 3:** Implement `plugins/superheroes/lib/engine_pref.py` (complete):
   ```python
   """Band-wide engine-preference policy: which ENGINE runs a role (claude|codex|cursor)
   and at what effort — the axis ORTHOGONAL to model_tier's model choice. Pure +
   deterministic. Fail-OPEN to claude — a wrong/absent/unavailable engine is a cost concern,
   never a safety one (exactly model_tier.py's posture). load_engine_prefs (Task 3) reads
   core.md's enginePreferences; these resolvers never touch disk."""
   import json
   import sys

   _MISSING = object()

   ENGINES = ("claude", "codex", "cursor")

   # role_kind -> the enginePreferences key it reads.
   _ROLE_KEY = {"review": "reviewer", "build": "implementation", "fix": "implementation"}

   # effort defaults per engine. codex is effort-tiered; cursor is one composer model
   # (FR-10, exempt); claude defers to model_tier (None).
   _CODEX_EFFORT = {"review": "high", "build": "high", "fix": "low"}
   _CURSOR_EFFORT = "composer"

   DEFAULT_STALL_LIMIT_SECONDS = 300


   def resolve_engine(role_kind, prefs):
       """Return the engine for `role_kind`, fail-open to 'claude'. A missing/unknown role,
       a non-dict `prefs`, an absent key, or a value outside ENGINES all fall open."""
       key = _ROLE_KEY.get(role_kind)
       if key is None:
           return "claude"
       if not isinstance(prefs, dict):
           return "claude"
       v = prefs.get(key)
       if isinstance(v, str) and v in ENGINES:
           return v
       return "claude"


   def resolve_effort(engine, role_kind, overrides=None):
       """Return the effort token for (engine, role_kind), or None (claude/unknown engine).
       A valid non-empty str override for role_kind wins; anything malformed falls to default."""
       if engine == "codex":
           default = _CODEX_EFFORT.get(role_kind, "high")
       elif engine == "cursor":
           default = _CURSOR_EFFORT
       else:
           return None  # claude (model_tier governs) or an unknown engine
       if isinstance(overrides, dict):
           v = overrides.get(role_kind, _MISSING)
           if isinstance(v, str) and v.strip():
               return v.strip()
       return default


   def resolve_timeout(overrides=None):
       """The finite UFR-5 stall limit in seconds. A valid positive int override wins; else the
       finite default. Always returns a finite positive int, never raises."""
       if isinstance(overrides, dict):
           v = overrides.get("timeout", _MISSING)
           if isinstance(v, bool):
               return DEFAULT_STALL_LIMIT_SECONDS  # bool is an int subclass — reject it
           if isinstance(v, int) and v > 0:
               return v
       return DEFAULT_STALL_LIMIT_SECONDS
   ```
- [ ] **Step 4:** Run to see the resolver tests PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py -q
   ```
   Expected: all tests in the file PASS (green).
- [ ] **Step 5:** Write the failing JS-twin parity fixtures. Create `plugins/superheroes/lib/tests/parity/engine_pref/resolveEngine/` with these files (one JSON each):
   - `review_codex.json`: `{"input": ["review", {"reviewer": "codex", "implementation": "cursor"}], "expected": "codex"}`
   - `build_cursor.json`: `{"input": ["build", {"reviewer": "codex", "implementation": "cursor"}], "expected": "cursor"}`
   - `fix_follows_implementation.json`: `{"input": ["fix", {"reviewer": "codex", "implementation": "cursor"}], "expected": "cursor"}`
   - `absent_key.json`: `{"input": ["review", {}], "expected": "claude"}`
   - `unknown_engine.json`: `{"input": ["review", {"reviewer": "bogus"}], "expected": "claude"}`
   - `non_str.json`: `{"input": ["review", {"reviewer": 7}], "expected": "claude"}`
   - `non_dict_prefs.json`: `{"input": ["review", "not-a-dict"], "expected": "claude"}`
   - `unknown_role.json`: `{"input": ["bogus-role", {"reviewer": "codex"}], "expected": "claude"}`
   - `prototype_named_engine.json`: `{"input": ["review", {"reviewer": "constructor"}], "expected": "claude"}`

   And `plugins/superheroes/lib/tests/parity/engine_pref/resolveEffort/`:
   - `codex_review_high.json`: `{"input": ["codex", "review", null], "expected": "high"}`
   - `codex_fix_low.json`: `{"input": ["codex", "fix", null], "expected": "low"}`
   - `cursor_composer.json`: `{"input": ["cursor", "review", null], "expected": "composer"}`
   - `claude_none.json`: `{"input": ["claude", "build", null], "expected": null}`
   - `unknown_engine_none.json`: `{"input": ["bogus", "build", null], "expected": null}`
   - `override_wins.json`: `{"input": ["codex", "review", {"review": "medium"}], "expected": "medium"}`
   - `malformed_override_empty.json`: `{"input": ["codex", "review", {"review": ""}], "expected": "high"}`
   - `malformed_override_non_str.json`: `{"input": ["codex", "review", {"review": 7}], "expected": "high"}`
   - `override_list_is_default.json`: `{"input": ["codex", "review", ["review"]], "expected": "high"}`  # M3: a list (non-dict) override → default

   And `plugins/superheroes/lib/tests/parity/engine_pref/resolveTimeout/` (M4 — the duplicated 300s default is twin-guarded):
   - `default_no_overrides.json`: `{"input": [null], "expected": 300}`
   - `default_empty_overrides.json`: `{"input": [{}], "expected": 300}`
   - `positive_int_wins.json`: `{"input": [{"timeout": 5}], "expected": 5}`
   - `zero_is_default.json`: `{"input": [{"timeout": 0}], "expected": 300}`
   - `negative_is_default.json`: `{"input": [{"timeout": -1}], "expected": 300}`
   - `non_int_is_default.json`: `{"input": [{"timeout": "5"}], "expected": 300}`
   - `non_dict_is_default.json`: `{"input": ["not-a-dict"], "expected": 300}`
- [ ] **Step 6:** Register the twin in `plugins/superheroes/lib/tests/test_parity.py`. Add THREE rows to `PARITY_TWINS` (after the `("model_tier", …)` row, ~line 25) — the third (M4) twin-guards the duplicated 300s stall default:
   ```python
       ("engine_pref", "resolveEngine", "engine_pref", "resolve_engine"),
       ("engine_pref", "resolveEffort", "engine_pref", "resolve_effort"),
       ("engine_pref", "resolveTimeout", "engine_pref", "resolve_timeout"),
   ```
   And add `"engine_pref"` to `PARITY_TARGET_MODULES` (line 52), e.g. append `, "engine_pref"` before the closing `]`. (`PARITY_TARGET_MODULES` already lists `engine_pref` once for the module — the three twin rows all live under the same `engine_pref` stem, matching the self-enforcement clause (a) requirement that every twin fn dir has fixtures: `resolveEngine/`, `resolveEffort/`, and `resolveTimeout/` all now carry fixtures.)
- [ ] **Step 7:** Run parity to see it FAIL (no `engine_pref.js` yet, and the Python-oracle rows now demand it):
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q
   ```
   Expected: the `engine_pref/resolveEngine`, `engine_pref/resolveEffort`, and `engine_pref/resolveTimeout` `test_js_twin` params FAIL (`node` cannot `require('../engine_pref.js')`) — RED. (The `test_python_oracle` params for all three engine_pref fns should already PASS against the Python `resolve_engine`/`resolve_effort`/`resolve_timeout`.)
- [ ] **Step 8:** Implement `plugins/superheroes/lib/engine_pref.js` (complete twin):
   ```javascript
   // engine_pref.js — twin of engine_pref.resolve_engine / resolve_effort.
   // Pure + deterministic engine-preference resolver. Fail-OPEN to 'claude'.

   const ENGINES = ['claude', 'codex', 'cursor']
   const DEFAULT_STALL_LIMIT_SECONDS = 300

   const _ROLE_KEY = { review: 'reviewer', build: 'implementation', fix: 'implementation' }
   const _CODEX_EFFORT = { review: 'high', build: 'high', fix: 'low' }
   const _CURSOR_EFFORT = 'composer'

   // Own-key membership (mirror model_tier.js): JS `in`/bracket walk the prototype chain,
   // so a prototype-named engine/role ('constructor', 'toString') must not drift the result.
   function hasOwn(o, k) {
     return Object.prototype.hasOwnProperty.call(o, k)
   }

   function resolveEngine(roleKind, prefs) {
     if (!hasOwn(_ROLE_KEY, roleKind)) return 'claude'
     const key = _ROLE_KEY[roleKind]
     if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) return 'claude'
     if (!hasOwn(prefs, key)) return 'claude'
     const v = prefs[key]
     if (typeof v === 'string' && ENGINES.indexOf(v) !== -1) return v
     return 'claude'
   }

   function resolveEffort(engine, roleKind, overrides) {
     let def
     if (engine === 'codex') def = hasOwn(_CODEX_EFFORT, roleKind) ? _CODEX_EFFORT[roleKind] : 'high'
     else if (engine === 'cursor') def = _CURSOR_EFFORT
     else return null // claude or unknown engine
     if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, roleKind)) {
       const v = overrides[roleKind]
       if (typeof v === 'string' && v.trim()) return v.trim()
     }
     return def
   }

   // Twin of resolve_timeout: the finite UFR-5 stall limit. A valid positive int override wins; else the
   // finite default. bool is excluded (JS has no int/bool subtype trap, but mirror the Python guard's intent:
   // only a real positive integer number is honored). Always returns a finite positive int; never throws.
   function resolveTimeout(overrides) {
     if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, 'timeout')) {
       const v = overrides.timeout
       if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
     }
     return DEFAULT_STALL_LIMIT_SECONDS
   }

   module.exports = { resolveEngine, resolveEffort, resolveTimeout, ENGINES, DEFAULT_STALL_LIMIT_SECONDS }
   ```
- [ ] **Step 9:** Run the full parity + engine_pref suite to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_engine_pref.py -q
   ```
   Expected: all PASS — including all three self-enforcement clauses. Clause (a) holds (all THREE new twin/fn dirs — `resolveEngine/`, `resolveEffort/`, `resolveTimeout/` — have fixtures); clause (b) holds (`PARITY_TARGET_MODULES` now equals the twin stems including `engine_pref`); clause (c) checks the direction *bundled ⊆ targets* only, so a target that is not yet bundled is fine — `engine_pref` being absent from `bundle_showrunner.js` MODULES here does NOT trip clause (c). (Task 10 adds `engine_pref`/`engine_dispatch` to MODULES + regenerates the bundle; that is what makes them *bundled*, still consistent with clause (c).)
- [ ] **Step 10:** Commit:
    ```
    git add plugins/superheroes/lib/engine_pref.py plugins/superheroes/lib/engine_pref.js plugins/superheroes/lib/tests/test_engine_pref.py plugins/superheroes/lib/tests/parity/engine_pref plugins/superheroes/lib/tests/test_parity.py
    git commit -m "feat(superheroes): add engine_pref resolvers + JS parity twin"
    ```

---

### Task 2

`core_md.py` — add `enginePreferences {reviewer, implementation}` to the machine block and bump `SCHEMA_VERSION` 1→2, preserving the upgrade-in-memory / behind policy. Round-trip tests (incl. MIXED reviewer≠implementation), v1→v2 upgrade, v3 behind.

**Files:**
- Modify: `plugins/superheroes/lib/core_md.py` — `SCHEMA_VERSION` (line 20), `render_core` block (lines 30-34), `parse_core` return (lines 90-99), `read` return (lines 143-153), `_diff_proposals` compared fields (line 191).
- Modify: `plugins/superheroes/lib/tests/test_core_md.py` — the two schema tests that assert the current version + new round-trip tests.

**Interfaces:**
- Produces: `core_md.parse_core(text)` and `core_md.read(cwd, root)` now return an `"enginePreferences"` key — a dict `{"reviewer": str, "implementation": str}` when the block carries one, else `{}` (absent). `render_core(facts, …)` reads `facts.get("enginePreferences")` and writes it into the json block. `SCHEMA_VERSION == 2`.
- Note (FR-9 effort override, additive — NO extra schema bump): `enginePreferences` may OPTIONALLY carry an `"effort"` sub-map `{review?, build?, fix?}` alongside `reviewer`/`implementation`. Because `render_core`/`parse_core` write and read the whole `enginePreferences` dict verbatim (`dict(...)`), an `effort` key survives the round-trip automatically — the round-trip test below asserts it explicitly so a future refactor can't drop it. Task 3's `engine_pref_load.py` surfaces this sub-map (absent → `{}`) so Tasks 11/12 can source the owner's effort override.
- Consumes: nothing new (still `mode_registry`, `store_core`).
- Note (consumed by Task 3 and the JS startup load): `read(...)["enginePreferences"]` is `{}` when absent; `engine_pref.load_engine_prefs` normalizes it to `{"reviewer":"claude","implementation":"claude","effort":{}}`.

**Steps:**

- [ ] **Step 1:** Write failing tests — append to `plugins/superheroes/lib/tests/test_core_md.py`:
   ```python
   def test_render_parse_engine_preferences_roundtrip_mixed():
       # MIXED: reviewer != implementation (guards a same-engine-only fixture masking a routing bug).
       # Also carries an optional FR-9 effort sub-map — it must survive the round-trip unchanged.
       facts = {"verifyCommand": "npm test", "stackTags": ["node"],
                "threatModel": "x", "patterns": "",
                "enginePreferences": {"reviewer": "codex", "implementation": "cursor",
                                      "effort": {"review": "medium", "fix": "high"}}}
       text = CM.render_core(facts, "confirmed", "2026-06-30", "2026-06-30")
       assert "schemaVersion=2" in text
       got = CM.parse_core(text)
       assert got["schemaVersion"] == 2
       assert got["enginePreferences"] == {"reviewer": "codex", "implementation": "cursor",
                                           "effort": {"review": "medium", "fix": "high"}}


   def test_parse_absent_engine_preferences_is_empty_dict():
       facts = {"verifyCommand": "npm test", "stackTags": [], "threatModel": "", "patterns": ""}
       text = CM.render_core(facts, "provisional", "2026-06-30", "2026-06-30")
       assert CM.parse_core(text)["enginePreferences"] == {}


   def test_read_current_schema_is_two_with_engine_prefs(tmp_path):
       repo = str(tmp_path)
       store = str(tmp_path / "store")
       facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "x",
                "patterns": "", "enginePreferences": {"reviewer": "codex", "implementation": "claude"}}
       CM.write(repo, facts, "confirmed", root=store, now="2026-06-30")
       got = CM.read(repo, root=store)
       assert got["schemaVersion"] == 2 and got["behind"] is False
       assert got["enginePreferences"] == {"reviewer": "codex", "implementation": "claude"}
   ```
   Also update the two existing schema tests to reflect v2-as-current: in `test_render_then_parse_roundtrips` change the asserted provenance to `schemaVersion=2` and `got["schemaVersion"] == 1` to `== 2`; the `test_read_older_schema_upgraded_in_memory_no_writeback` (writes v0) and `test_read_newer_schema_behind_no_downgrade` (writes `SCHEMA_VERSION + 1` = v3) already reference `CM.SCHEMA_VERSION`, so they self-adjust — leave them.
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_core_md.py -q
   ```
   Expected: `test_render_parse_engine_preferences_roundtrip_mixed`, `test_parse_absent_engine_preferences_is_empty_dict`, `test_read_current_schema_is_two_with_engine_prefs`, and the edited `test_render_then_parse_roundtrips` FAIL (no `enginePreferences` key; `schemaVersion` still 1) — RED.
- [ ] **Step 3:** Implement the bump. In `core_md.py`, change line 20:
   ```python
   SCHEMA_VERSION = 2
   ```
- [ ] **Step 4:** In `render_core` (the `block = {...}` dict, lines 30-34) add the field:
   ```python
       block = {
           "schemaVersion": SCHEMA_VERSION,
           "verifyCommand": facts.get("verifyCommand"),
           "stackTags": list(facts.get("stackTags") or []),
           "enginePreferences": dict(facts.get("enginePreferences") or {}),
       }
   ```
- [ ] **Step 5:** In `parse_core`, add `enginePreferences` to the returned dict (after the `stackTags` line in the return, ~line 94):
   ```python
       prefs = block.get("enginePreferences")
       return {
           "schemaVersion": int(block["schemaVersion"]),
           "status": status,
           "verifyCommand": block.get("verifyCommand"),
           "stackTags": list(tags) if isinstance(tags, list) else [],
           "enginePreferences": dict(prefs) if isinstance(prefs, dict) else {},
           "threatModel": _section(text, "Threat model"),
           "patterns": _section(text, "Canonical patterns"),
           "created": created,
           "updated": updated,
       }
   ```
- [ ] **Step 6:** In `read`, thread it through the returned dict (add after the `stackTags` line, ~line 147):
   ```python
       return {
           "schemaVersion": effective,
           "status": facts["status"],
           "verifyCommand": facts["verifyCommand"],
           "stackTags": facts["stackTags"],
           "enginePreferences": facts["enginePreferences"],
           "threatModel": facts["threatModel"],
           "patterns": facts["patterns"],
           "behind": behind,
           "created": facts["created"],
           "updated": facts["updated"],
       }
   ```
- [ ] **Step 7:** In `_diff_proposals` (line 191), add `"enginePreferences"` to the compared fields tuple so a differing preference is proposed, not silently clobbered:
   ```python
       for field in ("verifyCommand", "stackTags", "threatModel", "patterns", "enginePreferences"):
   ```
- [ ] **Step 8:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_core_md.py -q
   ```
   Expected: all core_md tests PASS — the v1→v2 upgrade-in-memory test (writes v0 → stamped current=2, no writeback) and the newer-schema behind test (writes v3 → behind=True) still hold because they key off `CM.SCHEMA_VERSION`.
- [ ] **Step 9:** Run the broader lib suite to catch any consumer that hard-codes the old shape:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/ -q
   ```
   Expected: PASS. (If any test asserted `set(read(...)) == {...specific keys...}` it would surface here; none currently does — `read`'s consumers use named keys.)
- [ ] **Step 10:** Commit:
    ```
    git add plugins/superheroes/lib/core_md.py plugins/superheroes/lib/tests/test_core_md.py
    git commit -m "feat(superheroes): persist enginePreferences in core.md (schemaVersion 1->2)"
    ```

---

### Task 3

`engine_pref.load_engine_prefs(cwd, root)` reads `core_md.read` → `enginePreferences` (absent/None/error → both claude) + the `engine_pref_load.py` startup CLI that mirrors `model_tier_overrides.py`'s startup pipe.

**Files:**
- Modify: `plugins/superheroes/lib/engine_pref.py` — add `load_engine_prefs` + `import`.
- Create: `plugins/superheroes/lib/engine_pref_load.py` (startup CLI).
- Modify: `plugins/superheroes/lib/tests/test_engine_pref.py` — round-trip tests via a written core.md + a CLI test.

**Interfaces:**
- Produces: `engine_pref.load_engine_prefs(cwd, root=None) -> {"reviewer": str, "implementation": str, "effort": dict}`. Calls `core_md.read(cwd, root)`; normalizes each of `reviewer`/`implementation` through the same validation `resolve_engine` uses (value in `ENGINES` else `"claude"`); surfaces the optional FR-9 `effort` sub-map (`enginePreferences.get("effort")` when it is a dict, else `{}`); absent block / `None` / any error → `{"reviewer":"claude","implementation":"claude","effort":{}}`. Never raises.
- Produces: `python3 lib/engine_pref_load.py [--cwd .] [--root R]` → prints JSON `{"reviewer","implementation","effort"}` to stdout, exit 0 always (belt-and-suspenders fail-open → both `"claude"`, `effort` `{}`). This is what Task 12 loads once at startup into `globalThis.__SR_ENGINE_PREFS`; Tasks 11/12 source the owner's effort override from its `effort` sub-map (keyed by role_kind {review,build,fix}), NOT from the model-tier `__SR_OVERRIDES` map.
- Consumes: `core_md.read(cwd, root)` (Task 2's `enginePreferences` key), `engine_pref.ENGINES`.

**Steps:**

- [ ] **Step 1:** Write failing tests — append to `plugins/superheroes/lib/tests/test_engine_pref.py`:
   ```python
   import subprocess
   import sys

   _LIB = os.path.join(_HERE, "..")


   def _write_core_with_prefs(repo, prefs):
       import importlib.util as _u
       spec = _u.spec_from_file_location("core_md", os.path.join(_LIB, "core_md.py"))
       cm = _u.module_from_spec(spec)
       spec.loader.exec_module(cm)
       cm.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                       "patterns": "", "enginePreferences": prefs}, "confirmed",
                root=os.path.join(repo, "store"), now="2026-06-30")


   def test_load_engine_prefs_reads_core_md(tmp_path):
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "cursor"})
       got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
       assert got == {"reviewer": "codex", "implementation": "cursor", "effort": {}}


   def test_load_engine_prefs_absent_is_both_claude(tmp_path):
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {})   # core.md exists but no engine prefs
       assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
           {"reviewer": "claude", "implementation": "claude", "effort": {}}


   def test_load_engine_prefs_greenfield_is_both_claude(tmp_path):
       # no core.md at all → both claude (fail-open, never raises)
       assert EP.load_engine_prefs(str(tmp_path), root=str(tmp_path / "store")) == \
           {"reviewer": "claude", "implementation": "claude", "effort": {}}


   def test_load_engine_prefs_normalizes_bad_values(tmp_path):
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {"reviewer": "bogus", "implementation": "cursor"})
       assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
           {"reviewer": "claude", "implementation": "cursor", "effort": {}}


   def test_load_engine_prefs_surfaces_effort_submap_and_resolve_effort_honors_it(tmp_path):
       # FR-9 round-trip: an effort override written into core.md's enginePreferences.effort is
       # surfaced by load_engine_prefs and honored by resolve_effort keyed by role_kind.
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                     "effort": {"review": "medium", "fix": "high"}})
       got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
       assert got["effort"] == {"review": "medium", "fix": "high"}
       # resolve_effort keyed by role_kind reads THIS effort sub-map (not the model-tier overrides).
       assert EP.resolve_effort("codex", "review", got["effort"]) == "medium"   # override wins
       assert EP.resolve_effort("codex", "fix", got["effort"]) == "high"        # override wins
       assert EP.resolve_effort("codex", "build", got["effort"]) == "high"      # no override -> default


   def test_load_engine_prefs_effort_non_dict_normalizes_to_empty(tmp_path):
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                     "effort": "not-a-dict"})
       assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))["effort"] == {}


   def test_cli_engine_pref_load_emits_json(tmp_path):
       repo = str(tmp_path)
       _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "claude",
                                     "effort": {"build": "low"}})
       out = subprocess.run(
           [sys.executable, os.path.join(_LIB, "engine_pref_load.py"),
            "--cwd", repo, "--root", os.path.join(repo, "store")],
           capture_output=True, text=True)
       assert out.returncode == 0
       assert json.loads(out.stdout) == {"reviewer": "codex", "implementation": "claude",
                                         "effort": {"build": "low"}}
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py -k load_engine_prefs -q
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py -k cli_engine_pref_load -q
   ```
   Expected: `AttributeError: module 'engine_pref' has no attribute 'load_engine_prefs'` and the CLI test fails (no `engine_pref_load.py`) — RED.
- [ ] **Step 3:** Implement `load_engine_prefs` in `engine_pref.py`. Add the stdlib-path shim + import at the top of the module (after the existing imports):
   ```python
   import os

   _LIB_DIR = os.path.dirname(os.path.abspath(__file__))
   if _LIB_DIR not in sys.path:
       sys.path.insert(0, _LIB_DIR)
   ```
   Then add the function (after `resolve_timeout`):
   ```python
   def _normalize(engine):
       return engine if isinstance(engine, str) and engine in ENGINES else "claude"


   def load_engine_prefs(cwd, root=None):
       """Read core.md's enginePreferences via core_md.read; normalize each role to a valid engine
       (else 'claude'); surface the optional FR-9 `effort` sub-map (a dict, else {}); absent block /
       None / any error → both 'claude' + empty effort. Never raises."""
       degenerate = {"reviewer": "claude", "implementation": "claude", "effort": {}}
       try:
           import core_md
           rec = core_md.read(cwd, root)
       except Exception:
           return degenerate
       if not isinstance(rec, dict):
           return degenerate
       prefs = rec.get("enginePreferences")
       if not isinstance(prefs, dict):
           return degenerate
       effort = prefs.get("effort")
       return {"reviewer": _normalize(prefs.get("reviewer")),
               "implementation": _normalize(prefs.get("implementation")),
               "effort": dict(effort) if isinstance(effort, dict) else {}}
   ```
- [ ] **Step 4:** Implement `plugins/superheroes/lib/engine_pref_load.py` (complete startup CLI):
   ```python
   #!/usr/bin/env python3
   """Startup pipe: print core.md's enginePreferences as JSON for the JS spine to load once
   into globalThis.__SR_ENGINE_PREFS (mirrors model_tier_overrides.py's startup pattern).
   Belt-and-suspenders fail-open: ANY failure prints both 'claude'. Exit 0 always."""
   import argparse
   import json
   import os
   import sys

   _LIB_DIR = os.path.dirname(os.path.abspath(__file__))
   if _LIB_DIR not in sys.path:
       sys.path.insert(0, _LIB_DIR)


   def main(argv):
       ap = argparse.ArgumentParser(prog="engine_pref_load")
       ap.add_argument("--cwd", default=".")
       ap.add_argument("--root", default=None)
       args = ap.parse_args(argv[1:])
       degenerate = {"reviewer": "claude", "implementation": "claude", "effort": {}}
       try:
           import engine_pref
           prefs = engine_pref.load_engine_prefs(args.cwd, args.root)
           if not isinstance(prefs, dict):
               prefs = degenerate
       except Exception:
           prefs = degenerate
       sys.stdout.write(json.dumps(prefs) + "\n")
       return 0


   if __name__ == "__main__":
       raise SystemExit(main(sys.argv))
   ```
- [ ] **Step 5:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py -q
   ```
   Expected: all engine_pref tests PASS (resolvers + loaders + CLI).
- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/lib/engine_pref.py plugins/superheroes/lib/engine_pref_load.py plugins/superheroes/lib/tests/test_engine_pref.py
   git commit -m "feat(superheroes): load_engine_prefs from core.md + engine_pref_load startup CLI"
   ```

---

### Task 4

`journal.py` — add `"external_dispatch"` to `EVENT_TYPES` so the FR-6/UFR-6 audit line can be appended, AND extend the JS seam `journal_entry.py` with an optional `--event-type` (default `"phase_record"`, VALIDATED against `journal.EVENT_TYPES`) so the JS dispatch (Task 10) can write a first-class `external_dispatch` line. Test append+read + the unknown-type `DurableWriteError` still holds + the CLI `--event-type` path.

**Files:**
- Modify: `plugins/superheroes/lib/journal.py` — `EVENT_TYPES` set (lines 19-23).
- Modify: `plugins/superheroes/lib/journal_entry.py` — add the optional `--event-type` arg (default `phase_record`; back-compat: absent flag → phase_record).
- Modify: `plugins/superheroes/lib/tests/test_journal.py` — new test for the `external_dispatch` append + assert the unknown-type guard still fires + a `journal_entry.py --event-type external_dispatch` CLI test.

**Interfaces:**
- Produces: `journal.EVENT_TYPES` now contains `"external_dispatch"`. `journal.append(events_path, "external_dispatch", *, payload={"engine","effort","roleKind","verify","outcome"}, root=…)` writes the `payload` AS-IS (non-secret; `detail`/`world` remain scrubbed fail-closed). An unknown type still raises `DurableWriteError` (→ orchestrator parks, UFR-6).
- Produces: `python3 lib/journal_entry.py --work-item W --payload JSON [--event-type T]` — `--event-type` defaults to `"phase_record"` (back-compat), and is passed straight to `journal.append` as the event type, so an unknown value raises `DurableWriteError` → the existing `{ok:false, error}` / park path (UFR-6). Task 10 calls it with `--event-type external_dispatch`.
- Consumes: nothing new.

**Steps:**

- [ ] **Step 1:** Confirm the existing test file's load idiom, then write the failing test. Append to `plugins/superheroes/lib/tests/test_journal.py`:
   ```python
   def test_external_dispatch_event_appends_and_reads(tmp_path):
       import journal
       p = str(tmp_path / "events.jsonl")
       journal.append(p, "external_dispatch",
                      payload={"engine": "codex", "effort": "high", "roleKind": "build",
                               "verify": "passed", "outcome": "ok"},
                      root=str(tmp_path))
       evs = journal.read_events(p)
       assert len(evs) == 1
       ev = evs[0]
       assert ev["type"] == "external_dispatch"
       # payload is written AS-IS (non-secret; the plan's §4.6)
       assert ev["payload"] == {"engine": "codex", "effort": "high", "roleKind": "build",
                                "verify": "passed", "outcome": "ok"}


   def test_unknown_event_type_still_raises_durable_write_error(tmp_path):
       import journal
       import pytest
       p = str(tmp_path / "events.jsonl")
       with pytest.raises(journal.DurableWriteError):
           journal.append(p, "not_a_real_event", root=str(tmp_path))


   def test_journal_entry_cli_writes_external_dispatch_type(tmp_path, monkeypatch):
       # The JS seam (Task 10) shells journal_entry.py --event-type external_dispatch; the written
       # line's `type` must be external_dispatch (not the hardcoded phase_record).
       import json as _json
       import os as _os
       import subprocess as _sp
       import sys as _sys
       import control_plane
       import journal
       _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
       monkeypatch.chdir(tmp_path)   # journal_entry.py uses os.getcwd() for the control-plane paths
       out = _sp.run(
           [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
            "--work-item", "wi-x", "--event-type", "external_dispatch",
            "--payload", _json.dumps({"engine": "codex", "effort": "high", "roleKind": "build",
                                      "verify": "pending", "outcome": "ok"})],
           capture_output=True, text=True)
       assert out.returncode == 0, out.stderr
       assert _json.loads(out.stdout) == {"ok": True}
       events = control_plane.paths(str(tmp_path), "wi-x")["events"]
       evs = journal.read_events(events)
       assert evs[-1]["type"] == "external_dispatch"
       assert evs[-1]["payload"]["engine"] == "codex"


   def test_journal_entry_cli_defaults_to_phase_record(tmp_path, monkeypatch):
       # Back-compat: NO --event-type -> phase_record (the existing behavior is byte-preserved).
       import json as _json
       import os as _os
       import subprocess as _sp
       import sys as _sys
       import control_plane
       import journal
       _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
       monkeypatch.chdir(tmp_path)
       out = _sp.run(
           [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
            "--work-item", "wi-y", "--payload", _json.dumps({"phase": "build", "ok": True})],
           capture_output=True, text=True)
       assert out.returncode == 0 and _json.loads(out.stdout) == {"ok": True}
       evs = journal.read_events(control_plane.paths(str(tmp_path), "wi-y")["events"])
       assert evs[-1]["type"] == "phase_record"
   ```
   (If `test_journal.py` does not yet `import journal` at module top or lacks a sys.path shim, match the file's existing idiom — the conftest already puts `lib/` on `sys.path`, so a bare `import journal` inside the test works.)
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_journal.py -k "external_dispatch or journal_entry_cli" -q
   ```
   Expected: `test_external_dispatch_event_appends_and_reads` FAILS — `append` raises `DurableWriteError("unknown event type: 'external_dispatch'")` because the type is not yet registered — RED; and `test_journal_entry_cli_writes_external_dispatch_type` FAILS — `journal_entry.py` hardcodes `phase_record` and has no `--event-type` arg. (`test_unknown_event_type_still_raises_durable_write_error` and `test_journal_entry_cli_defaults_to_phase_record` may already pass; they guard the invariants stay intact after the change.)
- [ ] **Step 3:** Implement — add `"external_dispatch"` to `EVENT_TYPES` in `journal.py` (lines 19-23):
   ```python
   EVENT_TYPES = {
       "run_started", "step_entered", "step_completed", "notify", "gate", "error",
       "resumed", "lease_acquired", "lease_reclaimed", "ci_fix_attempt", "parked",
       "run_completed", "phase_record", "external_dispatch",
   }
   ```
- [ ] **Step 4:** Extend `journal_entry.py` with the optional `--event-type` (default `phase_record`). The real file (grep it first) parses `--work-item` + `--payload` and calls `journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd())`. Add the arg and pass it as the event type — the existing `DurableWriteError` catch already handles an unknown type (→ `{ok:false, error}`, the park path, UFR-6):
   ```python
   ap.add_argument("--work-item", required=True)
   ap.add_argument("--payload", required=True)   # JSON event payload
   ap.add_argument("--event-type", default="phase_record")   # #38: JS seam may write external_dispatch
   a = ap.parse_args()
   ```
   and change the `append` call's hardcoded type to the parsed flag:
   ```python
   try:
       journal.append(paths["events"], a.event_type, payload=payload, root=os.getcwd())
       print(json.dumps({"ok": True}))
   except journal.DurableWriteError as e:
       print(json.dumps({"ok": False, "error": str(e)}))
   ```
   Back-compat: an absent `--event-type` still writes `phase_record`; an unknown value surfaces the same `{ok:false, error}` line (no crash) — the JS caller treats a non-`{ok:true}` journal result as UFR-6 unauditable.
- [ ] **Step 5:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_journal.py -q
   ```
   Expected: all new tests PASS (the `external_dispatch` append, the `journal_entry.py --event-type external_dispatch` line, and the default-`phase_record` back-compat); the whole journal suite stays green (the unknown-type guard still raises for a genuinely-unknown type).
- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/lib/journal.py plugins/superheroes/lib/journal_entry.py plugins/superheroes/lib/tests/test_journal.py
   git commit -m "feat(superheroes): add external_dispatch journal event type + journal_entry --event-type"
   ```

---

### Task 5

`engine_adapter.py` — `build_argv` (codex + cursor, read vs write sandbox, always explicit model+effort) + the single-sourced `TASK_ID_TRAILER` constant. Refactor `build_state_cli.py` to import the constant (single-source the "Task-Id" trailer across the JS↔Python boundary), keeping `build_state` tests green. Canned argv assertions per engine/role.

**Files:**
- Create: `plugins/superheroes/lib/engine_adapter.py` — `TASK_ID_TRAILER`, `build_argv`, argparse `build-argv` subcommand.
- Create: `plugins/superheroes/lib/tests/test_engine_adapter.py`.
- Modify: `plugins/superheroes/lib/build_state_cli.py` — import `TASK_ID_TRAILER` from `engine_adapter`; use it in the `git log --format` trailer key (line 55).

**Interfaces:**
- Produces: `engine_adapter.TASK_ID_TRAILER = "Task-Id"` (the single-sourced trailer constant; the committer in Task 7 and the `build_state_cli` parser both reference it).
- Produces: `engine_adapter.build_argv(engine, role_kind, effort, opts) -> list[str]`. `opts` keys: `cwd`, `schema_path` (no `prompt_path` — the prompt is fed to the process stdin by the JS runner, Task 10, not encoded into argv). `role_kind` "review" → read-only sandbox; "build"|"fix" → workspace-write. Always explicit model + effort. Deterministic → fully unit-testable. Model constants: codex model `gpt-5-codex`, cursor model `composer`.
- Produces: CLI `engine_adapter.py build-argv --engine E --role R --effort EFF [--cwd C] [--schema-path S]` → prints the argv as a JSON array on stdout.
- Consumes (in `build_state_cli.py`): `engine_adapter.TASK_ID_TRAILER`.

**Steps:**

- [ ] **Step 1:** Write the failing test `plugins/superheroes/lib/tests/test_engine_adapter.py` (build_argv section):
   ```python
   import importlib.util
   import json
   import os

   _HERE = os.path.dirname(os.path.abspath(__file__))


   def _load():
       spec = importlib.util.spec_from_file_location(
           "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod


   EA = _load()


   def test_task_id_trailer_constant():
       assert EA.TASK_ID_TRAILER == "Task-Id"


   def test_build_argv_codex_review_read_only():
       argv = EA.build_argv("codex", "review", "high",
                            {"cwd": "/wt", "schema_path": "/tmp/s.json"})
       assert argv[0] == "codex" and "exec" in argv
       assert "--sandbox" in argv and argv[argv.index("--sandbox") + 1] == "read-only"
       assert "model_reasoning_effort=high" in argv
       assert "--output-schema" in argv and argv[argv.index("--output-schema") + 1] == "/tmp/s.json"
       assert "-m" in argv  # explicit model, never ambient default
       assert argv[-1] == "-"  # codex reads the prompt from stdin (fed by the Task-10 JS runner)


   def test_build_argv_codex_build_workspace_write():
       argv = EA.build_argv("codex", "build", "high", {"cwd": "/wt"})
       assert argv[argv.index("--sandbox") + 1] == "workspace-write"
       assert "-C" in argv and argv[argv.index("-C") + 1] == "/wt"
       assert "model_reasoning_effort=high" in argv


   def test_build_argv_codex_fix_low_effort():
       argv = EA.build_argv("codex", "fix", "low", {"cwd": "/wt"})
       assert "model_reasoning_effort=low" in argv
       assert argv[argv.index("--sandbox") + 1] == "workspace-write"


   def test_build_argv_cursor_review_plan_mode():
       argv = EA.build_argv("cursor", "review", "composer", {"cwd": "/wt"})
       assert argv[0] == "cursor-agent"
       assert "--mode" in argv and argv[argv.index("--mode") + 1] == "plan"
       assert "-m" in argv and argv[argv.index("-m") + 1] == "composer"


   def test_build_argv_cursor_build_force_write():
       argv = EA.build_argv("cursor", "build", "composer", {"cwd": "/wt"})
       assert argv[0] == "cursor-agent"
       assert "-f" in argv                      # workspace-write / force
       assert argv[argv.index("-m") + 1] == "composer"


   def test_build_argv_cli(capsys):
       rc = EA.main(["build-argv", "--engine", "codex", "--role", "build", "--effort", "high",
                     "--cwd", "/wt"])
       out = json.loads(capsys.readouterr().out)
       assert rc == 0 and out[0] == "codex" and "workspace-write" in out
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py -q
   ```
   Expected: collection/import error — `engine_adapter.py` does not exist — RED.
- [ ] **Step 3:** Implement `plugins/superheroes/lib/engine_adapter.py` (the `build_argv` + constant + CLI portion; `parse_result` and `commit_result` land in Tasks 6 and 7):
   ```python
   #!/usr/bin/env python3
   """The deterministic engine argv/parse/commit core (kept out of the model-driven JS layer so
   it is unit-testable). Named engine_adapter (NOT engine_cli — that is test-pilot's). Every
   external free-text surface is scrubbed at THIS trust boundary (parse_result). Flags verified
   live in the #38 spike (codex 0.141.0, cursor-agent 2026.06.19)."""
   import argparse
   import json
   import os
   import sys

   _LIB_DIR = os.path.dirname(os.path.abspath(__file__))
   if _LIB_DIR not in sys.path:
       sys.path.insert(0, _LIB_DIR)

   # The SINGLE-SOURCED commit trailer. The committer (commit_result, Task 7) and the
   # build_state_cli git-log parser both reference this so the convention cannot fork.
   TASK_ID_TRAILER = "Task-Id"

   # Explicit model per engine (Config-determinism NFR — never the developer's ambient default).
   _CODEX_MODEL = "gpt-5-codex"
   _CURSOR_MODEL = "composer"


   def build_argv(engine, role_kind, effort, opts):
       """Return the argv list to dispatch `engine` for `role_kind` at `effort`. READ (review) →
       read-only sandbox; WRITE (build|fix) → workspace-write. Always explicit model+effort.
       opts keys: cwd, schema_path. The PROMPT is NOT encoded here — codex reads it from stdin
       (trailing `-`) and cursor-agent reads it from stdin when given no positional prompt; the JS
       runner (Task 10) feeds the staged prompt file to the process stdin. Deterministic; fully
       unit-testable."""
       opts = opts or {}
       cwd = opts.get("cwd")
       schema_path = opts.get("schema_path")
       is_read = role_kind == "review"
       if engine == "codex":
           sandbox = "read-only" if is_read else "workspace-write"
           argv = ["codex", "exec", "--sandbox", sandbox,
                   "-m", _CODEX_MODEL,
                   "-c", "model_reasoning_effort=%s" % effort]
           if not is_read and cwd:
               argv += ["-C", cwd]           # confine writes to the managed worktree
           if is_read and schema_path:
               argv += ["--output-schema", schema_path]  # enforced structured review output
           # trailing `-`: read the prompt from stdin. The Task-10 JS runner redirects the staged
           # prompt file into stdin (`<argv> < promptPath`) — the prompt is ALWAYS fed here.
           argv += ["-"]
           return argv
       if engine == "cursor":
           # No positional prompt argument: cursor-agent reads the prompt from stdin, which the
           # Task-10 JS runner redirects from the staged prompt file (`<argv> < promptPath`).
           argv = ["cursor-agent", "-m", _CURSOR_MODEL]
           if is_read:
               argv += ["--mode", "plan"]     # read-only planning mode
           else:
               argv += ["-f"]                 # force / workspace-write
           argv += ["--output-format", "stream-json"]
           return argv
       # Unknown engine: return an empty argv; the JS caller treats an empty argv as unrunnable
       # → fall open to claude (never raises here).
       return []


   def _cmd_build_argv(args):
       opts = {"cwd": args.cwd, "schema_path": args.schema_path}
       sys.stdout.write(json.dumps(build_argv(args.engine, args.role, args.effort, opts)) + "\n")
       return 0


   def main(argv):
       ap = argparse.ArgumentParser(prog="engine_adapter")
       sub = ap.add_subparsers(dest="cmd", required=True)
       b = sub.add_parser("build-argv")
       b.add_argument("--engine", required=True, choices=("codex", "cursor"))
       b.add_argument("--role", required=True, choices=("review", "build", "fix"))
       b.add_argument("--effort", required=True)
       b.add_argument("--cwd", default=None)
       b.add_argument("--schema-path", default=None)
       args = ap.parse_args(argv)
       if args.cmd == "build-argv":
           return _cmd_build_argv(args)
       return 0


   if __name__ == "__main__":
       raise SystemExit(main(sys.argv[1:]))
   ```
- [ ] **Step 4:** Run to see the build_argv tests PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py -q
   ```
   Expected: all build_argv + constant + CLI tests PASS.
- [ ] **Step 5:** Now single-source the trailer: refactor `build_state_cli.py`. Add the import (after the existing `import build_state, control_plane, ship_gate, base_ref` on line 6):
   ```python
   from engine_adapter import TASK_ID_TRAILER
   ```
   and change the `git log --format` on line 55 to interpolate it:
   ```python
       log = _git(git_root, "log",
                  "--format=%H%x1f%(trailers:key=" + TASK_ID_TRAILER + ",valueonly)",
                  "%s..HEAD" % mb)
   ```
- [ ] **Step 6:** Run the build_state tests to prove the refactor kept them green:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_build_state.py -q
   ```
   Expected: PASS — `parse_trailers` is unchanged and the `git log` format still keys on the identical `"Task-Id"` string (now sourced from the constant).
- [ ] **Step 7:** Guard the single-source with an explicit assertion — append to `test_engine_adapter.py`:
   ```python
   def test_build_state_cli_uses_shared_trailer_constant():
       import importlib.util as _u
       spec = _u.spec_from_file_location(
           "build_state_cli", os.path.join(_HERE, "..", "build_state_cli.py"))
       bsc = _u.module_from_spec(spec)
       spec.loader.exec_module(bsc)
       assert bsc.TASK_ID_TRAILER == EA.TASK_ID_TRAILER == "Task-Id"
   ```
- [ ] **Step 8:** Run both to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py plugins/superheroes/lib/tests/test_build_state.py -q
   ```
   Expected: all PASS.
- [ ] **Step 9:** Commit:
   ```
   git add plugins/superheroes/lib/engine_adapter.py plugins/superheroes/lib/tests/test_engine_adapter.py plugins/superheroes/lib/build_state_cli.py
   git commit -m "feat(superheroes): engine_adapter build_argv + single-source Task-Id trailer"
   ```

---

### Task 6

`engine_adapter.parse_result` — codex `--output-schema` JSON review + cursor stream-json `raw_decode` of the last JSON object; build/fix → `{ok, signal, evidence{testFailed,testPassed}}`; **scrub external finding body/suggestion at this boundary** (Secret-hygiene); `evidence` constrained to two booleans (never raw stdout); unreadable/empty → `{ok:false, reason:"unreadable"}`. Canned per-engine stdout fixtures incl. well-formed Critical + empty/garbled/unreadable + a secret-in-finding scrub test.

**Files:**
- Modify: `plugins/superheroes/lib/engine_adapter.py` — add `parse_result` + a `parse-result` CLI subcommand + `readout` import.
- Modify: `plugins/superheroes/lib/tests/test_engine_adapter.py` — parse_result fixtures + scrub test.

**Interfaces:**
- Produces: `engine_adapter.parse_result(engine, role_kind, stdout) -> dict`.
  - review → `{"ok": true, "findings": [...]}` — each finding's `body`/`suggestion` free-text is `readout.scrub`-ed at this boundary; codex parses the `--output-schema` JSON object; cursor `raw_decode`s the last JSON object in the stream.
  - build|fix → `{"ok": true, "signal": "ok", "evidence": {"testFailed": bool, "testPassed": bool}}` — `evidence` is CONSTRAINED to those two booleans, never raw stdout/stderr.
  - Unparseable/empty → `{"ok": false, "reason": "unreadable"}`. Never raises (structured failure).
- Produces: CLI `engine_adapter.py parse-result --engine E --role R [--stdout-path FILE]` reads the external stdout from `--stdout-path` (or stdin when omitted) → prints the result dict as JSON.
- Consumes: `readout.scrub(text, root=None) -> (scrubbed, ok)` — takes the first element.

**Steps:**

- [ ] **Step 1:** Write failing tests — append to `plugins/superheroes/lib/tests/test_engine_adapter.py`:
   ```python
   def test_parse_result_codex_review_critical():
       stdout = json.dumps({"findings": [
           {"severity": "Critical", "title": "path traversal",
            "body": "file path built from unsanitized input escapes its dir",
            "suggestion": "sanitize the path"}]})
       res = EA.parse_result("codex", "review", stdout)
       assert res["ok"] is True
       assert res["findings"][0]["severity"] == "Critical"
       assert res["findings"][0]["title"] == "path traversal"


   def test_parse_result_cursor_review_stream_json_last_object():
       # stream-json: several line-delimited events; the LAST JSON object carries the findings.
       stream = ('{"type":"progress"}\n'
                 '{"type":"result","findings":[{"severity":"Important","title":"x",'
                 '"body":"b","suggestion":"s"}]}\n')
       res = EA.parse_result("cursor", "review", stream)
       assert res["ok"] is True
       assert res["findings"][0]["severity"] == "Important"


   def test_parse_result_review_empty_is_unreadable():
       assert EA.parse_result("codex", "review", "") == {"ok": False, "reason": "unreadable"}
       assert EA.parse_result("cursor", "review", "   ") == {"ok": False, "reason": "unreadable"}


   def test_parse_result_review_garbled_is_unreadable():
       assert EA.parse_result("codex", "review", "{ not json").get("ok") is False
       assert EA.parse_result("codex", "review", "{ not json")["reason"] == "unreadable"


   def test_parse_result_scrubs_secret_in_finding_body():
       # Secret-hygiene: an external finding's free-text is scrubbed AT THIS BOUNDARY, so the
       # standalone /review-code --post PR comment (built from body/suggestion, unscrubbed there)
       # carries no external secret in the clear.
       stdout = json.dumps({"findings": [
           {"severity": "Important", "title": "leak",
            "body": "log shows Authorization: Bearer sk-secret-1234567890",
            "suggestion": "remove the header x-api-key: sk-live-99999999"}]})
       res = EA.parse_result("codex", "review", stdout)
       f = res["findings"][0]
       assert "sk-secret-1234567890" not in f["body"]
       assert "[REDACTED]" in f["body"]
       assert "sk-live-99999999" not in f["suggestion"]


   def test_parse_result_build_evidence_two_booleans():
       stdout = json.dumps({"ok": True, "evidence": {"testFailed": False, "testPassed": True}})
       res = EA.parse_result("codex", "build", stdout)
       assert res["ok"] is True and res["signal"] == "ok"
       assert res["evidence"] == {"testFailed": False, "testPassed": True}
       # evidence carries ONLY the two booleans — no raw stdout leaks into it
       assert set(res["evidence"]) == {"testFailed", "testPassed"}


   def test_parse_result_build_unreadable():
       assert EA.parse_result("cursor", "build", "").get("ok") is False


   def test_parse_result_cli(capsys):
       import io, sys as _sys
       stdout = json.dumps({"ok": True, "evidence": {"testFailed": False, "testPassed": True}})
       _old = _sys.stdin
       _sys.stdin = io.StringIO(stdout)
       try:
           rc = EA.main(["parse-result", "--engine", "codex", "--role", "build"])
       finally:
           _sys.stdin = _old
       out = json.loads(capsys.readouterr().out)
       assert rc == 0 and out["signal"] == "ok"
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py -k parse_result -q
   ```
   Expected: `AttributeError: module 'engine_adapter' has no attribute 'parse_result'` — RED.
- [ ] **Step 3:** Implement `parse_result` in `engine_adapter.py`. Add the `readout` import at the top (after the `TASK_ID_TRAILER`/model constants):
   ```python
   import readout  # noqa: E402  (the band's single scrub seam; same-tree sibling)
   ```
   Then add the functions (after `build_argv`):
   ```python
   def _last_json_object(stdout):
       """Return the LAST top-level JSON object in a (possibly line-delimited / streamed) blob,
       or None. Tries whole-blob parse first, then a raw_decode scan, then a per-line fallback."""
       s = (stdout or "").strip()
       if not s:
           return None
       try:
           obj = json.loads(s)
           if isinstance(obj, dict):
               return obj
       except ValueError:
           pass
       dec = json.JSONDecoder()
       last = None
       i, n = 0, len(s)
       while i < n:
           while i < n and s[i] in " \t\r\n":
               i += 1
           if i >= n:
               break
           try:
               obj, end = dec.raw_decode(s, i)
               if isinstance(obj, dict):
                   last = obj
               i = end
           except ValueError:
               i += 1  # skip a non-JSON char (stream noise) and keep scanning
       return last


   def _scrub(text):
       if not isinstance(text, str) or not text:
           return text
       scrubbed, _ok = readout.scrub(text)
       return scrubbed


   def _scrub_findings(findings):
       out = []
       for f in findings if isinstance(findings, list) else []:
           if not isinstance(f, dict):
               continue
           g = dict(f)
           if "body" in g:
               g["body"] = _scrub(g["body"])
           if "suggestion" in g:
               g["suggestion"] = _scrub(g["suggestion"])
           out.append(g)
       return out


   def parse_result(engine, role_kind, stdout):
       """Parse an external engine's stdout into the native result shape. review → scrubbed
       findings; build|fix → {ok,signal,evidence{testFailed,testPassed}}. Unparseable/empty →
       {ok:false, reason:'unreadable'}. External free-text is scrubbed HERE (Secret-hygiene).
       Never raises."""
       try:
           obj = _last_json_object(stdout)
           if obj is None:
               return {"ok": False, "reason": "unreadable"}
           if role_kind == "review":
               findings = obj.get("findings")
               if not isinstance(findings, list):
                   return {"ok": False, "reason": "unreadable"}
               return {"ok": True, "findings": _scrub_findings(findings)}
           # build | fix
           ev = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
           evidence = {"testFailed": bool(ev.get("testFailed")),
                       "testPassed": bool(ev.get("testPassed"))}
           return {"ok": True, "signal": "ok", "evidence": evidence}
       except Exception:
           return {"ok": False, "reason": "unreadable"}
   ```
- [ ] **Step 4:** Add the `parse-result` CLI subcommand. In `main`, register the subparser and dispatch:
   ```python
       pr = sub.add_parser("parse-result")
       pr.add_argument("--engine", required=True, choices=("codex", "cursor"))
       pr.add_argument("--role", required=True, choices=("review", "build", "fix"))
       pr.add_argument("--stdout-path", default=None,
                       help="file holding the external engine's raw stdout; stdin if omitted")
   ```
   and in the dispatch body (before the final `return 0`):
   ```python
       if args.cmd == "parse-result":
           if args.stdout_path:
               with open(args.stdout_path, encoding="utf-8") as _fh:
                   _raw = _fh.read()
           else:
               _raw = sys.stdin.read()
           res = parse_result(args.engine, args.role, _raw)
           sys.stdout.write(json.dumps(res) + "\n")
           return 0
   ```
   The JS `dispatchExternal` (Task 10) stages the raw stdout to a temp file and passes
   `--stdout-path`; the unit test below drives the stdin fallback — both paths are covered.
- [ ] **Step 5:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py -q
   ```
   Expected: all parse_result tests (Critical, cursor stream-json, empty/garbled unreadable, secret scrub, evidence two-booleans, CLI) PASS along with the Task-5 build_argv tests.
- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/lib/engine_adapter.py plugins/superheroes/lib/tests/test_engine_adapter.py
   git commit -m "feat(superheroes): engine_adapter parse_result with boundary secret-scrub"
   ```

---

### Task 7

`engine_adapter.commit_result` — the SOLE committer. `HEAD == pre_sha` (engine only edited) → single Task-Id-trailered commit; `HEAD != pre_sha` (engine left stray commits) → `git reset --soft <pre_sha>` folds ONLY this dispatch's commits, then the single trailered commit. Effectful git tmp-repo test incl. the MULTI-ROUND FOLD invariant (a prior round's landed trailered commit survives).

**Files:**
- Modify: `plugins/superheroes/lib/engine_adapter.py` — add `commit_result` + a `commit` CLI subcommand + `subprocess` import.
- Create: `plugins/superheroes/lib/tests/test_engine_adapter_effectful.py` (mirrors `test_buildtree_effectful.py`'s tmp-repo idiom).

**Interfaces:**
- Produces: `engine_adapter.commit_result(worktree, task_id, pre_sha) -> {"ok": bool, "sha"?: str, "error"?: str}`. If `HEAD == pre_sha`: `git -C wt add -A && git -C wt commit -m "<msg>\n\n{TASK_ID_TRAILER}: {task_id}"`. If `HEAD != pre_sha`: `git -C wt reset --soft <pre_sha>` (folds only this dispatch's commits — `pre_sha` captured per-dispatch), then the single trailered commit. Discards no prior work (prior commits precede `pre_sha`). Never a plain hard reset. Returns `{ok:false, error}` on any git failure (never raises).
- Produces: CLI `engine_adapter.py commit --worktree WT --task-id T --pre-sha SHA` → JSON.
- Consumes: `engine_adapter.TASK_ID_TRAILER`.

**Steps:**

- [ ] **Step 1:** Write the failing effectful test `plugins/superheroes/lib/tests/test_engine_adapter_effectful.py`:
   ```python
   import importlib.util
   import os
   import subprocess

   _HERE = os.path.dirname(os.path.abspath(__file__))


   def _load():
       spec = importlib.util.spec_from_file_location(
           "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod


   EA = _load()


   def _git(cwd, *args):
       return subprocess.run(["git", "-C", cwd, *args], check=True,
                             capture_output=True, text=True)


   def _repo(tmp_path):
       repo = tmp_path / "repo"
       repo.mkdir()
       _git(str(repo), "init", "-q")
       _git(str(repo), "config", "user.email", "t@t")
       _git(str(repo), "config", "user.name", "t")
       (repo / "f").write_text("x")
       _git(str(repo), "add", "f")
       _git(str(repo), "commit", "-qm", "init")
       return str(repo)


   def _head(repo):
       return _git(repo, "rev-parse", "HEAD").stdout.strip()


   def _trailer(repo, ref="HEAD"):
       return _git(repo, "log", "-1", "--format=%(trailers:key=Task-Id,valueonly)", ref).stdout.strip()


   def test_commit_result_edits_only_makes_single_trailered_commit(tmp_path):
       repo = _repo(tmp_path)
       pre = _head(repo)
       # engine EDITS only (no commit)
       (tmp_path / "repo" / "g").write_text("engine wrote this")
       res = EA.commit_result(repo, "task-42", pre)
       assert res["ok"] is True and res["sha"]
       assert _head(repo) != pre               # exactly one new commit
       assert _trailer(repo) == "task-42"      # Task-Id trailer present
       # the file the engine wrote is committed
       assert "g" in _git(repo, "show", "--name-only", "--format=", "HEAD").stdout


   def test_commit_result_folds_stray_engine_commit_via_soft_reset(tmp_path):
       repo = _repo(tmp_path)
       pre = _head(repo)
       # a MIS-behaving engine left a stray (untrailered) commit despite the instruction
       (tmp_path / "repo" / "g").write_text("stray edit")
       _git(repo, "add", "g")
       _git(repo, "commit", "-qm", "stray engine commit (no trailer)")
       assert _head(repo) != pre
       res = EA.commit_result(repo, "task-7", pre)
       assert res["ok"] is True
       # exactly ONE commit above pre now, and it carries the trailer (the stray was folded in)
       count = _git(repo, "rev-list", "--count", "%s..HEAD" % pre).stdout.strip()
       assert count == "1"
       assert _trailer(repo) == "task-7"


   def test_multi_round_fold_prior_landed_commit_survives(tmp_path):
       # The load-bearing invariant: per-dispatch preSHA scopes the soft-reset to THIS round's
       # commits only — a prior round's already-landed trailered commit is BELOW preSHA and survives.
       repo = _repo(tmp_path)
       # Round 1: engine edits, adapter lands a trailered commit.
       pre1 = _head(repo)
       (tmp_path / "repo" / "r1").write_text("round 1 work")
       r1 = EA.commit_result(repo, "task-1", pre1)
       assert r1["ok"] is True
       round1_sha = _head(repo)
       assert _trailer(repo, round1_sha) == "task-1"
       # Round 2: preSHA re-captured AFTER round 1's landed commit; a stray commit this round.
       pre2 = _head(repo)
       (tmp_path / "repo" / "r2").write_text("round 2 stray")
       _git(repo, "add", "r2")
       _git(repo, "commit", "-qm", "round 2 stray (no trailer)")
       r2 = EA.commit_result(repo, "task-1", pre2)
       assert r2["ok"] is True
       # round 1's trailered commit STILL EXISTS untouched (it is below pre2)
       assert _git(repo, "cat-file", "-t", round1_sha).stdout.strip() == "commit"
       assert _trailer(repo, round1_sha) == "task-1"
       # and round 2 folded into exactly one trailered commit above pre2
       count2 = _git(repo, "rev-list", "--count", "%s..HEAD" % pre2).stdout.strip()
       assert count2 == "1"
       assert _trailer(repo, "HEAD") == "task-1"


   def test_commit_result_bad_worktree_returns_error_never_raises(tmp_path):
       res = EA.commit_result(str(tmp_path / "not-a-repo"), "t", "deadbeef")
       assert res["ok"] is False and res.get("error")
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter_effectful.py -q
   ```
   Expected: `AttributeError: module 'engine_adapter' has no attribute 'commit_result'` — RED.
- [ ] **Step 3:** Implement `commit_result` in `engine_adapter.py`. Add `import subprocess` at the top, then the function (after `parse_result`):
   ```python
   def _git(worktree, *args):
       return subprocess.run(["git", "-C", worktree, *args],
                             capture_output=True, text=True)


   def commit_result(worktree, task_id, pre_sha):
       """The SOLE committer for external writes. HEAD==pre_sha (engine only edited) → make the
       single Task-Id-trailered commit. HEAD!=pre_sha (engine left stray commits) → soft-reset to
       pre_sha (folds ONLY this dispatch's commits — pre_sha is per-dispatch), then the single
       trailered commit. Never a hard reset; discards no prior work. Never raises."""
       msg = "build: apply external-engine change\n\n%s: %s" % (TASK_ID_TRAILER, task_id)
       try:
           head = _git(worktree, "rev-parse", "HEAD")
           if head.returncode != 0:
               return {"ok": False, "error": "cannot resolve HEAD: %s" % head.stderr.strip()}
           if head.stdout.strip() != pre_sha:
               # fold ONLY this dispatch's commits back into the index (prior work is below pre_sha)
               r = _git(worktree, "reset", "--soft", pre_sha)
               if r.returncode != 0:
                   return {"ok": False, "error": "soft-reset failed: %s" % r.stderr.strip()}
           add = _git(worktree, "add", "-A")
           if add.returncode != 0:
               return {"ok": False, "error": "git add failed: %s" % add.stderr.strip()}
           commit = _git(worktree, "commit", "-m", msg)
           if commit.returncode != 0:
               return {"ok": False, "error": "git commit failed: %s" % commit.stderr.strip()}
           new_head = _git(worktree, "rev-parse", "HEAD")
           return {"ok": True, "sha": new_head.stdout.strip()}
       except Exception as exc:
           return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
   ```
- [ ] **Step 4:** Add the `commit` CLI subcommand. In `main`:
   ```python
       cm = sub.add_parser("commit")
       cm.add_argument("--worktree", required=True)
       cm.add_argument("--task-id", required=True)
       cm.add_argument("--pre-sha", required=True)
   ```
   and dispatch (before the final `return 0`):
   ```python
       if args.cmd == "commit":
           res = commit_result(args.worktree, args.task_id, args.pre_sha)
           sys.stdout.write(json.dumps(res) + "\n")
           return 0
   ```
- [ ] **Step 5:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter_effectful.py -q
   ```
   Expected: all four effectful tests PASS — the edit-only single commit, the stray-commit fold, the MULTI-ROUND fold invariant (prior round survives), and the bad-worktree structured error.
- [ ] **Step 6:** Run the whole engine_adapter test set:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py plugins/superheroes/lib/tests/test_engine_adapter_effectful.py -q
   ```
   Expected: all PASS.
- [ ] **Step 7:** Commit:
   ```
   git add plugins/superheroes/lib/engine_adapter.py plugins/superheroes/lib/tests/test_engine_adapter_effectful.py
   git commit -m "feat(superheroes): engine_adapter commit_result sole committer + fold invariant"
   ```

---

### Task 8

`engine_detect.py` — `probe`/`decide`/`message` (injected `run=` probe, `gh_preflight.py` shape). Installed/authed matrix, fall-open cause + remediation.

**Files:**
- Create: `plugins/superheroes/lib/engine_detect.py`
- Create: `plugins/superheroes/lib/tests/test_engine_detect.py`

**Interfaces:**
- Produces: `engine_detect.probe(root, run=None) -> {"codex": {"installed": bool, "authed": bool, "error": str|None}, "cursor": {...}}`. `shutil.which` + each CLI's cheap whoami/auth check. NEVER raises; never prints creds. `run=` injectable (test seam; defaults `subprocess.run`).
- Produces: `engine_detect.decide(probe, engine) -> (ok: bool, cause: str|None, remediation: str|None)`. Pure, fail-closed, next-command remediation.
- Produces: `engine_detect.message(probe, engine, ok, cause, remediation) -> str`.
- Produces: `main(argv, run=None)` — `--engine` is OPTIONAL. With `--engine E`: the single-engine JSON verdict on stdout, exit 0/1. With NO `--engine` (what configure FR-11 shells): the both-engines readiness MATRIX `{"codex":{ok,cause,remediation,message,installed,authed}, "cursor":{...}}` from `probe(root)` + `decide` per engine, exit 0 if any engine is ready else 1.
- Consumes: nothing new.

**Steps:**

- [ ] **Step 1:** Write the failing test `plugins/superheroes/lib/tests/test_engine_detect.py`:
   ```python
   import importlib.util
   import json
   import os

   _HERE = os.path.dirname(os.path.abspath(__file__))


   def _load():
       spec = importlib.util.spec_from_file_location(
           "engine_detect", os.path.join(_HERE, "..", "engine_detect.py"))
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod


   ED = _load()


   class _Proc:
       def __init__(self, returncode=0, stdout="", stderr=""):
           self.returncode = returncode
           self.stdout = stdout
           self.stderr = stderr


   def _fake_run(script):
       """script: dict mapping the FIRST argv token -> _Proc (or an Exception to raise)."""
       def run(args, capture_output=True, text=True, timeout=10, cwd=None):
           key = args[0]
           val = script.get(key, _Proc(returncode=1))
           if isinstance(val, Exception):
               raise val
           return val
       return run


   def test_probe_both_installed_and_authed(monkeypatch):
       monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
       run = _fake_run({"codex": _Proc(0, "logged in"), "cursor-agent": _Proc(0, "user@x")})
       p = ED.probe(".", run=run)
       assert p["codex"]["installed"] is True and p["codex"]["authed"] is True
       assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is True


   def test_probe_codex_not_installed(monkeypatch):
       monkeypatch.setattr(ED.shutil, "which", lambda name: None if name == "codex" else "/usr/bin/" + name)
       run = _fake_run({"cursor-agent": _Proc(0, "user@x")})
       p = ED.probe(".", run=run)
       assert p["codex"]["installed"] is False and p["codex"]["authed"] is False
       assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is True


   def test_probe_cursor_installed_not_authed(monkeypatch):
       monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
       run = _fake_run({"codex": _Proc(0, "ok"), "cursor-agent": _Proc(1, "", "not signed in")})
       p = ED.probe(".", run=run)
       assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is False


   def test_probe_never_raises_on_run_exception(monkeypatch):
       monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
       run = _fake_run({"codex": RuntimeError("boom"), "cursor-agent": _Proc(0, "ok")})
       p = ED.probe(".", run=run)
       assert p["codex"]["authed"] is False and p["codex"]["error"]


   def test_decide_ready():
       probe = {"codex": {"installed": True, "authed": True, "error": None},
                "cursor": {"installed": False, "authed": False, "error": None}}
       ok, cause, rem = ED.decide(probe, "codex")
       assert ok is True and cause is None and rem is None


   def test_decide_not_installed_gives_remediation():
       probe = {"codex": {"installed": False, "authed": False, "error": None}, "cursor": {}}
       ok, cause, rem = ED.decide(probe, "codex")
       assert ok is False and cause == "not_installed" and rem


   def test_decide_not_authed_gives_remediation():
       probe = {"codex": {"installed": True, "authed": False, "error": None}, "cursor": {}}
       ok, cause, rem = ED.decide(probe, "codex")
       assert ok is False and cause == "not_authenticated" and rem


   def test_decide_unknown_engine_is_indeterminate():
       ok, cause, rem = ED.decide({"codex": {}, "cursor": {}}, "bogus")
       assert ok is False and cause == "indeterminate"


   def test_decide_error_set_is_indeterminate():
       # M2: an otherwise-installed engine whose probe recorded an `error` (timeout/OSError) is
       # indeterminate (fail-closed), NOT reported ready.
       probe = {"codex": {"installed": True, "authed": True, "error": "TimeoutExpired: x"},
                "cursor": {}}
       ok, cause, rem = ED.decide(probe, "codex")
       assert ok is False and cause == "indeterminate" and rem


   def test_message_and_main(monkeypatch, capsys):
       monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
       run = _fake_run({"codex": _Proc(0, "ok"), "cursor-agent": _Proc(0, "ok")})
       rc = ED.main(["--engine", "codex", "--root", "."], run=run)
       out = json.loads(capsys.readouterr().out)
       assert rc == 0 and out["ok"] is True and out["engine"] == "codex"


   def test_main_no_engine_prints_both_engines_matrix(monkeypatch, capsys):
       # I1 / FR-11: bare `engine_detect.py` (no --engine) prints the readiness matrix configure shows.
       monkeypatch.setattr(ED.shutil, "which",
                           lambda name: None if name == "cursor-agent" else "/usr/bin/" + name)
       run = _fake_run({"codex": _Proc(0, "ok")})
       rc = ED.main(["--root", "."], run=run)
       out = json.loads(capsys.readouterr().out)
       assert set(out.keys()) == {"codex", "cursor"}
       assert out["codex"]["ok"] is True
       assert out["cursor"]["ok"] is False and out["cursor"]["cause"] == "not_installed"
       assert out["cursor"]["remediation"]           # every not-ready engine carries remediation
       assert rc == 0                                 # at least one engine ready -> exit 0
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_detect.py -q
   ```
   Expected: import error — `engine_detect.py` does not exist — RED.
- [ ] **Step 3:** Implement `plugins/superheroes/lib/engine_detect.py` (complete, mirroring `gh_preflight.py`):
   ```python
   #!/usr/bin/env python3
   """Engine readiness preflight — the gh_preflight.py shape for Codex + Cursor (FR-11).
   Pure decide + best-effort injectable probe + JSON CLI verdict. Read-only; never prints or
   persists credentials; probe NEVER raises (any exception/timeout → error)."""
   import argparse
   import json
   import shutil
   import subprocess
   import sys

   # engine -> (the CLI binary, the cheap auth/whoami argv).
   _CLI = {
       "codex": ("codex", ["codex", "login", "status"]),
       "cursor": ("cursor-agent", ["cursor-agent", "status"]),
   }

   _CAUSE_TEXT = {
       "not_installed": "the CLI is not installed",
       "not_authenticated": "the CLI is not signed in",
       "indeterminate": "engine readiness could not be determined",
   }


   def _remediation(engine, cause):
       if cause == "not_installed":
           if engine == "codex":
               return "install Codex — see https://github.com/openai/codex"
           return "install Cursor — see https://cursor.com/cli"
       if cause == "not_authenticated":
           return "codex login" if engine == "codex" else "cursor-agent login"
       return "verify the engine CLI is installed and signed in, then retry"


   def _probe_one(engine, root, run):
       binary, auth_argv = _CLI[engine]
       rec = {"installed": False, "authed": False, "error": None}
       try:
           if shutil.which(binary) is None:
               return rec
           rec["installed"] = True
           proc = run(auth_argv, capture_output=True, text=True, timeout=10, cwd=root)
           rec["authed"] = (proc.returncode == 0)
           return rec
       except Exception as exc:  # timeout, OSError, anything — never propagate
           rec["error"] = "%s: %s" % (type(exc).__name__, exc)
           return rec


   def probe(root, run=None):
       """Best-effort world-read → {codex:{...}, cursor:{...}}. NEVER raises; never prints creds."""
       if run is None:
           run = subprocess.run
       return {"codex": _probe_one("codex", root, run),
               "cursor": _probe_one("cursor", root, run)}


   def decide(probe_dict, engine):
       """(ok, cause, remediation). Pure + fail-closed."""
       if engine not in _CLI or not isinstance(probe_dict, dict):
           return (False, "indeterminate", _remediation(engine, "indeterminate"))
       rec = probe_dict.get(engine)
       if not isinstance(rec, dict):
           return (False, "indeterminate", _remediation(engine, "indeterminate"))
       if rec.get("error"):
           return (False, "indeterminate", _remediation(engine, "indeterminate"))
       if rec.get("installed") is not True:
           return (False, "not_installed", _remediation(engine, "not_installed"))
       if rec.get("authed") is not True:
           return (False, "not_authenticated", _remediation(engine, "not_authenticated"))
       return (True, None, None)


   def message(probe_dict, engine, ok, cause, remediation):
       if ok:
           return "%s is ready" % engine
       parts = ["%s: %s" % (engine, _CAUSE_TEXT.get(cause, _CAUSE_TEXT["indeterminate"]))]
       rec = probe_dict.get(engine) if isinstance(probe_dict, dict) else None
       if cause == "indeterminate" and isinstance(rec, dict) and rec.get("error"):
           parts.append("(%s)" % str(rec["error"]).strip())
       parts.append("Fix: %s" % remediation)
       return " — ".join(parts)


   def _verdict(p, engine):
       """One engine's full verdict dict (ok/cause/remediation/message + the raw installed/authed)."""
       ok, cause, rem = decide(p, engine)
       rec = p.get(engine) if isinstance(p, dict) else {}
       rec = rec if isinstance(rec, dict) else {}
       return {"engine": engine, "ok": ok, "cause": cause, "remediation": rem,
               "message": message(p, engine, ok, cause, rem),
               "installed": bool(rec.get("installed")), "authed": bool(rec.get("authed"))}


   def main(argv, run=None):
       ap = argparse.ArgumentParser(prog="engine_detect")
       # --engine OPTIONAL: with it, the single-engine verdict; without it, the both-engines MATRIX
       # (what configure's FR-11 availability step shells).
       ap.add_argument("--engine", default=None, choices=("codex", "cursor"))
       ap.add_argument("--root", default=".")
       args = ap.parse_args(argv)
       try:
           p = probe(args.root, run=run)
       except Exception as exc:  # fail-CLOSED catch-all (probe already never raises; belt-and-suspenders)
           p = {"codex": {"installed": False, "authed": False, "error": "%s: %s" % (type(exc).__name__, exc)},
                "cursor": {"installed": False, "authed": False, "error": "%s: %s" % (type(exc).__name__, exc)}}
       if args.engine is None:
           # MATRIX mode: a verdict per engine; exit 0 if ANY engine is ready.
           matrix = {"codex": _verdict(p, "codex"), "cursor": _verdict(p, "cursor")}
           sys.stdout.write(json.dumps(matrix) + "\n")
           return 0 if (matrix["codex"]["ok"] or matrix["cursor"]["ok"]) else 1
       verdict = _verdict(p, args.engine)
       sys.stdout.write(json.dumps(verdict) + "\n")
       return 0 if verdict["ok"] else 1


   if __name__ == "__main__":
       sys.exit(main(sys.argv[1:]))
   ```
- [ ] **Step 4:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_detect.py -q
   ```
   Expected: all probe/decide/message/main tests PASS (installed+authed, not-installed, installed-not-authed, run-exception never-raises, decide matrix, indeterminate unknown engine, the M2 error-set indeterminate branch, the single-engine CLI verdict, AND the no-`--engine` both-engines readiness matrix).
- [ ] **Step 5:** Commit:
   ```
   git add plugins/superheroes/lib/engine_detect.py plugins/superheroes/lib/tests/test_engine_detect.py
   git commit -m "feat(superheroes): engine_detect readiness probe/decide/message"
   ```

---

### Task 9

`engine_authz.py` — `authorization_snippet` (show-but-don't-apply) + engine-aware `implementation_dispatch_allowed(cwd, engine, run=None)` (injected `run=`; a throwaway external write via THAT engine's write command inside the managed worktree; denied/failed → False → UFR-4 fall-open) + a `main(argv, run=None)` CLI with `snippet` / `test-dispatch` subcommands (the CLIs configure's set-up.md shells). Tests: allow→True, deny→False→UFR-4, snippet content + never-writes assertion, both CLI subcommands.

**Files:**
- Create: `plugins/superheroes/lib/engine_authz.py`
- Create: `plugins/superheroes/lib/tests/test_engine_authz.py`

**Interfaces:**
- Produces: `engine_authz.authorization_snippet(host, engine) -> str`. The exact `autoMode.allow` block + WHERE to paste it (`.claude/settings.local.json`), resolved per host. NEVER writes it.
- Produces: `engine_authz.implementation_dispatch_allowed(cwd, engine, run=None) -> bool`. Run-time preflight: a trivial throwaway external WRITE via `engine`'s OWN write command (`codex exec …` vs `cursor-agent …`) inside the managed worktree, so the host's `autoMode.allow` rule for `Bash(codex exec:*)` vs `Bash(cursor-agent:*)` is what is exercised. Observe allow vs deny; denied/failed → `False` (→ impl role falls open to Claude, UFR-4). `run=` injectable (test seam; defaults `subprocess.run`). Also used by configure's test-dispatch (FR-14). Wrong-assumption only falls open (safe). Never raises.
- Produces: CLI `python3 lib/engine_authz.py snippet --host <host> --engine <codex|cursor>` → prints `authorization_snippet(host, engine)`; `python3 lib/engine_authz.py test-dispatch --engine <codex|cursor> --cwd <dir>` → prints JSON `{"engine":E,"ok":bool}` (the run-time preflight verdict). `main(argv, run=None)` — `run=` injectable for the test.
- Consumes: nothing new.

**Steps:**

- [ ] **Step 1:** Write the failing test `plugins/superheroes/lib/tests/test_engine_authz.py`:
   ```python
   import importlib.util
   import json
   import os

   _HERE = os.path.dirname(os.path.abspath(__file__))


   def _load():
       spec = importlib.util.spec_from_file_location(
           "engine_authz", os.path.join(_HERE, "..", "engine_authz.py"))
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod


   AZ = _load()


   class _Proc:
       def __init__(self, returncode=0, stdout="", stderr=""):
           self.returncode = returncode
           self.stdout = stdout
           self.stderr = stderr


   def test_authorization_snippet_names_automode_allow_and_location():
       snip = AZ.authorization_snippet("claude-code", "cursor")
       assert "autoMode" in snip and "allow" in snip
       assert ".claude/settings.local.json" in snip


   def test_authorization_snippet_covers_both_engines():
       for engine in ("codex", "cursor"):
           snip = AZ.authorization_snippet("claude-code", engine)
           assert engine in snip.lower() or "cursor-agent" in snip.lower() or "codex" in snip.lower()


   def test_authorization_snippet_never_writes(tmp_path, monkeypatch):
       # a hard guard: calling the snippet builder touches NO file.
       calls = []
       real_open = open
       monkeypatch.setattr("builtins.open",
                           lambda *a, **k: calls.append(a) or real_open(*a, **k))
       AZ.authorization_snippet("claude-code", "cursor")
       # the snippet builder opened nothing for WRITE
       assert all("w" not in (a[1] if len(a) > 1 else "") for a in calls)


   def test_implementation_dispatch_allowed_true_when_probe_succeeds(tmp_path):
       def run(args, **k):
           return _Proc(returncode=0, stdout="wrote")
       assert AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run) is True


   def test_implementation_dispatch_allowed_false_when_denied_ufr4(tmp_path):
       # a denied write (nonzero exit) → False → implementation role falls open to Claude (UFR-4).
       def run(args, **k):
           return _Proc(returncode=1, stderr="denied by autoMode")
       assert AZ.implementation_dispatch_allowed(str(tmp_path), "cursor", run=run) is False


   def test_implementation_dispatch_allowed_false_on_exception(tmp_path):
       def run(args, **k):
           raise RuntimeError("boom")
       assert AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run) is False


   def test_implementation_dispatch_probes_the_engines_own_write_command(tmp_path):
       # The probe must exercise THAT engine's write command, so the host's per-engine autoMode.allow
       # rule (Bash(codex exec:*) vs Bash(cursor-agent:*)) is what gets tested.
       seen = {}
       def run(args, **k):
           seen["argv"] = args
           return _Proc(returncode=0)
       AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
       # argv is a LIST of separate tokens (["codex","exec","--sandbox","workspace-write","-C",cwd,prompt]),
       # so no single token contains "codex exec" — assert on the JOINED argv, which starts with "codex exec".
       assert " ".join(str(t) for t in seen["argv"]).startswith("codex exec")
       AZ.implementation_dispatch_allowed(str(tmp_path), "cursor", run=run)
       # cursor argv is (["cursor-agent","-f",prompt]) — the joined form starts with "cursor-agent".
       assert " ".join(str(t) for t in seen["argv"]).startswith("cursor-agent")


   def test_implementation_dispatch_unknown_engine_falls_open_false(tmp_path):
       def run(args, **k):
           return _Proc(returncode=0)
       assert AZ.implementation_dispatch_allowed(str(tmp_path), "bogus", run=run) is False


   def test_cli_snippet_subcommand(capsys):
       rc = AZ.main(["snippet", "--host", "claude", "--engine", "cursor"])
       out = capsys.readouterr().out
       assert rc == 0 and "autoMode" in out and ".claude/settings.local.json" in out


   def test_cli_test_dispatch_subcommand(capsys):
       def run(args, **k):
           return _Proc(returncode=0)
       rc = AZ.main(["test-dispatch", "--engine", "codex", "--cwd", "."], run=run)
       out = json.loads(capsys.readouterr().out)
       assert rc == 0 and out == {"engine": "codex", "ok": True}


   def test_cli_test_dispatch_denied_reports_false(capsys):
       def run(args, **k):
           return _Proc(returncode=1, stderr="denied")
       rc = AZ.main(["test-dispatch", "--engine", "cursor", "--cwd", "."], run=run)
       out = json.loads(capsys.readouterr().out)
       assert rc == 0 and out == {"engine": "cursor", "ok": False}
   ```
- [ ] **Step 2:** Run it to see it FAIL:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_authz.py -q
   ```
   Expected: import error — `engine_authz.py` does not exist — RED.
- [ ] **Step 3:** Implement `plugins/superheroes/lib/engine_authz.py` (complete):
   ```python
   #!/usr/bin/env python3
   """The show-but-don't-apply build-authorization helper (FR-13) + the run-time write preflight
   (UFR-4) + the configure CLIs (snippet / test-dispatch). Authorization is HOST-ENFORCED — the band
   never writes the owner's autoMode.allow grant; it shows the exact snippet and, at run time,
   behaviorally observes allow vs deny via a throwaway external write, run through THAT engine's own
   write command, inside the managed worktree. A wrong assumption only falls OPEN to Claude (a cost,
   never a corrupt result), so the failure mode is safe by construction."""
   import argparse
   import json
   import os
   import subprocess
   import sys

   # engine -> the dispatch command the owner's autoMode.allow rule must match (host-global grant).
   _DISPATCH_CMD = {"codex": "codex exec", "cursor": "cursor-agent"}


   def authorization_snippet(host, engine):
       """Return the exact autoMode.allow block for `engine` on `host` + WHERE to paste it. NEVER
       writes anything. The grant is host-global (matches the dispatch command, not a path)."""
       cmd = _DISPATCH_CMD.get(engine, engine)
       block = {"autoMode": {"allow": ["Bash(%s:*)" % cmd]}}
       location = ".claude/settings.local.json"
       return (
           "To let %s build autonomously on the %s host, add this one-time grant to your own\n"
           "%s (the band never writes it for you):\n\n"
           "%s\n\n"
           "This authorizes the `%s` dispatch command; remove it to revoke."
           % (engine, host, location, json.dumps(block, indent=2), cmd)
       )


   def implementation_dispatch_allowed(cwd, engine, run=None):
       """Run-time preflight: a trivial throwaway external WRITE inside the managed worktree to
       observe allow vs deny before the first real build/fix write. The probe is issued through
       `engine`'s OWN write command (`codex exec …` / `cursor-agent …`) so the host's per-engine
       autoMode.allow rule (`Bash(codex exec:*)` vs `Bash(cursor-agent:*)`) is exactly what is tested.
       An unknown engine, a denied/failed/errored write → False (→ implementation role falls open to
       Claude, UFR-4). Never raises."""
       if run is None:
           run = subprocess.run
       dispatch = _DISPATCH_CMD.get(engine)
       if dispatch is None:
           return False  # unknown engine -> fall open (safe): the impl role runs on Claude
       probe_file = os.path.join(cwd, ".superheroes-authz-probe")
       # A harmless throwaway write, but run as the ENGINE's own workspace-write dispatch command so the
       # host's autoMode classifier decides allow vs deny against the SAME grant a real build would hit.
       # `codex exec --sandbox workspace-write -C <cwd> "<prompt>"` / `cursor-agent -f "<prompt>"`.
       write_prompt = "write an empty file named .superheroes-authz-probe and exit"
       if engine == "codex":
           argv = ["codex", "exec", "--sandbox", "workspace-write", "-C", cwd, write_prompt]
       else:  # cursor
           argv = ["cursor-agent", "-f", write_prompt]
       try:
           proc = run(argv, capture_output=True, text=True, timeout=10, cwd=cwd)
           allowed = (getattr(proc, "returncode", 1) == 0)
       except Exception:
           allowed = False
       finally:
           try:
               os.remove(probe_file)
           except OSError:
               pass
       return bool(allowed)


   def _cmd_snippet(args):
       sys.stdout.write(authorization_snippet(args.host, args.engine) + "\n")
       return 0


   def _cmd_test_dispatch(args, run):
       ok = implementation_dispatch_allowed(args.cwd, args.engine, run=run)
       sys.stdout.write(json.dumps({"engine": args.engine, "ok": bool(ok)}) + "\n")
       return 0


   def main(argv, run=None):
       ap = argparse.ArgumentParser(prog="engine_authz")
       sub = ap.add_subparsers(dest="cmd", required=True)
       s = sub.add_parser("snippet")
       s.add_argument("--host", required=True)
       s.add_argument("--engine", required=True, choices=("codex", "cursor"))
       t = sub.add_parser("test-dispatch")
       t.add_argument("--engine", required=True, choices=("codex", "cursor"))
       t.add_argument("--cwd", default=".")
       args = ap.parse_args(argv)
       if args.cmd == "snippet":
           return _cmd_snippet(args)
       if args.cmd == "test-dispatch":
           return _cmd_test_dispatch(args, run)
       return 0


   if __name__ == "__main__":
       raise SystemExit(main(sys.argv[1:]))
   ```
- [ ] **Step 4:** Run to see PASS:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_authz.py -q
   ```
   Expected: all snippet + preflight + CLI tests PASS — snippet names `autoMode`/`allow` + the settings path, covers both engines, writes nothing; the preflight returns True on a 0-exit probe, False on deny (UFR-4), False on an exception, False on an unknown engine, and probes each engine's OWN write command (`codex exec` / `cursor-agent`); the `snippet` CLI prints the block + location, and `test-dispatch` prints `{"engine":E,"ok":bool}` for allow and deny.
- [ ] **Step 5:** Run the full backend lib suite (Tasks 1-9) as a final gate before handing off:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_pref.py plugins/superheroes/lib/tests/test_engine_adapter.py plugins/superheroes/lib/tests/test_engine_adapter_effectful.py plugins/superheroes/lib/tests/test_engine_detect.py plugins/superheroes/lib/tests/test_engine_authz.py plugins/superheroes/lib/tests/test_core_md.py plugins/superheroes/lib/tests/test_journal.py plugins/superheroes/lib/tests/test_build_state.py plugins/superheroes/lib/tests/test_parity.py -q
   ```
   Expected: all PASS, including every parity self-enforcement clause (clause (c) checks *bundled ⊆ targets*, so the not-yet-bundled `engine_pref` does not trip it). The backend tasks (1-9) leave the full lib suite GREEN; Task 10 adds `engine_pref`/`engine_dispatch` to `bundle_showrunner.js` MODULES + regenerates the bundle (its own bundle-drift gate).
- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/lib/engine_authz.py plugins/superheroes/lib/tests/test_engine_authz.py
   git commit -m "feat(superheroes): engine_authz authorization_snippet + dispatch preflight"
   ```

---

### Task 10 — `engine_dispatch.js` `dispatchExternal` (spine leaf wrapper) + bundle wiring + node smoke

**Files:**
- Create: `plugins/superheroes/lib/engine_dispatch.js`
- Create: `plugins/superheroes/lib/tests/engine_dispatch_smoke.js`
- Modify: `plugins/superheroes/lib/bundle_showrunner.js` — `MODULES` array (line 19-23): add `'engine_pref.js'` and `'engine_dispatch.js'` BEFORE `'build_phase.js'`.
- Modify: `plugins/superheroes/lib/tests/test_parity.py` — `BUNDLED_NON_TWINS` set (line 62-67): add `"engine_dispatch.js"` (it is a shell, not a pure twin; `engine_pref.js` is a real twin registered by Task 1 into `PARITY_TARGET_MODULES`).
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` — `SHOWRUNNER_SMOKES` list (line 9-63): append `"plugins/superheroes/lib/tests/engine_dispatch_smoke.js"`. *(Note: the discovery-guard at line 66-74 only auto-matches `showrunner_*` / `build_phase_*` names; `engine_dispatch_smoke.js` is NOT auto-discovered, so registering it in the list is sufficient and the discovery-equality assertion is unaffected.)*
- Modify: `plugins/superheroes/lib/showrunner.bundle.js` — regenerated (do NOT hand-edit; produced by `node bundle_showrunner.js --write`).

**Interfaces:**
- Consumes (from Tasks 5-7, exact CLI contract): `python3 plugins/superheroes/lib/engine_adapter.py build-argv|parse-result|commit … → JSON on stdout`. `build_argv(engine, role_kind, effort, opts{cwd,schema_path})` (the prompt is NOT in argv — it is fed to the process stdin by `_runArgv`'s redirect); `parse_result(engine, role_kind, stdout) → {ok, findings?|signal, evidence?} | {ok:false, reason:"unreadable"}` (already scrubbed at that boundary); `commit_result(worktree, task_id, pre_sha) → {ok, sha?, error?}`. `TASK_ID_TRAILER = "Task-Id"`.
- Consumes (the engine_pref twin, Task 1): `engine_pref.js` `resolveEngine(roleKind, prefs)`, `resolveEffort(engine, roleKind, overrides)`; `python3 plugins/superheroes/lib/engine_pref.py`-side `resolve_timeout(overrides) → int` is mirrored — for the JS UFR-5 default use the constant `DEFAULT_STALL_LIMIT_SECONDS = 300` echoed in `engine_dispatch.js` (test-settable via `opts.timeoutSeconds`).
- Consumes (spine): `globalThis.agent`, and `exec(commands)` from `showrunner.js` (the dumb-pipe). Reuse the established preSHA pattern `exec([\`git -C ${shq(wt)} rev-parse HEAD\`])` → parse `r0.stdout.trim()` (showrunner.js:1226-1231).
- Consumes: `globalThis.__SR_ENGINE_PREFS` (planted at startup in Tasks 11/12).
- Produces: `module.exports = { dispatchExternal }`. `dispatchExternal({engine, roleKind, effort, prompt, cwd, schema, timeoutSeconds, taskId, workItem}) → {ok, signal, evidence} | {findings} | {ok:false, reason}` (write roles read `taskId` for the adapter commit and `workItem` for the `external_dispatch` journal; read roles ignore both).

Steps:

- [ ] **Step 1:** Write the failing node smoke `engine_dispatch_smoke.js` for the **review (read-only) happy path**. Mirror `build_phase_setup_smoke.js`'s `makeAgent(routes)`/`execRoute` idiom (route by exact label, then prompt substring). Record every exec command string in an ordered `execLog` so the stdin-redirect assertion below can inspect the dispatch-run command. Stub `global.agent` so that:
   - an `exec` prompt containing `engine_adapter.py build-argv` returns `[{index:0,ok:true,stdout: JSON.stringify(["codex","exec","--sandbox","read-only","-"])}]`;
   - an `exec` prompt containing the argv token `codex` (the dispatch run) returns `[{index:0,ok:true,stdout:'{"raw":"external review output"}'}]`;
   - an `exec` prompt containing `engine_adapter.py parse-result` returns `[{index:0,ok:true,stdout: JSON.stringify({ok:true, findings:[{file:'a.py',line:3,title:'x',severity:'Minor',evidence:'e'}]})}]`.
   Call `const d = require('../engine_dispatch.js'); const r = await d.dispatchExternal({engine:'codex', roleKind:'review', effort:'high', prompt:'review', cwd:'/tmp/wt', schema:{}, timeoutSeconds:300})` and assert: (a) `assert.deepStrictEqual(r.findings, [...])`; (b) NO `git rev-parse` / `commit` exec was issued for a read role; (c) the dispatch-RUN command string (the one that runs the external argv) FEEDS the prompt file to stdin — it contains `< ` and the staged prompt path (`.prompt`), i.e. `const runCmd = execLog.find((c) => c.includes('--sandbox') && c.includes(' < ')); assert.ok(runCmd && /\.prompt/.test(runCmd), 'run must redirect the staged prompt file into stdin')`.

- [ ] **Step 2:** Run to FAIL:
   ```
   node plugins/superheroes/lib/tests/engine_dispatch_smoke.js
   ```
   Expected: `Error: Cannot find module '../engine_dispatch.js'` (module does not exist yet).

- [ ] **Step 3:** Create `engine_dispatch.js` with the module skeleton and the shared helpers (COMPLETE code):
   ```js
   // plugins/superheroes/lib/engine_dispatch.js
   // Spine leaf wrapper (#38): the single seam every JS call site invokes instead of agent() when the
   // engine is external (codex|cursor). Deterministic argv/parse/commit live in engine_adapter.py; this
   // wrapper sequences them through the spine's exec dumb-pipe and returns the NATIVE result shape so
   // everything downstream (loop math, verify gate, journal) is reused unchanged. Read roles are
   // read-only (no preSHA/commit); write roles capture preSHA -> engine edits -> adapter commits.
   const LIB = 'plugins/superheroes/lib'
   const DEFAULT_STALL_LIMIT_SECONDS = 300   // UFR-5 finite default; test-settable via opts.timeoutSeconds

   function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

   // Reuse the spine's exec dumb-pipe (lazy require avoids a load-time cycle: showrunner requires the
   // bundle graph; deferring keeps engine_dispatch's require surface minimal for the smokes).
   let _execFn = null
   function _exec(commands) {
     if (!_execFn) _execFn = require('./showrunner.js').exec
     return _execFn(commands)
   }

   // Run ONE command through the exec dumb-pipe and parse its JSON stdout. Mirrors the canonical
   // build_phase.js:43-64 `execJson` contract: the cheap haiku courier occasionally drops/garbles a
   // command's stdout even though it ran (live: a journal_entry.py leaf returned stdout:"" with ok:true,
   // so JSON.parse("") threw and the build fail-closed-parked); retry ONCE on an empty or unparseable
   // stdout before failing closed. The dispatch-path commands here (journal append, adapter build-argv /
   // parse-result / commit, preSHA) are idempotent / harmless to repeat. Returns the parsed object, or
   // null after the retry (the caller fails closed on null). A clean {"ok":true} on the first call returns
   // immediately (one exec, no behavior change); a parseable {"ok":false} (a REAL durable-write failure)
   // is returned as-is on the first call — it is NOT a courier-drop, so it is NOT retried.
   async function _execJson(cmd) {
     for (let attempt = 0; attempt < 2; attempt++) {
       const res = await _exec([cmd])
       const r0 = res && res[0]
       if (r0 && r0.ok) {
         const s = (r0.stdout == null ? '' : String(r0.stdout)).trim()
         if (s) { try { return JSON.parse(s) } catch (_e) { /* garbled -> retry */ } }
         // empty stdout -> retry (courier likely dropped it)
       }
       // exec-level failure or empty/garbled -> retry once, then give up
     }
     return null
   }
   ```

- [ ] **Step 4:** Add the write-role helper `_captureHead` and the argv-runner `_runArgv` (COMPLETE code) below the helpers:
   ```js
   // preSHA capture for write roles — the established spine pattern (showrunner.js:1226).
   async function _captureHead(wt) {
     const res = await _exec([`git -C ${shq(wt)} rev-parse HEAD`])
     const r0 = res && res[0]
     if (r0 && r0.ok) { const s = (r0.stdout == null ? '' : String(r0.stdout)).trim(); if (s) return s }
     return null
   }

   // Run the fully-formed external argv through exec, FEEDING the staged prompt file to the process
   // stdin via a shell redirect. BOTH engines take the prompt on stdin: codex's trailing `-` reads
   // stdin, and cursor-agent reads stdin when given no positional prompt. The argv tokens are
   // shell-quoted so paths/effort strings can't break the command; the redirect is appended last so
   // the prompt is always delivered (no </dev/null guard — there is always a prompt here).
   // Returns the raw stdout string (or null on fail).
   async function _runArgv(argv, promptPath) {
     const quoted = argv.map((a) => shq(a)).join(' ')
     const res = await _exec([`${quoted} < ${shq(promptPath)}`])
     const r0 = res && res[0]
     if (r0 && r0.ok) return (r0.stdout == null ? '' : String(r0.stdout))
     return null
   }
   ```

- [ ] **Step 5:** Add the core `dispatchExternal` (COMPLETE code). It journals `external_dispatch` BEFORE returning, wraps the run in the UFR-5 timeout, captures preSHA for write roles, and commits via the adapter on write success:
   ```js
   async function _journalExternal(payload) {
     // Journal the external action as a FIRST-CLASS `external_dispatch` event (FR-6): the audit line's
     // `type` is external_dispatch (Task 4 added the type + the journal_entry.py --event-type flag), and
     // the payload is written AS-IS (non-secret {engine,effort,roleKind,verify,outcome}). A failed durable
     // append -> {ok:false} -> the caller treats it as UFR-6 (fail-closed, unauditable).
     return _execJson(
       `python3 ${LIB}/journal_entry.py --work-item ${shq(payload.workItem || '')} ` +
       `--event-type external_dispatch --payload ` +
       shq(JSON.stringify({ engine: payload.engine, effort: payload.effort, roleKind: payload.roleKind,
         verify: payload.verify, outcome: payload.outcome })))
   }

   // Scrub external-derived free-text (git stderr in a commit/dispatch-failure reason) BEFORE it enters
   // an owner-facing notice — the band's single scrub seam (pr_comment.py scrub reads stdin -> scrubbed
   // stdout, the same scrubber readout/parse_result use). On any exec/scrub failure fall back to a
   // fixed generic label (never surface the raw external text). Only used on the failure/notice path.
   async function _scrubReason(reason) {
     const s = reason == null ? '' : String(reason)
     if (!s) return s
     const res = await _exec([`printf '%s' ${shq(s)} | python3 ${LIB}/pr_comment.py scrub`])
     const r0 = res && res[0]
     if (r0 && r0.ok && r0.stdout != null) return String(r0.stdout)
     return 'external error (scrubbed)'
   }

   async function dispatchExternal(o) {
     o = o || {}
     const { engine, roleKind, effort, prompt, cwd, schema, timeoutSeconds } = o
     const limitMs = (Number(timeoutSeconds) > 0 ? Number(timeoutSeconds) : DEFAULT_STALL_LIMIT_SECONDS) * 1000
     const isWrite = (roleKind === 'build' || roleKind === 'fix')

     // 1. Stage prompt + schema to disk (via exec). The PROMPT file is fed to the external process
     //    stdin by _runArgv (both engines read the prompt from stdin); the SCHEMA path is passed to
     //    build-argv via --schema-path (codex --output-schema for read roles).
     const runId = `${engine}-${roleKind}-${Date.now()}`
     const promptPath = `/tmp/engine-${runId}.prompt`
     const schemaPath = `/tmp/engine-${runId}.schema.json`
     const writeInputs = await _exec([
       `cat > ${shq(promptPath)} <<'__SR_ENG_EOF__'\n${prompt || ''}\n__SR_ENG_EOF__`,
       `cat > ${shq(schemaPath)} <<'__SR_ENG_EOF__'\n${JSON.stringify(schema || {})}\n__SR_ENG_EOF__`,
     ])
     if (!(writeInputs && writeInputs.every && writeInputs.every((r) => r && r.ok))) {
       return { ok: false, reason: 'could-not-stage-external-inputs' }
     }

     // 2. preSHA (write roles only — read roles never mutate the tree, FR-7).
     let preSha = null
     if (isWrite) {
       preSha = await _captureHead(cwd)
       if (!preSha) return { ok: false, reason: 'could-not-capture-preSHA' }
     }

     // 3. Wrap the whole dispatch in the UFR-5 finite timeout. A stall -> {ok:false, reason:'timeout'}.
     const run = (async () => {
       const argvObj = await _execJson(
         `python3 ${LIB}/engine_adapter.py build-argv --engine ${shq(engine)} --role ${shq(roleKind)} ` +
         `--effort ${shq(String(effort == null ? '' : effort))} --cwd ${shq(cwd || '.')} ` +
         `--schema-path ${shq(schemaPath)}`)
       const argv = argvObj && Array.isArray(argvObj.argv) ? argvObj.argv : (Array.isArray(argvObj) ? argvObj : null)
       if (!argv) return { ok: false, reason: 'build-argv-failed' }

       // Feed the staged prompt file to the external process stdin (the argv itself carries no prompt).
       const rawStdout = await _runArgv(argv, promptPath)
       if (rawStdout == null) return { ok: false, reason: 'external-run-failed' }

       // parse-result SCRUBS external free-text at the adapter boundary (Task 6); pass raw stdout by file.
       const rawPath = `/tmp/engine-${runId}.out`
       const wroteRaw = await _exec([`cat > ${shq(rawPath)} <<'__SR_ENG_EOF__'\n${rawStdout}\n__SR_ENG_EOF__`])
       if (!(wroteRaw && wroteRaw[0] && wroteRaw[0].ok)) return { ok: false, reason: 'could-not-stage-external-output' }
       const parsed = await _execJson(
         `python3 ${LIB}/engine_adapter.py parse-result --engine ${shq(engine)} --role ${shq(roleKind)} ` +
         `--stdout-path ${shq(rawPath)}`)
       if (!parsed || parsed.ok !== true) return { ok: false, reason: (parsed && parsed.reason) || 'unreadable' }
       return parsed
     })()

     let parsed
     try {
       parsed = await Promise.race([
         run,
         new Promise((resolve) => setTimeout(() => resolve({ ok: false, reason: 'timeout' }), limitMs)),
       ])
     } catch (_e) { parsed = { ok: false, reason: 'external-run-threw' } }

     // 4. Read role: return findings straight through (no commit). Failure -> caller falls open to Claude.
     if (!isWrite) {
       await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
         outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') })
       return parsed.ok ? { findings: parsed.findings || [] } : { ok: false, reason: parsed.reason }
     }

     // 5. Write role failure -> only uncommitted edits exist; caller reuses resetUncommitted + falls open (UFR-2).
     if (!parsed.ok) {
       await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
         outcome: parsed.reason || 'failed' })
       return { ok: false, reason: parsed.reason }
     }

     // 6. Write success -> the adapter is the SOLE committer (preSHA-scoped fold; single Task-Id trailer).
     const commit = await _execJson(
       `python3 ${LIB}/engine_adapter.py commit --worktree ${shq(cwd)} --task-id ${shq(o.taskId || '')} ` +
       `--pre-sha ${shq(preSha)}`)
     if (!commit || commit.ok !== true) {
       // M1: commit.error carries raw git stderr — SCRUB it before it can reach an owner-facing notice.
       const reason = (commit && commit.error) ? await _scrubReason(commit.error) : 'commit-failed'
       // sec-101: the engine DID run and edited the worktree here, so this outcome must ALSO leave exactly
       // one audit line — otherwise commit-failure is the single external-dispatch outcome with no journal
       // entry (FR-6/UFR-6 symmetry gap). Journal BEFORE returning; the reason is already scrubbed above.
       await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
         outcome: 'commit-failed' })
       return { ok: false, reason }
     }

     // 7. Journal BEFORE returning the native worker shape (UFR-6: unauditable -> the caller fails closed).
     const j = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind,
       verify: 'pending', outcome: 'ok' })
     if (!(j && j.ok)) return { ok: false, reason: 'unauditable' }
     return { ok: true, signal: parsed.signal || 'ok', evidence: parsed.evidence || {} }
   }

   module.exports = { dispatchExternal, DEFAULT_STALL_LIMIT_SECONDS }
   ```

- [ ] **Step 6:** Run the smoke to PASS the review-path assertion:
   ```
   node plugins/superheroes/lib/tests/engine_dispatch_smoke.js
   ```
   Expected: `OK: engine_dispatch review-path` (no non-zero exit).

- [ ] **Step 7:** Extend the smoke with the **write (build) happy path**: stub the `git rev-parse HEAD` exec → `preSHA-abc\n`, `build-argv` → a workspace-write argv (`["codex","exec","--sandbox","workspace-write","-C","/tmp/wt","-"]`), the argv run → success stdout, `parse-result` → `{ok:true,signal:'ok',evidence:{testFailed:true,testPassed:true}}`, `engine_adapter.py commit` → `{ok:true,sha:'newsha'}`, `journal_entry.py` → `{ok:true}`. Assert `r.ok===true && r.signal==='ok' && r.evidence.testPassed===true`, and assert: a `git rev-parse HEAD` exec fired (preSHA captured); a `commit` exec fired; the dispatch-RUN command redirected the prompt file to stdin (contains `< ` and `.prompt`); AND the `journal_entry.py` exec carried `--event-type external_dispatch` (FR-6 first-class audit event) — `assert.ok(execLog.some((c) => c.includes('journal_entry.py') && c.includes('--event-type external_dispatch')))`.

- [ ] **Step 8:** Run to FAIL then confirm the impl already satisfies it (the write path exists) → PASS:
   ```
   node plugins/superheroes/lib/tests/engine_dispatch_smoke.js
   ```
   Expected: `OK: engine_dispatch write-path`.

- [ ] **Step 9:** Extend the smoke with the **UFR-5 timeout**, **UFR-6 unauditable**, and **sec-101 commit-failure audit** cases: (a) make the argv-run exec hang by returning a never-resolving promise for that route and pass `timeoutSeconds:0.01` → assert `r.reason==='timeout'`; (b) write happy path but `journal_entry.py` → `{ok:false}` → assert `r.reason==='unauditable'` (fail-closed, commit already made); (c) **commit-failure audit (sec-101)** — write happy path through the argv-run + `parse-result`, but `engine_adapter.py commit` → `{ok:false, error:'nothing to commit'}` → assert `r.ok===false` (the returned `reason` is the scrubbed commit error) AND that an `external_dispatch` audit line fired on this path — `assert.ok(execLog.some((c) => c.includes('journal_entry.py') && c.includes('--event-type external_dispatch') && c.includes('commit-failed')))` — so the engine-ran-but-commit-failed outcome is NOT the one external-dispatch outcome with no audit line (FR-6/UFR-6 symmetry). Run to PASS:
   ```
   node plugins/superheroes/lib/tests/engine_dispatch_smoke.js
   ```
   Expected: `OK: engine_dispatch timeout + unauditable + commit-failure audit`.

- [ ] **Step 10:** Register the smoke: add `"plugins/superheroes/lib/tests/engine_dispatch_smoke.js"` to `SHOWRUNNER_SMOKES` in `test_showrunner_node_smokes.py` (after the last entry, line 62). Run the registration + smoke gate:
    ```
    python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q
    ```
    Expected: all smokes pass (the new parametrized `engine_dispatch_smoke.js` id is green; the discovery-equality test still passes because `engine_dispatch_smoke.js` is neither `showrunner_*` nor `build_phase_*`).

- [ ] **Step 11:** Wire the bundle: in `bundle_showrunner.js` `MODULES` (line 19-23), insert `'engine_pref.js'` and `'engine_dispatch.js'` immediately BEFORE `'build_phase.js'` (they must load before `build_phase.js`/`showrunner.js`, which will require them in Tasks 11/12). New line:
    ```js
    'worker_recovery.js', 'task_review.js', 'engine_pref.js', 'engine_dispatch.js', 'build_phase.js',
    ```

- [ ] **Step 12:** Update the parity coupling: in `test_parity.py` `BUNDLED_NON_TWINS` (line 62-67), add `"engine_dispatch.js"` (it is a spine shell, not a pure decider twin). `engine_pref.js` is NOT added here — Task 1 registers it in `PARITY_TARGET_MODULES` + `PARITY_TWINS`; clause (c) then finds it already parity-listed.
    ```py
    BUNDLED_NON_TWINS = {
        "showrunner.js",
        "review_panel_shell.js",
        "build_phase.js",
        "test_pilot_phase.js",
        "engine_dispatch.js",
    }
    ```

- [ ] **Step 13:** Regenerate the committed bundle:
    ```
    node plugins/superheroes/lib/bundle_showrunner.js --write
    ```
    Expected: `wrote …/showrunner.bundle.js`.

- [ ] **Step 14:** Run the drift + parity gates to PASS:
    ```
    node plugins/superheroes/lib/bundle_showrunner.js --check && python3 -m pytest plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
    ```
    Expected: `bundle up to date` + all parity clauses (a/b/c) green (clause (c) now accepts `engine_dispatch.js` via BUNDLED_NON_TWINS and `engine_pref.js` via PARITY_TARGET_MODULES from Task 1).

- [ ] **Step 15:** Commit:
    ```
    git add plugins/superheroes/lib/engine_dispatch.js plugins/superheroes/lib/tests/engine_dispatch_smoke.js plugins/superheroes/lib/bundle_showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
    git commit -m "feat(superheroes): engine_dispatch.js dispatchExternal spine leaf + bundle wiring (#38)"
    ```

---

### Task 11 — `build_phase.js` engine branch (worker / fixer / final-review) + startup `__SR_ENGINE_PREFS` + node smokes

**Files:**
- Modify: `plugins/superheroes/lib/build_phase.js`
  - top requires (line 9-16): add `const engineDispatch = require('./engine_dispatch.js')` and `const enginePrefTwin = require('./engine_pref.js')`.
  - new helper near `_overrides()` (line 85-87): `_enginePrefs()` reading `globalThis.__SR_ENGINE_PREFS`.
  - `buildOneTask` worker leaf (line 337-342): route to `dispatchExternal` when the implementation engine is external.
  - `reviewLoop` fixer leaf (line 461-464): same.
  - `runFinalReview` reviewer leaf (line 487-494) → reviewer engine (read-only) and final-fixer leaf (line 504-511) → implementation engine.
- Create: `plugins/superheroes/lib/tests/build_phase_engine_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` — `SHOWRUNNER_SMOKES`: append `"plugins/superheroes/lib/tests/build_phase_engine_smoke.js"`. *(This name IS auto-discovered by the guard — `build_phase_*_smoke.js` — so it MUST appear in the list or the discovery-equality test fails.)*
- Modify: `plugins/superheroes/lib/showrunner.bundle.js` — regenerated.

**Interfaces:**
- Consumes: `engineDispatch.dispatchExternal({engine, roleKind, effort, prompt, cwd, schema, taskId, workItem}) → {ok,signal,evidence}` (Task 10).
- Consumes (the engine_pref twin, Task 1): `enginePrefTwin.resolveEngine('build'|'fix', prefs) → 'claude'|'codex'|'cursor'`; `enginePrefTwin.resolveEffort(engine, roleKind, overrides) → token|null`.
- Consumes (UFR-4 run-time write preflight, Task 9 CLI): `python3 lib/engine_authz.py test-dispatch --engine <implEngine> --cwd <wt>` → JSON `{"engine":E,"ok":bool}`. Run ONCE per run before the FIRST external WRITE dispatch (build|fix); cache the verdict for the run (do not re-probe per task). `!ok` → the implementation role (build AND fixes) falls open to Claude for the run + one non-blocking notice. READ roles (review) need NO preflight.
- Consumes (unchanged spine, reused): `resetUncommitted(wt, branch)` (line 288-294) is the UFR-2 discard primitive; `fenceOrPark`, the write-time trailer gather (`build_state_cli.py gather`), `journal_entry.py`, `verify_command_cli.py`, `reviewPanel` — all BYTE-UNCHANGED.
- Consumes: `globalThis.__SR_ENGINE_PREFS` (planted at startup; see Task 12 for the `showrunner()` startup pipe — build_phase reads the same global, mirroring `_overrides()`).
- Produces: the SAME `{parked, reason}` / `{terminal}` return shapes — no downstream change.

Steps:

- [ ] **Step 1:** Write the failing smoke `build_phase_engine_smoke.js` for **build-then-verify on an external implementation engine (Codex)**. Set `globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }`. Stub `engine_dispatch.js`'s `dispatchExternal` by monkey-patching the required module (`require('../engine_dispatch.js').dispatchExternal = async (o) => {...}`) to return `{ok:true, signal:'ok', evidence:{testFailed:true,testPassed:true}}` and RECORD the call `o`. Stub `global.agent` via `makeAgent`/`execRoute` so `engine_authz.py test-dispatch` → `{engine:'codex',ok:true}` (the UFR-4 preflight passes), `build_state_cli.py gather` → clean (`unmapped_commits:0`), `journal_entry.py` → `{ok:true}`, and `fence_cli.py` → `{ok:true}`. Call `bp.buildOneTask('wi', 5, {id:'1',title:'One'}, 'br', '1', '/tmp/wt')` (it delegates to reviewLoop — stub the review agent to `complete`). Assert: (a) `dispatchExternal` was called with `roleKind:'build'`, `engine:'codex'`, `cwd:'/tmp/wt'`, `taskId:'1'`; (b) NO `worker` label agent() fired (the native worker was NOT used); (c) the verify-gate + trailer-gather ran unchanged (the `build_state_cli.py gather` exec fired); (d) the `engine_authz.py test-dispatch` preflight exec fired exactly ONCE for the run (cached).

- [ ] **Step 2:** Run to FAIL:
   ```
   node plugins/superheroes/lib/tests/build_phase_engine_smoke.js
   ```
   Expected: assertion fails — `dispatchExternal` never called (the native `worker` agent() ran) because the engine branch does not exist yet.

- [ ] **Step 3:** Add the requires + `_enginePrefs()` helper to `build_phase.js`. After line 16:
   ```js
   const engineDispatch = require('./engine_dispatch.js')
   const enginePrefTwin = require('./engine_pref.js')
   ```
   After `_overrides()` (line 87):
   ```js
   // engine prefs: mirror _overrides — read from globalThis.__SR_ENGINE_PREFS (planted by the Task-12
   // startup pipe; absent in test/throwaway runs -> both 'claude' -> the native agent() path, UNCHANGED).
   function _enginePrefs() {
     const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
     return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
   }

   // FR-9 effort overrides: the effort sub-map keyed by role_kind {review,build,fix} lives INSIDE the
   // engine-prefs object (NOT the model-tier __SR_OVERRIDES map). resolveEffort reads this map; absent -> null.
   function _effortOverrides() {
     const p = _enginePrefs()
     return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
   }
   ```

- [ ] **Step 4:** Add a small local router `_implDispatch` right above `buildOneTask` (line 331) that keeps the Claude path byte-identical and routes external engines through `dispatchExternal`, falling open to the native worker on any external failure (UFR-1/UFR-2). It ALSO runs the UFR-4 run-time write preflight ONCE per run (cached) before the first external WRITE — a denied grant → the impl role falls fully open to Claude for the run + one non-blocking notice:
   ```js
   // UFR-4 run-time write preflight — cache the verdict for the whole run so we probe the host's
   // autoMode.allow grant ONCE (not per task). null = not yet probed. The probe runs the engine's OWN
   // write command inside the worktree; a denied/failed grant -> the impl role falls open to Claude.
   let _writeAuthOk = null
   let _writeAuthNotified = false
   async function _implWriteAuthorized(engine, wt) {
     if (_writeAuthOk !== null) return _writeAuthOk
     const v = await execJson(
       `python3 ${LIB}/engine_authz.py test-dispatch --engine ${shq(engine)} --cwd ${shq(wt)}`)
     _writeAuthOk = !!(v && v.ok === true)
     if (!_writeAuthOk && !_writeAuthNotified) {
       _writeAuthNotified = true
       try { log(`build: ${engine} is not authorized to write in this run (autoMode.allow not granted) — the implementation role falls open to Claude for the whole run (UFR-4)`) } catch (_) {}
     }
     return _writeAuthOk
   }

   // Route the write role (build|fix) to the chosen implementation engine. claude -> the existing agent()
   // path, BYTE-UNCHANGED. external -> dispatchExternal; on ANY non-success reset uncommitted edits (UFR-2)
   // and fall open to the native agent() (UFR-1). preSHA/commit-discipline live inside dispatchExternal.
   async function _implDispatch({ workItem, roleKind, taskId, prompt, wt, branch, nativeAgentCall }) {
     const engine = enginePrefTwin.resolveEngine(roleKind, _enginePrefs())
     if (engine === 'claude') return nativeAgentCall()
     // UFR-4: before the FIRST external WRITE, confirm the host grants this engine write authority.
     // Denied -> fall open to Claude for the whole run (build AND fixes) + one notice. Read roles skip this.
     if (!(await _implWriteAuthorized(engine, wt))) return nativeAgentCall()
     // FR-9: effort override comes from the engine-prefs effort sub-map (keyed by role_kind), NOT the
     // model-tier _overrides() map (keyed by role->model — resolveEffort could never match it).
     const effort = enginePrefTwin.resolveEffort(engine, roleKind, _effortOverrides())
     const res = await engineDispatch.dispatchExternal({
       engine, roleKind, effort, prompt, cwd: wt, schema: { type: 'object', required: ['ok'] },
       taskId, workItem,
     })
     if (res && res.ok) return res
     // UFR-2: a failed/stalled external write left only uncommitted edits -> discard, then redo on Claude.
     await resetUncommitted(wt, branch)
     try { log(`build: ${engine} ${roleKind} did not complete (${(res && res.reason) || 'unknown'}) — falling open to Claude`) } catch (_) {}
     return nativeAgentCall()
   }
   ```
   Note: `_implDispatch` handles ONLY the write roles (build|fix). The read (review) role in `runFinalReview` routes through the reviewer-engine branch (Step 8) which needs NO write preflight (FR-7 read-only).

- [ ] **Step 5:** Rewire the `buildOneTask` worker leaf (line 337-342) to call `_implDispatch` with the native call preserved verbatim as the fall-open closure:
   ```js
       const worker = await _implDispatch({
         workItem, roleKind: 'build', taskId: task.id, wt, branch,
         prompt:
           `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: write the test(s), `
           + `run to observe FAIL, implement, run to observe PASS. Commit with a trailer line `
           + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Return JSON `
           + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool}}.`,
         nativeAgentCall: () => agent(
           `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: write the test(s), `
           + `run to observe FAIL, implement, run to observe PASS. Commit with a trailer line `
           + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Return JSON `
           + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool}}.`,
           { label: 'worker', schema: { type: 'object', required: ['ok'] } }),
       })
   ```
   Everything after `if (worker.ok) {` (the trailer gather at 348, the journal at 367, the review handoff at 374) is UNCHANGED — the external result carries the same `{ok,signal,evidence}` shape.

- [ ] **Step 6:** Run the build-then-verify assertion to PASS:
   ```
   node plugins/superheroes/lib/tests/build_phase_engine_smoke.js
   ```
   Expected: `OK: build routes to the external implementation engine + verify/audit unchanged`.

- [ ] **Step 7:** Rewire the `reviewLoop` fixer leaf (line 461-464) through `_implDispatch` with `roleKind:'fix'`, preserving the native call:
   ```js
       const _fixFindings = JSON.stringify((d.blocking || []).concat(d.cannot_verify || []))
       await _implDispatch({
         workItem, roleKind: 'fix', taskId: task.id, wt, branch,
         prompt: `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer "Task-Id: ${task.id}": ${_fixFindings}`,
         nativeAgentCall: () => agent(
           `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
           + `"Task-Id: ${task.id}": ${_fixFindings}`,
           { label: 'fixer', model: fixerModel }),
       })
   ```

- [ ] **Step 8:** Rewire `runFinalReview`'s reviewer leaf (line 487-494) to route the READ role to the reviewer engine (read-only), preserving the native call and the `null => did-not-complete` contract:
   ```js
     globalThis.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
       const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
       const prompt =
         `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
         + `Return ONLY a JSON object {"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if nothing to flag).`
       if (rEngine !== 'claude') {
         const eff = enginePrefTwin.resolveEffort(rEngine, 'review', _effortOverrides())
         const res = await engineDispatch.dispatchExternal({
           workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
           schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } },
         })
         // UFR-7: an unreadable/incomplete external review -> null -> the shell re-runs on Claude, never
         // recorded clean. dispatchExternal returns {findings} on success or {ok:false} on failure.
         if (res && Array.isArray(res.findings)) return res.findings
         const out = await agent(prompt, { label: `reviewer:${round}`, model: reviewerModel,
           schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
         return (out && Array.isArray(out.findings)) ? out.findings : null
       }
       const out = await agent(prompt, { label: `reviewer:${round}`, model: reviewerModel,
         schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
       return (out && Array.isArray(out.findings)) ? out.findings : null
     }
   ```
   Rewire the final-fixer leaf (line 504-511) through `_implDispatch` `roleKind:'fix'` (preserve the `fenceOrPark` guard at line 507 UNCHANGED — the fence stays before any external write). **CRITICAL contract (FIX I5):** the `fixStep` closure that `reviewPanel` invokes MUST keep returning the `{fixed:[...], deferred:[...]}` report shape the real `build_phase.js:504-511` returns (`return { fixed: blockers.map((b)=>b.id||b.title) }`). `review_panel_shell.js:runFixStep` treats a FALSY report as a fix-FAILURE → `halted` → the phase parks; and `recordDeferred` reads `report.fixed`. So the closure must NOT return `_implDispatch`'s raw dispatch result (`{ok,signal,evidence}` or a native agent result) or `undefined` — it wraps the dispatch and then returns the report. COMPLETE:
   ```js
     const fixStep = async (blockers) => {
       if (!(await fenceOrPark(workItem, generation))) return null   // UFR-10 fence — UNCHANGED (line 507)
       // The whole-branch final review has NO per-task id in scope (mirror the real 504-511 closure):
       // use the work-item as the fix dispatch's task id for the trailer/journal.
       await _implDispatch({
         workItem, roleKind: 'fix', taskId: workItem, wt, branch,
         prompt: `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
         nativeAgentCall: () => agent(
           `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
           { label: 'final-fixer', model: fixerModel }),
       })
       // Always return the {fixed, deferred} REPORT shape (never the raw dispatch result / undefined):
       // a truthy report so runFixStep does NOT treat it as a fix-failure, and recordDeferred can read .fixed.
       // This preserves the exact contract of the real build_phase.js:504-511 (`return { fixed: [...] }`).
       return { fixed: blockers.map((b) => b.id || b.title), deferred: [] }
     }
   ```
   The load-bearing point is the RETURN: `{ fixed: [...], deferred: [] }`, never `_implDispatch`'s return value or `undefined`.

- [ ] **Step 9:** Extend the smoke with the **fail-closed trio**, **UFR-2 discard**, and the **UFR-4 write-preflight-denied fall-open**: (a) `dispatchExternal` returns `{ok:false,reason:'external-run-failed'}` → assert `resetUncommitted` fired AND the native `worker` agent() then ran (fall open, loop not blocked); (b) verify-fail path is UNCHANGED — assert the native `verify_command_cli.py`/`reviewPanel` verify gate still runs on the external build result (the smoke asserts the `runFinalReview` reviewPanel got the external result and the `legKind.code` verify path is untouched); (c) `mixed reviewer=codex / impl=cursor` — set `__SR_ENGINE_PREFS={reviewer:'codex', implementation:'cursor', effort:{}}` and assert the reviewer leaf dispatched `roleKind:'review',engine:'codex'` while the fixer dispatched `roleKind:'fix',engine:'cursor'` (FR-15 split); (d) **UFR-4 preflight denied** — impl engine external (`implementation:'codex'`) but `engine_authz.py test-dispatch` → `{engine:'codex',ok:false}`. **The module-level `_writeAuthOk`/`_writeAuthNotified` cache in `build_phase.js` persists across scenarios in the same process — scenario (a)'s happy path already cached `_writeAuthOk=true`, so this denied scenario would inherit the stale `true` and pass for the WRONG reason.** Before running it, RESET the module using the repo's established idiom (see `showrunner_cmdrunner_cwd_smoke.js:31` — `delete require.cache[require.resolve('../showrunner.js')]` + re-require) applied to `build_phase.js`, so the denied preflight runs against a fresh `_writeAuthOk = null`:
   ```js
   // reset the preflight-cache-carrying module so this scenario re-probes from a clean _writeAuthOk = null
   delete require.cache[require.resolve('../build_phase.js')]
   delete require.cache[require.resolve('../engine_dispatch.js')]   // re-establish the dispatch spy on the fresh instance
   const engineDispatch = require('../engine_dispatch.js')
   const dispatchCalls = []
   engineDispatch.dispatchExternal = async (o) => { dispatchCalls.push(o); return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }
   const bp = require('../build_phase.js')
   ```
   Then, with `engine_authz.py test-dispatch` → `{engine:'codex',ok:false}`, assert: `dispatchExternal` was NEVER called for a write role (`dispatchCalls.every((o) => o.roleKind !== 'build' && o.roleKind !== 'fix')`), the native `worker` (and `fixer`) agent() ran instead, the run was NOT blocked (loop completes), and a non-blocking notice was logged; (e) **FIX I5 final-fixer report shape** — with an external implementation engine and a whole-branch blocking finding routed through `runFinalReview`'s `fixStep`, spy `recordDeferred` (or inspect the deferred-set) and assert the `fixStep` closure returned a truthy `{fixed:[...], deferred:[...]}` report (NOT `_implDispatch`'s raw `{ok,...}` result and NOT `undefined`) so `review_panel_shell.runFixStep` did NOT treat it as a fix-failure/`halted`, and `recordDeferred` saw the `fixed` ids. Run to PASS:
   ```
   node plugins/superheroes/lib/tests/build_phase_engine_smoke.js
   ```
   Expected: `OK: fail-closed trio + UFR-2 discard + UFR-4 write-preflight-denied fall-open + final-fixer {fixed,deferred} contract + mixed reviewer!=impl`.

- [ ] **Step 10:** Add the **commit-discipline multi-round fold invariant** to the smoke as a documented assertion at the JS boundary: across two fix rounds (round 1 and round 2 both external), assert `dispatchExternal` was called TWICE with `roleKind:'fix'` and the SAME `taskId`, and that each call carried its own dispatch (preSHA capture + commit happen inside `dispatchExternal`, so the JS boundary asserts a fresh dispatch per round — the per-`preSHA` fold correctness is unit-tested in Task 7). Run to PASS:
    ```
    node plugins/superheroes/lib/tests/build_phase_engine_smoke.js
    ```
    Expected: `OK: per-round external fix dispatch (fold invariant boundary)`.

- [ ] **Step 11:** Register the smoke: append `"plugins/superheroes/lib/tests/build_phase_engine_smoke.js"` to `SHOWRUNNER_SMOKES` (line 62). Confirm the existing build_phase smokes still pass unchanged (the Claude path is byte-identical when `__SR_ENGINE_PREFS` is absent → both 'claude'):
    ```
    python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q
    ```
    Expected: all smokes green incl. the pre-existing `build_phase_loop_smoke.js` / `build_phase_final_review_smoke.js` (which set no engine prefs → native path unchanged).

- [ ] **Step 12:** Regenerate the bundle + run drift/parity:
    ```
    node plugins/superheroes/lib/bundle_showrunner.js --write && node plugins/superheroes/lib/bundle_showrunner.js --check
    python3 -m pytest plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
    ```
    Expected: `wrote …` → `bundle up to date`; parity green.

- [ ] **Step 13:** Commit:
    ```
    git add plugins/superheroes/lib/build_phase.js plugins/superheroes/lib/tests/build_phase_engine_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/showrunner.bundle.js
    git commit -m "feat(superheroes): route native build worker/fixer/final-review through the implementation & reviewer engines (#38)"
    ```

---

### Task 12 — `showrunner.js` `reviewCodeLeaves` engine branch + startup `__SR_ENGINE_PREFS` load + node smokes

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.js`
  - top requires (line 6-14): add `const engineDispatch = require('./engine_dispatch.js')` and `const enginePrefTwin = require('./engine_pref.js')`.
  - `reviewCodeLeaves` (line 57-119): `reviewerAgent` (65-73) + `synthesisLeaf` (75-84) → reviewer engine (read-only); `fixStep` (87-97) → implementation engine (FR-15).
  - `showrunner()` startup (line 697-707): after the `__SR_OVERRIDES` load, add the `__SR_ENGINE_PREFS` load pipe (mirror exactly).
- Create: `plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` — append the new smoke.
- Modify: `plugins/superheroes/lib/showrunner.bundle.js` — regenerated.

**Interfaces:**
- Consumes: `engineDispatch.dispatchExternal(...)` (Task 10); `enginePrefTwin.resolveEngine/resolveEffort` (Task 1).
- Consumes (the Task 3 startup CLI): `python3 plugins/superheroes/lib/engine_pref_load.py` → prints JSON `{"reviewer","implementation"}` to stdout, exit 0 always, belt-and-suspenders fail-open to both `"claude"`.
- Consumes (unchanged): `reviewPanel`, `panel_tally.roundGate` (the `cannot-certify`/`incomplete` path is exactly UFR-7's incomplete-panel signal — reused, no new logic).
- Produces: identical `reviewCodeLeaves` return `{ reviewerAgent, synthesisLeaf, fixStep, recordDeferred }` and identical `showrunner()` flow; only `globalThis.__SR_ENGINE_PREFS` is newly planted.

Steps:

- [ ] **Step 1:** Write the failing smoke `showrunner_engine_review_smoke.js` — **PART A** (startup load), mirroring `showrunner_task17_smoke.js`'s PART A exactly. Stub `global.agent` so an `exec` prompt containing `engine_pref_load.py` returns `[{index:0,ok:true,stdout:'{"reviewer":"codex","implementation":"cursor","effort":{"review":"medium"}}'}]`, `recover_entry.py` → `{}`, `definition_doc.py read-gate` → `{"review":"passed"}`, all other exec → `{}`, and non-exec → `null` (park). Delete `globalThis.__SR_ENGINE_PREFS`, run `await sr.showrunner({workItem:'wi-eng'})` in a try/catch, then assert an exec containing `engine_pref_load.py` fired AND `globalThis.__SR_ENGINE_PREFS` deep-equals `{reviewer:'codex',implementation:'cursor',effort:{review:'medium'}}` (the whole object, incl. the FR-9 effort sub-map, is carried). Add the fail-safe case: `engine_pref_load.py` → `{ok:false,stdout:'not-json'}` → assert `__SR_ENGINE_PREFS` is `{reviewer:'claude',implementation:'claude',effort:{}}` (belt-and-suspenders, never crashes).

- [ ] **Step 2:** Run to FAIL:
   ```
   node plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js
   ```
   Expected: assertion (a1/a2) fails — no `engine_pref_load.py` exec fired and `__SR_ENGINE_PREFS` is undefined (the startup load does not exist yet).

- [ ] **Step 3:** Add the requires to `showrunner.js` after line 14:
   ```js
   const engineDispatch = require('./engine_dispatch.js')
   const enginePrefTwin = require('./engine_pref.js')
   ```

- [ ] **Step 4:** Add the startup load in `showrunner()` immediately after the `__SR_OVERRIDES` block (after line 707), mirroring the model-tier pipe (COMPLETE code):
   ```js
     // #38: load the per-role engine preferences once at startup from core.md's machine block. The
     // Python CLI prints {"reviewer","implementation"} (both "claude" when absent/unreadable — the safe
     // degenerate path, exit 0 always). Fail-safe: any exec error or bad JSON yields both-"claude" so the
     // review/build leaves take the byte-unchanged agent() path.
     const _epRes = await exec(['python3 plugins/superheroes/lib/engine_pref_load.py'])
     let _epMap = { reviewer: 'claude', implementation: 'claude', effort: {} }
     try {
       const _p = (_epRes[0] && _epRes[0].stdout) || ''
       const _parsed = JSON.parse(_p)
       if (_parsed && typeof _parsed === 'object' && !Array.isArray(_parsed)) {
         // Carry the whole object — reviewer/implementation AND the FR-9 effort sub-map (keyed by
         // role_kind), so resolveEffort can source the owner's effort override from __SR_ENGINE_PREFS.effort
         // (NOT from the model-tier __SR_OVERRIDES map, which is keyed by role->model).
         _epMap = {
           reviewer: _parsed.reviewer || 'claude',
           implementation: _parsed.implementation || 'claude',
           effort: (_parsed.effort && typeof _parsed.effort === 'object' && !Array.isArray(_parsed.effort)) ? _parsed.effort : {},
         }
       }
     } catch (_) {}
     if (typeof globalThis !== 'undefined') globalThis.__SR_ENGINE_PREFS = _epMap
   ```

- [ ] **Step 5:** Run PART A to PASS:
   ```
   node plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js
   ```
   Expected: `OK (a): startup plants __SR_ENGINE_PREFS (incl. effort sub-map) via exec(engine_pref_load.py); fail-safe both-claude+empty-effort on bad parse`.

- [ ] **Step 6:** Add module-local `_enginePrefs()` + `_effortOverrides()` readers near `authorModel()` (line 374-377):
   ```js
   function _enginePrefs() {
     const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
     return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
   }

   // FR-9 effort overrides: the role_kind-keyed effort sub-map INSIDE __SR_ENGINE_PREFS (NOT the model-tier
   // __SR_OVERRIDES map, which is keyed by role->model). resolveEffort reads this; absent -> null -> default.
   function _effortOverrides() {
     const p = _enginePrefs()
     return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
   }
   ```

- [ ] **Step 7:** Extend the smoke — **PART B** (reviewer leaf routes to the reviewer engine, read-only, incl. a Critical). Build the leaves via `sr` internals is not exported; instead exercise through `reviewCodeLeaves` if exported, else via `reviewCodePhase` with a stubbed panel. Grounded approach: `reviewCodeLeaves` is module-internal — call `reviewCodePhase('wi', {worktree:'/tmp/wt', expectedHead:'h', runDir:'…'})` with `__SR_ENGINE_PREFS={reviewer:'codex',implementation:'claude'}`, monkey-patch `require('../engine_dispatch.js').dispatchExternal` to return, for a `roleKind:'review'` call, `{findings:[{file:'p.py',line:9,title:'path traversal',severity:'Critical',evidence:'e'}]}` and RECORD the call. Stub `global.agent` for the config/verify/git leaves as in `showrunner_reviewcode_smoke.js`. Assert: (a) `dispatchExternal` was called with `roleKind:'review'`, `engine:'codex'`; (b) NO native reviewer `agent()` (label `architecture-reviewer` etc.) fired for that dispatch; (c) the Critical finding flowed into the panel (the run's gate is `changes-requested`, not `passed`).

- [ ] **Step 8:** Run PART B to FAIL:
   ```
   node plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js
   ```
   Expected: assertion fails — `dispatchExternal` never called; the native reviewer agent ran (the engine branch in `reviewerAgent` does not exist yet).

- [ ] **Step 9:** Rewire `reviewCodeLeaves.reviewerAgent` (line 65-73) with the engine branch (COMPLETE code; preserve the `null => did not complete` contract that feeds `panel_tally.roundGate`'s incomplete detection = UFR-7):
   ```js
     const reviewerAgent = async (reviewer, context, rubric, runDir, round) => {
       const model = REVIEW_DEEP.has(reviewer) ? tiers.reviewerDeep : tiers.reviewer
       const prompt =
         `You are the ${reviewer}. Review the built change for work-item ${context} against the ` +
         `${rubric} rubric. Return ONLY a JSON object {"findings":[...]} whose findings array lists each ` +
         `finding ({file, line, title, severity, evidence}); return {"findings":[]} if nothing to flag.${targetSuffix}`
       const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
       if (rEngine !== 'claude') {
         // FR-9: source the effort override from the engine-prefs effort sub-map (keyed by role_kind),
         // NOT the model-tier __SR_OVERRIDES map (keyed by role->model — resolveEffort could never match it).
         const eff = enginePrefTwin.resolveEffort(rEngine, 'review', _effortOverrides())
         const res = await engineDispatch.dispatchExternal({
           workItem: context, engine: rEngine, roleKind: 'review', effort: eff, prompt,
           cwd: (target.worktree || procCwd()),
           schema: FINDINGS_SCHEMA,
         })
         // UFR-7: unreadable/incomplete -> null; the panel's cannot-certify path re-runs the round on
         // Claude, never recorded clean. A successful external review returns {findings}.
         if (res && Array.isArray(res.findings)) return res.findings
         const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
         return (out && Array.isArray(out.findings)) ? out.findings : null
       }
       const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
       return (out && Array.isArray(out.findings)) ? out.findings : null
     }
   ```
   Note: the engine branches read the FR-9 effort override via `_effortOverrides()` (added in Step 6 — the role_kind-keyed `__SR_ENGINE_PREFS.effort` sub-map), NOT the model-tier `__SR_OVERRIDES` map that `authorModel` reads (that map is keyed by role→model, so `resolveEffort` — keyed by role_kind — could never match it; that mismatch was the FR-9 dead-override bug this fix closes). No `_overrides()` helper is needed for the engine branch.

- [ ] **Step 10:** Rewire `synthesisLeaf` (line 75-84) to run on the reviewer engine (read-only) when external, preserving the `[]`-on-miss contract; and rewire `fixStep` (line 87-97) to the **implementation** engine (FR-15 — the fix that resolves a finding runs on the implementation engine, not the reviewer), preserving the `null => fix failure` contract. Both keep their native `agent()` call as the fall-open closure (same pattern as step 9). For `fixStep`:
    ```js
     const fixStep = async (blockers, runDir) => {
       const prompt =
         `You are the code-fixer. For each blocking finding below, attempt a real fix and COMMIT it to ` +
         `the change under review. If a finding traces to an upstream phase (plan, tasks, or build) rather ` +
         `than the code under review, leave it unresolved and tag its originating phase. Never edit the ` +
         `review-loop machinery (refused edits surface as findings, not applied). Return ONLY a JSON object ` +
         `{"fixed": [<titles>], "deferred": [{"id", "severity", "parentOrigin"?}]}.\n\n` +
         `Blocking findings:\n${JSON.stringify(blockers)}${targetSuffix}`
       const iEngine = enginePrefTwin.resolveEngine('fix', _enginePrefs())
       if (iEngine !== 'claude') {
         const eff = enginePrefTwin.resolveEffort(iEngine, 'fix', _effortOverrides())
         const res = await engineDispatch.dispatchExternal({
           workItem: 'review-code', engine: iEngine, roleKind: 'fix', effort: eff, prompt,
           cwd: (target.worktree || procCwd()), schema: FIX_REPORT_SCHEMA,
         })
         if (res && res.ok) return { fixed: [], deferred: [] }   // external fix committed by the adapter; verify gate re-runs downstream
         const out = await agent(prompt, withModel(tiers.fixer, { label: 'code-fixer', schema: FIX_REPORT_SCHEMA }))
         return out || null
       }
       const out = await agent(prompt, withModel(tiers.fixer, { label: 'code-fixer', schema: FIX_REPORT_SCHEMA }))
       return out || null
     }
   ```

- [ ] **Step 11:** Extend the smoke with **UFR-7 incomplete/unreadable → re-run on Claude** and **mixed reviewer=Codex/impl=Cursor**: (a) `dispatchExternal` for `roleKind:'review'` returns `{ok:false,reason:'unreadable'}` → assert the native reviewer `agent()` then fired for that reviewer AND the round was not recorded clean; (b) set `__SR_ENGINE_PREFS={reviewer:'codex',implementation:'cursor'}` and assert the reviewer dispatch used `engine:'codex'` while `fixStep`'s dispatch used `engine:'cursor',roleKind:'fix'`. Run PART B to PASS:
    ```
    node plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js
    ```
    Expected: `OK (b): reviewer read-only on reviewer engine (Critical flows) + UFR-7 re-run on Claude + mixed reviewer!=impl (FR-15 split)`.

- [ ] **Step 12:** Register the smoke (append to `SHOWRUNNER_SMOKES`, line 62); run the smoke gate + confirm `showrunner_reviewcode_smoke.js` still passes unchanged (no engine prefs set in that smoke → native path):
    ```
    python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q
    ```
    Expected: all green.

- [ ] **Step 13:** Regenerate the bundle + run drift/parity:
    ```
    node plugins/superheroes/lib/bundle_showrunner.js --write && node plugins/superheroes/lib/bundle_showrunner.js --check
    python3 -m pytest plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
    ```
    Expected: `bundle up to date`; parity green.

- [ ] **Step 14:** Commit:
    ```
    git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/showrunner.bundle.js
    git commit -m "feat(superheroes): reviewCodeLeaves engine branch + startup __SR_ENGINE_PREFS load (#38)"
    ```

---

### Task 13 — Standalone `/review-code` skill engine branch (SKILL.md additive) + auto-fix-loop.md scrub-boundary note

**Files:**
- Modify: `plugins/superheroes/skills/review-code/SKILL.md` — the model-tier resolve block (line 116-132): add an ADDITIVE engine-resolve step alongside the `REVIEWER_MODEL`/`DEEP_MODEL`/`MECH_MODEL` block; add engine-branch dispatch prose in §3 (line 290-292). Do NOT restructure the 5-row dispatch table at line 296-303 (guarded by `test_dispatch_tables.py`).
- Modify: `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` — the `--post API Commands` section (line 253-296): add the secret-scrub-boundary note at the review.json build step (line 257-270).

**Interfaces:**
- Consumes (earlier tasks): `python3 ${ROOT_DIR}/lib/engine_pref_load.py` → `{"reviewer","implementation"}`; `engine_adapter.py build-argv|parse-result` for the external dispatch. `parse_result` pre-scrubs finding `body`/`suggestion` at the adapter boundary.
- Produces: no new lib; additive markdown only. `validate_skills.py` must stay green — bodyCeiling for `superheroes/review-code` is 499 (current SKILL.md = 477 lines → ~22-line headroom); required trigger phrases in the description are UNTOUCHED. **Cite NO new `CONVENTIONS §N` here.** `validate_skills.py`'s `check_conventions_refs` scans only `SKILL.md`, not `reference/*.md`, so a dangling ref in `auto-fix-loop.md` would NOT be caught — and Task 16 (which creates §7.5) runs later, so a forward `§7.5` cite would dangle across commits. Describe the cross-engine behavior INLINE without a `§7.5` reference; §7.5 exists as the durable contract but the skill files do not forward-cite it.

Steps:

- [ ] **Step 1:** Read the guard to confirm the constraint (no failing test to author here — this is a markdown-only, guard-protected task; the guard IS the test):
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_dispatch_tables.py -q
   ```
   Expected: passes now (baseline). Capture that it enforces "exactly one row per agents/ file + names every slug" against the 5-row table at SKILL.md:296-303.

- [ ] **Step 2:** Add the ADDITIVE engine-resolve step in SKILL.md after the model-tier block (after line 127, before the "When dispatching specialists" prose at 129). Insert (keep it tight — ~10 lines to respect the 499 ceiling):
   ```markdown
   **Resolve the per-role engine (orthogonal to the model tier).** The reviewer engine runs the five
   specialists (read-only); the implementation engine runs the auto-fix (FR-15). Default `claude` — a
   project that set nothing behaves exactly as today.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   EP=$(python3 "$ROOT_DIR/lib/engine_pref_load.py")            # {"reviewer","implementation"} (both "claude" if unset)
   REVIEWER_ENGINE=$(echo "$EP" | jq -r '.reviewer // "claude"')
   IMPL_ENGINE=$(echo "$EP" | jq -r '.implementation // "claude"')
   ```
   ```
   Then add one sentence to §3's dispatch prose (line 292): "When `$REVIEWER_ENGINE` is `codex` or `cursor`, dispatch each of the five specialists through `engine_adapter.py` (read-only sandbox) instead of the named subagent — the persona and `$RUBRIC` are unchanged, and each still returns its dimension's findings JSON; an unreadable or missing specialist slot is the same `cannot-certify` signal, re-run on Claude (UFR-7). When `$REVIEWER_ENGINE` is `claude`, dispatch the named subagents exactly as below."

- [ ] **Step 3:** Confirm the 5-row table is UNCHANGED and the dispatch-table guard still passes:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_dispatch_tables.py -q
   ```
   Expected: green (the table at 296-303 is byte-identical; engine-awareness is prose above it).

- [ ] **Step 4:** Add the implementation-engine note to §3 for the auto-fix: one sentence where the fixer subagent is described (SKILL.md line 285-286 auto-fix loop bullet): "The auto-fix runs on `$IMPL_ENGINE` (FR-15): when it is `codex`/`cursor`, the fix is written by the external engine via `engine_adapter.py` (workspace-write) and committed by the adapter, then the same verify gate runs; when it is `claude`, the fixer subagent runs as today."

   **Design note (sec-102 — no code, reviewer clarity):** Add one clarifying sentence to this SKILL.md auto-fix prose (or as an adjacent note) recording WHERE the write-authorization gate lives for THIS surface: the standalone `/review-code` auto-fix path is model-driven markdown (not the native `build_phase.js` run leg), so it has NO run-time `engine_authz.py test-dispatch` preflight — instead it relies on the **host classifier's `autoMode.allow` deny to fall open behaviorally** (an ungranted `Bash(codex exec:*)`/`Bash(cursor-agent:*)` dispatch is denied by the host, the external write never happens, and the fix falls open to Claude — behavioral UFR-4). This is consistent with the plan's decision that the run-time write preflight lives only in the native build leg (Task 11's `_implWriteAuthorized`); the standalone skill deliberately does not reimplement it in markdown. Documentation only — do NOT add any preflight code to the skill.

- [ ] **Step 5:** Add the secret-scrub-boundary note to `auto-fix-loop.md` at the `--post` review.json build step (after line 270, right after the `EOF`):
   ```markdown
   > **External-engine secret hygiene (#38).** When the reviewer engine is Codex or Cursor, each
   > finding's `body`/`suggestion` free-text is **already secret-scrubbed** at the adapter boundary
   > (`engine_adapter.parse_result` runs `readout.scrub` before the finding enters the standard form),
   > so this `--post` payload — which copies `body`/`suggestion` straight into the public PR comment via
   > `gh api … /reviews` with no scrub of its own — carries no external secret in the clear. This is the
   > one surface the native `readout.build_readout` handoff does not gate; the adapter pre-scrub covers it.
   ```
   *(Describe the behavior inline; do NOT add a `CONVENTIONS §7.5` citation here — §7.5 is created later in Task 16, and `check_conventions_refs` does not even scan `reference/*.md`, so a forward cite would silently dangle. There is no "no conventions-ref violation" claim tied to §7.5 to make.)*

- [ ] **Step 6:** Run the skills validator + the dispatch-table guard to PASS:
   ```
   python3 .github/scripts/validate_skills.py && python3 -m pytest plugins/superheroes/lib/tests/test_dispatch_tables.py -q
   ```
   Expected: `validate_skills.py` exits 0 (line-count under the 499 ceiling for `superheroes/review-code`; `auto-fix-loop.md` is 296+~7 lines >100 and already opens with a Contents heading — verify it still does; required phrases intact; NO new `CONVENTIONS §N` citation was added, so `check_conventions_refs` has nothing new to resolve). Dispatch-table guard green.

- [ ] **Step 7:** Confirm `auto-fix-loop.md` still opens with a Contents heading (it is >100 lines; check_toc requires the first heading to be `Contents`/`Table of Contents`). If the note was inserted mid-file this is unaffected — the FIRST heading is unchanged. Re-run:
   ```
   python3 .github/scripts/validate_skills.py
   ```
   Expected: no `table-of-contents:` violation for `auto-fix-loop.md`.

- [ ] **Step 8:** Commit:
   ```
   git add plugins/superheroes/skills/review-code/SKILL.md plugins/superheroes/skills/review-code/reference/auto-fix-loop.md
   git commit -m "feat(superheroes): additive engine branch in the standalone /review-code skill + --post scrub-boundary note (#38)"
   ```

---

### Task 14 — `configure` engine onboarding (set-up.md + view-and-tune.md + SKILL.md pointer)

**Files:**
- Modify: `plugins/superheroes/skills/configure/reference/set-up.md` — add a new engine-onboarding section after §4 "Offer the heavier heroes" (after line 47, before §5 secrets at line 49), since engine selection is an optional heavier capability that must land after the verify command (§3) is set.
- Modify: `plugins/superheroes/skills/configure/reference/view-and-tune.md` — add an engine-preference tune bullet to the §2 tune menu (line 29-33).
- Modify: `plugins/superheroes/skills/configure/SKILL.md` — add a one-line pointer noting the engine step lives in set-up.md/view-and-tune.md (near the Step-2 route pointers, line 51-53).

**Interfaces:**
- Consumes (earlier tasks): the CLIs — `python3 lib/engine_detect.py` (bare → both-engines readiness MATRIX JSON, FR-11); `python3 lib/engine_authz.py snippet --host <host> --engine <E>` (`authorization_snippet`, SHOWN never written); `python3 lib/engine_authz.py test-dispatch --engine <E> --cwd .` (`implementation_dispatch_allowed(cwd, engine, run=None)` → `{"engine":E,"ok":bool}`, the test dispatch, bounded by `engine_pref.resolve_timeout` = UFR-5); `core_md` write of `enginePreferences {reviewer,implementation}` (schemaVersion 1→2, Task 2).
- Produces: markdown only; no lib change (so no new lib test here — the libs are unit-tested in Tasks 1-9). `validate_skills.py` must stay green: `set-up.md` is 59 lines (well under 100 → no Contents heading required); `view-and-tune.md` is 60 lines → keep it under 100 (if the addition pushes it past 100, add a Contents heading — it currently has none); `configure/SKILL.md` required trigger phrases in its description are UNTOUCHED.

Steps:

- [ ] **Step 1:** Add the engine-onboarding section to `set-up.md` after §4 (line 47). Insert (host-neutral actions, one-question-at-a-time, INTERACTIVE=false strict posture — FR-11/13/14, UFR-4/5):
   ```markdown
   ## 4.5 — Offer an external engine per role (FR-11/12/13/14), decline still completes

   After the verify command (§3) is set — external implementers are verify-gated, so this must follow it —
   offer to bring **Codex** and/or **Cursor** into the loop, per role (reviewer engine, implementation
   engine), each independent, default **Claude**. A decline leaves both roles on Claude and set-up still
   completes.

   1. **Availability (FR-11).** Probe both engines and show a readiness matrix — installed + signed in, or
      what to fix:

      ```bash
      ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
      python3 "$ROOT_DIR/lib/engine_detect.py"   # JSON verdict per engine: installed/authed + remediation
      ```
      A not-ready engine is shown with its next-command remediation; it is never offered as ready.

   2. **Per-role preference (FR-12).** Ask, one at a time, which engine to use for the reviewer role and
      for the implementation role (only ready engines are selectable). Record the pick into `core.md`'s
      machine block `enginePreferences: {reviewer, implementation}` via `core_md` (schemaVersion 2). An
      absent block reads as both `claude`.

   3. **Show the build authorization — never apply it (FR-13).** If an external **implementation** engine
      is chosen, an external autonomous write needs a one-time owner grant. Show the exact snippet and where
      it goes; do **not** write it:

      ```bash
      python3 "$ROOT_DIR/lib/engine_authz.py" snippet --host claude --engine <codex|cursor>
      # prints the autoMode.allow block + its location (.claude/settings.local.json). SHOW it; never write it.
      ```

   4. **Test dispatch (FR-14), bounded by the stall limit (UFR-5).** After the owner grants the
      authorization, run one throwaway external write and report success / failure / no-response — the
      no-response case is bounded by the same finite limit as UFR-5 (`engine_pref.resolve_timeout`):

      ```bash
      python3 "$ROOT_DIR/lib/engine_authz.py" test-dispatch --engine <codex|cursor> --cwd .
      # -> {"engine":E,"ok":true}  (ready)
      # -> {"engine":E,"ok":false} (denied or no-response bounded by the UFR-5 limit -> falls open to
      #    Claude; tell the owner how to enable, leave the engine not-ready with a retry instruction)
      ```
      A failed or timed-out test dispatch leaves the engine **not-ready** — builds and mechanical fixes fall
      open to Claude until it works. Never present a not-working engine as ready.

   **Headless (`INTERACTIVE=false`).** Take the strict/provisional posture: probe and record what is
   detectable, but never block and never apply the authorization — leave any external implementation engine
   not-ready until an interactive run can grant + test it.
   ```

- [ ] **Step 2:** Add the tune bullet to `view-and-tune.md` §2 tune menu (after line 32, within the bullet list at 29-33):
   ```markdown
   - **Change the per-role engine** (reviewer engine / implementation engine) → the engine step in
     `reference/set-up.md` §4.5 (availability → preference → show-authorization → test-dispatch), writing
     `enginePreferences` through `core_md`. Set a role back to `claude` (or clear it) to fall fully open.
   ```

- [ ] **Step 3:** Add the SKILL.md pointer. In `configure/SKILL.md` Step 2 (near line 53, the view-and-tune pointer), add one sentence: "Engine onboarding (Codex/Cursor per role — availability, preference, show-authorization, test-dispatch) lives in `set-up.md` §4.5 and is tunable via `view-and-tune.md` §2."

- [ ] **Step 4:** Run `validate_skills.py` to PASS:
   ```
   python3 .github/scripts/validate_skills.py
   ```
   Expected: exit 0. Check specifically: `view-and-tune.md` line count — after the ~3-line bullet it is ~63 lines (< 100, no Contents heading required); `set-up.md` grows to ~110 lines with §4.5 → **it now exceeds 100 and needs a Contents heading**. Verify:
   ```
   wc -l plugins/superheroes/skills/configure/reference/set-up.md
   ```
   If `> 100`, add a `## Contents` heading as the FIRST heading of `set-up.md` listing its sections (§1–§5 + §4.5 + the recovery section). Re-run `validate_skills.py` → no `table-of-contents:` violation.

- [ ] **Step 5:** Confirm NO new `CONVENTIONS §N` citation was introduced in these skill files (FIX I6 — §7.5 is created later in Task 16, so a forward cite would dangle across commits; the cross-engine behavior is described inline in set-up.md/view-and-tune.md without a `§7.5` reference). Run:
   ```
   grep -rn "§7.5\|CONVENTIONS §" plugins/superheroes/skills/configure/ || echo "no CONVENTIONS §N citation in configure skill files — good"
   python3 .github/scripts/validate_skills.py
   ```
   Expected: the grep finds NO new `§7.5`/`CONVENTIONS §N` citation in the configure skill files; `validate_skills.py` exits 0 (nothing new for `check_conventions_refs` to resolve).

- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/skills/configure/reference/set-up.md plugins/superheroes/skills/configure/reference/view-and-tune.md plugins/superheroes/skills/configure/SKILL.md
   git commit -m "feat(superheroes): configure onboarding for per-role external engines (availability/pref/authorization/test-dispatch) (#38)"
   ```

---

### Task 15 — Owner-authority boundary + secret-scrub INTEGRATION tests (spec DoD)

**Files:**
- Modify: `plugins/superheroes/lib/tests/test_enforcer.py` — add a test asserting the enforcer's GATED_COMMANDS still gate the owner-authority set when the command is invoked BY / FOR an external engine (the enforcer fires on the host's Bash invocation regardless of who authored the command — confinement, not policing the external process).
- Create: `plugins/superheroes/lib/tests/test_engine_secret_scrub.py` — end-to-end assertion that a secret in external-engine output never reaches the `--post` PR comment / owner notice in the clear (through the adapter `parse_result` scrub boundary).

**Interfaces:**
- Consumes: `enforcer.classify_command(command, host="codex", in_scope=True) → (decision, reason)`; `decision[0]` ∈ `"allow"|"deny"|"ask"`. GATED_COMMANDS = merge-pr / merge-api / merge-graphql / release / run-workflow / force-push / push-to-default (enforcer.py:70-82). Claude host + gated → `"ask"`; Codex host + gated → `"deny"`.
- Consumes: `engine_adapter.parse_result(engine, role_kind, stdout)` (Task 6) — scrubs finding `body`/`suggestion` via `readout.scrub` at the boundary; `readout.scrub(text, root=None) → (scrubbed, ok)` (fail-closed to `"[omitted — scrub error]"`).
- Produces: two integration tests wired into the pytest gate (`plugins/superheroes/lib/tests/`).

Steps:

- [ ] **Step 1:** Write the failing owner-authority test in `test_enforcer.py` (mirror the existing `test_denies_every_merge_shape` idiom exactly — `enforcer.classify_command(cmd)[0]`):
   ```py
   def test_external_engine_paths_still_gate_owner_authority():
       # #38: an external producer is CONFINED, not policed — the enforcer fires on the HOST's Bash
       # invocation regardless of whether the command was authored for a codex/cursor dispatch. The
       # owner-authority set (merge / release / force-push / push-to-default / run-workflow) stays gated,
       # so an external engine can never autonomously merge/force-push/push-to-default.
       for cmd in (
           "gh pr merge 42 --squash",
           "gh api -X PUT repos/o/r/pulls/42/merge",
           "gh release create v1.0.0",
           "git push --force origin superheroes/x",
           "git push origin HEAD:main",
           "gh workflow run deploy.yml",
       ):
           # Codex host: gated -> deny (ask is not honored -> fail-safe deny + allowance flow).
           assert enforcer.classify_command(cmd, host="codex", in_scope=True)[0] == "deny", cmd
           # Claude host: gated -> ask (a native human prompt the agent cannot answer itself).
           assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "ask", cmd

   def test_external_engine_own_feature_branch_push_is_allowed():
       # The producer's OWN feature-branch push (no :main / force) is allowed — the named residual is
       # contained by the single-owner threat model (the engine is the owner's own signed-in tool).
       assert enforcer.classify_command("git push origin superheroes/x-abc", host="codex")[0] == "allow"
       assert enforcer.classify_command("cursor-agent -f -m composer", host="codex")[0] == "allow"
   ```

- [ ] **Step 2:** Run to observe the CURRENT behavior (this SHOULD already pass — the enforcer is unchanged; the test documents/locks the confinement guarantee that #38 relies on):
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_enforcer.py -q
   ```
   Expected: PASS (the enforcer is byte-unchanged; this is a lock-in / DoD test, not a behavior change). If any case is unexpectedly `allow`, that is a real gap → escalate; otherwise the confinement guarantee holds and is now asserted.

- [ ] **Step 3:** Write the failing secret-scrub integration test `test_engine_secret_scrub.py`. It exercises the real `engine_adapter.parse_result` boundary with a fake external stdout carrying a secret in a finding's `body`/`suggestion`, and asserts the parsed finding's free-text is scrubbed (never the raw secret). COMPLETE test:
   ```py
   import json
   import os
   import sys

   sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
   import engine_adapter  # Task 5/6

   _SECRET = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

   def test_external_review_finding_freetext_is_scrubbed_at_the_adapter_boundary():
       # A codex --output-schema review whose finding body leaks a secret. parse_result must scrub the
       # body/suggestion via readout.scrub BEFORE the finding enters the standard findings form, so the
       # standalone /review-code --post PR comment (built straight from body/suggestion) can carry no
       # secret in the clear (Secret-hygiene NFR).
       stdout = json.dumps({"findings": [{
           "file": "a.py", "line": 3, "title": "leak", "severity": "Critical",
           "body": f"token found: {_SECRET}", "suggestion": f"rotate {_SECRET}",
       }]})
       parsed = engine_adapter.parse_result("codex", "review", stdout)
       assert parsed["ok"] is True
       blob = json.dumps(parsed["findings"])
       assert _SECRET not in blob, "the raw secret must never survive parse_result (adapter scrub boundary)"

   def test_external_build_evidence_carries_no_freetext():
       # The build adapter's evidence is constrained to {testFailed,testPassed} booleans — never raw
       # stdout — so the journal payload (written as-is) can carry no external free-text.
       stdout = json.dumps({"ok": True, "signal": "ok",
                            "evidence": {"testFailed": False, "testPassed": True},
                            "leaked": f"secret {_SECRET}"})
       parsed = engine_adapter.parse_result("codex", "build", stdout)
       assert parsed["ok"] is True
       assert set(parsed["evidence"].keys()) <= {"testFailed", "testPassed"}
       assert _SECRET not in json.dumps(parsed["evidence"])
   ```

- [ ] **Step 4:** Run to FAIL (if `engine_adapter.parse_result` is not yet built in the branch, this errors on import — that is the expected RED until Tasks 5/6 land; sequence this task after Tasks 5-6, per the ordering). Once Tasks 5-6 are present:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_engine_secret_scrub.py -q
   ```
   Expected initially: FAIL if the adapter does not scrub (raw secret survives) — which drives the Task 6 scrub requirement; GREEN once `parse_result` scrubs and constrains `evidence`.

- [ ] **Step 5:** Confirm the two integration tests are picked up by the CI pytest glob (they live in `plugins/superheroes/lib/tests/`, already in the CI command). Run the combined gate:
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_enforcer.py plugins/superheroes/lib/tests/test_engine_secret_scrub.py -q
   ```
   Expected: all green (given Tasks 5-6 present).

- [ ] **Step 6:** Commit:
   ```
   git add plugins/superheroes/lib/tests/test_enforcer.py plugins/superheroes/lib/tests/test_engine_secret_scrub.py
   git commit -m "test(superheroes): owner-authority confinement + external-output secret-scrub integration (#38 DoD)"
   ```

---

### Task 16 — Docs (CONVENTIONS §7.5 + README + model_tier.py docstring) + LIVE-VERIFICATION checklist

**Files:**
- Modify: `CONVENTIONS.md` — insert a new `### 7.5 Cross-engine contract` after §7.4 (after line 745, before the `---` at line 746 and `## 8` at 748).
- Modify: `README.md` — the-architect / review-crew / workhorse hero-block prose (line 34-66 / 69-111 / 144-169): a short engine-selection note in each block's intro prose.
- Modify: `plugins/superheroes/lib/model_tier.py` — docstring lines 4-5 ("Workhorse's Build leg … is NOT a consumer"): note the native build leg is now an ENGINE consumer, engine axis orthogonal to the model tier.
- (No new file for the live checklist — it is recorded in THIS tasks doc as the explicit non-CI live-verification section at the end; see step 6.)

**Interfaces:**
- Consumes: nothing at runtime — docs only. `validate_skills.py` cares only about *skill* files, not README/CONVENTIONS/model_tier; `validate_marketplace.py`/`validate_hosts.py` are unaffected by these edits. `model_tier.py`'s docstring change must not alter any code path (the docstring is not parsed by tests).
- Produces: §7.5 (the durable cross-engine contract; §7.5 MAY reference the skills, but the skill files do NOT forward-cite §7.5 — FIX I6 — so there is no cross-commit dangling ref to resolve); README hero notes; the accurate `model_tier.py` build-engine-contract line.

Steps:

- [ ] **Step 1:** Insert §7.5 into `CONVENTIONS.md` after line 745 (COMPLETE prose):
   ```markdown

   ### 7.5 Cross-engine contract (host-run-on vs engine-dispatched-to)

   The **host** is the harness the plugin *runs on* (§7.1–§7.2 — Claude Code or Codex). The **engine** is
   the agent a working role is *dispatched to* — `claude` (the default, unchanged), `codex`, or `cursor` —
   chosen per role (reviewer engine, implementation engine) by the owner in `configure`. These are
   orthogonal axes: the host is where the plugin executes; the engine is which model family does a role's
   work. An engine is selected *below* the host, at the dispatch leaf.

   Two postures are held strictly separate, mirroring `model_tier`:
   - **Engine *selection* fails open.** An unknown / unavailable / unauthorized / stalled engine silently
     degrades to Claude — the same posture `model_tier` documents for a bad tier ("a wrong/absent tier is a
     cost concern, never a safety one"). No run hangs or hard-fails on engine choice.
   - **A completed external *result* fails closed.** A build or fix that fails or can't run verify stops the
     run; an unauditable run stops; an unreadable or incomplete review is re-run on Claude, never accepted
     as green. This reuses the existing gates — no new safety logic.

   **Build-engine contract.** The native build leg (`build_phase.js`) is now an *engine* consumer: its
   worker, fixer, and final-review-fix leaves route to the implementation engine, and its whole-branch
   review leaf routes to the reviewer engine, via `engine_dispatch.js` → `engine_adapter.py`. The engine
   axis is orthogonal to the model tier: `model_tier` still governs *which Claude model* runs when the
   engine is `claude`; when the engine is external, `engine_pref.resolve_effort` governs the engine's depth.

   **Confinement + hygiene.** External reviewers run read-only; external implementers run workspace-write,
   confined to the managed build worktree, with **no remote authority** — the band owns every push / PR /
   merge through its `enforcer.py`-gated path (an external producer can never autonomously merge, force-push,
   or push to the default branch). All external free-text is secret-scrubbed at the adapter boundary
   (`engine_adapter.parse_result` → `readout.scrub`) so every downstream surface — including the standalone
   `/review-code --post` PR comment — is clean. The build authorization is the owner's to grant; the band
   shows it and never applies it.
   ```

- [ ] **Step 2:** Verify §7.5 is now a well-formed CONVENTIONS heading:
   ```
   grep -n "^### 7.5" CONVENTIONS.md
   ```
   Expected: one match. Then run the full skills validator (it re-reads CONVENTIONS for `check_conventions_refs`):
   ```
   python3 .github/scripts/validate_skills.py
   ```
   Expected: exit 0. (No skill file forward-cites §7.5 — FIX I6 — so `check_conventions_refs` has no §7.5 citation to resolve; this step just confirms the new heading is well-formed and the validator stays green.)

- [ ] **Step 3:** Add the engine note to the-architect prose (README line 34-47 region), one sentence after the post-approval-path paragraph (line 47): "Engine selection is set per role in `configure` (Claude by default); the-architect's front-half authoring stays on Claude — the engine axis applies to the review and build roles."

- [ ] **Step 4:** Add the engine note to review-crew prose (README line 71-94 region), one sentence in the "Calibrated to your project" bullet area (after line 90): "You can also run the panel on a **different model family** — set the reviewer engine to Codex or Cursor in `configure` — for a cross-family safety net; findings flow through the same auto-fix loop unchanged, and the fix is written by the implementation engine."

- [ ] **Step 5:** Add the engine note to workhorse prose (README line 146-156 region), one sentence after the build description (after line 154, before the GitHub-access blockquote at 156): "The build and its mechanical fixes can run on an external **implementation engine** (Codex or Cursor, chosen in `configure`); every external result is verify-gated and audited, and the producer's owner-authority boundary is unchanged — it still never merges, force-pushes, or pushes to the default branch."

- [ ] **Step 6:** Update the `model_tier.py` module docstring. The only content change is the "Workhorse's Build leg … is NOT a consumer" sentence (real file lines 4-5) → note the native build leg is now an *engine* consumer and that the engine axis is orthogonal to the model tier; the fail-open paragraph and defaults note (real lines 9-12) are carried over VERBATIM. Replace the whole docstring (real file lines 1-13, the `"""…"""` block) with this COMPLETE new docstring:
   ```py
   """Band-wide model-tier policy: role -> dispatch model name (the cost/perf knob).

   Pure + deterministic. review-code is the first consumer; the review trio
   (review-spec/review-plan/review-tasks) and audit-debt wire it next. Workhorse's
   Build leg defers to SDD's own model heuristic and is NOT a model_tier consumer;
   note that the native build leg (build_phase.js) IS now an *engine* consumer (#38) —
   the engine axis (claude|codex|cursor via engine_pref) is orthogonal to this model
   tier and governs which agent family runs a role, not which Claude model.
   Returns the short names the Agent/Skill dispatch layer
   accepts ("sonnet"/"opus"/"haiku"), or None to inherit the session model.

   Fail-OPEN to the capable default — a wrong/absent tier is a cost concern, never a
   safety one (contrast escalation.py, which fails CLOSED). Defaults below apply when
   the profile is silent; a caller may pass {role: model} overrides from the project
   calibration profile.
   """
   ```
   This is the ENTIRE new module docstring (the `import json` line and everything below it are unchanged). Apply it with an Edit that replaces the current `"""…"""` block (real lines 1-13) with the block above.

- [ ] **Step 7:** Confirm nothing regressed — run the model_tier tests + parity (the docstring change is inert but re-run to be safe):
   ```
   python3 -m pytest plugins/superheroes/lib/tests/test_model_tier.py plugins/superheroes/lib/tests/test_parity.py -q
   ```
   Expected: green (docstring-only change; no behavior).

- [ ] **Step 8:** Commit:
   ```
   git add CONVENTIONS.md README.md plugins/superheroes/lib/model_tier.py
   git commit -m "docs(superheroes): cross-engine contract §7.5 + README hero engine notes + model_tier build-engine docstring (#38)"
   ```

- [ ] **Step 9:** **Run the full CI gate locally** to confirm the whole change is green end-to-end before handoff:
   ```
   python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_hosts.py && python3 .github/scripts/validate_skills.py && python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
   ```
   Expected: all validators exit 0; pytest all-green (includes the node smokes wrapper, parity, bundle-drift, dispatch-table, enforcer, and the new engine tests).

---

## LIVE-VERIFICATION checklist (manual / dogfood — NOT wired into CI; spec + plan DoD)

CI runs on `ubuntu-latest` with **no external CLI installed or signed in**, so the following acceptance
criteria cannot run in CI and are recorded here as an explicit, one-time manual/dogfood verification
(the pattern this project already uses for live-dependent features — the #115/#102/#112 eval runs). This
section is **not silently dropped**: it is the owner-run live gate that closes the spec's FR-3 / FR-4 /
confinement acceptance. Perform on a machine with **real Codex (`codex` 0.141.0+) and real Cursor
(`cursor-agent` 2026.06.19+) installed and signed in**, with the build authorization granted.

- [ ] **Real Codex review surfaces the seeded Critical.** On a branch seeded with the known
      path-traversal defect (a file path built from unsanitized input escaping its intended directory —
      the plan's fixture), set reviewer engine = Codex and run review; confirm the panel reports that
      defect as a **Critical** finding in the standard findings form (FR-3 acceptance, Codex).
- [ ] **Real Cursor review surfaces the seeded Critical.** Same branch, reviewer engine = Cursor;
      confirm the Critical is reported in the standard findings form (FR-3 acceptance, Cursor).
- [ ] **Real build on Codex.** Implementation engine = Codex; build a task; confirm the change lands on
      the work-item branch, passes the verify command, and the audit log names engine=codex + the
      high-effort setting (FR-4 / FR-5 / FR-6 build acceptance).
- [ ] **Real build on Cursor.** Implementation engine = Cursor (composer); build a task; confirm the
      change lands, passes verify, audit names engine=cursor + composer (FR-4 / FR-10).
- [ ] **Mixed reviewer=Codex / implementation=Cursor auto-fix (FR-15).** Run `/review-code` on a branch
      with a fixable finding; confirm the review is performed by Codex (read-only, tree unchanged during
      review — FR-7) and the auto-fix is written by Cursor.
- [ ] **Cursor remote-confinement acceptance (Risks).** Verify a live Cursor implementer **cannot reach
      the remote** (network-off confinement). **If that cannot be guaranteed**, the fallback is to default
      Cursor implementation to the **diff-apply path** (read-only engine → emit diff → band applies it
      natively) rather than direct workspace-write — record which posture was taken. Codex
      `--sandbox workspace-write` already disables network (structural), so its remote-confinement is
      verified by construction.
- [ ] **Owner-authority holds live.** Confirm no external run merges, force-pushes, or pushes to the
      default branch on its own — every remote mutation is the band's `enforcer.py`-gated path (the
      automated `test_enforcer.py` locks the classifier; this box confirms it end-to-end in a live run).
- [ ] **Secret hygiene live.** Confirm a secret present in real external-engine output never reaches a PR
      comment or an owner notice in the clear (Secret-hygiene NFR; the automated
      `test_engine_secret_scrub.py` locks the adapter boundary; this box confirms it end-to-end).
