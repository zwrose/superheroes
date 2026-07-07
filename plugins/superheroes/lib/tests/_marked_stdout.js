'use strict'

function markedStdout(body) {
  const text = typeof body === 'string' ? body : JSON.stringify(body)
  return text.includes('__SR_EXIT') ? text : text + '\n__SR_EXIT:0'
}

function saveProgressOk(extra) {
  return markedStdout(Object.assign({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }, extra || {}))
}

module.exports = { markedStdout, saveProgressOk }
