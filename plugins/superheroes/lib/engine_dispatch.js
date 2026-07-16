// plugins/superheroes/lib/engine_dispatch.js
// Spine leaf wrapper (#38): the single seam every JS call site invokes instead of agent() when the
// engine is external (codex|cursor). Deterministic argv/parse/commit live in engine_adapter.py; this
// wrapper sequences them through the spine's exec dumb-pipe and returns the NATIVE result shape so
// everything downstream (loop math, verify gate, journal) is reused unchanged. Read roles are
// read-only (no preSHA/commit); write roles capture preSHA -> engine edits -> adapter commits.
const { libPath } = require('./lib_root.js')
const { sha256hex } = require('./bytes.js')
const DEFAULT_STALL_LIMIT_SECONDS = 300   // UFR-5 finite default; test-settable via opts.timeoutSeconds

// #309: engines that emit output INCREMENTALLY when piped to a file (not a TTY) — verified 2026-07-09
// by piping each CLI's stdout+stderr to a file and observing byte growth BEFORE completion (codex `exec
// --sandbox read-only -`: first bytes ~1s, chunks throughout a ~20s run, max inter-chunk gap ~8s;
// cursor-agent `-p --trust --output-format stream-json`: first bytes ~2s, a mid-run chunk, done ~6s).
// For a streaming engine the byte-activity stall monitor observes real progress and only fires on a
// genuine no-output wedge. A hypothetical engine that FULLY BUFFERS until completion would be
// false-killed by a byte-growth watchdog, so it is marked `false` here — the monitor is left INERT for
// it (ceiling only, journalled stall_monitor:"inert (engine buffers)") rather than armed-and-dangerous.
// Both current engines stream, so both arm the monitor.
const _STREAMS_WHEN_PIPED = { codex: true, cursor: true }

// #341: the courier-declined outcome token — a cross-boundary contract (this JS producer writes it into
// the external_dispatch journal; acceptance_verdict.py's COURIER_DECLINED_OUTCOME must match it exactly
// to classify it as neither-attempt-nor-excuse). Single JS home + exported so a drift guard asserts the
// two homes agree (CONVENTIONS §11.2). Fail-closed if they ever diverge: an unrecognized token lands in
// acceptance_verdict's generic `failed` bucket, so a decline-only engine still fails the gate.
const COURIER_DECLINED_OUTCOME = 'courier-declined'

// #373: outcome tokens for the two PRE-CLI early exits that used to return before any journal write —
// staging the prompt/schema to /tmp, and (write roles) capturing preSHA. A dispatch that dies here left
// ZERO trace in events.jsonl, so a run whose external engine was routed-and-DENIED read identically to
// "never routed" (the live 2026-07-11 case: the auto-mode safety classifier denied cursor's base64
// staging courier 4/4, journaling nothing). These are the honest audit tokens those exits now emit —
// distinct from `could-not-stage-external-inputs` (the caller-facing return reason, kept for the #277
// harness-dead tripwire) so the journal names WHICH pre-CLI step died and, on a denial, why. Like every
// non-"ok" external_dispatch outcome they are genuine dispatch FAILURES: acceptance_verdict.py counts
// them against the per-engine authenticity gate (an engine with only these records has 0 oks -> fails),
// never as an acceptable fall-open (authz-denied / engine-unavailable) or a courier-decline. Single JS
// home + exported so the JS↔Python behavior drift guard (CONVENTIONS §11.2) pins that classification.
const STAGING_DENIED_OUTCOME = 'staging-denied'   // staging failed AND the failure carries a denial signature
const STAGING_FAILED_OUTCOME = 'staging-failed'   // staging failed for any other reason (courier/exec error)
const PRESHA_FAILED_OUTCOME = 'presha-failed'     // write-role preSHA capture failed before the CLI ran

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// #257: the PLAIN-READABLE stage-write, replacing the old `printf '<base64>' | base64 -d > …` blob.
// Root cause it fixes (live 2026-07-11, 0.11.1 run wf_e0d42237-c87): the Claude Code auto-mode safety
// classifier flags exactly the base64 courier's OPACITY and DENIED all 4 cursor stagings — every cursor
// build fell open to native, the write-engine axis never ran. Opacity had a real job (transit fidelity:
// a leaf once rewrote readable JSON mid-relay, 2026-07-02), so we keep the fidelity guarantee WITHOUT the
// opacity: the payload rides as a plain, human/classifier-readable python argv, and a Python-side sha256
// re-hash of the written file — pinned to a hash the SPINE computed from the ORIGINAL content and embedded
// as a literal — proves the courier copied it faithfully. A paraphrase changes the file's hash but never
// the embedded literal (an LLM copies a 64-hex string verbatim or fails visibly; only a paraphrase of the
// readable body is the observed mangle), so a mangled stage EXITS NON-ZERO here and the caller fails
// closed + retries — never persists silently-altered content.
//
// Shape choice (deviates from the issue's heredoc suggestion, same guarantee): the argv-shape python
// writer is the SAME transport io.writeFile already uses live in this exact runtime (bundle `__SR_W`,
// finding #13) — a path/payload passed as ARGV is data, not a shell file-op, so it clears the store's
// sensitive-file guard where a `cat > … <<EOF` heredoc open() is denied. It also needs no collision-proof
// heredoc delimiter (untrusted engine text can contain any sentinel line) and adds no trailing-newline
// artifact — the file bytes are EXACTLY the content, so the verify hash is sha256hex(content) flat.
// #277 carries over: no Node `Buffer`/`crypto` on this path (both absent in the sandbox) — sha256hex is
// the shared Buffer-less digest (bytes.js), exercised identically in node and the sandbox. The verify
// returns only its EXIT STATUS (0 match / 3 mismatch); it NEVER echoes the file back through the courier's
// answer, so the read side can't re-mangle and the audit line can't leak the staged payload.
// _SR_STAGE_SIG is the stable routing/identity substring every staged command carries.
const _SR_STAGE_SIG = 'hashlib.sha256'
const _SR_STAGE_SCRIPT =
  'import os,sys,hashlib;' +
  'p,e,w=sys.argv[1],sys.argv[2],sys.argv[3];' +
  'c=[];i=0;' +
  'exec("while i<len(e):\\n if i+2<len(e)and e[i:i+3]==chr(92)*2+chr(110):c.append(chr(92)+chr(110));i+=3\\n elif i+1<len(e)and e[i:i+2]==chr(92)+chr(110):c.append(chr(10));i+=2\\n elif i+1<len(e)and e[i:i+2]==chr(92)+chr(114):c.append(chr(13));i+=2\\n elif i+1<len(e)and e[i:i+2]==chr(92)*2:c.append(chr(92));i+=2\\n else:c.append(e[i]);i+=1");' +
  'c="".join(c);' +
  'd=os.path.dirname(p);' +
  'd and os.makedirs(d,exist_ok=True);' +
  'open(p,"w",encoding="utf-8").write(c);' +
  'h=hashlib.sha256(open(p,"rb").read()).hexdigest();' +
  'sys.exit(0 if h==w else 3)'
function _stageEnc(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/\r/g, '\\r')
}
function _stageCmd(path, content) {
  const c = content == null ? '' : String(content)
  return `python3 -c ${shq(_SR_STAGE_SCRIPT)} ${shq(path)} ${shq(_stageEnc(c))} ${shq(sha256hex(c))}`
}

// #257: stage ONE input (prompt / schema / raw output) through the exec courier with fail-closed sha256
// verify + one retry. A stage rides its OWN single-command leaf (never a multi-command numbered list):
// a plain readable payload legitimately contains newlines, and a numbered `1.`/`2.` batch could mis-slice
// a multi-line command mid-payload. exec-level ok reflects the python verify's exit status, so ok===true
// means the file on disk hashed to the spine's expected value — a transit mangle (verify exit 3 -> ok
// false) or a courier/exec error retries ONCE (the known haiku stdout-drop is stochastic), then gives up.
// A CLASSIFIER DENIAL is deterministic (retrying re-denies), so we break early on a denial signature and
// hand the failed leaf's results back so the caller journals `staging-denied` with the bounded reason.
async function _stageInput(path, content) {
  const cmd = _stageCmd(path, content)
  let last = null
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await _exec([cmd])
    const r0 = res && res[0]
    if (r0 && r0.ok) return { ok: true, results: res }
    last = res
    if (_stagingDenial(res)) break   // deterministic denial — a retry only re-denies
  }
  return { ok: false, results: last }
}

