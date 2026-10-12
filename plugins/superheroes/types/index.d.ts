declare module 'claude-code' {
  interface PluginState {
    superheroes: {
      transcriptPath: string | null
      // from session.start: false for `claude -p` and the SDK, where nothing runs automatically
      isInteractive: boolean
      // true from turn.start to the main loop's turn.complete
      isTurnActive: boolean
      // set while an automatic or Now checkpoint runs; the notes as they stood before it
      checkpoint: { startedAt: number; notesBefore: string | null } | null
      // the fill below which a Snooze holds the automatic run back
      snoozeUntilTokens: number | null
      // the last decision's showBand: the band draws from this
      band: boolean
    }
  }
}
