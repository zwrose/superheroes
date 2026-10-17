// The prompt the mod submits once a compaction it started, or a manual /compact, has completed
// in the main conversation, so the compacted session carries on (#1891). Pure: its one `claude-code` import is a type.

import type { SessionCompactTrigger } from 'claude-code'

/** The one definition of the resume prompt's text, as the owner agreed it (#1891); tests import it. */
export const RESUME_PROMPT =
  'Resume: this session was just compacted. Re-read your resume point (your checkpoint notes, and your charter if this session has one), then continue where you left off.'

/**
 * Whether a completed main-conversation compaction gets the resume prompt: the mod's own
 * (`plugin`) and a manual /compact do; the harness's mid-turn `auto` compaction already
 * carries on, and a `precompute` one is no compaction of the conversation yet.
 */
export const resumesAfter = (trigger: SessionCompactTrigger): boolean =>
  trigger === 'plugin' || trigger === 'manual'
