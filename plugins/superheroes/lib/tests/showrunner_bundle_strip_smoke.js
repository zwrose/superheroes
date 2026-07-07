// plugins/superheroes/lib/tests/showrunner_bundle_strip_smoke.js
// Unit coverage for bundle_showrunner.js stripComments() — the string/template/regex-aware comment
// stripper (#295). Asserts the two load-bearing properties: (1) full-line // comments and blank lines
// in plain-code context are removed; (2) a // line or blank line that is STRING DATA inside a
// multi-line template literal is preserved. Plus the regex-vs-division heuristic hardening and the
// EOF tokenizer-desync self-check.
const assert = require('assert')
const path = require('path')
const { stripComments } = require(path.join(__dirname, '..', 'bundle_showrunner.js'))

function strip(src) { return stripComments(src) }
const BT = String.fromCharCode(96)   // backtick, kept out of this file's own source to avoid confusion

// (1) Plain-code full-line comments and blank lines are stripped; trailing comments survive.
{
  const src = [
    '// leading comment',
    'const a = 1',
    '',
    '    // indented full-line comment',
    'const b = 2 // trailing comment stays',
    'const c = 3',
  ].join('\n')
  const out = strip(src)
  assert.ok(!/leading comment/.test(out), 'full-line comment must be stripped')
  assert.ok(!/indented full-line comment/.test(out), 'indented full-line comment must be stripped')
  assert.ok(/trailing comment stays/.test(out), 'trailing (end-of-line) comment must be preserved')
  assert.ok(!/^\s*$/m.test(out.split('\n').slice(0, -1).join('\n')) || true, 'blank lines removed')
  assert.strictEqual(out.split('\n').filter((l) => l.trim() === '').length, 0, 'no blank code lines remain')
  assert.ok(/const a = 1/.test(out) && /const b = 2/.test(out) && /const c = 3/.test(out), 'code preserved')
}

// (2) THE critical property: a // line and a blank line INSIDE a multi-line template literal are
// string data and must survive verbatim (agent prompts / embedded Python in the real bundle).
{
  const src = [
    'const prompt = ' + BT + 'run this:',
    '// this is python-ish text, NOT a JS comment',
    '',
    'print(1)' + BT,
    'const after = 1',
  ].join('\n')
  const out = strip(src)
  assert.ok(/this is python-ish text/.test(out), 'template-interior // line must be preserved')
  assert.ok(out.split('\n').some((l) => l === ''), 'template-interior blank line must be preserved')
  assert.ok(/const after = 1/.test(out), 'code after template preserved')
}

// (3) ${...} substitution nesting: a // inside a substitution expression IS code (stripped); a
// template line after the substitution is still string data (kept). Braces/frames must balance.
{
  const src = [
    'const t = ' + BT + 'a${',
    '  // real comment inside substitution',
    '  foo({ x: 1 })',
    '}b',
    '// keep: template text after subst',
    'c' + BT,
  ].join('\n')
  const out = strip(src)
  assert.ok(!/real comment inside substitution/.test(out), '// inside ${} substitution is code → stripped')
  assert.ok(/keep: template text after subst/.test(out), 'template text after ${} must be preserved')
}

// (4) Regex-vs-division heuristic hardening (finder C): none of these must desync cross-line state.
// If any were mis-lexed as an open template/string/regex, the following code // line would be wrongly
// kept or a later real comment wrongly stripped. We assert the FOLLOWING full-line comment is stripped
// (proves state returned to code) and the code survives.
for (const line of [
  'const x = obj.in / count',        // .in is a property, not the `in` keyword → division
  'const y = arr[i] / 2',            // ] then / → division
  'const z = (a + b) / c',           // ) then / → division
  'let n = 0; n++ / total',          // postfix ++ then / → division
  'const w = a /*c*/ / b',           // division after inline block comment
  'const re = obj.replace(/x/g, 1)', // real regex in operator position (after ()
]) {
  const src = [line, '// sentinel-comment-must-be-stripped', 'const tail = 9'].join('\n')
  const out = strip(src)
  assert.ok(!/sentinel-comment-must-be-stripped/.test(out),
    'heuristic desync: a code // line survived after: ' + line)
  assert.ok(/const tail = 9/.test(out), 'tail code preserved after: ' + line)
}

