# Dual-Host Runtime Parity Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement first-class Claude Code and Codex packaging for the superheroes marketplace while preserving the existing Claude runtime surface and allowing both hosts to coexist in one project.

**Architecture:** Build two host-native package surfaces over one shared contract layer. Claude keeps its existing root package files, skills, and bundled agents. Codex gets package-local manifests, skills, helper/runtime files, shared contract copies, and installed-package verification; shared schemas/readers enforce bidirectional artifact compatibility without moving existing writers to v2.

**Tech Stack:** Python 3.12, pytest, jsonschema, Markdown skill files, JSON manifests, GitHub Actions, existing review-crew/test-pilot/the-architect helpers.

---

## Source Documents

- `docs/superpowers/specs/2026-06-18-dual-host-first-class-design.md`
- `docs/superpowers/plans/2026-06-18-dual-host-plugin-runtime-parity.md`
- `CONVENTIONS.md`
- `.github/scripts/validate_marketplace.py`

## File Map

Create:

- `.agents/plugins/marketplace.json`
- `.github/scripts/validate_dual_host_marketplace.py`
- `eval/fixtures/dual-host/README.md`
- `eval/fixtures/dual-host/manifests/*.json`
- `eval/fixtures/dual-host/contracts/*.json`
- `eval/fixtures/dual-host/conformance/*.json`
- `eval/lib/schemas/dual-host/*.schema.json`
- `eval/lib/tests/test_dual_host_marketplace.py`
- `eval/lib/tests/test_runtime_layout.py`
- `eval/lib/tests/test_dual_host_contracts.py`
- `eval/lib/tests/test_dual_host_conformance.py`
- `plugins/*/shared/dual_host_artifacts.py`
- `plugins/*/codex/*/lib/dual_host_artifacts.py`
- `plugins/review-crew/shared/README.md`
- `plugins/review-crew/shared/REVIEWERS.md`
- `plugins/review-crew/shared/reviewers/*-reviewer.md`
- `plugins/review-crew/codex/review-crew/.codex-plugin/plugin.json`
- `plugins/review-crew/codex/review-crew/shared/README.md`
- `plugins/review-crew/codex/review-crew/shared/rubric/review-base.md`
- `plugins/review-crew/codex/review-crew/shared/reviewers/*-reviewer.md`
- `plugins/review-crew/codex/review-crew/lib/*.py`
- `plugins/review-crew/codex/review-crew/skills/*/SKILL.md`
- `plugins/test-pilot/shared/README.md`
- `plugins/test-pilot/codex/test-pilot/.codex-plugin/plugin.json`
- `plugins/test-pilot/codex/test-pilot/shared/README.md`
- `plugins/test-pilot/codex/test-pilot/lib/*.py`
- `plugins/test-pilot/codex/test-pilot/templates/*`
- `plugins/test-pilot/codex/test-pilot/skills/*/SKILL.md`
- `plugins/the-architect/shared/README.md`
- `plugins/the-architect/codex/the-architect/.codex-plugin/plugin.json`
- `plugins/the-architect/codex/the-architect/shared/README.md`
- `plugins/the-architect/codex/the-architect/lib/*.py`
- `plugins/the-architect/codex/the-architect/templates/*`
- `plugins/the-architect/codex/the-architect/skills/*/SKILL.md`
- `plugins/review-crew/lib/tests/test_shared_reviewers.py`
- `plugins/review-crew/lib/tests/test_codex_review_crew_contracts.py`
- `docs/dual-host-runtime.md`
- `docs/dual-host-migration.md`

Modify:

- `.github/workflows/ci.yml`
- `.gitignore`
- `README.md`
- `CONTRIBUTING.md`
- `RELEASING.md`
- `plugins/review-crew/agents/*-reviewer.md`

Do not change:

- Existing Claude plugin names, versions, or root package locations.
- Existing workflow writer behavior for review-crew, test-pilot, or the-architect.
- Existing runtime state locations.

## Verification Command

Run this after every task that changes executable code or test fixtures:

```bash
python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_dual_host_marketplace.py --phase metadata && python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
```

After Codex package roots, shared docs, and Codex skills exist, run strict validation:

```bash
python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_dual_host_marketplace.py && python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
```

## Task 1: Codex Marketplace And Dual-Host Validator

**Files:**

- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/*/codex/*/.codex-plugin/plugin.json`
- Create: `.github/scripts/validate_dual_host_marketplace.py`
- Create: `eval/fixtures/dual-host/manifests/*.json`
- Test: `eval/lib/tests/test_dual_host_marketplace.py`

- [ ] **Step 1: Add the Codex marketplace and minimal manifests**

Write `.agents/plugins/marketplace.json`:

```json
{
  "name": "superheroes",
  "interface": {
    "displayName": "Superheroes"
  },
  "plugins": [
    {
      "name": "the-architect",
      "source": { "source": "local", "path": "./plugins/the-architect/codex/the-architect" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    },
    {
      "name": "review-crew",
      "source": { "source": "local", "path": "./plugins/review-crew/codex/review-crew" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    },
    {
      "name": "test-pilot",
      "source": { "source": "local", "path": "./plugins/test-pilot/codex/test-pilot" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

Add `.codex-plugin/plugin.json` in each `plugins/<name>/codex/<name>` Codex package root with `name`, `version`, `description`, `author`, `skills`, and `interface` metadata. Set `skills` to `./skills/`. Copy version and author from the matching Claude manifest so metadata validation can enforce drift from the first task without exposing the Claude root `skills/` tree to Codex discovery. Descriptions may use host-native wording, but must be non-empty and reviewed for equivalent intent before release.

- [ ] **Step 2: Write failing marketplace tests**

Create `eval/lib/tests/test_dual_host_marketplace.py` with subprocess tests for:

```python
STRICT_FAILING_FIXTURES = {
    "codex-marketplace.bad-source.json": "Codex source",
    "marketplace-name-drift.json": "marketplace name",
    "plugin-version-drift.json": "plugin version",
    "codex-invalid-source-object.json": "source",
    "codex-source-traversal.json": "source path",
    "codex-source-wrong-plugin-dir.json": "plugins/<name>/codex/<name>",
    "codex-source-claude-root.json": "Claude root",
    "codex-entry-version.json": "version",
    "codex-invalid-policy.json": "policy",
    "codex-missing-interface.json": "interface",
    "codex-unsupported-host-field.json": "host",
    "codex-invalid-semver.json": "SemVer",
    "plugin-set-drift.json": "plugin set",
    "author-drift.json": "author",
    "codex-missing-shared-readme.json": "shared/README.md",
    "codex-missing-skill.json": "skills",
}
```

Add one metadata-phase test that runs missing shared README and missing skill fixtures with:

```bash
python3 .github/scripts/validate_dual_host_marketplace.py --phase metadata
```

Expected: exit code `0`, output contains `warning:`.

- [ ] **Step 3: Implement the validator**

Implement these functions in `.github/scripts/validate_dual_host_marketplace.py` with the exact names and return contracts below:

- `load_json(path: Path) -> dict | None`: returns parsed JSON, appends a readable error for missing or invalid files, and never raises JSON errors to callers.
- `validate_claude_marketplace(repo: Path, errors: list[str]) -> dict`: validates `.claude-plugin/marketplace.json`, returns `{name, plugins}` where each plugin record includes `name`, `version`, `author`, `description`, and resolved `source`.
- `validate_codex_marketplace(repo: Path, phase: str, errors: list[str], warnings: list[str]) -> dict`: validates `.agents/plugins/marketplace.json`, returns the same normalized `{name, plugins}` shape as Claude, reads `.codex-plugin/plugin.json` from each `plugins/<entry-name>/codex/<entry-name>` package root, and uses `warnings` rather than `errors` for missing `shared/README.md` and skill files when `phase == "metadata"`.
- `validate_cross_host_drift(claude: dict, codex: dict, errors: list[str]) -> None`: compares marketplace name, plugin set, plugin manifest version, author name, and non-empty descriptions. Descriptions remain host-native; validation enforces presence only. Equivalent description intent is a release-review checklist item, not a CI inference.
- `main(argv: list[str] | None = None) -> int`: parses `--phase metadata|strict`, prints warnings before errors, prints `dual-host marketplace + plugin manifests valid` on success, and returns `1` on any error.

Rules:

- Resolve Codex `source.path` with `Path.resolve()`.
- Reject any resolved path not equal to `repo / "plugins" / entry_name / "codex" / entry_name`, so the marketplace entry, Codex package-root directory basename, and `.codex-plugin/plugin.json` `name` all match the Codex plugin contract while staying isolated from the Claude root.
- Reject `plugins[].version` and unsupported Codex manifest fields including `host`.
- Require Codex `policy.installation`, `policy.authentication`, `category`, `skills`, and `interface`.
- Compare plugin versions from plugin manifests, not marketplace entries.

- [ ] **Step 4: Verify Task 1**

Run:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_dual_host_marketplace.py --phase metadata
python3 -m pytest eval/lib/tests/test_dual_host_marketplace.py -q
```

Expected: Claude validator passes; dual-host metadata phase passes with warnings for missing package-local shared files and Codex skills, while still enforcing marketplace paths and `.codex-plugin/plugin.json` metadata; marketplace tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add .agents/plugins/marketplace.json plugins/*/codex/*/.codex-plugin/plugin.json .github/scripts/validate_dual_host_marketplace.py eval/fixtures/dual-host/manifests eval/lib/tests/test_dual_host_marketplace.py
git commit -m "feat: add codex marketplace validation"
```

## Task 2: Shared Runtime Layout Guards

**Files:**

- Create: `plugins/*/shared/README.md`
- Create: `plugins/*/codex/*/shared/README.md`
- Create: `plugins/review-crew/codex/review-crew/shared/rubric/review-base.md`
- Test: `eval/lib/tests/test_runtime_layout.py`

- [ ] **Step 1: Write failing layout tests**

Create `eval/lib/tests/test_runtime_layout.py` with exact expected sets:

```python
EXPECTED_CLAUDE_SKILLS = {
    "review-crew": {"audit-debt", "review-code", "review-init", "review-plan", "review-spec", "review-tasks"},
    "test-pilot": {"test-pilot-execute", "test-pilot-init", "test-pilot-plan"},
    "the-architect": {"discovery", "plan", "tasks", "writing-specs"},
}

