// The one home of the argv the mod runs against lib/compaction_directive.py. Pure and
// import-free so the real-CLI test can compile this file alone and execute exactly
// what the mod would run (lib/tests/test_compaction_mod_argv_1814.py).

const base = (pluginRoot: string, verb: string): string[] => [
  'python3',
  '-B',
  `${pluginRoot}/lib/compaction_directive.py`,
  verb,
]

export const instructionsArgv = (
  pluginRoot: string,
  sessionId: string,
  transcript: string | null,
  owner: string | null,
): string[] => {
  const argv = [...base(pluginRoot, 'instructions'), '--session-id', sessionId]

  if (transcript !== null) {
    argv.push('--transcript', transcript)
  }
  if (owner !== null) {
    argv.push('--user-instructions', owner)
  }

  return argv
}

export const markArgv = (pluginRoot: string, sessionId: string): string[] => [
  ...base(pluginRoot, 'mark'),
  '--session-id',
  sessionId,
]

// The checkpoint block body travels on stdin.
export const saveArgv = (pluginRoot: string, sessionId: string): string[] => [
  ...base(pluginRoot, 'save'),
  '--session-id',
  sessionId,
]
