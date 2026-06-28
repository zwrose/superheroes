// plugins/superheroes/lib/eval_clamp.js
//
// Pure numeric clamp. Evaluates the lower bound first so an inverted range (lo > hi)
// deterministically returns hi (not lo and not a throw).
function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

module.exports = { clamp };