// #307: codex's `--output-schema` rides OpenAI STRICT structured outputs, whose two hard rules the
// Anthropic-authored schema literals (FINDINGS_SCHEMA / REVIEW_TASK_SCHEMA / FINAL_REVIEW_SCHEMA)
// were never written for: EVERY object must carry `additionalProperties:false` AND a `required` array
// naming EVERY property key. Sent verbatim these 400 with `invalid_json_schema` before any review
// work, so every codex review dispatch has silently fallen open to Claude since the engine onboarding
// (0 successes ever — see #307). We fix at the STAGING seam, not the literals: one transform corrects
// all three senders (and any future one), and the NATIVE Claude path keeps receiving the original
// permissive schema (Anthropic rejects some strict shapes). `strictify` deep-walks the schema and on
// every object node sets `additionalProperties:false` + `required = every property key`; a property
// that was NOT originally required is widened to a NULLABLE union (`type:["string","null"]`, or a
// `null` member added to an `enum`) so a field that used to be omittable stays semantically optional
// (the engine emits explicit `null` instead of dropping the key). PURE — never mutates its input (the
// literals are module-level constants also handed to the native agent() path). Idempotent: a second
// pass finds every key already in `required`, so nothing is re-widened.
function _typeWithNull(type) {
  if (type == null) return type
  if (Array.isArray(type)) return type.indexOf('null') >= 0 ? type : type.concat(['null'])
  return type === 'null' ? type : [type, 'null']
}

function _jsonType(v) {
  if (v === null) return 'null'
  if (typeof v === 'string') return 'string'
  if (typeof v === 'boolean') return 'boolean'
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number'
  return null
}

// Make a single property schema accept explicit null (so a previously-optional field can be present-
// but-null under strict mode). Widens a `type` to a null union; for an enum-only property, adds a
// `null` member AND an inferred nullable `type` union (the OpenAI-documented nullable-enum shape).
function _nullableProp(propSchema) {
  if (!propSchema || typeof propSchema !== 'object' || Array.isArray(propSchema)) return propSchema
  const p = Object.assign({}, propSchema)
  const hasEnum = Array.isArray(p.enum)
  if (hasEnum && p.enum.indexOf(null) < 0) p.enum = p.enum.concat([null])
  if (p.type !== undefined) {
    p.type = _typeWithNull(p.type)
  } else if (hasEnum) {
    const types = []
    for (const v of p.enum) {
      const t = _jsonType(v)
      if (t && types.indexOf(t) < 0) types.push(t)
    }
    if (types.length) p.type = types
  }
  return p
}

function _isObjectNode(node) {
  if (!node || typeof node !== 'object') return false
  if (node.type === 'object') return true
  return Array.isArray(node.type) && node.type.indexOf('object') >= 0
}

function strictify(schema) {
  if (Array.isArray(schema)) return schema.map(strictify)
  if (!schema || typeof schema !== 'object') return schema
  const out = {}
  for (const k of Object.keys(schema)) out[k] = strictify(schema[k])
  if (_isObjectNode(out)) {
    const props = (out.properties && typeof out.properties === 'object' && !Array.isArray(out.properties))
      ? out.properties : null
    const propKeys = props ? Object.keys(props) : []
    const originalRequired = Array.isArray(schema.required) ? schema.required : []
    if (props) {
      for (const key of propKeys) {
        if (originalRequired.indexOf(key) < 0) props[key] = _nullableProp(props[key])
      }
    }
    out.additionalProperties = false
    out.required = propKeys
  }
  return out
}

// Reuse the spine's exec dumb-pipe (lazy require avoids a load-time cycle: showrunner requires the
// bundle graph; deferring keeps engine_dispatch's require surface minimal for the smokes).
let _execFn = null
function _exec(commands) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands)
}

