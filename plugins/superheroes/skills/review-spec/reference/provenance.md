<!-- provenance-version: 1 -->

# Provenance: the Grounding seat & the citation pincer

The review-side detail for issue #517's "provenance pincer" (design authority:
ratified #514 D3). This brief ships now; the **dispatched** Grounding reviewer seat
(roster slot + agent) is wired later by the lens-recast issue (#514 D1). Until then
the deterministic validator (the compile step) plus the mirror-claim rule (carried by
the existing spec panel via the shared `rubric/review-base.md`) carry the pincer.

## The Grounding seat's job

**Uncited-mirror detection.** "This statement smells like it mirrors the repo — it
asserts an existing fact the repo could contradict — but it carries no `[cite: …]`.
Cite it or flag it." The seat's **silence is load-bearing**: when there is nothing
that mirrors the repo, it reports nothing. It does not manufacture findings.

## Two legs, split cleanly

The pincer has two legs, and they must not blur:

- **(a) The deterministic leg — `lib/citation_validator.py`.** Existence only: does the
  cited path (or `path § anchor`) resolve? It is **fail-closed on a dangling citation**
  and emits an `Important` / `Grounding` / `dangling-citation` finding (`citation-NNN`)
  at the spec `file:line`. It knows nothing about whether the source *says* what the
  spec claims. It runs in main context at the review-spec compile step (SKILL §4).
- **(b) The judgment leg — this seat's own.** **Content-match** (does the cited source
  actually *say* what the spec claims?) plus **uncited-mirror detection** (a mirror-fact
  carrying no citation at all). This is verifier judgment; no validator can decide it.

## Mirror-vs-definition test

Not every sentence needs a citation. The test:

- **Mirror-fact** — asserts something about the **existing repo** the repo could
  contradict. NEEDS a `[cite: …]`.
- **Definition** — a **new behavior the spec defines**. NO citation (there is nothing
  yet to mirror).
- The one-question test: **"Could today's repo contradict this sentence?"** YES → cite.
  NO → no cite.

## Noise budget

Citations are **rare** by design — only load-bearing mirror-facts carry one. Most spec
sentences are definitions and correctly carry none. Do not push for citations on
definitional requirements; an over-cited spec is its own failure mode.

## The mirror-claim verification rule

A **mirror claim** — a finding asserting the spec contradicts, misstates, or fabricates
a repo fact — may be emitted **High** confidence only if the reviewer has **read the
cited source** (or, when the spec left it uncited, the repo location it mirrors). Without
that read, emit it **Low** (naming the unread source in `evidence`) or drop it. The
deterministic `citation_validator.py` covers only *existence* (does the cited path/anchor
resolve); whether the source *says* what the spec claims — content-match — is this
verifier judgment.

## Carve-out (do not flag a citation as a defect)

A `[cite: …]` provenance marker is a sanctioned spec construct (CONVENTIONS §3.2), not
leaked implementation detail and not a leftover placeholder — never strip or flag it as
tech-leak, a path reference, or `{{…}}`/TBD noise.

## Citation grammar (illustration only)

`[cite: <repo-relative-path>]` or `[cite: <path> § <anchor>]`. The canonical worked
example lives in `templates/spec.md`, the §11 drift witness; this brief does not re-type it
(a concrete copy here would be an unguarded duplicate — a future rename would leave this
teaching doc silently stale, the §11.2 "new copy invisible to the drift test" hazard). This
grammar is shown here for illustration only; the one machine home for the citation grammar is
`lib/citation_validator.py` — do not re-encode a second machine-parseable literal anywhere else.
