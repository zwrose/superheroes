// plugins/superheroes/lib/io_seam.js
// The injectable I/O seam. The spine + its bundled siblings perform every filesystem /
// path / tmpdir touch through io(), so the SAME control flow runs in two runtimes:
//   - node (the smoke harnesses + the per-task tests): global.io unset -> defaultIo (fs/os backed).
//   - the Workflow-tool bundle: global.io is replaced with a leaf-bash implementation, because
//     the Workflow sandbox forbids require()/fs/path/os in the script body.
// Keeping the seam here (not in showrunner.js) lets the bundler inline it once.
const PATH_SEP = '/'
function joinPath() {
  const parts = Array.prototype.slice.call(arguments)
  return parts.join(PATH_SEP).replace(/\/+/g, '/')
}
const defaultIo = {
  writeFile(p, s) {
    require('fs').writeFileSync(p, typeof s === 'string' ? s : JSON.stringify(s))
  },
  readText(p) { return require('fs').readFileSync(p, 'utf8') },
  readJson(p, dflt) {
    try { return JSON.parse(require('fs').readFileSync(p, 'utf8')) } catch (_) { return dflt }
  },
  mkdirp(d) { require('fs').mkdirSync(d, { recursive: true }) },
  tmpdir() { return require('os').tmpdir() },
  join: joinPath,
}
function io() { return global.io || defaultIo }
module.exports = { io, defaultIo, joinPath }
