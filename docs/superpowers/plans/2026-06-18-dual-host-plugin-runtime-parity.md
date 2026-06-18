# Dual-Host Plugin Runtime Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the superheroes plugin marketplace first-class for both Claude Code and Codex while preserving the existing first-class Claude experience and avoiding changes to the plugins' core workflow behavior.

**Architecture:** Keep one shared product contract and two host-native runtime surfaces. Claude keeps Claude-native manifests, slash-command skills, and bundled agents. Codex gets Codex-native manifests, plugin metadata, skills, and runtime guidance. CI validates that shared contracts, versions, schemas, and reviewer methodology cannot drift.

**Tech Stack:** Python 3.12, pytest, jsonschema, Markdown skill files, JSON plugin manifests, GitHub Actions.

---

## Source Design

This plan implements the reviewed design in:

- `docs/superpowers/specs/2026-06-18-dual-host-first-class-design.md`

The implementation must preserve these constraints:

- Do not prefer Claude over Codex, or Codex over Claude.
- Do not weaken Claude-native instructions to make them generic.
- Do not phrase Codex support as Claude compatibility mode.
- Do not change review-crew, test-pilot, or the-architect core behavior.
- Do not introduce committed runtime state under `.superheroes/`.
- Generate only stable metadata after the hand-authored host-native patterns exist.

## Current File Map

Existing marketplace and plugin metadata:

- `.claude-plugin/marketplace.json`
- `plugins/review-crew/.claude-plugin/plugin.json`
- `plugins/test-pilot/.claude-plugin/plugin.json`
- `plugins/the-architect/.claude-plugin/plugin.json`
- `.github/scripts/validate_marketplace.py`
- `.github/workflows/ci.yml`

Existing host runtime sources:

- `plugins/review-crew/skills/`
- `plugins/review-crew/agents/`
- `plugins/review-crew/rubric/`
- `plugins/test-pilot/skills/`
- `plugins/test-pilot/templates/`
- `plugins/the-architect/skills/`
- `plugins/the-architect/templates/`

Existing shared contracts and tests:

- `CONVENTIONS.md`
- `eval/lib/schemas/*.schema.json`
- `eval/lib/tests/test_schemas.py`
- `plugins/review-crew/lib/tests/test_dispatch_tables.py`
- `plugins/review-crew/lib/tests/test_skill_markdown.py`
- `plugins/test-pilot/lib/tests/`
- `plugins/the-architect/lib/tests/`

New files introduced by this plan:

- `.agents/plugins/marketplace.json`
- `.github/scripts/validate_dual_host_marketplace.py`
- `eval/fixtures/dual-host/README.md`
- `eval/fixtures/dual-host/manifests/*.json`
- `eval/fixtures/dual-host/contracts/*.json`
- `eval/lib/tests/test_dual_host_contracts.py`
- `eval/lib/tests/test_dual_host_marketplace.py`
- `eval/lib/tests/test_runtime_layout.py`
- `plugins/review-crew/shared/reviewers/*.md`
- `plugins/review-crew/shared/README.md`
- `plugins/review-crew/codex/review-crew/.codex-plugin/plugin.json`
- `plugins/review-crew/codex/review-crew/lib/*.py`
- `plugins/review-crew/codex/review-crew/shared/README.md`
- `plugins/review-crew/codex/review-crew/skills/*/SKILL.md`
- `plugins/test-pilot/shared/README.md`
- `plugins/test-pilot/codex/test-pilot/.codex-plugin/plugin.json`
- `plugins/test-pilot/codex/test-pilot/lib/*.py`
- `plugins/test-pilot/codex/test-pilot/templates/*`
- `plugins/test-pilot/codex/test-pilot/shared/README.md`
- `plugins/test-pilot/codex/test-pilot/skills/*/SKILL.md`
- `plugins/the-architect/shared/README.md`
- `plugins/the-architect/codex/the-architect/.codex-plugin/plugin.json`
- `plugins/the-architect/codex/the-architect/lib/*.py`
- `plugins/the-architect/codex/the-architect/templates/*`
- `plugins/the-architect/codex/the-architect/shared/README.md`
- `plugins/the-architect/codex/the-architect/skills/*/SKILL.md`
- `eval/lib/schemas/dual-host/*.schema.json`
- `docs/dual-host-runtime.md`
- `docs/dual-host-migration.md`

---

## Task 1: Add Codex Marketplace Skeleton And Manifest Fixtures

- [ ] Create `.agents/plugins/marketplace.json` with the same three plugin names as `.claude-plugin/marketplace.json`, using the Codex-native marketplace shape from `plugin-creator/references/plugin-json-spec.md`.

  Required shape:

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

- [ ] Add `eval/fixtures/dual-host/manifests/claude-marketplace.valid.json` by copying the current Claude marketplace shape.
- [ ] Add `eval/fixtures/dual-host/manifests/codex-marketplace.valid.json` by copying the new Codex marketplace shape.
- [ ] Add negative fixture `eval/fixtures/dual-host/manifests/codex-marketplace.bad-source.json` where one Codex source points at `./plugins/review-crew/codex` instead of the named package root.
- [ ] Add negative fixture `eval/fixtures/dual-host/manifests/codex-source-claude-root.json` where one Codex source points at `./plugins/review-crew`, proving the validator rejects the mixed Claude/Codex root.
- [ ] Add negative fixture `eval/fixtures/dual-host/manifests/marketplace-name-drift.json` where the Claude and Codex marketplace names differ.
- [ ] Add negative fixture `eval/fixtures/dual-host/manifests/plugin-version-drift.json` where one Codex plugin manifest version differs from the matching Claude plugin manifest version.
- [ ] Run the existing Claude marketplace validator to confirm this task has not regressed Claude:

  ```bash
  python3 .github/scripts/validate_marketplace.py
  ```

  Expected output includes:

  ```text
  marketplace + plugin manifests valid
  ```

## Task 2: Create Codex Package Roots Without Moving Claude Runtime Files

- [ ] Create these package-root directories:

  ```text
  plugins/review-crew/codex/review-crew/.codex-plugin/
  plugins/review-crew/codex/review-crew/skills/
  plugins/test-pilot/codex/test-pilot/.codex-plugin/
  plugins/test-pilot/codex/test-pilot/skills/
  plugins/the-architect/codex/the-architect/.codex-plugin/
  plugins/the-architect/codex/the-architect/skills/
  ```

