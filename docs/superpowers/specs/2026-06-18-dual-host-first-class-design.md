# Dual-Host First-Class Plugin Design

## Purpose

Make the superheroes marketplace first-class for both Claude Code and Codex without
making either host feel secondary. The long-term target is full runtime parity:
Claude users and Codex users can install, invoke, and operate the same plugin family
in the same project, with host-native ergonomics on both sides and shared artifacts
that remain compatible across hosts.

This design is intentionally about the plan and architecture. It does not change
review-crew, test-pilot, or the-architect behavior by itself.

## Goals

- Preserve a first-class Claude experience: Claude-native manifests, slash-command
  usage, bundled Claude agents, Claude interaction primitives, and Claude-specific
  docs remain valid and intentionally maintained.
- Add a first-class Codex experience: Codex-native manifests, marketplace metadata,
  install/update docs, runtime instructions, browser/tool discovery, and agent
  orchestration guidance are intentionally maintained rather than translated from
  Claude as an afterthought.
- Let Claude and Codex users work in the same project without corrupting shared
  artifacts, profiles, checkpoints, review findings, test plans, or definition-docs.
- Keep shared contracts identical where sameness matters: schemas, rubric versions,
  artifact formats, gate semantics, version metadata, lock behavior, and compatibility
  guarantees.
- Avoid premature generation of runtime instructions. Hand-author host-native
  runtime paths now; generate only stable metadata or repetitive packaging later.

## Non-Goals

- Do not replace Claude-specific execution with generic capability language.
- Do not make Codex emulate Claude concepts when Codex has a native mechanism.
- Do not migrate existing plugin behavior as part of the first design checkpoint.
- Do not create a least-common-denominator runtime path.
- Do not make either `.claude/` or `.agents/` the universal shared project-state
  namespace.

## Recommended Approach

Use the hybrid strategy:

1. **Now: Option 1 for runtime authoring.**
   Maintain a shared contract layer plus host-specific runtime files. Claude and
   Codex instructions can use their own vocabulary, tools, and best practices.

2. **Now: Option 3-style validation for shared metadata and contracts.**
   Add deterministic checks so plugin names, versions, sources, schemas, rubric
   versions, artifact formats, and compatibility claims cannot drift silently.

3. **Later: Generate only the boring parts after patterns stabilize.**
   Once the host-native structures have proven themselves, generate manifest
   fragments, compatibility matrices, or repeated metadata. Do not generate nuanced
   runtime instructions until the templates can preserve host quality.

This mirrors mature multi-host plugin ecosystems: one product contract, parallel
host-native packaging and runtime surfaces, and shared validation where drift is
dangerous.

## Architecture

### Layer 1: Shared Product Contract

The shared contract defines what Claude and Codex must agree on:

- plugin identity and versioning
- artifact schemas
- `spec`, `plan`, and `tasks` definition-doc frontmatter
- review findings schema
- severity rubric and verdict mapping
- test-pilot manifest and PR comment formats
- profile and calibration schema
- runtime lock semantics
- host/run provenance fields
- backwards-compatible reads for legacy paths

This layer should live in shared docs, schema files, and test fixtures. It should
not contain host-specific runtime instructions except as compatibility requirements.

### Layer 2: Claude-Native Surface

Claude keeps first-class Claude mechanics:

- `.claude-plugin/marketplace.json`
- `plugins/<name>/.claude-plugin/plugin.json`
- Claude slash-command docs
- Claude bundled agents for review-crew specialists
- Claude `Agent` dispatch instructions
- Claude interaction primitives where they are the best UX
- Claude Design as the first-class design handoff path for Claude users
- Claude install, update, release, and troubleshooting docs

Claude instructions should not be softened merely because Codex needs a different
runtime path.

### Layer 3: Codex-Native Surface

Codex gets first-class Codex mechanics:

- `.agents/plugins/marketplace.json`
- `plugins/<name>/.codex-plugin/plugin.json`
- Codex plugin install/update docs
- Codex-native skill/runtime instructions
- Codex tool discovery instructions
- Codex browser guidance using the available browser tooling
- Codex subagent or worker guidance where available
- Codex-native alternatives for Claude-only surfaces such as Claude Design