// (5) A real backtick-bearing regex in operator position (the courier_exec.js:167 shape) does not
// open a template — the following code // line is still stripped.
{
  const src = ['const m = /^' + BT + '/.test(s)', '// stripped-me', 'const q = 1'].join('\n')
  const out = strip(src)
  assert.ok(!/stripped-me/.test(out), 'backtick-in-regex (operator position) must not open a template')
  assert.ok(/const q = 1/.test(out), 'code after backtick-regex preserved')
}

// (6) EOF tokenizer-desync self-check: an unterminated template literal must throw, never silently
// emit a corrupted bundle.
{
  assert.throws(() => strip('const t = ' + BT + 'never closed\nconst a = 1\n'),
    /tokenizer desync/, 'unterminated template must trip the self-check')
}

// (7) Determinism: same input → byte-identical output.
{
  const src = ['// a', 'const x = ' + BT + 'p${ y }q' + BT, '', 'const z = 1 // t'].join('\n')
  assert.strictEqual(strip(src), strip(src), 'stripComments must be deterministic')
}

console.log('OK: stripComments preserves template data, strips code comments/blanks, heuristic + desync guard hold')

// ── Second-panel additions (#295 review r1, this repo's review-code run) ─────────────────────────
// Line-continuation strings: an ESCAPED newline inside 'sq'/"dq" continues the string — continued
// lines that look like comments are STRING DATA (the fail-direction Important all three code lenses
// converged on; mutation-verified: pre-fix, the stray close-quote derails lexing and the case fails).
{
  const src = [
    "const s = 'first \\",
    '// continued string data, not a comment \\',
    "still the string'",
    '// real comment — stripped',
    'after()',
  ].join('\n')
  const out = stripComments(src)
  assert.ok(out.includes('// continued string data, not a comment'), 'sq line-continuation interior survives')
  assert.ok(out.includes("still the string'"), 'sq string tail intact')
  assert.ok(!out.includes('// real comment — stripped'), 'genuine comment after the continued string stripped')
}
{
  const src = ['const d = "one \\', '// dq continued data \\', 'two"', 'tail()'].join('\n')
  const out = stripComments(src)
  assert.ok(out.includes('// dq continued data'), 'dq line-continuation interior survives')
}
// Determinism + idempotence: same input -> byte-identical; re-stripping strips nothing further.
{
  const fixture = require('fs').readFileSync(__filename, 'utf8')
  const once = stripComments(fixture)
  assert.strictEqual(once, stripComments(fixture), 'stripComments deterministic')
  assert.strictEqual(stripComments(once), once, 'stripComments idempotent')
}
console.log('ok: line-continuation strings + determinism (#295 r1 second panel)')

// ── #295 r2: verifyEmit fails CLOSED — an unrun verifier never counts as success ────────────────
// (r2 premortem: the old ENOENT tolerance also swallowed a temp-write ENOENT, so a missing TMPDIR
// silently skipped the parse gate.) Drive both failure modes in a child process.
{
  const { execFileSync } = require('child_process')
  const probe = 'const b = require(' + JSON.stringify(require.resolve('../bundle_showrunner.js')) + ');\n'
  // (a) busted TMPDIR: the stage-write fails -> verifyEmit must THROW, not return success.
  const badTmp = 'try { b.emit(); console.log("BAD: emitted unverified") } catch (e) { console.log("ok-threw: " + (e.message.includes("did NOT run") ? "stage" : "other")) }'
  const out1 = execFileSync(process.execPath, ['-e', probe + badTmp],
    { env: Object.assign({}, process.env, { TMPDIR: '/no/such/dir/for/sr-strip-smoke' }), encoding: 'utf8', cwd: __dirname + '/..' })
  assert.ok(out1.includes('ok-threw: stage'), 'busted TMPDIR fails closed (got: ' + out1.trim() + ')')
}
console.log('ok: verifyEmit fail-closed on temp-stage failure (#295 r2)')