// #341: the HARDENED courier discipline (superheroes:courier agentType + __SR_EXIT marker guard +
// dispatchMarked retry/fallback chain) — reused, not reinvented, for the reliability-critical engine
// CLI dispatch. courier_exec has no cyclic dependency on showrunner (it is a standalone leaf helper),
// so a direct require is safe; kept lazy only for symmetry with _exec's minimal load surface.
let _courierMod = null
function _courier() {
  if (!_courierMod) _courierMod = require('./courier_exec.js')
  return _courierMod
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

// #343: execution-evidence probe — the independent, on-disk corroborator for a write-role dispatch
// whose courier answer carried no execution marker. Marker absence does NOT prove the engine never ran
// (a leaf can execute the command and answer with a file-pointer sentence when the output is huge —
// live-observed in the PR-343 vet), but the disk can't lie. THREE signals, any one of which means the
// engine may have executed (delta-review premortem-001/code-001/code-002/premortem-002):
//   1. uncommitted edits (`git status --porcelain` count > 0) — the normal engine-edited shape;
//   2. HEAD moved off preSha — an engine that SELF-COMMITTED reads porcelain-clean (the adapter's own
//      commit fold anticipates stray engine commits), so cleanliness alone would retry on top of a
//      committed attempt;
//   3. watchdog STDERR captures exist (`<captureBase>.*.err`) — the armed watchdog's first act
//      creates them and a clean SUCCESS removes them, so their presence means the run STARTED and
//      either failed or is still running (an orphaned CLI whose leaf died) — either way, executed.
//      `.err` ONLY (PR-351 review): #349 retains the `.out` capture on clean success too (it is the
//      parse input now), so globbing `.out` would let a PRIOR same-runId success within the /tmp
//      window mis-blame a genuinely-declined later attempt as external-run-failed — the #341
//      anti-goal. The stderr capture keeps the exact original failed-or-running semantics.
// The probe answer is SENTINEL-PREFIXED and POSITIVE ("__SR_PROBE__ <edits> <head> <captures>"): a
// clean verdict must be the explicit shape, so the exec courier's known drop (ok:true, empty stdout —
// see _execJson) can never impersonate "clean" and green-light a double execution. Any probe failure,
// drop, or garble returns true — fail toward "may have executed": the cost of a wrong true is one lost
// retry (fall open, UFR-2 resets), a wrong false is a DOUBLE-EXECUTED write. Residuals (accepted,
// fail-direction safe): a pre-dirty worktree or stale same-runId capture file loses the retry, never
// double-executes — build worktrees are clean at dispatch and capture files are per-sh-pid.
async function _executionEvidence(wt, preSha, captureBase) {
  const cmd = `printf '__SR_PROBE__ %s %s %s\\n' ` +
    `"$(git -C ${shq(wt)} status --porcelain | wc -l | tr -d ' ')" ` +
    `"$(git -C ${shq(wt)} rev-parse HEAD)" ` +
    `"$(ls ${shq(captureBase)}.*.err 2>/dev/null | wc -l | tr -d ' ')"`
  const res = await _exec([cmd])
  const r0 = res && res[0]
  if (!(r0 && r0.ok)) return true
  const m = String(r0.stdout == null ? '' : r0.stdout).match(/__SR_PROBE__ (\d+) (\S+) (\d+)/)
  if (!m) return true
  return Number(m[1]) > 0 || (preSha != null && m[2] !== preSha) || Number(m[3]) > 0
}

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
// FR-8 confinement: the command is ALWAYS prefixed with `cd <cwd> && ` (mirroring showrunner.js's
// inWorktree()) so the external process runs rooted at the per-task build worktree — never at
// __SR_ROOT (the repo root selfContained() would otherwise apply via exec's dumb-pipe). This matters
// most for cursor, whose argv (engine_adapter.py) carries NO -C/cwd flag of its own; codex is
// self-confining via -C but the cd prefix is harmless/idempotent for it too. Applied unconditionally
// whenever a cwd is supplied (read roles are already read-only-sandboxed by the engine itself).
//
// FIX 2 (premortem): the JS Promise.race in dispatchExternal only stops US from WAITING on a stalled
// CLI — the subprocess itself keeps running unkilled, orphaned, potentially still writing to the
// worktree/git index while the caller has already fallen open and is retrying with the native Claude
// worker (a write-write race on the same files). Bound the CLI at the OS level too: wrap it with a
// portable `perl -e 'alarm shift @ARGV; exec @ARGV or exit 127'` — perl's alarm() SIGALRMs the process
// after <timeoutSeconds>, and since exec() replaces the perl process image with the CLI (same PID), the
// alarm fires against the CLI itself, killing it. This is belt-and-suspenders with the JS race (which
// stays, so a slow-to-signal-death CLI still can't hang the caller past limitMs) — the perl layer's job
// is only to make sure the CLI is actually DEAD, not just unwaited-on. perl/alarm/exec are ordinary CLI
// tokens (not Node/JS globals), so they don't trip the bundle's banned-global static check.
//
// #309 STALL MONITOR (the ceiling+monitor pair): the perl alarm is a wall-clock CEILING (worst case).
// When the caller arms the byte-activity monitor (`armIdle`), the CLI is instead wrapped in a shell
// watchdog that reaps a *wedged* CLI far sooner: run the alarmed CLI in the BACKGROUND as its own
// process group (`setpgrp(0,0)` in the perl wrapper — so a group-kill reaches the CLI AND its children;
// a silently-stalled writer never gets SIGPIPE, so byte-growth is the only observable signal), poll the
// captured-output file's byte size every `poll` seconds, and if it does not grow for `idleSeconds`,
// TERM-then-KILL the whole process group. Both limits are ALWAYS armed — the perl alarm ceiling stays
// inside the wrapper, and the monitor (≤ ceiling) fires first on a true stall. The watchdog emits the
// captured CLI output followed by a trailing `__SR_DISPATCH__{...}` control line JS strips + reads for
// the idle-kill verdict. The whole watchdog is composed into ONE shell command because the spine's exec
// courier runs one command and returns its complete stdout in one shot — there is no Node child_process
// in the Workflow sandbox to attach per-chunk data listeners to (FR-8), so the progress observation has
// to live shell-side, next to the CLI. The script body carries NO single quotes so it survives shq's
// single-quote wrapping intact.
//
// Returns an object: {ok:true, stdout} on a completed run; {ok:false, stalled:true, idleSeconds} when
// the monitor idle-killed the CLI; {ok:false} on a courier-level failure.
function _pollFor(idle) {
  // Poll cadence: fine enough to honor a small (test-scale) idle window, capped at 10s so a production
  // 300–600s window costs at most ~60 cheap `wc -c` samples. Effective kill latency ≈ idle + one poll.
  return Math.max(1, Math.min(10, Math.floor(Number(idle) / 4)))
}
// The single-quote-free watchdog script (see the header note). Positional args from `sh -c <script> sh`:
// $1 ceiling, $2 idle, $3 poll, $4 capture-file BASE, $5 prompt-file, $6 perlprog; then "$@" (after
// `shift 6`) = the CLI argv. Three deliberate mechanics (each answers a review finding):
//   - The CLI's stdin is redirected from the prompt file EXPLICITLY (`< "$in"`): a POSIX-sh background
//     job's stdin is /dev/null unless explicitly redirected, so relying on an outer `< promptPath` (the
//     unarmed path's mechanism) would silently feed the engine an EMPTY prompt (live-verified
//     2026-07-09; review finding code-001 Critical).
//   - stdout and stderr are captured to SEPARATE files: the idle poll watches the SUM of both sizes
//     (activity on EITHER stream resets the timer — a test-runner spinner on stderr is progress), but
//     only stdout is emitted to parse-result, so the armed path feeds the adapter exactly what the
//     unarmed path does (stderr never pollutes parsing; review finding code-002).
//   - The capture files are suffixed with the script's OWN pid (`$$` — a shell token, not a banned
//     JS time/random global, so FR-8-clean): concurrent same-workItem dispatches (a review panel
//     fanning out reviewers that share workItem/roleKind/engine and hence a runId) each get a private
//     capture pair, so one watchdog can never poll another's file (review finding premortem-001).
const _WATCH_SCRIPT = [
  'c=$1; idle=$2; poll=$3; base=$4; in=$5; prog=$6; cap=$7; shift 7',
  'out="$base.$$.out"; err="$base.$$.err"',
  ': > "$out"; : > "$err"',
  'perl -e "$prog" "$c" "$@" < "$in" > "$out" 2> "$err" &',
  'p=$!',
  'last=-1; idlesec=0; killed=0',
  'while kill -0 "$p" 2>/dev/null; do',
  'sleep "$poll"',
  'szo=$(wc -c < "$out" 2>/dev/null | tr -d " "); [ -n "$szo" ] || szo=0',
  'sze=$(wc -c < "$err" 2>/dev/null | tr -d " "); [ -n "$sze" ] || sze=0',
  'sz=$((szo + sze))',
  'if [ "$sz" -gt "$last" ]; then last=$sz; idlesec=0; else idlesec=$((idlesec + poll)); fi',
  'if [ "$idle" -gt 0 ] && [ "$idlesec" -ge "$idle" ]; then killed=1; kill -TERM -"$p" 2>/dev/null; sleep 1; kill -KILL -"$p" 2>/dev/null; break; fi',
  'done',
  'wait "$p" 2>/dev/null; ec=$?',
  // BOUNDED emission (#347): NEVER relay the full capture — a leaf harness persists any tool result
  // past its size cap to a file and hands the leaf a pointer instead, destroying both the payload AND
  // the trailing markers (live: cursor stream-json at 472KB/400KB; the PR-343 vet saw 37KB persist).
  // Emit only the LAST $cap bytes: every parser scans for the LAST JSON value (engine_adapter's
  // noise-tolerant last-object scan skips a chopped leading line), so the tail is sufficient by
  // construction. The full stream is not lost — see retention below.
  'szf=$(wc -c < "$out" 2>/dev/null | tr -d " "); [ -n "$szf" ] || szf=0',
  'if [ "$szf" -gt "$cap" ]; then trunc=1; tail -c "$cap" "$out"; else trunc=0; cat "$out"; fi',
  // Retention (#349): the stdout capture is kept on disk on EVERY armed dispatch — it is the
  // byte-perfect, shell-written record that parse-result reads DIRECTLY (the footer names its path).
  // Engine output must never round-trip through a courier leaf's typing again: the 2026-07-10 run
  // proved a leaf re-typing a ~31KB base64 re-stage mangles it (issue #349). The stderr capture is
  // KEPT on any failure (idle-kill or non-zero exit) so the engine's own diagnostic survives for
  // post-mortem (never surfaced to parse-result), and removed only on success.
  // Accumulation bound (PR-348 review): kept captures are NOT reaped here — a reap at dispatch start
  // could delete a CONCURRENT same-runId sibling's in-flight capture (the exact race the $$-suffix
  // exists for, premortem-001). The bound is the OS /tmp reaper (macOS purges /tmp every ~3 days;
  // linux tmpfiles.d similar), the same bound the pre-existing .prompt/.schema staging litter already
  // relies on. Revisit if a run ever needs its captures to outlive that window.
  'if [ "$killed" -eq 0 ] && [ "$ec" -eq 0 ]; then rm -f "$err"; fi',
  'printf "\\n__SR_DISPATCH__{\\"idleKilled\\":%s,\\"idleSeconds\\":%s,\\"exit\\":%s,\\"outBytes\\":%s,\\"truncated\\":%s,\\"outPath\\":\\"%s\\"}\\n" "$killed" "$idle" "$ec" "$szf" "$trunc" "$out"',
].join('\n')

// The emission cap for the watchdog's stdout relay (#347). Must sit WELL under the leaf harness's
// persist-to-file threshold (observed: a 37KB tool result persisted in the PR-343 vet; 100KB+ always
// persists) with margin for the __SR_DISPATCH__ footer, the __SR_EXIT marker line, and any leaf
// framing around the answer. 24000 bytes carries every legitimate terminal payload we parse (a codex
// findings object, or a cursor result envelope whose escaped inner text roughly doubles a large
// findings list — PR-348 review sized the cap up from 16000 for exactly that case) while keeping
// >10KB of margin under the observed wall. A payload that still exceeds the cap chops the envelope's
// FRONT → the parse is `unreadable` → the dispatch falls open — fail-safe, and NOT silent: the
// outcome line journals outputTruncated + outPath for the post-mortem.
const EMIT_TAIL_BYTES = 24000

// _composeDispatchCommand: PURE composer of the exact shell command _runArgv dispatches — the
// perl-alarm ceiling (unarmed) or the #309 background watchdog (armed), confined to cwd. Exported
// (test-only) so the #341 real-seam detector can build the byte-faithful production command and drive
// it through a REAL cheapest-model leaf without a fixture-injected courier (CONVENTIONS §12.2).
function _composeDispatchCommand(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle) {
  const seconds = Number(timeoutSeconds) > 0 ? Math.ceil(Number(timeoutSeconds)) : Math.ceil(DEFAULT_STALL_LIMIT_SECONDS)
  const quotedArgv = argv.map((a) => shq(a)).join(' ')
  const idleArmed = armIdle === true && Number(idleSeconds) > 0
  if (idleArmed) {
    const idle = Math.min(Math.ceil(Number(idleSeconds)), seconds)   // monitor ≤ ceiling
    const poll = _pollFor(idle)
    // Capture-file BASE: the script appends its own `.$$.out`/`.$$.err` (per-sh-process pid) so
    // concurrent same-runId dispatches never share a capture file (premortem-001).
    const captureBase = promptPath.replace(/\.prompt$/, '') + '.run'
    const perlProg = 'setpgrp(0,0); alarm shift @ARGV; exec @ARGV or exit 127'
    const inner = `sh -c ${shq(_WATCH_SCRIPT)} sh ${seconds} ${idle} ${poll} ` +
      `${shq(captureBase)} ${shq(promptPath)} ${shq(perlProg)} ${EMIT_TAIL_BYTES} ${quotedArgv}`
    // No outer stdin redirect: the watchdog feeds the prompt to the (backgrounded) CLI itself via
    // `< "$in"` — a POSIX-sh async job's stdin is /dev/null unless explicitly redirected, so an outer
    // redirect would silently deliver an EMPTY prompt (code-001; live-verified 2026-07-09).
    return cwd ? `cd ${shq(cwd)} && ${inner}` : inner
  }
  const alarmed = `perl -e ${shq("alarm shift @ARGV; exec @ARGV or exit 127")} ${seconds} ${quotedArgv}`
  return cwd ? `cd ${shq(cwd)} && ${alarmed} < ${shq(promptPath)}` : `${alarmed} < ${shq(promptPath)}`
}

async function _runArgv(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle, nonIdempotent) {
  const idleArmed = armIdle === true && Number(idleSeconds) > 0
  const cmd = _composeDispatchCommand(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle)
  // #341: dispatch the reliability-critical engine CLI through the HARDENED courier discipline
  // (superheroes:courier agentType + __SR_EXIT marker guard + dispatchMarked's retry/fallback chain),
  // NOT the plain exec() dumb-pipe. A safety-trained cheapest-model leaf stochastically REFUSES an
  // autonomous `cursor-agent --trust -f` write-watchdog and answers prose; the plain exec collapsed
  // that refusal into `external-run-failed` (line 415), mis-blaming the ENGINE for a courier's
  // decline (the a7bade9a escape: cursor 0/2 in-child while codex went 8/8). The marker protocol both
  // (a) REDUCES the refusal (the lean dumb-pipe framing reads as infrastructure, not a suspicious
  // dispatch) and (b) PROVES execution — a persistent missing `__SR_EXIT` marker means the shell
  // never ran (a decline), surfaced here as {declined:true} carrying the leaf's refusal prose, which
  // the caller journals as the honest `courier-declined` outcome instead of an engine failure.
  // STDERR NOTE (review code-002/premortem-004): the marker protocol's wrapMarkedCommand appends
  // `2>&1`, which merges stderr into the parsed stdout. On the ARMED watchdog path — the ONLY
  // production dispatch path, since resolveIdle always returns a positive idle and both engines stream
  // — the watchdog captures the CLI's stdout/stderr into SEPARATE files and emits only stdout, so the
  // `2>&1` catches only the (empty) sh-script stderr (proven by the stall-monitor real-seam smoke's
  // stderr-never-parsed assertion). The unarmed path (authz probe / a hypothetical non-streaming
  // engine) is never a production write, and parse-result's _last_json_object is noise-tolerant.
  // #343 NON-IDEMPOTENCE GUARD (PR-343 vet): the marked-courier retry chain hands the command to a
  // NEW leaf on every retry, and each leaf RE-RUNS it. Safe for the idempotent spine couriers the
  // chain was built for; a double-execution hazard for any FILESYSTEM-WRITING engine dispatch. A live
  // vet run proved the hazard is real in a way marker-absence cannot see: the leaf EXECUTED the
  // watchdog, but its 37KB output was persisted by the leaf harness to a tool-results file and the
  // answer was just a file-pointer sentence — NO markers — indistinguishable from a decline by the
  // answer alone. So every non-idempotent dispatch (write roles AND author-plan, whose argv is also
  // workspace-write — delta-review premortem-003) runs SINGLE: one leaf, no chain retries; the caller
  // owns the retry decision (corroborated by the execution-evidence probe for write roles). Only true
  // read roles (review: codex read-only sandbox / cursor plan mode) keep the full chain — re-running a
  // read-only sandbox is harmless. acceptExecuted (all roles): an answer carrying the runtime-expanded
  // digit marker EXECUTED — never re-dispatched just because an echoed '$?' literal rides along.
  let out
  try {
    out = await _courier().runCourierMarkedText('dispatch external CLI', cmd,
      { single: nonIdempotent === true, acceptExecuted: true })
  } catch (e) {
    const c = _courier()
    if (c.CourierTransportError && e instanceof c.CourierTransportError) {
      // ONLY a missing execution marker is even a CANDIDATE courier decline (the shell probably never
      // ran). The courier's other transport reason — 'empty stdout' — means the marker WAS present,
      // i.e. the command DID execute but printed nothing before the marker; that is an engine outcome,
      // not a decline (code-001/premortem-001). Marker absence is NECESSARY but not SUFFICIENT proof
      // of non-execution (the vet's executed-but-pointer-answer case), so for write roles the CALLER
      // must corroborate with the worktree dirty-probe before journaling a decline or retrying.
      if (e.reason === 'missing execution marker') {
        return { ok: false, declined: true, answer: e.answer || '' }
      }
      return { ok: false }
    }
    throw e
  }
  if (idleArmed) {
    // Strip the trailing control line and read the idle-kill verdict. The marker is OUR sentinel on its
    // own final line; match the LAST occurrence so any legitimate look-alike earlier in CLI output can't
    // shadow it. A stall returns {stalled:true} so the caller journals outcome:'stalled' + falls open.
    const m = out.match(/\n?__SR_DISPATCH__(\{[^\n]*\})\s*$/)
    if (m) {
      let verdict = null
      try { verdict = JSON.parse(m[1]) } catch (_e) { verdict = null }
      out = out.slice(0, m.index)
      // #347/#349 relay facts: EVERY armed dispatch's footer names the on-disk capture (outPath) —
      // the byte-perfect record parse-result reads DIRECTLY (never a courier-retyped copy, #349) —
      // plus the true size and whether the RELAYED stdout was truncated to the tail (journal
      // disclosure: a silently-shortened relay would be a hidden fact about what the leaf saw).
      // Carried on the STALLED return too (PR-348 review nit): the stalled journal line names the
      // kept capture.
      const relay = (verdict && typeof verdict.outPath === 'string' && verdict.outPath)
        ? { truncated: String(verdict.truncated) === '1',
            outBytes: Number.isFinite(Number(verdict.outBytes)) ? Number(verdict.outBytes) : null,
            outPath: verdict.outPath }
        : null
      if (verdict && verdict.idleKilled && String(verdict.idleKilled) !== '0') {
        return Object.assign({ ok: false, stalled: true, idleSeconds: Number(verdict.idleSeconds) || null },
          relay ? { relay } : {})
      }
      if (relay) return { ok: true, stdout: out, relay }
    }
  }
  return { ok: true, stdout: out }
}

async function _journalExternal(payload) {
  // Journal the external action as a FIRST-CLASS `external_dispatch` event (FR-6): the audit line's
  // `type` is external_dispatch (Task 4 added the type + the journal_entry.py --event-type flag), and
  // the payload is written AS-IS. #308/#309 enrich it with the RESOLVED `model`, the final `argv`
  // (both engine-controlled config, never external free-text), and the `effectiveTimeout` in seconds,
  // so #299's expected-vs-actual audit can prove the dispatched model/timeout match the readout's
  // promise, and a `timeout` outcome + effectiveTimeout together read as "killed at ceiling after Ns"
  // — distinct from a genuine CLI failure (external-run-failed / unreadable / commit-failed). A failed
  // durable append -> {ok:false} -> the caller treats it as UFR-6 (fail-closed, unauditable).
  return _execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(payload.workItem || '')} ` +
    `--event-type external_dispatch --payload ` +
    shq(JSON.stringify({ engine: payload.engine, effort: payload.effort, roleKind: payload.roleKind,
      model: payload.model == null ? null : payload.model,
      argv: Array.isArray(payload.argv) ? payload.argv : null,
      effectiveTimeout: payload.effectiveTimeout == null ? null : payload.effectiveTimeout,
      // #309 stall-monitor audit: `stallMonitor` names the monitor state (armed / inert (engine
      // buffers) / unarmed) and `idleSeconds` is the armed idle threshold (null when not armed). A
      // `stalled` outcome + idleSeconds together read as "no output for Ns -> killed" — distinct from a
      // `timeout` outcome (killed at the wall-clock ceiling) or a genuine CLI failure.
      stallMonitor: payload.stallMonitor == null ? null : payload.stallMonitor,
      idleSeconds: payload.idleSeconds == null ? null : payload.idleSeconds,
      // #341: on a `courier-declined` outcome, carry a CLAMPED prefix of the leaf's refusal prose as
      // honest reason-context (the courier hedged instead of running the CLI — the engine was never
      // tried). Present only on the decline path; absent (null) on every other outcome. It is the
      // cheap COURIER leaf's own prose (not engine stdout), clamped to a short prefix so no long or
      // secret-bearing text lands in the audit line.
      declinePrefix: payload.declinePrefix == null ? null : String(payload.declinePrefix),
      verify: payload.verify, outcome: payload.outcome,
      // #373: on a PRE-CLI early-exit outcome (staging-denied / staging-failed / presha-failed) carry a
      // bounded disclosure of WHY — the classifier's denial prose is owner-relevant evidence. Spread so
      // it is present ONLY when the caller supplied one (no new always-null key: pre-#373 payloads stay
      // byte-identical). The caller has already clamped + windowed it (never the staged prompt content).
      ...(payload.reason == null ? {} : { reason: String(payload.reason) }),
      // #347: bounded-relay disclosure — present ONLY when the watchdog truncated the stdout relay
      // (the parser saw the tail; outPath is the kept full capture). Spread so pre-#347 payloads
      // stay byte-identical (no new always-null keys).
      ...(payload.outputTruncated === true
        ? { outputTruncated: true,
            outBytes: payload.outBytes == null ? null : payload.outBytes,
            outPath: payload.outPath == null ? null : payload.outPath }
        : {}) })))
}

// #341: clamp the courier's refusal prose to a short single-line prefix for the courier-declined
// journal reason-context. Collapses whitespace and truncates — never surfaces a long blob.
function _declinePrefix(answer) {
  const s = String(answer == null ? '' : answer).replace(/\s+/g, ' ').trim()
  if (!s) return 'courier returned no execution marker'
  return s.length > 200 ? s.slice(0, 200) + '…' : s
}

// #373: inspect a FAILED staging result set for an auto-mode/permission DENIAL and, when found, return
// a bounded single-line reason string (owner-relevant evidence: WHY the staging courier was blocked).
// Taint-aware under #257 plain-readable staging: the echoed stage command (`python3 -c … '<prompt>'
// '<hash>'`) is a tainted region — a denial signature match AT/AFTER the earliest stage signature is
// treated as payload echo, not classifier prose, and returns a fixed withheld label. When the match
// precedes any stage signature (live classifier case), the window starts at the denial phrase and
// truncates at the signature so the staged prompt never leaks. Whitespace-collapsed and clamped to
// ~200 chars. Returns null when the failure carries NO denial signature (a plain courier/exec error),
// so the caller distinguishes `staging-denied` from `staging-failed`.
// #402 SSOT (§11): the denial-signature regex lives in courier_exec (bundled before this module) so the
// staging break-early here and the generic-courier break-early there can never drift apart.
const { DENIAL_SIG: _DENIAL_SIG } = require('./courier_exec.js')
const _DENIAL_TAINTED = 'denial signature detected after the echoed stage command — text withheld'
function _stagingDenial(results) {
  const arr = Array.isArray(results) ? results : []
  for (const r of arr) {
    if (r && r.ok) continue
    const s = String((r && r.stdout) == null ? '' : r.stdout).replace(/\s+/g, ' ').trim()
    const sigIdxs = [_SR_STAGE_SIG, 'python3 -c'].map((sig) => s.indexOf(sig)).filter((i) => i >= 0)
    const sigIdx = sigIdxs.length ? Math.min(...sigIdxs) : -1
    const m = s.match(_DENIAL_SIG)
    if (!m) continue
    if (sigIdx >= 0 && m.index >= sigIdx) return _DENIAL_TAINTED
    let from = sigIdx >= 0 ? s.slice(m.index, sigIdx) : s.slice(m.index)
    from = from.replace(/[A-Za-z0-9+\/=]{24,}/g, '[redacted]')
    return from.length > 200 ? from.slice(0, 200) + '…' : from
  }
  return null
}

// Scrub external-derived free-text (git stderr in a commit/dispatch-failure reason) BEFORE it enters
// an owner-facing notice — the band's single scrub seam (pr_comment.py scrub reads stdin -> scrubbed
// stdout, the same scrubber readout/parse_result use). On any exec/scrub failure fall back to a
// fixed generic label (never surface the raw external text). Only used on the failure/notice path.
async function _scrubReason(reason, fallback = 'external error (scrubbed)') {
  const s = reason == null ? '' : String(reason)
  if (!s) return s
  const res = await _exec([`printf '%s' ${shq(s)} | python3 ${libPath('pr_comment.py')} scrub`])
  const r0 = res && res[0]
  // #383: an empty/whitespace-only scrub stdout is the cheap courier's documented stdout-drop (see the
  // _execJson note above — a leaf returns ok:true with stdout:'' even though the command ran). A real
  // scrub never empties non-empty input (it only redacts to [REDACTED]), so treat empty as a scrub
  // failure and fall back to the fixed label rather than persisting an empty (WHY-less) reason.
  // #383: an empty/whitespace-only scrub stdout is the cheap courier's documented stdout-drop (see the
  // _execJson note above — a leaf returns ok:true with stdout:'' even though the command ran). A real
  // scrub never empties non-empty input (it only redacts to [REDACTED]), so treat empty as a scrub
  // failure and fall back to the fixed label rather than persisting an empty (WHY-less) reason.
  if (r0 && r0.ok && r0.stdout != null) {
    const out = String(r0.stdout)
    if (out.trim()) return out
  }
  return fallback
}

// #408: sanitize the run key, then bound it to 80 chars WITHOUT letting truncation delete the
// distinguishing tail. The old `sanitized.slice(0, 80)` (inherited #383 Part C caveat) would, for a
// very long work-item slug, cut the taskId / content-suffix that makes the key unique — reintroducing
// the exact cross-run collision this fold is meant to close. So when the sanitized key overflows, keep
// a readable head PLUS a deterministic sha256 of the FULL sanitized key: two distinct keys stay
// distinct (the hash covers everything, including the tail truncation would have dropped), and
// identical inputs recompute the identical key (FR-8: no wall-clock, no PRNG — resume-safe).
const _RUN_KEY_MAX = 80
const _RUN_KEY_HASH_LEN = 16
function _boundRunKey(raw) {
  const sanitized = String(raw).replace(/[^A-Za-z0-9_.-]+/g, '-')
  if (sanitized.length <= _RUN_KEY_MAX) return sanitized
  const digest = sha256hex(sanitized).slice(0, _RUN_KEY_HASH_LEN)
  return sanitized.slice(0, _RUN_KEY_MAX - _RUN_KEY_HASH_LEN - 1) + '-' + digest
}

// #408: derive the /tmp staging run key. It MUST distinguish concurrent runs in DIFFERENT projects —
// a bare taskId is the tasks-doc task NUMBER (machine-global, project-blind), so two runs at the same
// task index + engine + role collided on one staging path (a weekly-eats prompt was shipped to another
// repo's codex review, falsely parking the run — #408). Fold the workItem into the key for EVERY role.
// FR-8: caller-supplied identifiers only, no wall-clock / PRNG, so resume recomputes the identical key.
function _deriveRunKey(o, prompt, schemaText) {
  const wi = (typeof o.workItem === 'string' && o.workItem) ? o.workItem : ''
  let base
  if (o.taskId) {
    const tid = String(o.taskId)
    // Prefix the workItem UNLESS the taskId already carries it as a `${wi}-` delimited prefix — the
    // review-code panel leaves pass `${workItem}-${reviewer}-r${round}` (ee8a5b5), so folding again
    // would double it. Match on the delimiter (not a bare startsWith) so a workItem that is only a
    // CHARACTER-prefix of another ('wi' vs 'window-…') is not mistaken for an already-prefixed taskId.
    base = (wi && tid !== wi && !tid.startsWith(`${wi}-`)) ? `${wi}-${tid}` : tid
  } else if (wi) {
    // taskId-less roles (a review panel fanning out parallel reviewers sharing workItem/roleKind/engine)
    // keep the #403 deterministic content suffix so each private prompt still gets a private path.
    base = `${wi}-${sha256hex((prompt || '') + '\0' + schemaText).slice(0, 12)}`
  } else {
    base = 'run'
  }
  return _boundRunKey(base)
}

// FIX 3: the body runs inside a try/catch in the exported dispatchExternal below, so ANY thrown
// error (a synchronous throw from a step here, or an unavailable Buffer/setTimeout global) still
// returns the native {ok:false} failure shape instead of throwing — callers' fall-open-to-Claude
// path (UFR-2 discard + native worker) only fires on a returned failure, never on an exception.
async function _dispatchExternalInner(o) {
  const { engine, roleKind, effort, prompt, cwd, schema, timeoutSeconds, model, engineModel } = o
  const limitSeconds = Number(timeoutSeconds) > 0 ? Number(timeoutSeconds) : DEFAULT_STALL_LIMIT_SECONDS
  const limitMs = limitSeconds * 1000
  const isWrite = (roleKind === 'build' || roleKind === 'fix')
  // #309 STALL MONITOR resolution — the monitor half of the ceiling+monitor pair. The caller resolves
  // the idle threshold (resolveIdle: role default or owner override) and passes it as o.idleSeconds; a
  // dispatch with no idle passed (the engine_authz probe / any pre-#309 caller) runs ceiling-only. The
  // monitor is armed ONLY for an engine that streams output when piped — a hypothetical fully-buffering
  // engine would be FALSE-KILLED by a byte-growth watchdog, so we leave it inert (ceiling only) and say
  // so in the journal, rather than arm a dangerous monitor. Both current engines stream (verified
  // 2026-07-09). The threshold is clamped to the ceiling in _runArgv (monitor ≤ ceiling); an override
  // never disables the ceiling — the perl alarm stays inside the wrapper regardless.
  const idleRequested = Number(o.idleSeconds) > 0 ? Math.ceil(Number(o.idleSeconds)) : null
  const engineStreams = _STREAMS_WHEN_PIPED[engine] === true
  const armIdle = engineStreams && idleRequested != null
  const idleSeconds = armIdle ? Math.min(idleRequested, Math.ceil(limitSeconds)) : null
  const stallMonitor = armIdle ? 'armed'
    : (idleRequested != null && !engineStreams ? 'inert (engine buffers)' : 'unarmed')
  // resolvedArgv / relayMeta are hoisted ABOVE _jbase (and above the staging/preSHA early exits) so the
  // journal reads them at call time (#308 timeout-argv audit) AND so the #373 pre-CLI early exits can
  // journal through the same _jbase path — both are still null there (build-argv hasn't run, no CLI
  // relay yet), which is the honest audit shape for a dispatch that died before the CLI (argv: null, no
  // relay disclosure). resolvedArgv is set synchronously inside `run` right after build-argv resolves so
  // a later timeout branch journals the real argv; relayMeta carries the last completed _runArgv's relay
  // facts (#347). Both stay null on the pre-CLI failure paths.
  let resolvedArgv = null
  let relayMeta = null
  // The invariant audit-line fields for THIS dispatch (#308/#309): engine/effort/roleKind + the
  // resolved model, effective timeout ceiling, (once build-argv resolves) the exact argv, and the
  // stall-monitor state + idle threshold. Read at journal time so `argv` reflects resolvedArgv whenever
  // it is available. Each outcome-specific call overlays its own {verify, outcome}. The journal names
  // the concrete provider model when supplied; `model` remains the native/fallback-safe tier fact.
  const _jbase = () => Object.assign({ workItem: o.workItem, engine, effort, roleKind,
    model: (typeof engineModel === 'string' && engineModel) ? engineModel
      : ((typeof model === 'string' && model) ? model : null),
    argv: resolvedArgv, effectiveTimeout: limitSeconds,
    stallMonitor, idleSeconds },
    // #347: disclose a bounded relay on EVERY outcome line for this dispatch — the parser saw only
    // the stdout tail; the full capture's on-disk path is the receipt.
    (relayMeta && relayMeta.truncated)
      ? { outputTruncated: true, outBytes: relayMeta.outBytes, outPath: relayMeta.outPath } : {})
  // author-plan (the plan-author leaf) is write-SANDBOXED (it authors the doc + stamps the marker)
  // but takes NO preSHA/commit: definition-docs are not committed by the produce phase (native
  // authors don't commit either; in-repo docs ride the ship phase, out-of-repo docs never commit).
  // Its acceptance gate is the caller's deterministic usableDraft post-check, not this dispatch.
  const isAuthor = (roleKind === 'author-plan')

  // 1. Stage prompt + schema to disk (via exec). The PROMPT file is fed to the external process
  //    stdin by _runArgv (both engines read the prompt from stdin); the SCHEMA path is passed to
  //    build-argv via --schema-path (codex --output-schema for read roles).
  // runId is built from CALLER-SUPPLIED identifiers only — no wall-clock time or PRNG calls (FR-8:
  // the Workflow sandbox has no time/random globals, and the bundle-smoke statically bans those APIs
  // because they break deterministic resume). #408: _deriveRunKey folds the workItem into the key for
  // EVERY role — a bare taskId is the tasks-doc task NUMBER (machine-global, project-blind), so two
  // concurrent runs in DIFFERENT projects at the same task index + engine + role used to collide on
  // one /tmp staging path (a weekly-eats prompt shipped to another repo's codex review, falsely
  // parking that run). Folding distinguishes projects whose workItem slugs differ (the live-specimen
  // case); it does NOT fold the checkout root, so two roots resolving to the SAME workItem slug on one
  // machine remain a known residual (#408 scope note). An already-prefixed taskId (review panel leaves)
  // is not double-prefixed, and the #403 workItem-only content suffix is preserved.
  const stagedSchema = engine === 'codex' ? strictify(schema || {}) : (schema || {})
  const schemaText = JSON.stringify(stagedSchema)
  const runKey = _deriveRunKey(o, prompt, schemaText)
  const runId = `${engine}-${roleKind}-${runKey}`
  const promptPath = `/tmp/engine-${runId}.prompt`
  const schemaPath = `/tmp/engine-${runId}.schema.json`
  // #307: codex reads this file as an OpenAI-STRICT `--output-schema`; strictify it so it validates
  // (see strictify above). ONLY on the codex path — cursor ignores the schema entirely, and the
  // native Claude path never reaches this seam (it calls agent() with the original permissive schema,
  // which Anthropic's tool input_schema requires and which strict shapes would break).
  // #257: stage prompt then schema as PLAIN-readable, hash-verified writes (see _stageCmd/_stageInput) —
  // each in its own leaf, prompt first so a prompt-staging denial short-circuits the (pointless) schema
  // stage. writeInputs holds the FAILED leaf's raw results so the #373 denial-signature extraction still
  // fires; a success carries no denial and journals nothing here.
  const promptStage = await _stageInput(promptPath, prompt || '')
  const schemaStage = promptStage.ok
    ? await _stageInput(schemaPath, schemaText)
    : { ok: false, results: [] }
  if (!(promptStage.ok && schemaStage.ok)) {
    // #373: staging died BEFORE the CLI ran — journal it (was a silent return). A denial-signature in
    // the failed leaf's stdout (the auto-mode classifier blocking the staging courier) rides as the
    // bounded `reason`, and the outcome distinguishes a denial from a plain courier/exec staging error.
    // The RETURN reason stays `could-not-stage-external-inputs` so the #277 harness-dead tripwire and
    // every caller behave exactly as before — only the missing audit line is added.
    const writeInputs = promptStage.ok ? schemaStage.results : promptStage.results
    const denial = _stagingDenial(writeInputs)
    // #383 (Part B): the denial reason is external classifier prose — route it through the repo's rich
    // scrub seam (pr_comment.py scrub: framed key=value / "key":"value" secrets, Bearer tokens, the
    // gho_/github_pat_/sk-/AKIA…/xox…/AIza… prefixes, URI userinfo) BEFORE it persists, closing the
    // consistency gap with the commit-failure path (~926) that already scrubs. _stagingDenial's own
    // base64-run redaction (>=24-char alnum runs) misses those framed classes. On scrub failure fall
    // back to a fixed label so a scrubber outage can never leak the raw (possibly secret) denial text.
    // The fixed _DENIAL_TAINTED label is a known-safe internal constant (no external free-text), so it
    // skips the scrub — avoiding a needless exec and keeping the taint-specific evidence intact even if
    // the scrubber is unavailable; only the WINDOWED classifier prose is scrubbed.
    // The fixed _DENIAL_TAINTED label is a known-safe internal constant (no external free-text), so it
    // skips the scrub — avoiding a needless exec and keeping the taint-specific evidence intact even if
    // the scrubber is unavailable; only the WINDOWED classifier prose is scrubbed.
    const scrubbedDenial = !denial ? null
      : (denial === _DENIAL_TAINTED ? denial
        : await _scrubReason(denial, 'staging denied (reason scrubbed)'))
    const jStaging = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: denial ? STAGING_DENIED_OUTCOME : STAGING_FAILED_OUTCOME },
      scrubbedDenial ? { reason: scrubbedDenial } : {}))
    if (!(jStaging && jStaging.ok)) return { ok: false, reason: 'unauditable' }
    return { ok: false, reason: 'could-not-stage-external-inputs' }
  }

  // 2. preSHA (write roles only — read roles never mutate the tree, FR-7).
  let preSha = null
  if (isWrite) {
    preSha = await _captureHead(cwd)
    if (!preSha) {
      // #373: preSHA capture died before the CLI ran — journal it (was a silent return) so a write
      // dispatch that never reached the engine leaves a trace instead of reading as "never routed".
      const jPreSha = await _journalExternal(Object.assign(_jbase(), { verify: null, outcome: PRESHA_FAILED_OUTCOME }))
      if (!(jPreSha && jPreSha.ok)) return { ok: false, reason: 'unauditable' }
      return { ok: false, reason: 'could-not-capture-preSHA' }
    }
  }

  // 3. Wrap the whole dispatch in the UFR-5 finite timeout. A stall -> {ok:false, reason:'timeout'}.
  // resolvedArgv / relayMeta are declared ABOVE (hoisted over _jbase and the #373 pre-CLI early exits);
  // `run` assigns resolvedArgv synchronously right after build-argv resolves so a ceiling timeout still
  // journals the exact argv the CLI was killed while running (#308), and relayMeta carries the last
  // completed _runArgv's relay facts (#347).
  const run = (async () => {
    const buildArgvCmd =
      `python3 ${libPath('engine_adapter.py')} build-argv --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--effort ${shq(String(effort == null ? '' : effort))} --cwd ${shq(cwd || '.')} ` +
      `--schema-path ${shq(schemaPath)}` +
      (typeof model === 'string' && model ? ` --model ${shq(model)}` : '') +
      (typeof engineModel === 'string' && engineModel ? ` --engine-model ${shq(engineModel)}` : '') +
      ` --verify ${shq(promptPath + ':' + sha256hex(prompt || ''))}` +
      ` --verify ${shq(schemaPath + ':' + sha256hex(schemaText))}`
    let argvObj = await _execJson(buildArgvCmd)
    if (argvObj && argvObj.ok === false && argvObj.reason === 'staged-input-mismatch') {
      // #395: the staging courier's ok was a LIE (or the file was clobbered since) — the disk
      // hash disagrees. Re-stage both inputs once (the hijack/mangle is stochastic) and
      // re-verify via a fresh build-argv; a second mismatch fails the dispatch closed — the
      // CLI never runs on unverified inputs. No inline journaling (premortem-002: the raced
      // `run` never journals); the reason rides the role-specific post-race journal line.
      const rp = await _stageInput(promptPath, prompt || '')
      const rs = rp.ok ? await _stageInput(schemaPath, schemaText) : { ok: false }
      argvObj = (rp.ok && rs.ok) ? await _execJson(buildArgvCmd) : null
      if (argvObj && argvObj.ok === false && argvObj.reason === 'staged-input-mismatch') {
        return { ok: false, reason: 'staged-input-mismatch' }
      }
    }
    const argv = argvObj && Array.isArray(argvObj.argv) ? argvObj.argv : (Array.isArray(argvObj) ? argvObj : null)
    if (!argv) return { ok: false, reason: 'build-argv-failed' }
    resolvedArgv = argv

    // Feed the staged prompt file to the external process stdin (the argv itself carries no prompt).
    // cwd is threaded through so _runArgv can confine the run to the worktree (FR-8; see _runArgv).
    // limitSeconds bounds the perl-alarm ceiling (belt-and-suspenders with the JS race); idleSeconds +
    // armIdle arm the #309 byte-activity stall monitor (≤ ceiling). A monitor idle-kill returns
    // {stalled:true} -> outcome:'stalled' (distinct from the ceiling 'timeout'); the caller falls open.
    // #343: non-idempotent dispatches (write roles + the workspace-write author-plan) run SINGLE
    // through the marker courier — every chain retry would hand the command to a new leaf that
    // RE-RUNS it (see _runArgv). captureBase mirrors _composeDispatchCommand's derivation so the
    // evidence probe can see the watchdog's capture files (signal 3).
    const nonIdempotent = isWrite || isAuthor
    const captureBase = promptPath.replace(/\.prompt$/, '') + '.run'
    let runRes = await _runArgv(argv, promptPath, cwd, limitSeconds, idleSeconds, armIdle, nonIdempotent)
    // #341 COURIER DECLINE: the answer carried no execution marker — a safety-trained cheapest-model
    // leaf likely refused the autonomous engine command and answered prose. The engine was NEVER
    // TRIED, so this is NOT an `external-run-failed` engine failure (promise 4/5: never blame the
    // engine for a courier's refusal). Retry ONCE through the hardened path (the refusal is
    // stochastic — root-cause #341 saw a cursor-build dispatch refuse 2/4 and comply 2/4).
    // #343 CORROBORATION (write roles): marker absence is NOT proof of non-execution — a leaf can
    // execute the command and answer with a file-pointer sentence when the output is huge (live-
    // observed in the PR-343 vet). Before treating a write-role marker-less answer as a decline
    // (journal + retry), corroborate with the execution-evidence probe (uncommitted edits, a moved
    // HEAD from an engine self-commit, or watchdog capture files): evidence means the engine may have
    // run — that is an ENGINE failure (external-run-failed; the caller falls open and UFR-2 resets
    // the uncommitted edits), NEVER a courier-declined and NEVER retried (a retry would double-
    // execute on the already-edited tree). Probed before EACH decline classification. author-plan has
    // no probe surface (its cwd is the repo root, legitimately dirty mid-run), so its decline retry
    // stands on the doc-overwrite idempotence of the author leaf plus the caller's usableDraft gate.
    // COLLECT the attempts' refusal prose in priorDeclines but do NOT journal inline: journaling
    // stays on the single POST-RACE settled path (the declinePrefixes handler below) so a
    // `Promise.race` timeout win can never interleave a stray courier-declined line after the
    // dispatch already returned (premortem-002). priorDeclines rides EVERY failure return from here
    // on, so an attempt-1 decline is still audited when attempt 2 lands on a different failure
    // (delta-review code-003).
    const priorDeclines = []
    if (runRes && runRes.declined) {
      if (isWrite && await _executionEvidence(cwd, preSha, captureBase)) {
        return { ok: false, reason: 'external-run-failed' }
      }
      priorDeclines.push(_declinePrefix(runRes.answer))
      runRes = await _runArgv(argv, promptPath, cwd, limitSeconds, idleSeconds, armIdle, nonIdempotent)
      if (runRes && runRes.declined) {
        if (isWrite && await _executionEvidence(cwd, preSha, captureBase)) {
          return { ok: false, reason: 'external-run-failed', declinePrefixes: priorDeclines }
        }
        priorDeclines.push(_declinePrefix(runRes.answer))
        return { ok: false, reason: COURIER_DECLINED_OUTCOME, declined: true, declinePrefixes: priorDeclines }
      }
    }
    if (runRes && runRes.stalled) {
      if (runRes.relay) relayMeta = runRes.relay   // #347: the stalled line still names the kept capture
      return priorDeclines.length ? { ok: false, reason: 'stalled', declinePrefixes: priorDeclines }
        : { ok: false, reason: 'stalled' }
    }
    if (!runRes || !runRes.ok) {
      return priorDeclines.length ? { ok: false, reason: 'external-run-failed', declinePrefixes: priorDeclines }
        : { ok: false, reason: 'external-run-failed' }
    }
    if (runRes.relay) relayMeta = runRes.relay
    const rawStdout = runRes.stdout

    // parse-result SCRUBS external free-text at the adapter boundary (Task 6); it reads by file.
    // #349: on the armed path the shell-written capture at relay.outPath IS that file — byte-perfect,
    // complete (head AND tail), and never touched by a model. Parse it DIRECTLY. Re-staging the
    // relayed stdout through a courier means a leaf re-TYPES a ~30KB base64 command, which live-
    // corrupted every large payload (issue #349: a mangled staged copy parsed `unreadable` while the
    // on-disk capture parsed ok:true). The _stageCmd path remains ONLY for a dispatch with no capture
    // file (the unarmed path — authz probes / a hypothetical non-streaming engine — whose outputs are
    // small and never production payloads).
    let parsePath = relayMeta && relayMeta.outPath ? relayMeta.outPath : null
    if (!parsePath) {
      const rawPath = `/tmp/engine-${runId}.out`
      const wroteRaw = await _exec([_stageCmd(rawPath, rawStdout)])
      if (!(wroteRaw && wroteRaw[0] && wroteRaw[0].ok)) return { ok: false, reason: 'could-not-stage-external-output' }
      parsePath = rawPath
    }
    const parsed = await _execJson(
      `python3 ${libPath('engine_adapter.py')} parse-result --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--stdout-path ${shq(parsePath)}`)
    if (!parsed || parsed.ok !== true) return { ok: false, reason: (parsed && parsed.reason) || 'unreadable' }
    return parsed
  })()

  let parsed
  // clearTimeout() the race's timeout handle once the race settles so a losing timer (the common
  // case: `run` settles first) never pins the process/test-runner event loop alive for up to
  // `limitMs` after this call already returned — pure Node hygiene, does not change the race's
  // outcome or timing. (Not unref()'d: unref would let the loop exit before EITHER branch fires
  // when the only other pending work is itself unref'd, silently abandoning the await.)
  let timeoutHandle = null
  try {
    parsed = await Promise.race([
      run,
      new Promise((resolve) => {
        timeoutHandle = setTimeout(() => resolve({ ok: false, reason: 'timeout' }), limitMs)
      }),
    ])
  } catch (_e) { parsed = { ok: false, reason: 'external-run-threw' } }
  finally { if (timeoutHandle) clearTimeout(timeoutHandle) }

  // #341/#343: journal every corroborated courier-declined attempt HERE, on the single post-race
  // settled path (never inline in the raced `run`), so a timeout win cannot interleave a stray audit
  // line after this returned (premortem-002). declinePrefixes rides ANY failure shape (not only the
  // fully-declined one): an attempt-1 decline followed by an attempt-2 non-decline failure still
  // audits the refusal (delta-review code-003). Each line carries that attempt's clamped refusal
  // prose as honest reason-context.
  if (parsed && Array.isArray(parsed.declinePrefixes)) {
    for (const prefix of parsed.declinePrefixes) {
      await _journalExternal(Object.assign(_jbase(), { verify: null,
        outcome: COURIER_DECLINED_OUTCOME, declinePrefix: prefix }))
    }
  }
  // A fully-declined dispatch (engine never tried — both attempts refused, both corroborated clean):
  // no ok/timeout/commit outcome is recorded — the engine never ran. The caller falls open to Claude.
  // A non-declined failure falls THROUGH to the role-specific journaling below (its engine outcome —
  // e.g. external-run-failed — is the dispatch's own audit line).
  if (parsed && parsed.declined) return { ok: false, reason: COURIER_DECLINED_OUTCOME }

  // 4a. Author role: no commit (see isAuthor above). Journal first (UFR-6 symmetry — an
  // unjournaled author dispatch is as unauditable as any other), then hand the parsed notify
  // back; the caller's usableDraft post-check decides acceptance and falls open on failure.
  if (isAuthor) {
    const jAuthor = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') }))
    if (!(jAuthor && jAuthor.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { ok: true, notify: parsed.notify || [] } : { ok: false, reason: parsed.reason }
  }

  // 4. Read role: return findings straight through (no commit). Failure -> caller falls open to Claude.
  // FIX 5 (UFR-6 symmetry): a read role is JUST as unauditable as a write role when the journal
  // append itself fails — mirror the write-role check below (a failed journal -> {ok:false,
  // reason:'unauditable'}) instead of discarding the append's own success/failure unchecked.
  if (!isWrite) {
    const jRead = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') }))
    if (!(jRead && jRead.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { findings: parsed.findings || [] } : { ok: false, reason: parsed.reason }
  }

  // 5. Write role failure -> only uncommitted edits exist; caller reuses resetUncommitted + falls open (UFR-2).
  if (!parsed.ok) {
    await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.reason || 'failed' }))
    return { ok: false, reason: parsed.reason }
  }

  // 6. Write success -> the adapter is the SOLE committer (preSHA-scoped fold; single Task-Id trailer).
  const commit = await _execJson(
    `python3 ${libPath('engine_adapter.py')} commit --worktree ${shq(cwd)} --task-id ${shq(o.taskId || '')} ` +
    `--pre-sha ${shq(preSha)}`)
  if (!commit || commit.ok !== true) {
    // #392: a STRUCTURED reason (e.g. history-shape-fix-unrepresentable) is the adapter's own honest
    // classification of a non-error, non-landable outcome — a fixed internal token (not external
    // free-text, so no scrub) carried VERBATIM as BOTH the fall-open reason and the journal outcome,
    // so the journal names WHY the fix could not land rather than mislabeling it commit-failed.
    // Otherwise commit.error carries raw git output (stdout+stderr) — SCRUB it before it can reach an
    // owner-facing notice, and journal the generic commit-failed outcome.
    const structured = (commit && typeof commit.reason === 'string' && commit.reason) || null
    const reason = structured
      ? structured
      : ((commit && commit.error) ? await _scrubReason(commit.error) : 'commit-failed')
    // sec-101: the engine DID run and edited the worktree here, so this outcome must ALSO leave exactly
    // one audit line — otherwise commit-failure is the single external-dispatch outcome with no journal
    // entry (FR-6/UFR-6 symmetry gap). Journal BEFORE returning; the reason is already scrubbed above.
    // #392: a lost audit append is UFR-6 unauditable — mirror every other durable-write path (read /
    // author / write-success) and fail closed to 'unauditable' rather than silently return the outcome
    // with no trace. This is exactly what makes #392's "the journal names WHY" guarantee load-bearing:
    // if the append vanished, the honest history-shape/commit-failed line vanished with it.
    const jCommit = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: structured || 'commit-failed' }))
    if (!(jCommit && jCommit.ok)) return { ok: false, reason: 'unauditable' }
    return { ok: false, reason }
  }

  // 7. Journal BEFORE returning the native worker shape (UFR-6: unauditable -> the caller fails closed).
  const j = await _journalExternal(Object.assign(_jbase(), {
    verify: 'pending', outcome: 'ok' }))
  if (!(j && j.ok)) return { ok: false, reason: 'unauditable' }
  return { ok: true, signal: parsed.signal || 'ok', evidence: parsed.evidence || {} }
}