- [ ] Add `plugins/review-crew/codex/review-crew/.codex-plugin/plugin.json`:

  ```json
  {
    "name": "review-crew",
    "version": "0.4.0",
    "description": "Multi-agent review of code, plans, and technical debt - calibrated per-project, with Codex-native runtime guidance.",
    "author": { "name": "zwrose" },
    "skills": "./skills/",
    "interface": {
      "displayName": "Review Crew",
      "shortDescription": "Multi-agent code, plan, and technical-debt review.",
      "longDescription": "Review Crew provides Codex-native review skills backed by the shared superheroes review contract.",
      "developerName": "zwrose",
      "category": "Productivity",
      "capabilities": ["Review", "Write"],
      "defaultPrompt": ["Review this branch with review-crew."]
    }
  }
  ```

- [ ] Add `plugins/test-pilot/codex/test-pilot/.codex-plugin/plugin.json`:

  ```json
  {
    "name": "test-pilot",
    "version": "0.1.0",
    "description": "Seeded manual test plans on PRs plus autonomous browser execution - with Codex-native browser and verification guidance.",
    "author": { "name": "zwrose" },
    "skills": "./skills/",
    "interface": {
      "displayName": "Test Pilot",
      "shortDescription": "Seeded test plans and browser execution guidance.",
      "longDescription": "Test Pilot provides Codex-native planning and browser-verification skills backed by shared test-pilot contracts.",
      "developerName": "zwrose",
      "category": "Productivity",
      "capabilities": ["Test", "Interactive"],
      "defaultPrompt": ["Create a seeded manual test plan."]
    }
  }
  ```

- [ ] Add `plugins/the-architect/codex/the-architect/.codex-plugin/plugin.json`:

  ```json
  {
    "name": "the-architect",
    "version": "0.1.0",
    "description": "Requirements-first discovery, planning, and task authoring - with Codex-native design capture guidance.",
    "author": { "name": "zwrose" },
    "skills": "./skills/",
    "interface": {
      "displayName": "The Architect",
      "shortDescription": "Requirements-first discovery, planning, and task authoring.",
      "longDescription": "The Architect provides Codex-native discovery, plan, and task skills backed by shared definition-doc contracts.",
      "developerName": "zwrose",
      "category": "Productivity",
      "capabilities": ["Plan", "Write"],
      "defaultPrompt": ["Turn this idea into a reviewed implementation plan."]
    }
  }
  ```

- [ ] Keep existing root-level Claude package sources in place:

  ```text
  plugins/*/.claude-plugin/
  plugins/*/skills/
  plugins/review-crew/agents/
  ```

- [ ] Do not move or rewrite Claude skill files in this task.

## Task 3: Add Dual-Host Manifest Validation

- [ ] Create `.github/scripts/validate_dual_host_marketplace.py`.
- [ ] Reuse the SemVer regex from `.github/scripts/validate_marketplace.py`.
- [ ] Implement JSON loading helpers that collect errors and return nonzero on any error.
- [ ] Validate the Claude marketplace at `.claude-plugin/marketplace.json`.
- [ ] Validate the Codex marketplace at `.agents/plugins/marketplace.json`.
- [ ] For each Claude plugin entry:

  - [ ] Resolve `source` relative to repo root.
  - [ ] Require `<source>/.claude-plugin/plugin.json`.
  - [ ] Require `plugin.json.name` to match the marketplace entry.
  - [ ] Require `plugin.json.version` to be valid SemVer.

