// The one home of the argv the mod runs against lib/compaction_directive.py. Pure and
// import-free so the real-CLI test can compile this file alone and execute exactly
// what the mod would run (lib/tests/test_compaction_mod_argv_1814.py). It spells no verb
// and no flag: the vocabulary is lib/compaction_cli.json, the definition the CLI's own
// parser is built from, handed in by the caller.

// One verb of the CLI: its name and the flag each role is spelled with.
export type CliVerb<Role extends string> = {
  readonly verb: string
  readonly flags: Readonly<Record<Role, string>>
}

export type CliVocabulary = {
  readonly instructions: CliVerb<'sessionId' | 'transcriptPath' | 'userInstructions'>
  readonly mark: CliVerb<'sessionId'>
  readonly path: CliVerb<'sessionId'>
  readonly save: CliVerb<'sessionId'>
  readonly unmark: CliVerb<'sessionId' | 'since' | 'until'>
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const pick = <Role extends string>(
  verbs: Record<string, unknown>,
  verb: string,
  roles: readonly Role[],
): CliVerb<Role> => {
  const entry = verbs[verb]

  if (!isRecord(entry)) {
    throw new Error(`compaction_cli.json lacks the ${verb} verb`)
  }

  const flags = {} as Record<Role, string>

  for (const role of roles) {
    const flag = entry[role]

    if (typeof flag !== 'string' || !flag.startsWith('--')) {
      throw new Error(`compaction_cli.json: ${verb} lacks a flag for ${role}`)
    }
    flags[role] = flag
  }

  return { verb, flags }
}

// Reads the text of lib/compaction_cli.json; throws on anything but the expected shape.
export const parseVocabulary = (text: string): CliVocabulary => {
  const parsed: unknown = JSON.parse(text)
  const verbs = isRecord(parsed) ? parsed.verbs : undefined

  if (!isRecord(verbs)) {
    throw new Error('compaction_cli.json lacks a verbs object')
  }

  return {
    instructions: pick(verbs, 'instructions', ['sessionId', 'transcriptPath', 'userInstructions']),
    mark: pick(verbs, 'mark', ['sessionId']),
    path: pick(verbs, 'path', ['sessionId']),
    save: pick(verbs, 'save', ['sessionId']),
    unmark: pick(verbs, 'unmark', ['sessionId', 'since', 'until']),
  }
}

const base = (pluginRoot: string, verb: string): string[] => [
  'python3',
  '-B',
  `${pluginRoot}/lib/compaction_directive.py`,
  verb,
]

export const instructionsArgv = (
  vocabulary: CliVocabulary,
  pluginRoot: string,
  sessionId: string,
  transcript: string | null,
  owner: string | null,
): string[] => {
  const { verb, flags } = vocabulary.instructions
  const argv = [...base(pluginRoot, verb), flags.sessionId, sessionId]

  if (transcript !== null) {
    argv.push(flags.transcriptPath, transcript)
  }
  if (owner !== null) {
    argv.push(flags.userInstructions, owner)
  }

  return argv
}

export const markArgv = (
  vocabulary: CliVocabulary,
  pluginRoot: string,
  sessionId: string,
): string[] => [
  ...base(pluginRoot, vocabulary.mark.verb),
  vocabulary.mark.flags.sessionId,
  sessionId,
]

// Removes the delivered marker of the attempt that ran from `since` to `until` (epoch ms).
export const unmarkArgv = (
  vocabulary: CliVocabulary,
  pluginRoot: string,
  sessionId: string,
  since: number,
  until: number,
): string[] => {
  const { verb, flags } = vocabulary.unmark

  return [
    ...base(pluginRoot, verb),
    flags.sessionId,
    sessionId,
    flags.since,
    String(since),
    flags.until,
    String(until),
  ]
}

export const pathArgv = (
  vocabulary: CliVocabulary,
  pluginRoot: string,
  sessionId: string,
): string[] => [
  ...base(pluginRoot, vocabulary.path.verb),
  vocabulary.path.flags.sessionId,
  sessionId,
]

// The checkpoint block body travels on stdin.
export const saveArgv = (
  vocabulary: CliVocabulary,
  pluginRoot: string,
  sessionId: string,
): string[] => [
  ...base(pluginRoot, vocabulary.save.verb),
  vocabulary.save.flags.sessionId,
  sessionId,
]