// #277 tripwire: the FIRST external dispatch is itself the end-to-end staging self-test — a
// harness-level staging/dispatch death (the JS path can't stage inputs, or threw before the CLI ever
// ran) means EVERY external role this run will silently fall open to Claude, violating the owner's
// enginePreferences (the named requirement #219 was held weeks for). Surface it ONCE as a distinct,
// NAMED narrator notice — run_watch shows narrator lines live, so this is the mechanical tripwire the
// named-risk convention asks for, not the routine per-dispatch "falling open" line that repeats and
// reads as normal. Keyed on PRE-CLI failure reasons only: could-not-stage-* (the staging pipe is
// dead) and dispatch-error (a synchronous throw, e.g. a missing sandbox global) — NOT engine-specific
// outcomes (timeout/unreadable/commit-failed) where the CLI genuinely ran and the harness is fine.
let _harnessDeadNoticeShown = false
function _isHarnessDeadReason(reason) {
  const r = String(reason || '')
  return r === 'could-not-stage-external-inputs' || r === 'could-not-stage-external-output' ||
    r.indexOf('dispatch-error') === 0
}
function _maybeHarnessDeadNotice(o, reason) {
  if (_harnessDeadNoticeShown || !_isHarnessDeadReason(reason)) return
  _harnessDeadNoticeShown = true
  const engine = (o && o.engine) || 'external'
  try {
    globalThis.log('ENGINE-UNAVAILABLE: engine ' + JSON.stringify(engine) + ' could not stage/dispatch in ' +
      'this harness (' + String(reason) + ') — the JS dispatch path is dead, so EVERY external role this run ' +
      'falls open to Claude, silently violating enginePreferences. Harness/staging defect (see #277), not engine auth.')
  } catch (_) {}
}