- [ ] For each Codex plugin entry:

  - [ ] Require `source` to be an object with `"source": "local"` and a non-empty `path`.
  - [ ] Resolve `source.path` relative to repo root.
  - [ ] Require the resolved real path to stay inside the repo and equal `plugins/<entry-name>/codex/<entry-name>`, so the marketplace entry name, Codex package-root directory basename, and `.codex-plugin/plugin.json` `name` all match the Codex plugin contract while staying isolated from the Claude root.
  - [ ] Reject path traversal and symlink escapes before loading the Codex manifest.
  - [ ] Require `policy.installation` to be one of `NOT_AVAILABLE`, `AVAILABLE`, or `INSTALLED_BY_DEFAULT`.
  - [ ] Require `policy.authentication` to be one of `ON_INSTALL` or `ON_USE`.
  - [ ] Require a non-empty `category`.
  - [ ] Reject unsupported Codex marketplace plugin-entry fields such as `version`; `plugin.json` remains the single source of truth for plugin versions on both hosts.
  - [ ] Require `<source>/.codex-plugin/plugin.json`.
  - [ ] Require `plugin.json.name` to match the marketplace entry.
  - [ ] Require `plugin.json.version` to be valid SemVer.
  - [ ] Require `plugin.json.skills` to be `./skills/`.
  - [ ] Require `plugin.json.interface.displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, and `defaultPrompt`.
  - [ ] Reject unsupported Codex manifest fields, including `host`.
  - [ ] In `--phase metadata` mode, warn when `<source>/shared/README.md` or `<source>/skills/*/SKILL.md` is missing.
  - [ ] In default strict mode, require `<source>/shared/README.md` so the Codex package is self-contained.
  - [ ] In default strict mode, require at least one skill under `<source>/skills/*/SKILL.md`.

- [ ] Add cross-host drift checks:

  - [ ] Marketplace `name` matches.
  - [ ] Plugin sets match exactly by plugin name.
  - [ ] Each plugin version matches across Claude and Codex.
  - [ ] Each plugin author name matches across Claude and Codex.
  - [ ] Each plugin description is non-empty on both hosts.
  - [ ] Do not require Claude marketplace-only fields such as `owner.name` or `metadata.version` in the Codex marketplace. Version parity belongs to plugin manifests or a future shared metadata artifact, not the host-specific marketplace root.

- [ ] The validator must support `--phase metadata` for Tasks 1-3, where only marketplace files, plugin manifests, and cross-host manifest drift are blocking.
- [ ] The validator must run in default strict mode after Tasks 4 and 6 have created the package-local shared docs and Codex skill wrappers.
- [ ] Print a success message exactly:

  ```text
  dual-host marketplace + plugin manifests valid
  ```

- [ ] Add `eval/lib/tests/test_dual_host_marketplace.py` with subprocess tests:

  - [ ] Current repo fixtures pass.
  - [ ] `codex-marketplace.bad-source.json` fails with a message containing `Codex source`.
  - [ ] `marketplace-name-drift.json` fails with a message containing `marketplace name`.
  - [ ] `plugin-version-drift.json` fails with a message containing the plugin name and `plugin version`; the fixture must create matching Claude and Codex plugin manifest roots with different `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` versions, not encode a version field inside marketplace entries.
  - [ ] `codex-invalid-source-object.json` fails with a message containing `source`.
  - [ ] `codex-source-traversal.json` fails with a message containing `source path`.
  - [ ] `codex-source-wrong-plugin-dir.json` fails with a message containing `plugins/<name>/codex/<name>`.
  - [ ] `codex-source-claude-root.json` fails with a message containing `Claude root`.
  - [ ] `codex-entry-version.json` fails with a message containing `version`.
  - [ ] `codex-invalid-policy.json` fails with a message containing `policy`.
  - [ ] `codex-missing-interface.json` fails with a message containing `interface`.
  - [ ] `codex-unsupported-host-field.json` fails with a message containing `host`.
  - [ ] `codex-invalid-semver.json` fails with a message containing `SemVer`.
  - [ ] `plugin-set-drift.json` fails with a message containing `plugin set`.
  - [ ] `author-drift.json` fails with a message containing `author`.
  - [ ] In default strict mode, `codex-missing-shared-readme.json` fails with a message containing `shared/README.md`.
  - [ ] In default strict mode, `codex-missing-skill.json` fails with a message containing `skills`.
  - [ ] In metadata phase, the same missing shared README and missing skill fixtures pass with warnings:

    ```bash
    python3 .github/scripts/validate_dual_host_marketplace.py --phase metadata
    ```

- [ ] Do not add the validator to `.github/workflows/ci.yml` until Task 6 has created the files strict mode requires.
- [ ] After Task 6, add the validator to `.github/workflows/ci.yml` after the existing Claude validator:

  ```yaml
  - name: Validate dual-host marketplace + plugin manifests
    run: python3 .github/scripts/validate_dual_host_marketplace.py
  ```

## Task 4: Introduce Shared Contract Directories Without Runtime State

- [ ] Create shared directories:

  ```text
  plugins/review-crew/shared/
  plugins/test-pilot/shared/
  plugins/the-architect/shared/
  ```

- [ ] Add `plugins/review-crew/shared/README.md` explaining:

  - Reviewer methodology is shared.
  - Claude agents and Codex skills must preserve the same dimensions, severity rules, taxonomy, gate semantics, and findings filenames.
  - Mutable review runtime state remains in existing machine-local stores.

- [ ] Add `plugins/test-pilot/shared/README.md` explaining:

  - Catalog format, seeded mutations, protected-target rules, navigation constraints, scrubber behavior, and PR comment formats are shared contracts.
  - Browser execution instructions remain host-native.
  - Mutable execution state remains in existing machine-local stores.

- [ ] Add `plugins/the-architect/shared/README.md` explaining:

  - Discovery, plan, tasks, definition-doc frontmatter, owner approval gates, review gates, parent linkage, work-item identity, and design-source recording are shared contracts.
  - Design capture remains host-native.
  - Mutable workflow state remains in existing machine-local stores.

- [ ] Copy each shared README into the matching Codex package root:

  ```text
  plugins/review-crew/shared/README.md -> plugins/review-crew/codex/review-crew/shared/README.md
  plugins/test-pilot/shared/README.md -> plugins/test-pilot/codex/test-pilot/shared/README.md
  plugins/the-architect/shared/README.md -> plugins/the-architect/codex/the-architect/shared/README.md
  ```

- [ ] Treat those Codex-local shared README files as vendored package contents, not a second source of truth.
- [ ] Copy the base rubric into the review-crew Codex package root:

  ```text
  plugins/review-crew/rubric/review-base.md -> plugins/review-crew/codex/review-crew/shared/rubric/review-base.md
  ```

- [ ] Treat `plugins/review-crew/codex/review-crew/shared/rubric/review-base.md` as vendored package content, not a second source of truth.
- [ ] Add `eval/lib/tests/test_runtime_layout.py` with assertions:

  - Every plugin has a root `.claude-plugin/plugin.json`.
  - Every root Claude marketplace `source` still points at `plugins/<name>` and not `plugins/<name>/codex`.
  - Every Claude plugin root has the exact expected `skills/*/SKILL.md` set for that plugin.
  - The review-crew Claude plugin root has the exact expected `agents/*-reviewer.md` set.
  - Existing Claude runtime directories remain present for all three plugins, including `plugins/review-crew/agents/`, `plugins/test-pilot/skills/`, and `plugins/the-architect/skills/`.
  - Every plugin has an isolated Codex package root at `plugins/<name>/codex/<name>/` with `.codex-plugin/plugin.json` whose `skills` path points at `./skills/`.
  - Every plugin has a `shared/README.md`.
  - Every plugin has a package-local `codex/<name>/shared/README.md`.
  - Each `codex/<name>/shared/README.md` is byte-for-byte identical to the matching `shared/README.md`.
  - The review-crew Codex package has `codex/review-crew/shared/rubric/review-base.md`.
  - The review-crew Codex package-local rubric is byte-for-byte identical to `plugins/review-crew/rubric/review-base.md`.
  - Every Codex package source has at least one `skills/*/SKILL.md`.
  - No Codex skill references shared runtime dependencies outside its package root.
  - No file under any `plugins/*/shared/` path has a runtime-state extension or name from this denylist:

    ```python
    DENIED_RUNTIME_NAMES = {
        "checkpoint.json",
        "queue.json",
        "lock.json",
        "state.json",
        "cache.json",
        ".lock",
    }
    ```

  - The same denylist must scan committed neutral or host-control paths that could be mistaken for shared runtime state, including `.superheroes/**`, `.claude/superheroes/**`, `docs/superheroes/**`, and existing control-plane state names from `CONVENTIONS.md` such as `queue.json`, `checkpoint.json`, `meta.json`, `config.lock`, `events/`, `events.jsonl`, `issues/*/checkpoint.json`, and `refs/superheroes/locks/**`, while explicitly allowing schema, fixture, plan, and spec documentation directories.

## Task 5: Establish Review-Crew Shared Reviewer Methodology

- [ ] Create `plugins/review-crew/shared/reviewers/`.
- [ ] Extract host-neutral reviewer methodology into these shared files. The shared files must not contain Claude agent frontmatter, Claude tool declarations, `${CLAUDE_PLUGIN_ROOT}`, `.claude/review-profile.md` as the only profile path, or other Claude-only runtime instructions:

  ```text
  plugins/review-crew/shared/reviewers/architecture-reviewer.md
  plugins/review-crew/shared/reviewers/code-reviewer.md
  plugins/review-crew/shared/reviewers/premortem-reviewer.md
  plugins/review-crew/shared/reviewers/security-reviewer.md
  plugins/review-crew/shared/reviewers/test-reviewer.md
  ```

- [ ] Add `plugins/review-crew/shared/REVIEWERS.md` explaining that `shared/reviewers/*-reviewer.md` is the neutral methodology source and that Claude agents and Codex skills are host-native wrappers around it.
- [ ] Update existing Claude reviewer agent files only as needed to reference or preserve the neutral methodology while retaining Claude-native agent metadata and Claude tool declarations.
- [ ] Copy the reviewer methodology into the Codex package root:

  ```text
  plugins/review-crew/shared/reviewers/architecture-reviewer.md -> plugins/review-crew/codex/review-crew/shared/reviewers/architecture-reviewer.md
  plugins/review-crew/shared/reviewers/code-reviewer.md -> plugins/review-crew/codex/review-crew/shared/reviewers/code-reviewer.md
  plugins/review-crew/shared/reviewers/premortem-reviewer.md -> plugins/review-crew/codex/review-crew/shared/reviewers/premortem-reviewer.md
  plugins/review-crew/shared/reviewers/security-reviewer.md -> plugins/review-crew/codex/review-crew/shared/reviewers/security-reviewer.md
  plugins/review-crew/shared/reviewers/test-reviewer.md -> plugins/review-crew/codex/review-crew/shared/reviewers/test-reviewer.md
  ```

- [ ] Treat `plugins/review-crew/codex/review-crew/shared/reviewers/*.md` as vendored package contents, not a second source of truth.
- [ ] Add a drift test in `plugins/review-crew/lib/tests/test_dispatch_tables.py` or a new `plugins/review-crew/lib/tests/test_shared_reviewers.py`.
- [ ] The drift test must assert the neutral shared reviewer files contain no Claude-only wrapper metadata or tool declarations.
- [ ] The drift test must assert each Claude agent wrapper either explicitly loads and applies the matching neutral shared reviewer file at runtime or embeds a generated methodology body whose normalized hash matches that shared file while remaining Claude-native. A filename-only reference must fail.
- [ ] The drift test must compare each shared reviewer file with the matching Codex package-local reviewer file byte-for-byte.
- [ ] The test must enumerate only `*-reviewer.md` files and assert that the reviewer filename set is exactly:

  ```python
  {
      "architecture-reviewer.md",
      "code-reviewer.md",
      "premortem-reviewer.md",
      "security-reviewer.md",
      "test-reviewer.md",
  }
  ```

- [ ] Do not rewrite existing Claude agent dispatch instructions in this task.

## Task 6: Add Codex-Native Skill Wrappers

- [ ] Add Codex skill directories:

  ```text
  plugins/review-crew/codex/review-crew/skills/review-code/
  plugins/review-crew/codex/review-crew/skills/review-plan/
  plugins/review-crew/codex/review-crew/skills/review-spec/
  plugins/review-crew/codex/review-crew/skills/review-tasks/
  plugins/review-crew/codex/review-crew/skills/audit-debt/
  plugins/review-crew/codex/review-crew/skills/review-init/
  plugins/test-pilot/codex/test-pilot/skills/test-pilot-init/
  plugins/test-pilot/codex/test-pilot/skills/test-pilot-plan/
  plugins/test-pilot/codex/test-pilot/skills/test-pilot-execute/
  plugins/the-architect/codex/the-architect/skills/discovery/
  plugins/the-architect/codex/the-architect/skills/plan/
  plugins/the-architect/codex/the-architect/skills/tasks/
  plugins/the-architect/codex/the-architect/skills/writing-specs/
  ```

- [ ] For each Codex `SKILL.md`, hand-author host-native instructions.
- [ ] Each Codex skill must include these sections in this order:

  ```markdown
  ---
  name: skill-name
  description: One-sentence Codex-native trigger description.
  ---

  # Skill Name

  ## When To Use

  ## Codex Runtime

  ## Shared Contract

  ## Host Coexistence

  ## Verification
  ```

- [ ] Codex `Codex Runtime` sections may reference Codex concepts such as subagents, tool discovery, browser tools, commentary updates, and plan-mode loops.
- [ ] Codex `Shared Contract` sections must point to the package-local `shared/README.md` inside the Codex package root.
- [ ] Codex `Host Coexistence` sections must state that Claude runtime files remain authoritative for Claude users and that shared artifacts must use the shared schemas.
- [ ] Codex `Verification` sections must be package-runtime safe:

  - They may describe package-local checks such as validating generated artifacts against package-local shared schemas.
  - They must not require `.github/scripts`, repo-root `plugins/*/lib/tests`, or other source-checkout-only paths.
  - They may include a short note that contributor verification lives in the source checkout docs, not inside the installed runtime surface.

- [ ] Package the runtime helpers the Codex skills need inside each Codex package root, without changing the existing source-checkout helper behavior:

  - [ ] Add package-local helper directories such as `plugins/review-crew/codex/review-crew/lib/`, `plugins/test-pilot/codex/test-pilot/lib/`, and `plugins/the-architect/codex/the-architect/lib/`.
  - [ ] Copy or wrap the current helpers referenced by the corresponding workflows, including review-crew review storage, loop-state, circuit-breaker, line-resolution, escalation, and decision helpers; test-pilot engine/store/scrubber helpers and templates; and the-architect definition-doc, gate, queue, and template helpers.
  - [ ] Codex skill instructions must resolve helpers and templates relative to their installed package root, not `.github/scripts`, repo-root `plugins/*/lib`, or `${CLAUDE_PLUGIN_ROOT}`.
  - [ ] Add drift tests that fail when package-local helper copies diverge from the source helpers unless the divergence is documented in an explicit allowlist with a reason.
  - [ ] Add an installed-package smoke test parametrized over every Codex package root and every Codex skill that references executable helpers or templates. For each package, copy it to a temporary directory outside the repo and prove all skill-visible package-local helper and template paths resolve there.
  - [ ] The installed-package smoke test must execute representative package-local helper commands from the copied temp package, not only check paths. Cover at least the-architect definition-doc frontmatter or gate rendering, review-crew loop/line-resolution helper CLIs, and test-pilot engine/template rendering.
  - [ ] Codex helper adapters must read package-local `.codex-plugin/plugin.json` when source helpers currently assume `.claude-plugin/plugin.json`.

- [ ] Keep the source-checkout verification command in `docs/dual-host-runtime.md`, `CONTRIBUTING.md`, `RELEASING.md`, and Task 11:

  ```bash
  python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_dual_host_marketplace.py && python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
  ```

- [ ] Do not change existing plugin runtime Python behavior in this task; copied package-local helpers must preserve the current behavior or document any host-adapter-only difference.
- [ ] Add `eval/lib/tests/test_codex_skill_markdown.py`.
- [ ] The test must assert the exact expected skill set per plugin before checking file contents:

  ```python
  EXPECTED_CODEX_SKILLS = {
      "review-crew": {
          "audit-debt",
          "review-code",
          "review-init",
          "review-plan",
          "review-spec",
          "review-tasks",
      },
      "test-pilot": {
          "test-pilot-execute",
          "test-pilot-init",
          "test-pilot-plan",
      },
      "the-architect": {
          "discovery",
          "plan",
          "tasks",
          "writing-specs",
      },
  }
  ```

- [ ] The test must enumerate every `plugins/*/codex/*/skills/*/SKILL.md` file after proving the discovered set equals `EXPECTED_CODEX_SKILLS`.
- [ ] For every Codex skill file, assert it starts with YAML frontmatter containing non-empty `name` and `description` fields.
- [ ] For every Codex skill file, assert the required headings appear in exactly this order:

  ```python
  REQUIRED_HEADINGS = [
      "## When To Use",
      "## Codex Runtime",
      "## Shared Contract",
      "## Host Coexistence",
      "## Verification",
  ]
  ```

- [ ] For every Codex skill file, assert:

  - It references `shared/README.md`.
  - It does not reference `../shared/README.md` or `plugins/<name>/shared/README.md`.
  - It contains the phrase `Claude runtime files remain authoritative for Claude users`.
  - It does not contain `.github/scripts`.
  - It does not contain `python3 -m pytest plugins/`.
  - It states that source-checkout verification lives in contributor docs.

- [ ] For every Codex skill file, parse only the `## Codex Runtime` section and assert it does not contain Claude-only runtime primitives unless they appear in an explicit host-coexistence warning outside that section:

  ```python
  CLAUDE_ONLY_RUNTIME_TOKENS = {
      "AskUserQuestion",
      "TodoWrite",
      "${CLAUDE_PLUGIN_ROOT}",
      "subagent_type",
      "Claude Design",
  }
  ```

