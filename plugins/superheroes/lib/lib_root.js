// plugins/superheroes/lib/lib_root.js
// #170: the spine CODE root — where every `python3 <libRoot>/<cli>.py` compose points. It is the
// SECOND explicit root, distinct from the TARGET repo (`__SR_ROOT`, where git/build/docs operate):
// the code being EXECUTED and the repo being OPERATED ON are no longer assumed to be the same tree.
//
// Read at CALL time (never captured in a module-load const) from globalThis.__SR_LIB, which the
// bundle ENTRY plants from args.libRoot — the launching skill passes the versioned, immutable plugin
// cache (${CLAUDE_PLUGIN_ROOT}/lib), so a live run is pinned to its launch-time code version by
// construction. Absent (raw-module node smokes, a no-args launch, dev/dogfood) it falls back to the
// repo-relative path, which resolves under the leaf's `cd <root>` — so absent-libRoot composes stay
// BYTE-IDENTICAL to the pre-#170 spine.
'use strict'

const DEFAULT_LIB = 'plugins/superheroes/lib'

// libRoot: the resolved code-root string. globalThis exists in both node and the Workflow sandbox.
function libRoot() {
  const v = (typeof globalThis !== 'undefined') ? globalThis.__SR_LIB : null
  return (typeof v === 'string' && v.length) ? v : DEFAULT_LIB
}

// libPath: the interpreter-path segment for a shell compose — `python3 ${libPath('fence_cli.py')}`.
// With the default (relative) libRoot this yields the exact pre-#170 literal, so composes are byte-
// identical; with an absolute libRoot it yields the cache path (portable + cwd-independent).
function libPath(script) { return libRoot() + '/' + script }

// isAbsoluteLibRoot: true only when a caller planted an ABSOLUTE __SR_LIB (production / portable
// runs). The relative default (or any relative override) is treated as dev/dogfood mode.
function isAbsoluteLibRoot() { return libRoot().charAt(0) === '/' }

// _sq: POSIX single-quote a shell word (same escape as the spine's shq).
function _sq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// libRootProbe: a shell prefix that fail-closes when an ABSOLUTE spine code root has gone missing
// (e.g. a plugin-cache eviction between phases). It rides an ALREADY-composed command —
// `${libRootProbe()}python3 <lib>/recover_entry.py …` — so it adds NO leaf. When the dir is absent it
// echoes a PARSEABLE failure object carrying MISSING_MARKER, then __SR_EXIT:0, and exits 0; when
// present it is a no-op passthrough. In dev/dogfood mode (relative libRoot) it emits nothing, so the
// compose stays byte-identical.
//
// The payload is a JSON `{"ok":false,"reason":"<marker>"}` (not a bare echo) so BOTH probe sites map
// it to the same named park uniformly: the exec-based launch probe (reconcile) substring-matches the
// marker in raw stdout, and the runCourierMarkedJson-based back-half probe (persistPhase) gets it
// back verbatim as an `ok:false` failure only AFTER execution is proven via __SR_EXIT (#218). The
// failure branch must echo __SR_EXIT before exit — wrapMarkedCommand's trailing marker never runs
// after `exit 0`, and without an in-branch marker a genuine missing libRoot looks like a lazy parrot.
//
// Residual fabricability (#218): the __SR_EXIT guard proves a marker-SHAPED answer, not that Bash
// ran. This compose now embeds both the failure payload AND `echo __SR_EXIT:0` in the prompt, so a
// courier that SIMULATES the failure branch (payload + marker, no execution) would still pass the
// guard. Do NOT "harden" this with proof-of-execution (nonce/hash/timestamp) — the Workflow sandbox
// has no crypto, wall-clock, or RNG primitives, so the JS side cannot verify a computed proof; that
// is why #218 chose the marker protocol. The guard rejects the observed did-not-run shapes (bare
// payload with no marker; echoed command with literal __SR_EXIT:$?), and runCourierMarked*'s 2×3
// retry-then-default-dispatch chain bounds the residual simulation class.
const MISSING_MARKER = '__SR_LIBROOT_MISSING__'
function libRootProbe() {
  if (!isAbsoluteLibRoot()) return ''
  const payload = '{"ok":false,"reason":"' + MISSING_MARKER + '"}'
  return 'test -d ' + _sq(libRoot()) + " || { echo '" + payload + "'; echo __SR_EXIT:0; exit 0; }; "
}

// pyLibDir: a Python EXPRESSION that evaluates to the lib dir, for embedded
// `sys.path.insert(0, <pyLibDir()>)` scripts. Default mode reproduces the exact pre-#170 expression
// (byte-identical); an absolute libRoot becomes a bare string literal.
function pyLibDir() {
  const r = libRoot()
  return r === DEFAULT_LIB
    ? 'os.path.join(os.getcwd(), "plugins/superheroes/lib")'
    : JSON.stringify(r)
}

// pyLibScript: a Python string LITERAL for one lib script path, for embedded
// `subprocess.run(["python3", <pyLibScript('build_entry.py')>, …])`. Byte-identical in default mode.
function pyLibScript(name) { return JSON.stringify(libPath(name)) }

module.exports = {
  DEFAULT_LIB, libRoot, libPath, isAbsoluteLibRoot,
  libRootProbe, MISSING_MARKER, pyLibDir, pyLibScript,
}
