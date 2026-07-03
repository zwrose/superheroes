// Unit smoke: _policyChangedSubjects derives policy subjects from the live code-fixer shape
// (fixes as {id,summary,files} objects + changedSubjects as file paths). Regression for #157 —
// the Trust-or-Escalate scheduler keys on this signal; empty/malformed subjects force full Opus-deep.
'use strict'
const assert = require('assert')
const roundPolicy = require('../review_round_policy.js')
const { normalizeFixResult, _policyChangedSubjects } = require('../showrunner.js')

// Run wf_09c036a1-242 round-2 fix shape: file-path changedSubjects + object fixes.
const RUN21_PRIOR = [
  {
    file: 'plugins/superheroes/lib/acceptance_run.py',
    dimension: 'Architecture',
    title: 'acceptance runner bypasses worktree guard',
    severity: 'Important',
    taxonomy: 'architecture',
  },
  {
    file: 'plugins/superheroes/lib/acceptance_deps.py',
    dimension: 'Failure-Mode',
    title: 'missing dependency failure handling',
    severity: 'Critical',
    taxonomy: 'failure',
  },
  {
    file: 'plugins/superheroes/lib/acceptance_launch.py',
    dimension: 'Code',
    title: 'launch path swallows import errors',
    severity: 'Important',
    taxonomy: 'bug',
  },
  {
    file: 'plugins/superheroes/lib/review_memory.py',
    dimension: 'Test',
    title: 'missing regression for changedSubjects',
    severity: 'Minor',
    taxonomy: 'coverage',
  },
]

const RUN21_FIX = {
  fixes: [
    {
      id: 'Architecture::architecture::acceptance runner bypasses worktree guard',
      summary: 'guard worktree before launch',
      files: ['plugins/superheroes/lib/acceptance_run.py'],
    },
    {
      id: 'plugins/superheroes/lib/acceptance_deps.py::missing dependency failure handling',
      summary: 'surface dependency failures',
      files: ['plugins/superheroes/lib/acceptance_deps.py'],
    },
    {
      id: 'Code::bug::launch path swallows import errors',
      summary: 'propagate import errors',
      files: ['plugins/superheroes/lib/acceptance_launch.py'],
    },
  ],
  deferred: [],
  changedSubjects: [
    'plugins/superheroes/lib/acceptance_run.py',
    'plugins/superheroes/lib/acceptance_deps.py',
    'plugins/superheroes/lib/acceptance_launch.py',
  ],
  coverageDecisions: [],
}

const fixContext = { priorFindings: RUN21_PRIOR }

function main() {
  const subjects = _policyChangedSubjects(RUN21_FIX, fixContext)
  assert.deepStrictEqual(subjects, ['Architecture', 'Code', 'Failure-Mode'],
    'file-path changedSubjects + object fixes must yield touched policy subjects')

  const normalized = normalizeFixResult(RUN21_FIX, fixContext)
  assert.deepStrictEqual(normalized.changedSubjects, ['Architecture', 'Code', 'Failure-Mode'])
  assert.deepStrictEqual(normalized.changedSubjectDetails, RUN21_FIX.changedSubjects,
    'raw file-path details must be preserved for audit')

  // Object-stringify regression: fixes with no id match still derive via files[].
  const filesOnly = {
    fixes: RUN21_FIX.fixes.map((f) => ({ summary: f.summary, files: f.files })),
    changedSubjects: RUN21_FIX.changedSubjects,
    coverageDecisions: [],
  }
  assert.deepStrictEqual(_policyChangedSubjects(filesOnly, fixContext),
    ['Architecture', 'Code', 'Failure-Mode'],
    'files[] on fix objects must join to priorFindings by path')

  // End-to-end: normalized subjects must unlock cheap-first scheduling (not unknown-changed-subjects).
  const policy = roundPolicy.planRound({
    round: 2,
    dimensions: [
      'architecture-reviewer', 'code-reviewer', 'security-reviewer',
      'test-reviewer', 'premortem-reviewer',
    ],
    changedSubjects: normalized.changedSubjects,
    previous: {
      'architecture-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Architecture'], round: 1 },
      'code-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Code'], round: 1 },
      'security-reviewer': { status: 'run', confidence: 'high', hasFindings: false, subjects: ['Security'], round: 1 },
      'test-reviewer': { status: 'run', confidence: 'high', hasFindings: false, subjects: ['Test'], round: 1 },
      'premortem-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Failure-Mode'], round: 1 },
    },
    confirmation: false,
  })
  assert.strictEqual(policy.escalationPolicy, 'cheap-first')
  assert.strictEqual(policy.dimensions['security-reviewer'].action, 'skip',
    'clean untouched security must skip on intermediate round')
  assert.strictEqual(policy.dimensions['architecture-reviewer'].tier, 'reviewer',
    'touched architecture must run cheap-first on Sonnet')
  assert.strictEqual(policy.dimensions['premortem-reviewer'].tier, 'reviewer',
    'touched failure-mode must run cheap-first on Sonnet')

  // Runtime hop: normalizeFixResult → extras.changedSubjects → planRound input (review_panel_shell.js:566→482).
  const lastExtras = normalized.extras
  assert.deepStrictEqual(lastExtras.changedSubjects, ['Architecture', 'Code', 'Failure-Mode'])
  const wired = roundPolicy.planRound({
    round: 2,
    dimensions: [
      'architecture-reviewer', 'code-reviewer', 'security-reviewer',
      'test-reviewer', 'premortem-reviewer',
    ],
    changedSubjects: lastExtras.changedSubjects,
    previous: {
      'architecture-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Architecture'], round: 1 },
      'code-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Code'], round: 1 },
      'security-reviewer': { status: 'run', confidence: 'high', hasFindings: false, subjects: ['Security'], round: 1 },
      'test-reviewer': { status: 'run', confidence: 'high', hasFindings: false, subjects: ['Test'], round: 1 },
      'premortem-reviewer': { status: 'run', confidence: 'high', hasFindings: true, subjects: ['Failure-Mode'], round: 1 },
    },
    confirmation: false,
  })
  assert.strictEqual(wired.escalationPolicy, policy.escalationPolicy,
    'extras.changedSubjects must be the exact signal planRound receives on the next round')

  console.log('ok: _policyChangedSubjects derives policy subjects from code-fixer file-path shape')
}

main()