- [ ] For every Codex skill file, assert the `## Codex Runtime` section contains at least one Codex-native runtime marker appropriate to the skill, such as `commentary`, `request_user_input`, `plan mode`, `tool_search`, `browser MCP`, `Codex subagent`, or `worker`.
- [ ] For every Codex skill file, assert the `## Codex Runtime` section resolves package-local helper paths under the installed `codex/` package root when the skill needs executable helpers.

- [ ] Add `plugins/review-crew/lib/tests/test_codex_review_crew_contracts.py`.
- [ ] For `plugins/review-crew/codex/review-crew/skills/review-code/SKILL.md`, assert it references exactly these reviewer files:

  ```python
  REVIEW_CREW_REVIEWERS = {
      "architecture-reviewer.md",
      "code-reviewer.md",
      "premortem-reviewer.md",
      "security-reviewer.md",
      "test-reviewer.md",
  }
  ```

- [ ] For `review-plan`, `review-spec`, and `review-tasks`, assert the same reviewer set unless a skill explicitly documents a narrower scope and the existing Claude skill has the same narrower scope.
- [ ] For `audit-debt`, assert its documented reviewer set matches the existing Claude `audit-debt` skill's intentional subset.
- [ ] For every Codex review-crew review skill, derive the expected findings filenames from the matching Claude skill's reviewer set before asserting filenames. Skills that use all five reviewers expect:

  ```python
  FINDINGS_FILES = {
      "findings-architecture.json",
      "findings-code.json",
      "findings-premortem.json",
      "findings-security.json",
      "findings-test.json",
  }
  ```

