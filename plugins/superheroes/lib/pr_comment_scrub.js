// Pure-JS port of pr_comment.scrub — bundle-safe (no child_process).
const SECRET_KEY_NAMES = 'session[_-]?id|session|sid|token|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|pwd|client[_-]?secret'

const SCRUB_PATTERNS = [
  [new RegExp('^(\\s*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-api[_-]?key)\\s*:\\s*).+$', 'gim'), '$1[REDACTED]'],
  [new RegExp('(?<!\\w)(x[_-]?api[_-]?key)(?:\\\\?["\'])?\\s*:\\s*(?:\\\\?"[^"\\n]*\\\\?"|\\\\?\'[^\'.\\n]*\\\\?\'|[^\\s}\'",]+)', 'gi'), '$1: [REDACTED]'],
  [/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, 'Bearer [REDACTED]'],
  [new RegExp('\\b(' + SECRET_KEY_NAMES + '|x[_-]?api[_-]?key)=([^&\\s;"\']+)', 'gi'), '$1=[REDACTED]'],
  [new RegExp('(\\\\?["\'](' + SECRET_KEY_NAMES + ')\\\\?["\']\\s*:\\s*)(?:\\\\?"[^"\\n]*\\\\?"|\\\\?\'[^\'.\\n]*\\\\?\')', 'gi'), '$1[REDACTED]'],
  [/\b([a-z][a-z0-9+.\-]*:\/\/[^/\s:@]+):([^@\s/]+)@/gi, '$1:[REDACTED]@'],
]

function scrub(text) {
  let out = String(text || '')
  for (const [pattern, repl] of SCRUB_PATTERNS) {
    out = out.replace(pattern, repl)
  }
  return out
}

module.exports = { scrub }