Codex instructions should not be phrased as a Claude compatibility mode.

## Project Coexistence

Shared project artifacts must live in a host-neutral space, but the migration to
that space must not bypass the existing storage contract in `CONVENTIONS.md`.
Preferred long-term in-repo locations:

- `docs/superheroes/<work-item>/` for definition-docs
- `.superheroes/` for shared calibration and compatibility metadata when in-repo
  mode is selected

Host-specific configuration remains host-specific:

- `.claude/` for Claude-owned configuration and host-local compatibility shims
- `.agents/` for Codex-owned configuration and host-local marketplace/plugin data

Runtime records, locks, caches, queues, checkpoints, and host-local execution
state must not be committed into `.superheroes/`. They stay in the existing
machine-local project/control-plane stores, or in host-owned local storage, until a
specific schema migration says otherwise. Add validation that rejects mutable
runtime artifacts under committed neutral paths.

Every mutable runtime record that may be touched by either host should include:

- `schemaVersion`
- `pluginVersion`
- `host`
- `hostVersion` when discoverable
- `runId`
- `created`
- `updated`

These fields require a schema-version migration before any runtime writer emits
them. Existing strict schemas such as queue and checkpoint records need
backwards-compatible v1 readers, v2 fixtures, and explicit field naming. For
example, do not silently replace an existing field such as `updatedAt` with
`updated`; either preserve the old field or define the v2 rename and migration.

Any shared file that can be written by both hosts needs the same cross-host lock
contract. The lock contract is part of the shared product contract, not a
host-local implementation detail:

- lock location is in the machine-local project/control-plane store, never in a
  committed neutral directory
- lock acquisition is atomic
- lock ownership records `host`, `runId`, `pluginVersion`, and timestamp
- writes use a generation or fencing token so stale owners cannot commit
- stale-lock recovery is deterministic and logged
- each shared artifact is classified as single-writer, lock-protected, or
  read-only compatibility input

Host-local ephemeral state can remain in host-specific storage.

## Migration And Compatibility

The neutral namespace supersedes the old Claude-named shared paths only through a
versioned migration. Until that migration completes, existing `.claude/...` and
`~/.claude/...` stores remain authoritative for the data they already own.

The migration must be expand/migrate/contract:

1. **Expand.** Add readers that can see both legacy and neutral paths. Keep writes
   on the existing authoritative path.
2. **Migrate.** Under the project config lock, copy each artifact class to the
   neutral location, validate it, and write an authoritative migration marker.
3. **Contract.** Switch writes to the neutral location only after both hosts'
   minimum compatible plugin versions can read it. Legacy paths become read-only
   compatibility inputs.

For each artifact class, the implementation plan must define:

- source-of-truth precedence during migration
- idempotent copy/backfill command
- completion marker and registry/storage-mode update
- validation before cutover
- rollback behavior if copying, validation, or marker write fails
- behavior for cached old plugins that still read legacy paths

Before a host writes a new shared schema, it must run a compatibility preflight:
the other host's minimum compatible plugin version must be known, or the writer
must stay in dual-compatible mode. Unknown schema versions still fail closed, but
the preferred failure happens before the incompatible write.

Add a dual-host `doctor` / `reconcile` command before broad rollout. It reports:

- legacy-vs-neutral divergence
- stale locks
- unsupported host/plugin versions
- last-writer provenance
- missing migration markers
- explicit recovery actions before either host writes again

## Runtime File Layout

Use a concrete, host-native source layout so contributors and CI can see the
boundary. Long term, each plugin uses:

```text
plugins/<name>/
  shared/                 # schemas, contracts, fixtures, shared reviewer methodology
  claude/                 # Claude-native package source
    .claude-plugin/
    skills/
    agents/
  codex/                  # Codex-native package source
    .codex-plugin/
    skills/
    agents/               # wrappers or host files when Codex needs them
```

The current root-level `skills/`, `agents/`, and `.claude-plugin/` directories are
the legacy Claude package source until the packaging cleanup lands. The cleanup
must either move them into `claude/` or explicitly mirror them there, with tests
proving the published Claude package still contains the same skill and agent
surface.

