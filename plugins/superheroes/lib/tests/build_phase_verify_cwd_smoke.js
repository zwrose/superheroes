// #396: the whole-branch final-review verify gate must run the project's verify command IN THE BUILD
// WORKTREE (deterministic --cwd), not the hosting session's inherited cwd, and must enforce its
// duration ceiling mechanically (explicit --timeout + a self-bounding perl-alarm wrapper) rather than
// depending on the courier honoring a prompt-text Bash timeout. Before the fix, verifyAgent composed
// `verify_gate.py --command … --out …` with no --cwd, so the courier leaf ran verify in the launching
// session's directory — false red (a broken session tree parks a good branch) and, worse, false green
// (the branch's changes are never in the tested tree).
//
// This exercises verifyAgent (the exported leaf reused by both reviewPanel's per-round gate and
// build_phase.runFinalReview's #382 post-cap fix-pass verify) two ways:
//   1. BEHAVIORAL — a courier stub that ACTUALLY runs the composed command from a session cwd that is
//      NOT the worktree; the verify command prints `pwd`, and the round-stamped result must record the
//      WORKTREE path, proving the subprocess ran there.
//   2. STRING PIN — the composed command carries the explicit --cwd, --timeout, and perl-alarm wrapper
//      when a worktree is threaded, and is byte-identical to the pre-fix command when none is (so the
//      review-code leg, which roots via withTargetCommandPrompts' prompt cd-wrap, is unaffected).
// Run: node plugins/superheroes/lib/tests/build_phase_verify_cwd_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { execSync } = require('child_process')

// Absolute spine code root so `libPath('verify_gate.py')` yields an absolute, cwd-independent path —
// exactly the production posture (the launcher plants an absolute __SR_LIB). Set BEFORE requiring the
// shell so libRoot() reads it at call time.
global.__SR_LIB = path.resolve(__dirname, '..')
const { verifyAgent } = require('../review_panel_shell.js')
const { io } = require('../io_seam.js')

global.log = () => {}

function freshDir(prefix) { return fs.mkdtempSync(path.join(os.tmpdir(), prefix)) }

// Extract the exact shell command verifyAgent asks the courier to run: the leaf prompt is
// "Run exactly this …:\n\n<command>", so the command is the tail after the sole blank-line boundary.
function commandFromPrompt(prompt) { return String(prompt).split('\n\n').pop() }

async function main() {
  // ── 1. BEHAVIORAL: verify runs in the worktree, not the session cwd ────────────────────────────
  {
    const worktree = freshDir('vc-worktree-')
    const sessionCwd = freshDir('vc-session-')   // a DIFFERENT tree — stands in for the hosting session
    const runDir = freshDir('vc-run-')
    let captured = null
    // The courier stub runs the EXACT composed command (as the real courier leaf would) from the
    // session cwd, then echoes verify_gate.py's stdout JSON back — the round-stamped --out file is the
    // authoritative read-back verifyAgent consults.
    global.agent = async (prompt) => {
      const cmd = commandFromPrompt(prompt)
      captured = cmd
      const stdout = execSync(cmd, { cwd: sessionCwd, encoding: 'utf8' })
      return JSON.parse(stdout)
    }
    const result = await verifyAgent('pwd', runDir, 1, io(), worktree)
    assert.strictEqual(result, 'pass', 'pwd exits 0 → the verify gate classifies pass')
    const payload = JSON.parse(fs.readFileSync(path.join(runDir, 'verify-result-r1.json'), 'utf8'))
    // realpath: macOS /tmp is a symlink to /private/tmp, so `pwd` prints the resolved worktree path.
    const realWorktree = fs.realpathSync(worktree)
    const realSession = fs.realpathSync(sessionCwd)
    assert.ok(payload.tail.includes(realWorktree),
      `verify ran in the WORKTREE: result tail must contain ${realWorktree}, got: ${payload.tail}`)
    assert.ok(!payload.tail.includes(realSession),
      `verify did NOT run in the session cwd: tail must not contain ${realSession}, got: ${payload.tail}`)
    // And the composed command carries the deterministic seam controls.
    assert.ok(captured.includes(`--cwd '${worktree}'`), 'composed command threads --cwd <worktree>')
    assert.ok(/--timeout 600(\s|$)/.test(captured), 'composed command passes an explicit --timeout')
    assert.ok(captured.includes("perl -e 'alarm shift; exec @ARGV' 630 "),
      'composed command is self-bounding via a perl-alarm wrapper whose ceiling (630) > gate --timeout (600)')
  }

  // ── 2a. STRING PIN: worktree threaded → --cwd + --timeout + perl wrapper, gate timeout below alarm ─
  {
    const runDir = freshDir('vc-pin-')
    let seen = null
    global.agent = async (prompt) => { seen = commandFromPrompt(prompt); return null }
    // No --out file is written (stub returns null and runs nothing), so both read-backs miss and the
    // gate fails closed — irrelevant here; we only pin the composed command shape.
    await verifyAgent('npm run check', runDir, 2, io(), '/build/worktree/x')
    assert.ok(seen.includes("--command 'npm run check'"), 'the verify command is quoted into --command')
    assert.ok(seen.includes("--cwd '/build/worktree/x'"), 'the threaded worktree becomes --cwd')
    assert.ok(seen.includes('--timeout 600'), 'the gate timeout is passed explicitly (not prompt-only)')
    assert.ok(seen.startsWith("perl -e 'alarm shift; exec @ARGV' 630 python3 "),
      'the whole invocation is wrapped in a perl alarm ceiling ABOVE the gate timeout')
    assert.ok(seen.includes('verify-result-r2.json'), 'the round-stamped --out path rides along')
  }

  // ── 2b. STRING PIN: no worktree threaded → byte-identical to the pre-#396 command (review-code leg) ─
  {
    const runDir = freshDir('vc-compat-')
    let seen = null
    global.agent = async (prompt) => { seen = commandFromPrompt(prompt); return null }
    await verifyAgent('npm run check', runDir, 1, io())   // no cwd arg — the review-code posture
    assert.ok(!seen.includes('--cwd'), 'no worktree threaded → no --cwd (review-code cd-wraps the prompt instead)')
    assert.ok(!seen.includes('--timeout'), 'no worktree threaded → no explicit --timeout (unchanged)')
    assert.ok(!seen.includes('perl '), 'no worktree threaded → no perl wrapper (byte-identical to pre-#396)')
    const expected = `python3 ${global.__SR_LIB}/verify_gate.py --command 'npm run check' --out ` +
      `'${path.join(runDir, 'verify-result-r1.json')}'`
    assert.strictEqual(seen, expected, 'the no-cwd composed command is byte-identical to the pre-#396 form')
  }

  console.log('build_phase_verify_cwd_smoke: OK')
}

main().catch((e) => { console.error(e); process.exit(1) })