- [ ] `audit-debt` must expect only the findings files for its existing Claude reviewer subset unless the Claude `audit-debt` skill is intentionally expanded first.

- [ ] For every Codex review-crew review skill, assert the dimension names `Architecture`, `Code`, `Security`, `Test`, and `Failure-Mode` appear unless the corresponding Claude skill intentionally omits that dimension.
- [ ] For every Codex review-crew review skill, assert it references the package-local base rubric at `shared/rubric/review-base.md` and does not restate severity tiers inline.
- [ ] For every Codex review-crew review skill, assert the skill contains explicit runtime instructions to load each expected package-local reviewer methodology file before dispatching or simulating that reviewer; filename references alone are not sufficient.

## Task 7: Add Versioned Shared Contract Schemas And Fixtures

- [ ] Create `eval/fixtures/dual-host/contracts/`.
- [ ] Create `eval/lib/schemas/dual-host/`.
- [ ] Add `definition-doc-v1-legacy.valid.json` using the current `definition-doc.schema.json` valid shape from `eval/lib/tests/test_schemas.py`.
- [ ] Add `checkpoint-v1-legacy.valid.json` using the current checkpoint valid shape from `eval/lib/tests/test_schemas.py`.
- [ ] Add `queue-v1-legacy.valid.json` using the current queue valid shape from `eval/lib/tests/test_schemas.py`.
- [ ] Add `registry-v1-legacy.valid.json` using the current registry valid shape from `eval/lib/schemas/registry.schema.json` and current registry readers.
- [ ] Add v1 legacy fixtures for the remaining shared artifact classes:

  ```text
  finding-v1-legacy.valid.json
  review-profile-v1-legacy.valid.md
  test-pilot-plan-v1-legacy.valid.json
  test-pilot-results-v1-legacy.valid.json
  lock-v1-legacy.valid.json
  ```

