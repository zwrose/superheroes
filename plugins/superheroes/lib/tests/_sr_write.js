// plugins/superheroes/lib/tests/_sr_write.js
// #435 shared test helper: parse a PLAIN-VISIBLE io write command (the base64-free __SR_W successor) the
// way a real shell would, so the canned-shell smokes (misbehaving / stretch-budget) can recover the
// path + written content without re-implementing shell tokenization. The write transport is now:
//   python3 -c '<writer-script>' '<path>' '<enc-payload>' ['<expected-hash>']            (standalone write)
//   python3 -c '<writer-script>' '<path>' '<enc-payload>' >/dev/null && <helper> 2>&1; …  (stage+run chain)
// The payload rides ESCAPE-ENCODED plain text (bytes.encPayload) inside a shq-quoted argv — it can contain
// spaces, quotes (as the `'\''` shq idiom), and non-ASCII, so a `'([^']*)'` regex is NOT safe. shellSplit
// honors single-quoting and the shq `\'` escape; decPayload (bytes.js) reverses the escape-encoding.
'use strict'
const { decPayload } = require('../bytes.js')

// shellSplit: minimal POSIX word splitter — enough for the spine's own composed write commands. Honors
// single-quoted segments and the `'\''`/`\'` escaped-quote idiom shq emits; unquoted whitespace separates
// words. (No double-quote / variable handling — the spine never composes those into a write command.)
function shellSplit(s) {
  const words = []
  let cur = '', i = 0, inSingle = false, started = false
  while (i < s.length) {
    const c = s[i]
    if (inSingle) {
      if (c === "'") { inSingle = false; i += 1 } else { cur += c; i += 1 }
    } else if (c === "'") { inSingle = true; started = true; i += 1 }
    else if (c === '\\' && s[i + 1] === "'") { cur += "'"; started = true; i += 2 }
    else if (c === ' ' || c === '\t' || c === '\n') { if (started) { words.push(cur); cur = ''; started = false } i += 1 }
    else { cur += c; started = true; i += 1 }
  }
  if (started) words.push(cur)
  return words
}

// isWriteCommand: TRUE when cmd is a __SR_W write leaf. TWO signals, both required:
//   - the writer script carries the unique __SR_WROTE marker literal; AND
//   - the leaf is composed as a BARE `python3 -c '<writer>' …` (writeFile / stageAndRunHelper), NOT the
//     quoted `'python3' '-c' …` shape __argv emits for runHelper / record_composed leaves.
// The second signal is load-bearing: the composed-exact record_composed leaf EMBEDS the io write command as
// an argv payload (so its own bytes contain __SR_WROTE) — anchoring on the bare `python3 -c '` prefix (after
// any cd-root wrap) excludes it, so a registration leaf is never mis-parsed as the write it registers.
function isWriteCommand(cmd) {
  const bare = String(cmd).replace(/^cd '(?:[^'\\]|\\.)*' && /, '')
  return /^python3 -c '/.test(bare) && String(cmd).indexOf('__SR_WROTE') >= 0
}

// parseWrite: recover { path, content, hash, chained, helper } from a write / stage command. `content` is
// the decoded (original) file bytes the leaf would land on disk. `hash` is the expected-hash argv (present
// on a verified standalone write, absent on a 2-arg stage). `chained` marks the stage+run shape; `helper`
// is the trailing helper command string when chained.
function parseWrite(cmd) {
  const words = shellSplit(String(cmd))
  // words: ['python3','-c',<script>,<path>,<enc>, ...tail]
  const path = words[3]
  const content = decPayload(words[4] == null ? '' : words[4])
  const tail = words[5]
  if (tail === '>/dev/null') {
    const raw = String(cmd)
    const idx = raw.indexOf('>/dev/null && ')
    let helper = idx >= 0 ? raw.slice(idx + '>/dev/null && '.length) : ''
    helper = helper.replace(/\s*2>&1;\s*echo __SR_EXIT:\$\?\s*$/, '')
    return { path, content, hash: null, chained: true, helper }
  }
  return { path, content, hash: tail || null, chained: false, helper: null }
}

module.exports = { shellSplit, isWriteCommand, parseWrite, decPayload }