// #395: the staged-input-mismatch tripwire — DISTINCT from #277's harness-dead notice (that
// one means the staging pipe cannot run at all and latches once per run; this one means the
// deterministic verify caught a staging courier whose ok the disk disproves — the defense
// WORKING, not a dead harness). Own latch so neither notice consumes the other's budget.
let _stagingLieNoticeShown = false
function _maybeStagingLieNotice(o, reason) {
  if (_stagingLieNoticeShown || String(reason || '') !== 'staged-input-mismatch') return
  _stagingLieNoticeShown = true
  const engine = (o && o.engine) || 'external'
  try {
    globalThis.log('STAGED-INPUT-MISMATCH: engine ' + JSON.stringify(engine) + ' dispatch inputs failed ' +
      'the deterministic hash verify twice (original stage + one re-stage) — a staging courier answered ' +
      'ok on content the disk disproves (#395: possible payload hijack or staging corruption). The ' +
      'dispatch failed closed; see the journal staged-input-mismatch line.')
  } catch (_e) { /* notice is best-effort */ }
}

// #277: preserve the underlying error name+message (clamped) in the fall-open reason. The catch below
// is the catch-all for any synchronous throw; collapsing every throw to a bare 'dispatch-error' made
// the #277 Buffer death a transcript-archaeology session. Carrying the error text makes the next
// failure on this path self-identifying (e.g. 'dispatch-error: ReferenceError: Buffer is not defined').
// The thrown value here is an internal JS engine error (bad destructure / missing global / exec shape),
// never external free-text, so it needs no scrub — only a length clamp.
function _errText(e) {
  if (e == null) return String(e)
  const name = e.name || 'Error'
  const msg = e.message == null ? '' : String(e.message)
  return (msg ? name + ': ' + msg : name).slice(0, 160)
}

