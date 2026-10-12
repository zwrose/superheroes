declare module 'claude-code' {
  interface PluginState {
    superheroes: {
      transcriptPath: string | null
      // from session.start: false for `claude -p` and the SDK, where nothing runs automatically
      isInteractive: boolean
      // true from turn.start to the main loop's turn.complete
      isTurnActive: boolean
      // set while an automatic or Now checkpoint runs (and through the compaction it ends in,
      // `compacting`); the notes as they stood before it: null = no file, absent = unreadable
      checkpoint: { startedAt: number; notesBefore?: string | null; compacting?: boolean } | null
      // the fill below which a Snooze holds the automatic run back
      snoozeUntilTokens: number | null
      // the last decision's showBand: the band draws from this
      band: boolean
    }
  }
}