Codex marketplace entries should point at a self-contained Codex package root.
Codex runtime files must not depend on files outside the package archive unless the
packaging step vendors those shared files into the Codex package. The same
self-contained rule applies to Claude packages.

Review-crew reviewer methodology has one shared source of truth. Preferred path:
`plugins/review-crew/shared/reviewers/*.md`. During migration, existing
`plugins/review-crew/agents/*.md` may be treated as the temporary shared
methodology source consumed directly by Claude and referenced by Codex wrappers.
The implementation must add drift checks so Claude and Codex cannot diverge in
severity, taxonomy, verification behavior, or reviewer coverage.

## Workflow Strategy

### review-crew

Shared:

- shared reviewer methodology source of truth
- base rubric
- findings schema
- compile, dedupe, and diff-scope rules
- verdict mapping
- learning-loop records

Claude-native:

- bundled reviewer agents dispatched by Claude `Agent`
- Claude slash invocation
- Claude interaction and posting flow

Codex-native:

- Codex-compatible reviewer wrappers or runtime files
- Codex subagent/worker dispatch guidance where available
- Codex interaction flow for judgment calls and auto-fix decisions

The outcome should be equivalent findings and gates, not identical mechanics.
Equivalence is tested with shared fixtures: both hosts must dispatch the same
dimensions, apply the same verdict mapping, preserve the same gate semantics, and
emit findings that conform to the same taxonomy and severity rules.

### test-pilot

Shared:

- seeding engine contracts
- catalog format
- test-plan record format
- protected-target safety rules
- navigation constraints
- PR comment format and scrubber behavior

Claude-native:

- Claude browser/tool discovery and Claude-specific browser session guidance

Codex-native:

- Codex browser/tool discovery and Codex-specific execution guidance

The same plan should be inspectable by either host, and eventually executable by
either host when the required browser/tooling is present.

### the-architect

Shared:

- Discovery -> Plan -> Tasks contract
- definition-doc schemas
- gate semantics
- work-item identifiers
- owner approval rules

Claude-native:

- Claude Design remains a first-class design handoff path

Codex-native:

- Codex-native design capture path that records the actual design source instead
  of assuming Claude Design

The spec should describe the design source neutrally so either host can continue
the work item.

## Data Flow

1. User installs the relevant marketplace for Claude, Codex, or both.
2. Each host loads its own manifest and runtime instructions.
3. When a workflow creates shared artifacts, it writes the shared schema and host
   provenance.
4. The other host reads the artifact through the shared resolver and validates the
   schema before acting.
5. Mutable shared records are updated through the shared lock contract or an
   explicit single-writer rule.
6. CI validates that the shared contract and host manifests remain compatible.

## Error Handling

- Unknown schema versions fail closed with a clear update/migration message.
- Missing host-native tooling degrades within that host only; it does not change
  the shared contract.
- Legacy `.claude/...` data is read as compatibility input, not overwritten
  blindly.
- Conflicting writes are blocked by lock ownership or resolved through explicit
  migration commands.
- If one host cannot execute a workflow yet, it should still explain which shared
  artifacts it can read and which host-native runtime capability is missing.
- Version skew is caught before writes. A host that cannot prove the other host's
  minimum compatible plugin band must keep writing the legacy-compatible format or
  stop with upgrade instructions.
- Recovery is an explicit workflow, not just an error message: run the dual-host
  `doctor` / `reconcile` flow before retrying after migration, lock, or
  version-skew failures.

## Validation And Testing

Add validation at three levels:

1. **Manifest validation**
   - Claude marketplace and plugin manifests validate.
   - Codex marketplace and plugin manifests validate.
   - Cross-host metadata drift fails CI.
   - Codex marketplace parses, has a non-empty `plugins` array, and every source
     path points at a self-contained Codex package root.
   - Codex plugin manifests have valid semver and required interface metadata.
   - Claude and Codex manifests agree on plugin name, version, description intent,
     author, repository, license, and release source path.
   - Duplicate-version traps are checked for both hosts.
   - `.github/workflows/ci.yml` runs Claude validation, Codex validation, and the
     cross-host drift validator.