EXPECTED_REVIEW_CREW_AGENTS = {
    "architecture-reviewer.md",
    "code-reviewer.md",
    "premortem-reviewer.md",
    "security-reviewer.md",
    "test-reviewer.md",
}

DENIED_RUNTIME_NAMES = {
    "checkpoint.json",
    "queue.json",
    "lock.json",
    "state.json",
    "cache.json",
    "meta.json",
    "config.lock",
    "registry.json",
    "resume-brief.md",
    "events.jsonl",
    ".lock",
}

DENIED_RUNTIME_PATTERNS = {
    "events/",
    "issues/*/checkpoint.json",
    "refs/superheroes/locks/**",
}
```

Assert root Claude marketplace sources are `./plugins/<name>`, not `./plugins/<name>/codex`.

- [ ] **Step 2: Add shared README files and rubric copy**

Create:

- `plugins/review-crew/shared/README.md`
- `plugins/test-pilot/shared/README.md`
- `plugins/the-architect/shared/README.md`

Copy each to `plugins/<name>/codex/<name>/shared/README.md`.

Copy:

```text
plugins/review-crew/rubric/review-base.md
```

to:

```text
plugins/review-crew/codex/review-crew/shared/rubric/review-base.md
```

- [ ] **Step 3: Verify Task 2**

Run:

```bash
python3 -m pytest eval/lib/tests/test_runtime_layout.py -q
python3 .github/scripts/validate_dual_host_marketplace.py --phase metadata
```

Expected: runtime layout tests pass; metadata phase still passes.

- [ ] **Step 4: Commit Task 2**

```bash
git add eval/lib/tests/test_runtime_layout.py plugins/*/shared plugins/*/codex/*/shared
git commit -m "feat: add shared runtime layout guards"
```

## Task 3: Review-Crew Shared Reviewer Methodology

**Files:**

- Create: `plugins/review-crew/shared/REVIEWERS.md`
- Create: `plugins/review-crew/shared/reviewers/*-reviewer.md`
- Create: `plugins/review-crew/codex/review-crew/shared/reviewers/*-reviewer.md`
- Modify: `plugins/review-crew/agents/*-reviewer.md`
- Test: `plugins/review-crew/lib/tests/test_shared_reviewers.py`

- [ ] **Step 1: Write failing reviewer drift tests**

Create `plugins/review-crew/lib/tests/test_shared_reviewers.py` with:

```python
REVIEWER_FILES = {
    "architecture-reviewer.md",
    "code-reviewer.md",
    "premortem-reviewer.md",
    "security-reviewer.md",
    "test-reviewer.md",
}

CLAUDE_ONLY_TOKENS = {
    "tools:",
    "${CLAUDE_PLUGIN_ROOT}",
    "subagent_type",
}
```

Assertions:

- `plugins/review-crew/shared/reviewers` contains exactly `REVIEWER_FILES`.
- Shared reviewer files do not contain `CLAUDE_ONLY_TOKENS`.
- Codex package-local reviewer files are byte-for-byte equal to shared reviewer files.
- Claude agent files retain Claude-native frontmatter and either:
  - contain an explicit runtime instruction to load and apply the matching neutral shared reviewer file, or
  - embed a generated methodology body whose normalized hash matches the shared reviewer file while allowing only Claude frontmatter/tool metadata to differ.

- [ ] **Step 2: Extract neutral reviewer methodology**

For each file in `plugins/review-crew/agents/*-reviewer.md`, create a neutral shared file under `plugins/review-crew/shared/reviewers/` that preserves methodology, dimension calibration, verification rules, and output expectations while removing Claude-only wrapper metadata.

- [ ] **Step 3: Update Claude wrappers**

Keep each Claude agent in `plugins/review-crew/agents/` Claude-native. Add an enforceable shared-methodology contract:

```markdown
Shared methodology source: `plugins/review-crew/shared/reviewers/<name>.md`.
This wrapper must load and apply that shared methodology before emitting findings.
```

Do not remove existing Claude agent tool metadata. A filename-only note is not enough for the drift test; the wrapper must either load the shared file at runtime or carry a generated methodology body whose normalized hash is checked against the shared source.

- [ ] **Step 4: Verify Task 3**

Run:

```bash
python3 -m pytest plugins/review-crew/lib/tests/test_shared_reviewers.py plugins/review-crew/lib/tests/test_dispatch_tables.py -q
```

Expected: shared reviewer tests and existing dispatch table tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add plugins/review-crew/shared plugins/review-crew/codex/review-crew/shared/reviewers plugins/review-crew/agents plugins/review-crew/lib/tests/test_shared_reviewers.py
git commit -m "feat: add shared reviewer methodology"
```

## Task 4: Codex Package Roots, Skills, And Installed Helper Smoke Tests

**Files:**

- Modify: `plugins/*/codex/*/.codex-plugin/plugin.json`
- Create: `plugins/*/codex/*/skills/*/SKILL.md`
- Create: `plugins/*/codex/*/lib/*.py`
- Create: `plugins/test-pilot/codex/test-pilot/templates/*`
- Create: `plugins/the-architect/codex/the-architect/templates/*`
- Test: `eval/lib/tests/test_codex_skill_markdown.py`
- Test: `plugins/review-crew/lib/tests/test_codex_review_crew_contracts.py`
- Test: `eval/lib/tests/test_codex_helper_drift.py`

- [ ] **Step 1: Write failing Codex skill tests**

Create `eval/lib/tests/test_codex_skill_markdown.py` with exact skill sets:

```python
EXPECTED_CODEX_SKILLS = {
    "review-crew": {"audit-debt", "review-code", "review-init", "review-plan", "review-spec", "review-tasks"},
    "test-pilot": {"test-pilot-execute", "test-pilot-init", "test-pilot-plan"},
    "the-architect": {"discovery", "plan", "tasks", "writing-specs"},
}
```

Require YAML frontmatter with `name` and `description`, required heading order, package-local `shared/README.md`, no `.github/scripts`, no `python3 -m pytest plugins/`, no Claude-only runtime tokens in `## Codex Runtime`, and at least one Codex-native marker.

- [ ] **Step 2: Write failing installed-package smoke tests**

Add tests that copy each `plugins/<name>/codex/<name>` package root to a temp directory outside the repo and execute representative Codex helpers from the copied package:

```bash
python3 lib/resolve_diff_lines.py --help
python3 lib/loop_state.py --help
python3 lib/definition_doc.py frontmatter --help
python3 lib/engine.py --help
```

Use only commands that exist for the copied package. Keep `--help` checks as CLI sanity checks, but require at least one non-help, read-only representative command per helper family from the copied temp package: resolving a tiny review diff, running review-crew loop/gate helpers against fixture docs, parsing or rendering definition-doc frontmatter/gate fixtures, and rendering or validating test-pilot plan/results fixtures. Assert non-zero contract checks return structured, documented errors rather than tracebacks.

For review-crew specifically, the copied-package smoke tests must invoke `gate_write.py` in both `--mode reset` and `--mode certify` against fixture docs with a resolvable package-local `architect_lib.py` / the-architect helper path, so the installed Codex package proves the same gate-write dependency chain that Claude/source-checkout users rely on.

- [ ] **Step 3: Finalize Codex manifests**

Review the `.codex-plugin/plugin.json` files created in Task 1 and add any missing full `interface` metadata. Keep `name`, `version`, and `author` synchronized with the matching Claude plugin manifests, keep descriptions host-native but equivalent in intent, and keep `skills` pointed at `./skills/` inside the isolated Codex package root.

- [ ] **Step 4: Add Codex skills**

For every Codex skill:

- Start with YAML frontmatter.
- Include `## When To Use`, `## Codex Runtime`, `## Shared Contract`, `## Host Coexistence`, and `## Verification`.
- In `## Codex Runtime`, use Codex terms such as `commentary`, `tool_search`, `request_user_input`, `browser MCP`, `Codex subagent`, or `worker`.
- In `## Host Coexistence`, include: `Claude runtime files remain authoritative for Claude users`.
- Reference package-local shared files and package-local helpers.

- [ ] **Step 5: Package helper adapters**

Copy or wrap:

- review-crew: `review_store.py`, `loop_state.py`, `circuit_breaker.py`, `resolve_diff_lines.py`, `repo_doctor.py`, `decisions.py`, `architect_lib.py`, `gate_write.py`
- test-pilot: `engine.py`, `store.py`, `state.py`, `lock.py`, `catalog.py`, `blocks.py`, `pr_comment.py`, templates
- the-architect: `definition_doc.py`, `identifiers.py`, templates

Where a source helper reads `.claude-plugin/plugin.json`, add a Codex adapter path that reads `.codex-plugin/plugin.json`.

For copied helpers that do not currently support `--help`, create package-local Codex CLI adapters that provide a deterministic `--help` exit `0` and execute the vendored package-local helper implementation for real commands. Installed Codex package helpers must not import from, execute, or resolve implementation code from the source checkout. Declared band dependencies may resolve package-local files from installed sibling plugin roots in the same marketplace/cache, such as review-crew resolving the installed the-architect package for gate writes. Do not change the Claude helper CLI contract just to satisfy Codex smoke tests.

The installed-package smoke tests must copy each Codex package to a temporary directory outside the repository and fail if any skill-visible helper command resolves implementation code, templates, schemas, or shared files from the source checkout rather than the copied package root or an explicitly declared installed sibling plugin root. Include a temporary installed marketplace/cache containing both review-crew and the-architect packages to prove gate-write dependency resolution works without source-checkout access.

Add `eval/lib/tests/test_codex_helper_drift.py` (or equivalent per-plugin contract-test files) parameterized over every copied package-local helper family: review-crew, test-pilot, and the-architect. The drift tests compare copied package helpers against source helpers with an explicit allowlist for intentional Codex adapter differences such as manifest lookup, installed sibling resolution, and `--help` wrapper code.

- [ ] **Step 6: Verify Task 4**

Run:

```bash
python3 .github/scripts/validate_dual_host_marketplace.py
python3 -m pytest eval/lib/tests/test_codex_skill_markdown.py plugins/review-crew/lib/tests/test_codex_review_crew_contracts.py eval/lib/tests/test_codex_helper_drift.py -q
```

Expected: strict dual-host validator passes; Codex skill, review-crew contract, and all-plugin helper-drift tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add plugins/*/codex/*/.codex-plugin/plugin.json plugins/*/codex eval/lib/tests/test_codex_skill_markdown.py plugins/review-crew/lib/tests/test_codex_review_crew_contracts.py eval/lib/tests/test_codex_helper_drift.py
git commit -m "feat: add codex package roots and skills"
```

## Task 5: Dual-Host Schemas, Fixtures, Readers, And Conformance

**Files:**

- Create: `eval/lib/schemas/dual-host/*.schema.json`
- Create: `eval/lib/schemas/dual-host/compatibility-matrix-v2.schema.json`
- Create: `eval/fixtures/dual-host/contracts/*`
- Create: `eval/fixtures/dual-host/conformance/*`
- Create: `eval/fixtures/dual-host/compatibility/*`
- Create: `plugins/*/shared/compatibility.json`
- Create: `plugins/*/codex/*/shared/compatibility.json`
- Create: `plugins/*/shared/dual_host_artifacts.py`
- Create: `plugins/*/codex/*/lib/dual_host_artifacts.py`
- Test: `eval/lib/tests/test_dual_host_contracts.py`
- Test: `eval/lib/tests/test_dual_host_conformance.py`
- Test: `eval/lib/tests/test_dual_host_reader_drift.py`
- Test: `eval/lib/tests/test_dual_host_runtime_wiring.py`

- [ ] **Step 1: Write failing schema matrix tests**

Create `eval/lib/tests/test_dual_host_contracts.py` with:

```python
SHARED_ARTIFACTS = {
    "definition-doc",
    "checkpoint",
    "queue",
    "finding",
    "finding-batch",
    "review-profile",
    "test-pilot-plan",
    "test-pilot-results",
    "lock",
    "registry",
    "compatibility-matrix",
}

COMMON_PROVENANCE = {"schemaVersion", "host", "hostVersion", "pluginVersion", "runId"}
```

Require v1 fixture, v2 schema, Claude positive fixture, Codex positive fixture, and unknown-schema negative fixture for every artifact that preserves an existing runtime format. `compatibility-matrix` is new and starts at v2, so require its v2 schema, Claude positive fixture, Codex positive fixture, and unknown-schema negative fixture, but do not require or synthesize a v1 fixture.

- [ ] **Step 2: Add schemas and fixtures**

Add v2 schemas with `additionalProperties: false`, `schemaVersion: 2`, common provenance, and artifact timestamps. Preserve v1 fixture shapes from current schemas, runtime templates, and markdown profile output.

Add `compatibility-matrix-v2.schema.json` and fixtures. The matrix is a new v2-only artifact that records, per plugin and artifact class, the supported schema versions, supported legacy inputs, minimum compatible Claude plugin version, minimum compatible Codex plugin version, and whether the artifact remains in dual-compatible mode. Name one canonical compatibility matrix source, validate it against manifests and schemas, then copy it into each source-checkout `shared/` directory and each Codex package-local `shared/` directory so compatibility preflight has one explicit source of version truth in both hosts. Add CI that compares every packaged `plugins/*/shared/compatibility.json` and `plugins/*/codex/*/shared/compatibility.json` copy to the canonical matrix byte-for-byte or by normalized hash.

For review profiles, include both:

- `review-profile-v1-legacy.valid.md`
- `review-profile-v2-claude.valid.json`
- `review-profile-v2-codex.valid.json`

The v1 validator must parse markdown/provenance fields current readers depend on.

- [ ] **Step 3: Add package-local reader helpers**

Create runtime reader helpers in package-local locations, not in `eval/lib`:

```text
plugins/review-crew/shared/dual_host_artifacts.py
plugins/review-crew/codex/review-crew/lib/dual_host_artifacts.py
plugins/test-pilot/shared/dual_host_artifacts.py
plugins/test-pilot/codex/test-pilot/lib/dual_host_artifacts.py
plugins/the-architect/shared/dual_host_artifacts.py
plugins/the-architect/codex/the-architect/lib/dual_host_artifacts.py
```

Treat `plugins/<name>/shared/dual_host_artifacts.py` as the canonical source-checkout implementation for that plugin's artifact reader. Treat `plugins/<name>/codex/<name>/lib/dual_host_artifacts.py` as a vendored installed-package copy. Do not hand-maintain two independent algorithms. Add reader drift tests that compare the canonical and vendored implementations, with an explicit allowlist for intentional package-root discovery differences.

Each host-specific skill and runtime entrypoint that reads shared artifacts must call its package-local helper. Claude source-checkout workflows call `plugins/<name>/shared/dual_host_artifacts.py`; installed Claude packages call `${CLAUDE_PLUGIN_ROOT}/shared/dual_host_artifacts.py`; installed Codex packages call `plugins/<name>/codex/<name>/lib/dual_host_artifacts.py` inside the copied Codex package root. `eval/lib/tests` may import or execute these helpers, but must not own the implementation. Add smoke/path tests for both installed Claude package layout and installed Codex package layout.

Implement these interfaces:

- `class ArtifactReadError(Exception)`: raised for fail-closed reader failures.
- `read_artifact(path: Path, artifact: str, *, expected_fencing_token: str | None = None, lock_record: dict | None = None) -> dict | list[dict]`: reads v1 or v2 artifacts, normalizes known v1 markdown/JSON records to dicts, preserves review-crew findings batches as lists for `finding-batch`, and raises `ArtifactReadError` for unknown schema versions. For lock-protected artifacts, the reader must require non-null fencing context or route through a lock-protected API that requires it.
- `read_registry(path: Path) -> dict`: reads registry/storage-mode records and returns a normalized dict with `schemaVersion`, `storageMode`, `remoteKey`, and timestamps.
- `validate_known_schema(record: dict | list[dict], artifact: str, *, expected_fencing_token: str | None = None, lock_record: dict | None = None) -> dict | list[dict]`: validates a normalized record or findings batch against the known artifact contract and returns it when valid.

Readers must fail closed on unknown schema version, unsupported plugin version, missing v2 provenance, missing fencing context for lock-protected artifacts, stale fencing tokens, and host/version skew that requires doctor/reconcile.

- [ ] **Step 3a: Wire the real runtime surfaces**

Update or verify the actual Claude skill instructions, Codex skill instructions, and helper entrypoints that read shared artifacts so they route through the package-local reader helpers above. Add `eval/lib/tests/test_dual_host_runtime_wiring.py` to fail if a workflow still bypasses the reader helper or points at `eval/lib` as the implementation. The test must cover at least review-crew findings batches and profiles, test-pilot plans/results, and the-architect definition-docs.

- [ ] **Step 4: Add doctor/reconcile helper**

Create doctor/reconcile helpers beside the readers in the same package-local files or package-local companion modules. The helpers must be callable from installed Codex packages without importing `eval/lib`.

- `diagnose(paths: list[Path]) -> dict`: returns a dict with `status`, `problems`, and `actions`; `status` is one of `ok`, `diverged`, or `blocked`.
- `reconcile(paths: list[Path], *, dry_run: bool = True) -> dict`: returns a dict with `status`, `changes`, and `problems`; `status` is one of `would-change`, `changed`, or `blocked`. For this release, reconciliation is report-only: `dry_run=False` must return `blocked` with an action explaining that write reconciliation is deferred to the migration implementation. A future write-capable reconcile must acquire the artifact-specific lock, validate all inputs before writing, write through atomic temp-file-and-rename steps, record an idempotent marker after validation, and be resumable or safely rolled back after interruption.

Return machine-readable statuses for divergence, stale locks, version skew, and missing migration markers.

- [ ] **Step 5: Add conformance tests**

Create `eval/lib/tests/test_dual_host_conformance.py` that executes real reader and doctor/reconcile helpers against:

- Claude-authored and Codex-authored findings
- Claude-authored and Codex-authored findings batches copied from real `findings-*.json` arrays
- Claude-authored and Codex-authored test-pilot plans/results
- Claude-authored and Codex-authored definition-docs
- held, stale, and fencing-token lock cases
- registry/storage-mode records
- divergence, stale-lock, and version-skew doctor fixtures
- review-crew finding-to-verdict and loop-gate fixtures from both host directions
- test-pilot protected-target, navigation, scrubber, and PR-comment formatting fixtures
- the-architect definition-doc owner/review-gate, parent-linkage, and design-source fixtures

- [ ] **Step 6: Verify Task 5**

Run:

```bash
python3 -m pytest eval/lib/tests/test_dual_host_contracts.py eval/lib/tests/test_dual_host_conformance.py eval/lib/tests/test_dual_host_reader_drift.py eval/lib/tests/test_dual_host_runtime_wiring.py -q
```

Expected: all dual-host contract and conformance tests pass.

- [ ] **Step 7: Commit Task 5**

```bash
git add eval/lib/schemas/dual-host eval/fixtures/dual-host plugins/*/shared/compatibility.json plugins/*/codex/*/shared/compatibility.json plugins/*/shared/dual_host_artifacts.py plugins/*/codex/*/lib/dual_host_artifacts.py eval/lib/tests/test_dual_host_contracts.py eval/lib/tests/test_dual_host_conformance.py eval/lib/tests/test_dual_host_reader_drift.py eval/lib/tests/test_dual_host_runtime_wiring.py
git commit -m "feat: add dual-host artifact contracts"
```

## Task 6: Docs, CI, And Release Guardrails

**Files:**

- Create: `docs/dual-host-runtime.md`
- Create: `docs/dual-host-migration.md`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `RELEASING.md`

- [ ] **Step 1: Unignore public dual-host docs**

Update `.gitignore` so only these docs are tracked under `docs/`:

```gitignore
!docs/
docs/*
!docs/dual-host-runtime.md
!docs/dual-host-migration.md
!docs/superpowers/
!docs/superpowers/specs/
!docs/superpowers/specs/*.md
!docs/superpowers/plans/
!docs/superpowers/plans/*.md
```

- [ ] **Step 2: Add runtime and migration docs**

`docs/dual-host-runtime.md` must include:

- plugin-by-plugin table
- Claude remains first-class section
- Codex becomes first-class section
- same project, both hosts section

`docs/dual-host-migration.md` must include:

- expand/migrate/contract rules
- artifact-specific locks
- registry/storage-mode behavior
- doctor/reconcile recovery behavior

- [ ] **Step 3: Update user-facing docs**

Update `README.md`, `CONTRIBUTING.md`, and `RELEASING.md` with dual-host status, install pointers, validation commands, and release checklist. Preserve existing Claude install and usage path. The Codex install pointers must explain that a repo-local marketplace requires `codex plugin marketplace add <path-to-repo>` before `codex plugin add <plugin-name>@<marketplace-name>`, and the release checklist must include a manual review that Claude and Codex descriptions remain host-native but equivalent in intent.

- [ ] **Step 4: Add CI validator**

In `.github/workflows/ci.yml`, run:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_dual_host_marketplace.py
python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
```

- [ ] **Step 5: Verify Task 6**

Run the strict verification command from the top of this plan.

- [ ] **Step 6: Commit Task 6**

```bash
git add .gitignore .github/workflows/ci.yml README.md CONTRIBUTING.md RELEASING.md docs/dual-host-runtime.md docs/dual-host-migration.md docs/superpowers/specs/*.md docs/superpowers/plans/*.md
git commit -m "docs: add dual-host runtime and release guidance"
```

## Task 7: Final Verification And Review Handoff

**Files:**

- Inspect all changed files.

- [ ] **Step 1: Run full verification**

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_dual_host_marketplace.py
python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
```

Expected: both validators pass and all tests pass.

- [ ] **Step 2: Run placeholder scan**

```bash
python3 - <<'PY'
import pathlib

roots = [".agents", "plugins", "docs", "eval", ".github", "README.md", "CONTRIBUTING.md", "RELEASING.md"]
markers = ["TB" + "D", "TO" + "DO", "PLACE" + "HOLDER", "FIX" + "ME"]
allowed_existing = {
    ("plugins/the-architect/skills/tasks/SKILL.md", 25),
    ("plugins/review-crew/skills/audit-debt/SKILL.md", 9),
}
for root in roots:
    path = pathlib.Path(root)
    if not path.exists():
        continue
    paths = [path] if path.is_file() else path.rglob("*")
    for file_path in paths:
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in markers):
                if (str(file_path), line_no) in allowed_existing:
                    continue
                print(f"{file_path}:{line_no}:{line}")
PY
```

Expected: no output other than the explicit `allowed_existing` baseline. Any new placeholder-like marker in the generated Codex package roots, dual-host docs, schema/fixture work, CI, or updated top-level docs fails the scan.

- [ ] **Step 3: Review changed files**

```bash
git status --short
git diff --stat main...HEAD
```

Expected: only planned files changed; no runtime state files committed.

- [ ] **Step 4: Commit verification note if needed**

If verification changes docs or fixtures, commit them:

```bash
git add <changed-files>
git commit -m "chore: finalize dual-host verification"
```

## Self-Review Checklist

- [ ] Every source design requirement maps to a task above.
- [ ] Claude root manifests, skills, and agents stay present.
- [ ] Codex manifests, skills, shared files, and helper packages are package-local.
- [ ] Marketplace drift tests compare plugin manifest versions, not marketplace entry versions.
- [ ] Review-profile v1 compatibility uses real markdown/provenance, not synthetic JSON.
- [ ] Registry/storage-mode is included in fixtures, schemas, readers, conformance, and migration docs.
- [ ] Reader tests include fail-closed negatives.
- [ ] Installed-package smoke tests execute representative helper commands.
- [ ] CI runs both validators and the full test suite.