- [ ] `review-profile-v1-legacy.valid.md` must be copied from the real markdown/provenance profile shape produced by `review-init` and resolved by `review_store.py`; a synthetic JSON profile fixture alone is not sufficient evidence of legacy profile compatibility.

- [ ] Add companion v2 schemas without changing existing runtime writers:

  ```text
  eval/lib/schemas/dual-host/definition-doc-v2.schema.json
  eval/lib/schemas/dual-host/checkpoint-v2.schema.json
  eval/lib/schemas/dual-host/queue-v2.schema.json
  eval/lib/schemas/dual-host/finding-v2.schema.json
  eval/lib/schemas/dual-host/finding-batch-v2.schema.json
  eval/lib/schemas/dual-host/review-profile-v2.schema.json
  eval/lib/schemas/dual-host/test-pilot-plan-v2.schema.json
  eval/lib/schemas/dual-host/test-pilot-results-v2.schema.json
  eval/lib/schemas/dual-host/lock-v2.schema.json
  eval/lib/schemas/dual-host/registry-v2.schema.json
  ```

- [ ] The v2 schemas must keep `additionalProperties: false`.
- [ ] The v2 schemas must require common host provenance:

  ```python
  COMMON_PROVENANCE = {"schemaVersion", "host", "hostVersion", "pluginVersion", "runId"}
  ```

- [ ] Every v2 schema must pin `schemaVersion` with `const: 2`.
- [ ] The v2 schemas must enforce artifact-specific timestamp fields:

  ```python
  TIMESTAMP_FIELDS = {
      "definition-doc": {"created", "updated"},
      "checkpoint": {"createdAt", "updatedAt"},
      "queue": {"createdAt", "updatedAt"},
      "finding": {"createdAt", "updatedAt"},
      "finding-batch": {"createdAt", "updatedAt"},
      "review-profile": {"created", "updated"},
      "test-pilot-plan": {"createdAt", "updatedAt"},
      "test-pilot-results": {"createdAt", "updatedAt"},
      "lock": {"acquiredAt", "updatedAt"},
      "registry": {"createdAt", "updatedAt"},
  }
  ```

- [ ] `definition-doc-v2.schema.json` must preserve the current definition-doc fields and add:

  ```json
  {
    "schemaVersion": 2,
    "host": "codex",
    "hostVersion": "unknown",
    "pluginVersion": "0.1.0",
    "runId": "run-codex-001",
    "designSource": { "host": "codex", "type": "conversation" }
  }
  ```

- [ ] `checkpoint-v2.schema.json` must preserve the current `updatedAt` field, add `createdAt`, and add the common host provenance fields.
- [ ] `queue-v2.schema.json` must preserve the current `items` shape and add `createdAt`, `updatedAt`, and the common host provenance fields at the top level.
- [ ] `finding-v2.schema.json` must preserve the full review-base finding contract needed by the runtime, require `id`, `title`, `dimension`, `severity`, `file`, `line`, `body`, and `suggestion`, preserve optional taxonomy and `tradeoff`, require `confidence` and evidence fields for Critical/Important findings according to the rubric, allow Minor/Nit findings to omit `confidence` with the rubric's default-High interpretation, and add the common host provenance fields.
- [ ] `finding-batch-v2.schema.json` must preserve review-crew's current per-reviewer findings-file contract. It must accept legacy v1 top-level arrays copied from real `findings-*.json` files through the v1 reader path, and define v2 as an object with batch provenance plus a `findings` array validated item-by-item with `finding-v2.schema.json`.
- [ ] `review-profile-v2.schema.json` must preserve the profile calibration concepts from `.claude/review-profile.md`, including the markdown/provenance artifact contract current readers parse, and add the common host provenance fields without requiring existing markdown profiles to be rewritten.
- [ ] `test-pilot-plan-v2.schema.json` must preserve the plan/comment fields used by `plugins/test-pilot/templates/plan-comment.md` and the engine state readers, then add the common host provenance fields.
- [ ] `test-pilot-results-v2.schema.json` must preserve the results/comment fields used by `plugins/test-pilot/templates/results-comment.md`, then add the common host provenance fields.
- [ ] `lock-v2.schema.json` must preserve atomic lock ownership fields and require `host`, `runId`, `pluginVersion`, `acquiredAt`, `updatedAt`, and a generation or fencing token.
- [ ] `registry-v2.schema.json` must preserve the current `eval/lib/schemas/registry.schema.json` storage-mode contract, add the common host provenance fields, and require `createdAt` and `updatedAt`.
- [ ] Add positive fixtures:

  ```text
  definition-doc-v2-codex.valid.json
  definition-doc-v2-claude.valid.json
  checkpoint-v2-codex.valid.json
  checkpoint-v2-claude.valid.json
  queue-v2-claude.valid.json
  queue-v2-codex.valid.json
  finding-v2-codex.valid.json
  finding-v2-claude.valid.json
  finding-batch-v1-reviewer.valid.json
  finding-batch-v2-codex.valid.json
  finding-batch-v2-claude.valid.json
  review-profile-v2-claude.valid.json
  review-profile-v2-codex.valid.json
  test-pilot-plan-v2-codex.valid.json
  test-pilot-plan-v2-claude.valid.json
  test-pilot-results-v2-claude.valid.json
  test-pilot-results-v2-codex.valid.json
  lock-v2-codex.valid.json
  lock-v2-claude.valid.json
  registry-v2-codex.valid.json
  registry-v2-claude.valid.json
  ```

- [ ] Add negative fixtures:

  ```text
  definition-doc-v2-missing-host.invalid.json
  definition-doc-v2-invalid-host.invalid.json
  definition-doc-v2-unknown-schema.invalid.json
  checkpoint-v2-missing-createdAt.invalid.json
  checkpoint-v2-unknown-schema.invalid.json
  queue-v2-unknown-schema.invalid.json
  queue-v2-unsupported-plugin.invalid.json
  finding-v2-invalid-severity.invalid.json
  finding-v2-unknown-schema.invalid.json
  finding-batch-v2-invalid-item.invalid.json
  finding-batch-v2-unknown-schema.invalid.json
  review-profile-v2-unknown-schema.invalid.json
  test-pilot-plan-v2-missing-steps.invalid.json
  test-pilot-plan-v2-unknown-schema.invalid.json
  test-pilot-results-v2-unknown-schema.invalid.json
  lock-v2-missing-fencing-token.invalid.json
  lock-v2-unknown-schema.invalid.json
  registry-v2-unknown-schema.invalid.json
  registry-v2-unsupported-storage-mode.invalid.json
  ```

