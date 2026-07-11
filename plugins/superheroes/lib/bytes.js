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
// Consumers share this ONE copy (SSOT, #231):
//   - the bundle preamble's leaf-bash io (`__b64`/`__utf8Bytes`, which delegate here) — the
//     opaque-payload transport for io.writeFile/stageAndRunHelper (base64), and the UTF-8 byte step of
//     `__contentHash` (whose sha-256 parity with Python/hashlib is load-bearing for the fenced
//     set-gate — so utf8Bytes MUST stay byte-exact; the parity smoke pins b64 against Node's Buffer).
//   - engine_dispatch.js `_stageCmd` — #257 dropped base64 for a PLAIN-readable stage-write (the
//     auto-mode classifier flagged the base64 courier's opacity), pinning transit fidelity with
//     `sha256hex` instead: the spine hashes the readable content and a Python-side re-hash of the
//     written file proves the courier copied it faithfully. Still Buffer-less (same #277 constraint).

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

// sha256hex: lowercase-hex SHA-256 of the string's UTF-8 bytes — a pure-JS, Buffer-LESS digest that
// runs byte-identically in node and the Workflow sandbox (same #277 constraint as b64: no `Buffer`,
// no `crypto` — both absent in the sandbox). Byte-for-byte equal to Node's
// `crypto.createHash('sha256').update(text,'utf8').digest('hex')` AND to Python's
// `hashlib.sha256(text.encode('utf-8')).hexdigest()` — the parity bytes_smoke pins both oracles.
// #257: engine_dispatch._stageCmd stages a PLAIN-readable prompt/schema (base64 opacity dropped —
// the auto-mode classifier flagged the base64 courier) and pins its transit fidelity with this hash:
// the spine computes sha256hex(content) BEFORE the payload rides the courier, embeds it as a literal
// in the staging command, and a Python-side re-hash of the written file proves the leaf copied the
// readable content faithfully (a paraphrase fails the compare -> fail-closed + retry). The algorithm
// mirrors the bundle preamble's __contentHash (SSOT for the fenced set-gate); kept a plain module fn
// here so engine_dispatch (node AND bundled) can require it without the preamble.
function sha256hex(text) {
  var bytes = utf8Bytes(text), i, j
  var hi = (bytes.length / 0x20000000) | 0, lo = (bytes.length << 3) >>> 0
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  bytes.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255,
             (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255)
  var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]
  var w = new Array(64)
  for (i = 0; i < bytes.length; i += 64) {
    for (j = 0; j < 16; j++) {
      var off = i + j * 4
      w[j] = (bytes[off] << 24) | (bytes[off + 1] << 16) | (bytes[off + 2] << 8) | bytes[off + 3]
    }
    for (j = 16; j < 64; j++) {
      var x = w[j - 15], y = w[j - 2]
      var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)
      var s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10)
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) | 0
    }
    var a = H[0], b = H[1], c2 = H[2], dd = H[3], e = H[4], f = H[5], g = H[6], h = H[7]
    for (j = 0; j < 64; j++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))
      var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[j] + w[j]) | 0
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))
      var t2 = (S0 + ((a & b) ^ (a & c2) ^ (b & c2))) | 0
      h = g; g = f; f = e; e = (dd + t1) | 0; dd = c2; c2 = b; b = a; a = (t1 + t2) | 0
    }
    H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c2) | 0; H[3] = (H[3] + dd) | 0
    H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0
  }
  var out = ''
  for (i = 0; i < 8; i++) for (j = 3; j >= 0; j--) out += ('0' + ((H[i] >>> (j * 8)) & 255).toString(16)).slice(-2)
  return out
}

module.exports = { utf8Bytes, b64, sha256hex }