2. **Contract validation**
   - Shared schemas validate.
   - Rubric and artifact versions are consistent.
   - Definition-doc, finding, profile, and test-plan fixtures round-trip.
   - Positive fixtures include Claude-produced and Codex-produced records with
     `schemaVersion`, `pluginVersion`, `host`, `hostVersion`, `runId`, `created`,
     and `updated` or the artifact's explicitly versioned timestamp field.
   - Negative fixtures cover missing provenance fields, unknown schema versions,
     invalid host identifiers, unsupported plugin versions, and writes attempted
     before compatibility preflight.
   - Queue, checkpoint, profile, definition-doc, finding, and test-pilot plan
     fixtures include v1 legacy inputs and v2 host-provenance inputs.
   - Strict schemas set `additionalProperties` intentionally, and any added field
     ships with a schema-version bump plus compatibility reader tests.
   - Reviewer-methodology drift tests prove Claude and Codex wrappers reference
     the same methodology source and preserve dimension names, taxonomy terms,
     severity rules, and findings filenames.

3. **Coexistence validation**
   - Claude-created shared artifacts are readable by Codex.
   - Codex-created shared artifacts are readable by Claude.
   - Legacy `.claude/...` data is still discoverable.
   - Neutral shared paths are preferred for new shared writes after migration.
   - Concurrent host runs cannot clobber shared mutable state.
   - Legacy `.claude/...` data is read but not overwritten during expand mode.
   - New writes prefer neutral paths only after the authoritative migration marker
     exists.
   - A held lock blocks the second host and reports the lock holder.
   - Stale-lock recovery is deterministic and covered by a crash/timeout fixture.
   - A partial migration can be re-run idempotently or rolled back.
   - The dual-host `doctor` / `reconcile` fixture reports legacy-vs-neutral
     divergence, stale locks, unsupported versions, and last-writer provenance.
   - Cross-host behavioral conformance fixtures exercise review-crew verdicts,
     gate writes, test-pilot plan readability, and the-architect definition-doc
     continuation from both host directions.
   - Test-pilot conformance fixtures cover every safety-relevant runtime
     invariant from both host directions: seeded mutations go through the shared
     engine, protected-target checks block unsafe writes, navigation constraints
     are enforced, diagnostic scrubber behavior is identical, and PR comments keep
     the shared plan/results format.
   - The-architect conformance fixtures cover owner approval gates, review-gate
     semantics, definition-doc frontmatter, parent linkage, work-item identity,
     and design-source recording from both host directions.

## Implementation Sequence

1. Document dual-host principles and shared boundaries.
2. Decide the runtime file layout and packaging roots.
3. Add Codex marketplace and plugin manifests beside Claude manifests.
4. Add manifest and metadata drift validation.
5. Define neutral shared-state paths, legacy read compatibility, and migration
   cutover markers.
6. Define the shared lock contract and dual-host doctor/reconcile flow.
7. Migrate affected schemas with v1 readers, v2 fixtures, and version-skew
   preflight rules.
8. Split runtime guidance into shared contract plus Claude-native and Codex-native
   runtime files.
9. Port review-crew runtime guidance for Codex while preserving Claude agent flow.
10. Port test-pilot runtime guidance for Codex while preserving Claude browser flow.
11. Port the-architect runtime guidance for Codex while preserving Claude Design flow.
12. Add coexistence fixtures and cross-host behavioral smoke tests.
13. Revisit generation only for stable, repetitive metadata.

## Open Decisions

- Which pieces of plugin metadata become generated first.
- Whether `.superheroes/` is introduced as a breaking convention migration or
  deferred in favor of the existing `.claude/superheroes/` storage contract for
  the first dual-host runtime release.
- Whether the root-level Claude package source is moved to `claude/` immediately
  or mirrored there for one release before removal.

## Acceptance Criteria

- A contributor can explain which files are shared contract, Claude-native runtime,
  and Codex-native runtime.
- Claude install and runtime docs remain first-class and host-native.
- Codex install and runtime docs become first-class and host-native.
- Both hosts can share project artifacts through a neutral contract.
- CI catches manifest drift and shared-schema incompatibility.
- No plugin behavior is changed until an implementation plan explicitly scopes that
  behavior change.