- [ ] Add `eval/lib/tests/test_dual_host_contracts.py` that loads these fixtures.
- [ ] Make `test_dual_host_contracts.py` table-driven over this exact artifact set:

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
  }
  ```

- [ ] The test must fail if any artifact in `SHARED_ARTIFACTS` lacks a v1 fixture, v2 schema, positive v2 fixture, or negative v2 fixture.
- [ ] The test must fail if any artifact in `SHARED_ARTIFACTS` lacks both `<artifact>-v2-claude.valid.json` and `<artifact>-v2-codex.valid.json`.
- [ ] The test must fail if any artifact in `SHARED_ARTIFACTS` lacks an unknown-schema negative fixture.
- [ ] In the test file, validate schema-backed v1 fixtures against the existing strict schemas:

  ```python
  SCHEMA_BACKED_V1 = {"definition-doc", "checkpoint", "queue", "registry"}
  ```

- [ ] For v1 artifacts without existing schemas, add current-shape validators in `test_dual_host_contracts.py` instead of pretending a schema exists:

  ```python
  SHAPE_BACKED_V1 = {
      "finding",
      "finding-batch",
      "review-profile",
      "test-pilot-plan",
      "test-pilot-results",
      "lock",
  }
  ```

- [ ] The shape validators must assert only fields that are already produced or documented by the current runtime/templates.
- [ ] The `review-profile` v1 shape validator must parse the real markdown/provenance fixture and assert the fields current readers depend on, including verify mode or command, profile status/provenance, and review calibration sections.
- [ ] In the test file, validate v2 fixtures against the new companion v2 schemas.
- [ ] Generate required-field negative cases in the test, not only fixture files: for every positive v2 fixture, remove each field in `COMMON_PROVENANCE` and the artifact's `TIMESTAMP_FIELDS` entry, then assert the matching v2 schema rejects it with a missing-required-field error.
- [ ] Add `finding-v2-important-missing-evidence.invalid.json` and generated cases proving Important and Critical findings require non-empty evidence while Minor and Nit findings remain valid without evidence.
- [ ] The tests must prove the negative fixtures fail for the intended reason:

  - missing required host field
  - invalid host identifier
  - missing artifact-specific timestamp
  - unknown schema version
  - unsupported plugin version

- [ ] Add shared artifact reader helpers that the host-native skills can call before any workflow writer switches to v2:

- [ ] The readers must accept legacy v1 artifacts and v2 artifacts for every artifact in `SHARED_ARTIFACTS`.
- [ ] The readers must live in package-local locations usable by installed Codex packages and source-checkout Claude workflows.
- [ ] The readers must resolve the same registry/storage-mode state for Claude and Codex before any migration cutover.
- [ ] The conformance tests in Task 11 must invoke these real readers, not test-only parsers.
  - [ ] Add fail-closed negative reader tests for every artifact class: unknown schema version, unsupported plugin version, missing required provenance on v2, stale or mismatched fencing token for lock-protected records, and host/version skew that should trigger doctor/reconcile rather than a permissive read.
  - [ ] Existing writers must continue writing their current legacy formats in this task.

- [ ] Document in the test module docstring that these v2 schemas establish schema-level reader compatibility, but no existing workflow writer switches to v2 until the migration tasks are implemented.
- [ ] Do not modify existing plugin workflow writers in this task.

## Task 8: Document The Migration Contract Without Switching Writers

- [ ] Add `docs/dual-host-migration.md`.
- [ ] Include an `Expand / Migrate / Contract` section with these rules:

  - Expand: both hosts may read legacy and neutral paths, but existing writers keep writing legacy paths.
  - Migrate: a future migration command copies artifacts under the correct lock for each artifact class, validates them, and writes a marker.
  - Mutable runtime artifact migration must acquire the artifact's runtime lock or quiesce the workflow, preserve and validate fencing or generation tokens, and write the marker atomically.
  - The project config lock is only sufficient for registry, calibration, and config-mode updates.
  - Contract: neutral paths become write targets only after both hosts' minimum compatible plugin versions can read them.

- [ ] Include artifact classes:

  - Definition-docs
  - Review findings
  - Test-pilot plans
  - Test-pilot results
  - Checkpoints
  - Queues
  - Profiles and calibration
  - Locks
  - Registry/storage-mode records

- [ ] For each artifact class, document:

  - Current source of truth.
  - Neutral target path.
  - Whether it is read-only, single-writer, or lock-protected.
  - Source-of-truth precedence during expand mode.
  - Idempotent copy/backfill command shape.
  - Completion marker path and contents.
  - Registry or storage-mode update performed after validation.
  - Validation command that must pass before cutover.
  - Rollback behavior.
  - Behavior for cached old plugins that still read legacy paths.

- [ ] Include the lock contract from the design:

  - Atomic acquisition.
  - Machine-local location.
  - Ownership records `host`, `runId`, `pluginVersion`, and timestamp.
  - Generation or fencing token.
  - Deterministic stale-lock recovery.

- [ ] Include a `Doctor / Reconcile` section that reports:

  - Legacy-vs-neutral divergence.
  - Stale locks.
  - Unsupported host/plugin versions.
  - Last-writer provenance.
  - Missing migration markers.

- [ ] State explicitly that this task does not switch any existing writer to a new neutral runtime path.

## Task 9: Document Host-Native Runtime Boundaries

- [ ] Add `docs/dual-host-runtime.md`.
- [ ] Include a table with these columns:

  ```text
  Plugin | Shared Contract | Claude Runtime Surface | Codex Runtime Surface | Coexistence Rule
  ```

- [ ] Add rows for:

  - review-crew
  - test-pilot
  - the-architect

- [ ] Include a `Claude remains first-class` section:

  - Root-level Claude package files remain valid during this release.
  - Claude agents remain Claude-native.
  - Claude browser and design workflows remain documented in Claude skill files.

- [ ] Include a `Codex becomes first-class` section:

  - Codex manifests live under each `codex/` package root.
  - Codex skills are hand-authored, not generated from Claude files.
  - Codex runtime guidance can use Codex-native plan loops, subagents, tool discovery, and browser tooling.

- [ ] Include a `Same project, both hosts` section:

  - Host config remains in host-specific directories.
  - Shared artifacts use shared schemas and provenance.
  - Mutable runtime records do not move until migration is explicitly implemented.

## Task 10: Update User-Facing Docs Without Rebranding The Project Around Codex

- [ ] Update `README.md` to mention that superheroes is becoming a dual-host marketplace for Claude Code and Codex.
- [ ] Preserve the existing Claude-oriented install and usage path.
- [ ] Add a Codex install/status section that points to `.agents/plugins/marketplace.json`.
- [ ] Link to `docs/dual-host-runtime.md`.
- [ ] Update `.gitignore` and repo conventions as needed so `docs/dual-host-runtime.md` and `docs/dual-host-migration.md` are explicitly tracked public docs, while existing scratch/design docs under `docs/` remain local-only unless separately unignored.
- [ ] Update `CONTRIBUTING.md` with a `Dual-host changes` section:

  - Change shared contracts in `shared/` or schema files.
  - Change Claude-specific runtime files in existing Claude package roots.
  - Change Codex-specific runtime files under `codex/`.
  - Run both marketplace validators before opening a PR.

- [ ] Update `RELEASING.md` with a dual-host release checklist:

  - Claude manifests validate.
  - Codex manifests validate.
  - Cross-host versions match.
  - Codex package roots are self-contained.
  - Shared reviewer methodology drift test passes.

- [ ] Do not remove existing Claude examples or Claude wording unless the sentence is specifically describing the marketplace as Claude-only.

## Task 11: Verify The Full Contract

- [ ] Add `eval/fixtures/dual-host/conformance/` with bidirectional coexistence fixtures:

  - [ ] Claude-authored review finding batch read by the Codex contract reader.
  - [ ] Codex-authored review finding batch read by the Claude contract reader.
  - [ ] Claude-authored test-pilot plan and results read by the Codex contract reader.
  - [ ] Codex-authored test-pilot plan and results read by the Claude contract reader.
  - [ ] Claude-authored definition-doc read by the Codex contract reader.
  - [ ] Codex-authored definition-doc read by the Claude contract reader.
  - [ ] Held lock, stale lock, and fencing-token lock cases for both hosts.
  - [ ] Doctor/reconcile output fixtures for both host directions.

- [ ] Add `eval/lib/tests/test_dual_host_conformance.py`.
- [ ] The conformance tests must prove that each host can read the other host's shared artifacts without rewriting host-native runtime files.
- [ ] The conformance tests must cover held-lock behavior, stale-lock recovery behavior, doctor output, reconcile output, and all three workflow families: review-crew, test-pilot, and the-architect.
- [ ] The conformance tests must fail if either host direction is absent; do not count schema-only fixture validation as operational coexistence.
- [ ] Implement a dual-host doctor/reconcile helper or CLI before writing the doctor/reconcile conformance assertions.
- [ ] The doctor/reconcile tests must execute the helper against divergence, stale-lock, and version-skew fixtures and assert the recovery guidance and machine-readable status, not only compare static output files.
- [ ] The conformance tests must invoke the shared artifact readers from Task 7 for v1 and v2 Claude-authored and Codex-authored fixtures.

- [ ] Run marketplace validators:

  ```bash
  python3 .github/scripts/validate_marketplace.py
  python3 .github/scripts/validate_dual_host_marketplace.py
  ```

- [ ] Run the full test suite:

  ```bash
  python3 -m pytest plugins/review-crew/lib/tests/ plugins/review-crew/eval/tests/ plugins/test-pilot/lib/tests/ plugins/the-architect/lib/tests/ eval/lib/tests/ -q
  ```

- [ ] Run a placeholder scan:

  ```bash
  python3 - <<'PY'
  import pathlib

  roots = [".agents", "plugins", "docs", "eval", ".github"]
  markers = ["TB" + "D", "TO" + "DO", "PLACE" + "HOLDER", "FIX" + "ME"]
  for root in roots:
      path = pathlib.Path(root)
      if not path.exists():
          continue
      for file_path in path.rglob("*"):
          if not file_path.is_file():
              continue
          try:
              text = file_path.read_text()
          except UnicodeDecodeError:
              continue
          for line_no, line in enumerate(text.splitlines(), 1):
              if any(marker in line for marker in markers):
                  print(f"{file_path}:{line_no}:{line}")
  PY
  ```

- [ ] Inspect git changes:

  ```bash
  git status --short
  git diff --stat
  ```

- [ ] Confirm these conditions before completion:

  - Existing Claude validator passes.
  - New dual-host validator passes.
  - Existing plugin tests pass.
  - New dual-host tests pass.
  - Bidirectional conformance tests pass for Claude-authored and Codex-authored artifacts.
  - No core plugin Python behavior changed except tests or validation helpers.
  - Claude package files still exist at their current paths.
  - Codex package roots are self-contained enough for validation.

## Review Checkpoints

After Task 3:

- Review whether the Codex manifest shape is host-native enough without making claims about unsupported runtime capabilities.
- Review whether the drift validator catches version and source-root mistakes.

After Task 6:

- Review Codex skill wrappers for host-native quality.
- Confirm they do not read like Claude instructions with renamed nouns.
- Confirm they do not weaken or contradict Claude skills.

After Task 8:

- Review migration documentation against `CONVENTIONS.md`.
- Confirm no committed runtime path is introduced for mutable state.

After Task 11:

- Request a full plan/code review using review-crew.
- Fix any findings that identify concrete compatibility, validation, or documentation risks.

## Acceptance Criteria

- Claude users still have the same first-class manifest, skill, and agent surface they had before.
- Codex users have first-class marketplace metadata, plugin manifests, and host-native skill wrappers.
- Both host surfaces agree on plugin identity, versions, author, and shared contracts.
- CI fails if Codex package roots point at Claude package roots.
- CI fails if plugin versions drift across hosts.
- CI fails if shared reviewer methodology drifts from Claude reviewer agents during the transition.
- Shared contract fixtures cover Claude-produced and Codex-produced artifacts.
- Migration docs define expand, migrate, contract, rollback, lock semantics, and doctor/reconcile behavior.
- No existing plugin workflow behavior is changed by this implementation.