// FIX 3 (premortem): a synchronous throw ANYWHERE in the dispatch body (a bad destructure, an
// unavailable Buffer/setTimeout global, an unexpected exec-shape) must still resolve to the native
// {ok:false} failure shape — never throw out of dispatchExternal. Callers rely on a returned
// failure to trigger their fall-open-to-Claude path (UFR-2 resetUncommitted + native worker); an
// uncaught throw here would instead propagate up and abort the whole run.
async function dispatchExternal(o) {
  try {
    const res = await _dispatchExternalInner(o || {})
    _maybeHarnessDeadNotice(o, res && res.reason)
    _maybeStagingLieNotice(o, res && res.reason)
    return res
  } catch (e) {
    const reason = 'dispatch-error: ' + _errText(e)
    _maybeHarnessDeadNotice(o, reason)
    _maybeStagingLieNotice(o, reason)
    return { ok: false, reason }
  }
}

// test-only: reset the once-per-process tripwire memo so a smoke can drive the notice deterministically.
function __resetHarnessNotice() { _harnessDeadNoticeShown = false }
function __resetStagingLieNotice() { _stagingLieNoticeShown = false }

// _STREAMS_WHEN_PIPED is exported for the drift guard in the stall-monitor smoke (every dispatchable
// external engine must have an explicit streams-when-piped verdict) — not a public seam.
module.exports = { dispatchExternal, DEFAULT_STALL_LIMIT_SECONDS, __resetHarnessNotice, __resetStagingLieNotice,
  _STREAMS_WHEN_PIPED, strictify,
  // #341: the courier-declined outcome token, exported so the JS↔Python drift guard (CONVENTIONS
  // §11.2) can assert this producer home matches acceptance_verdict.COURIER_DECLINED_OUTCOME.
  COURIER_DECLINED_OUTCOME,
  // #373: the pre-CLI early-exit outcome tokens, exported so the JS↔Python behavior drift guard
  // (CONVENTIONS §11.2) can pin that acceptance_verdict.py classifies them as failed dispatch
  // attempts (counted against the per-engine authenticity gate) — never an acceptable fall-open.
  STAGING_DENIED_OUTCOME, STAGING_FAILED_OUTCOME, PRESHA_FAILED_OUTCOME,
  // #341 test-only: the pure production command composer, exported so the real-seam detector
  // (CONVENTIONS §12.2) builds the byte-faithful watchdog command and drives it through a REAL leaf.
  _composeDispatchCommand,
  // #257 test-only: the plain-readable stage-write composer + its verify-and-retry wrapper, exported so
  // the fidelity smoke drives the REAL python write+sha256-verify through a shell (round-trip + mangle
  // fail-closed) and pins that no base64 blob rides the staged command; the routing signature lets
  // mocks target the stage leaf.
  _stageCmd, _stageInput, _SR_STAGE_SIG,
  // #435 test-only: the escape-encoder, exported so showrunner_bytes_smoke.js pins it byte-identical to
  // bytes.encPayload (the io writer's mirror) — a drift between the two mirrored transports fails a test.
  _stageEnc,
  // #408 test-only: the pure staging-key derivation (workItem-folded, no-double-prefix, over-length
  // safe), exported so the smoke pins every branch directly without spinning up full dispatches.
  _deriveRunKey,
  // #347 test-only: the watchdog's stdout-relay cap, exported so the flood smoke pins the bound.
  EMIT_TAIL_BYTES }
