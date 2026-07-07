// plugins/superheroes/lib/bytes.js
// The single source of truth for sandbox-safe byte encoding. The Workflow sandbox has NO Node
// `Buffer` global (same class as the FR-8-banned wall-clock/PRNG globals — see #277), so the spine cannot
// reach for `Buffer.from(...).toString('base64')` anywhere on a live-run code path: the very first
// such statement throws `ReferenceError: Buffer is not defined`. These pure-JS encoders run
// byte-identically in BOTH runtimes (node smokes AND the sandbox), so a code path that stages via
// b64() is exercised the same way everywhere — no `typeof Buffer` fork that leaves the sandbox path
// untested (the exact blind spot that let #277 ship: staging was Buffer-based, smokes ran in node
// where Buffer exists, and the dead sandbox path was invisible until a live run).
//
// Two consumers share this ONE copy (SSOT, #231):
//   - engine_dispatch.js `_stageCmd` — base64-encodes untrusted external prompt/schema/output before
//     it rides the LLM `exec` courier as an OPAQUE blob (a courier can copy alphabet-soup verbatim or
//     fail visibly; it cannot paraphrase it the way it rewrites readable text — the 2026-07-02 mangle
//     class), then a shell `base64 -d` decodes it.
//   - the bundle preamble's leaf-bash io (`__b64`/`__utf8Bytes`, which delegate here) — the same
//     opaque-payload transport for io.writeFile/stageAndRunHelper, and the UTF-8 byte step of
//     `__contentHash` (whose sha-256 parity with Python/hashlib is load-bearing for the fenced
//     set-gate — so utf8Bytes MUST stay byte-exact; the parity smoke pins b64 against Node's Buffer).

// utf8Bytes: the string's UTF-8 bytes as a plain array (no TextEncoder — absent in the sandbox).
// Byte-array output (no string escapes) so no control characters ever appear in the generated bundle
// (the Workflow permission layer rejects them). A well-formed surrogate pair encodes as the astral
// codepoint; a LONE surrogate encodes as U+FFFD, matching node's utf-8 conversion.
function utf8Bytes(text) {
  var str = String(text || ''), bytes = [], i, c
  for (i = 0; i < str.length; i++) {
    c = str.charCodeAt(i)
    if (c < 0x80) bytes.push(c)
    else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c >= 0xd800 && c < 0xdc00 && i + 1 < str.length && str.charCodeAt(i + 1) >= 0xdc00 && str.charCodeAt(i + 1) < 0xe000) {
      c = 0x10000 + ((c - 0xd800) << 10) + (str.charCodeAt(i + 1) - 0xdc00); i++
      bytes.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    } else if (c >= 0xd800 && c < 0xe000) bytes.push(0xef, 0xbf, 0xbd)
    else bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return bytes
}

// b64: standard base64 (RFC 4648, `+`/`/` alphabet, `=` padding) over the UTF-8 bytes. Byte-for-byte
// identical to `Buffer.from(text, 'utf8').toString('base64')` — the parity smoke pins that invariant.
function b64(text) {
  var bytes = utf8Bytes(text), A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/', out = ''
  for (var i = 0; i < bytes.length; i += 3) {
    var b0 = bytes[i], b1 = bytes[i + 1], b2 = bytes[i + 2]
    out += A[b0 >> 2] + A[((b0 & 3) << 4) | ((b1 === undefined ? 0 : b1) >> 4)]
    out += (b1 === undefined) ? '=' : A[((b1 & 15) << 2) | ((b2 === undefined ? 0 : b2) >> 6)]
    out += (b2 === undefined) ? '=' : A[b2 & 63]
  }
  return out
}

module.exports = { utf8Bytes, b64 }
