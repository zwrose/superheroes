const { io } = require('./io_seam.js')
const { libPath } = require('./lib_root.js')   // #170: spine code root for lib composes

// fencedJsonWrite: put a JSON artifact on disk through the courier in ONE leaf (fold 1, #141) —
// io.stageAndRunHelper chains the opaque base64 stage-write AND the fenced_json.py verify-write
// into a single leaf-bash command (mkdir -p <dir> && stage && helper). fenced_json.py still
// verifies the staged text's sha256 ITSELF before applying (--payload-hash), so a courier that
// mangles the staged body in transit (live 2026-07-02) fails the Python-side hash check as
// payload-corrupt and the write is retried once, then fail-closed — never silently altered
// content. This folds the old 6-leaf ceremony (pre-read + current-read + mkdir + stage + hash
// read-back + write) all the way down to ONE staged+verified leaf. D3 durability byte-identical:
// the staged-hash contract, the fence, and the overwrite/CAS semantics are unchanged — only the
// two transport leaves (stage, verify-write) collapse into one.
//
// opts: { runId, lease?, expectedHash?, overwrite? } — exactly one of expectedHash (CAS fence
// against the hash the caller last observed) or overwrite:true. Overwrite is LAST-WRITER-WINS,
// accepted deliberately for run artifacts the runtime composes fresh and unconditionally
// replaces (terminal-record.json, the front-half outcome): the cooperative lease serializes
// live sessions, the lease is stamped into the record (not verified at write time), and the
// old read-hash-then-CAS pair detected only a competitor writing inside its own read→write
// window — a zombie that pre-read defeated it too. In overwrite mode --payload-hash is the
// ONLY integrity guard, so fenced_json.py refuses overwrite writes that arrive without it.
async function fencedJsonWrite(path, payload, opts) {
  const ioApi = io()
  if (!opts || !opts.runId) return { ok: false, reason: 'missing-run-id' }
  if (!opts.expectedHash && !opts.overwrite) return { ok: false, reason: 'missing-expected-hash' }
  const next = Object.assign({}, payload || {}, { runId: opts.runId, lease: opts.lease })
  const text = JSON.stringify(next)
  const want = ioApi.contentHash(text)
  const stagedPath = path + '.payload'
  const args = [libPath('fenced_json.py'), 'write', '--path', path,
    '--payload-path', stagedPath, '--payload-hash', want, '--run-id', opts.runId]
  if (opts.overwrite) args.push('--allow-overwrite')
  else args.push('--expected-hash', opts.expectedHash)
  if (opts.lease) args.push('--lease', opts.lease)
  // stageAndRunHelper folds the parent-dir create into the same op, so the missing-dir first-attempt
  // failure the old two-leaf path retried through is gone. The one retry now covers only a
  // transport-corrupt stage (payload-corrupt), an unparseable helper answer, or a THROWING transport
  // (bundle: a courier reject after courier_exec's retries; defaultIo: an fs error). The old two-leaf
  // path caught the io.writeFile throw and retried -> fail-closed; keep that contract here so a
  // transport throw parks {ok:false} for the callers' !recWrite.ok branch instead of crashing the run.
  let lastReason = null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let out
    try {
      out = await ioApi.stageAndRunHelper(stagedPath, text, 'python3', args)
    } catch (_) {
      lastReason = 'payload-stage-failed'
      continue
    }
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (stale, missing-run-id, replace-failed) is final; only a transport-corrupt
    // stage (or an unparseable answer) earns the one retry.
    if (parsed && parsed.reason && parsed.reason !== 'payload-corrupt' && parsed.reason !== 'payload-unreadable') {
      return { ok: false, reason: parsed.reason }
    }
    lastReason = (parsed && parsed.reason) || lastReason
  }
  return { ok: false, reason: lastReason || 'payload-stage-failed' }
}

// writeTerminalRecord: persist the review loop's terminal record WITHOUT ever staging the full
// verdict through the courier (live 2026-07-02, run wf_94c879e0-747: the ~14KB evidence-bodied
// verdict, base64-staged via one haiku writeFile, was byte-dropped in transit; the Python
// --payload-hash correctly refused the mangled stage and the phase parked payload-stage-failed).
//
// Instead — same shape as #136 compose-persist — review_memory.py compose-terminal composes the
// record PYTHON-SIDE from state already on disk: the unbounded synthesis outputs (fixes / deferred
// / coverageDecisions) come from round-records.json, the telemetry summary from
// review-telemetry.json, and the evidence-bodied `findings` are dropped entirely (no
// terminal-record consumer reads them). Only the small verdict scalars ride inline, self-verified
// by --verdict-hash so a courier that mangles them fails closed instead of persisting altered
// content. Overwrite is finalize's job: the record is durable for crash-resume, not append-only.
async function writeTerminalRecord(recPath, verdict, opts) {
  const ioApi = io()
  if (!opts || !opts.runId) return { ok: false, reason: 'missing-run-id' }
  const p = String(recPath)
  const runDir = opts.runDir || p.slice(0, p.lastIndexOf('/'))
  // strip the fields the record must never carry (the evidence-bodied ones) or re-derives from
  // disk (the unbounded synthesis outputs) — what remains is the small, self-verifying scalar set.
  const slim = Object.assign({}, verdict || {})
  delete slim.findings
  delete slim.carriedFindings
  delete slim.fixes
  delete slim.deferred
  delete slim.coverageDecisions
  const verdictJson = JSON.stringify(slim)
  const verdictHash = ioApi.contentHash(verdictJson)
  const args = [libPath('review_memory.py'), 'compose-terminal',
    '--path', recPath,
    '--records-path', ioApi.join(runDir, 'round-records.json'),
    '--telemetry-path', ioApi.join(runDir, 'review-telemetry.json'),
    '--verdict-json', verdictJson, '--verdict-hash', verdictHash,
    '--run-id', opts.runId]
  if (opts.lease) args.push('--lease', opts.lease)
  let lastReason = null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const out = await ioApi.runHelper('python3', args)
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (missing-run-id, write-failed) is final; only a courier that mangled the
    // small inline verdict in transit (verdict-corrupt) or an unparseable answer earns the one
    // retry — the same self-verify-then-retry contract fencedJsonWrite uses for its staged payload.
    if (parsed && parsed.reason && parsed.reason !== 'verdict-corrupt') {
      return { ok: false, reason: parsed.reason }
    }
    lastReason = (parsed && parsed.reason) || 'terminal-record-write-failed'
  }
  return { ok: false, reason: lastReason || 'terminal-record-write-failed' }
}

module.exports = { fencedJsonWrite, writeTerminalRecord }
