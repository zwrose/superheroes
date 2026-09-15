# The prose standard

How process prose is written in this plugin: the charters, the rubric, the reference docs, the
founding documents, and the PR bodies and commit messages that land them. Read it before you write
or review any of those. This file is reference. Its rules are for lookup, each with its reason
where the rule is one a careful writer would not guess. A reviewer cites a rule by its heading. A reviewer cites this file, and a writer works from it. Nothing checks it
mechanically, and no document claims to follow it.

The standard has two layers. The document layer decides what a document holds and where each part
sits, because an agent runs the document the same way every time. The sentence layer decides how
each sentence reads, because a tired reader gets one pass. Apply both. When a rule makes a sentence
worse, fix the sentence another way or leave it alone. The rules serve the reader.

## Three rules above the rest

- Cut every word that does no work. If the sentence survives without the word, the word goes.
  "In order to" is "to". "It is important to note that" is nothing.
- Use the short, everyday word. "Use", not "utilize". "Help", not "facilitate". A long word buys
  its length with precision or it goes.
- Write the real name. The codebase is the word list: the symbol, the file, the flag, the command,
  never a description of it. When the thing is a rule, its name is its glossary slug.

## The document layer

### Context pointers

A context pointer is a line an agent holds in context that names material outside it and says when
to reach for it: a skill description, a charter line that names a reference doc, a "read this
when" sentence. The pointer's wording, not its target, decides whether the agent reaches the
material. A must-have target behind a weak pointer is a variance bug. Sharpen the wording first.
Inline the material only when sharpening fails.

A pointer does two jobs: it says what the material is, and it lists the branches that should send
the reader there. Every word of an always-loaded pointer costs on every turn, so:

- Put the triggering word first.
- Name one trigger per branch. Synonyms for one branch are one branch written twice.
- Cut identity the body already carries.

### The two loads

Every document and pointer spends one of two budgets. Context load is the cost of always-loaded
material on the agent's window: a charter line, a skill description, anything present every turn
whether or not it fires. Cognitive load is the cost on the person: which documents exist and when to
reach for each. The person is the index. Cognitive load is the price of human agency, so spend it
where judgment matters and remove it where it does not. Material behind a pointer escapes context
load at the price of the pointer's own line.

### Hierarchy and disclosure

A document holds steps (what the agent does, in order) and reference (definitions, rules, and facts
consulted on demand). Place each piece on the hierarchy by how immediately the agent needs it:

1. In-file step: what the agent does, in order. The primary tier.
2. In-file reference: consulted on demand. A flat set of peers is a fine shape, not a smell.
3. Disclosed reference: a separate file reached by a pointer, loaded only when the pointer fires.

Inline what every branch needs. Push behind a pointer what only some branches reach. When steps
share a file with reference that should have been disclosed, the reference buries the steps and
attending to them becomes a coin flip. Sprawl is the failure mode: a document too long even when
every line is live. The cure is the same ladder: disclose reference, and split by branch or
sequence so each path carries only what it needs.

Keep a concept's definition, rules, and caveats under one heading, so reading one part brings its
neighbors. Scattering fragments one meaning across many places. Duplication repeats one meaning in
two. Both cost.

### Completion criteria

End every step on a completion criterion: the condition that tells the agent the step is done. Two
properties make it work. Clarity: the agent can tell done from not done, so "understanding
reached" fails and "every modified model accounted for" passes. Demand: how much the criterion
requires, which drives the digging the agent does without a separate step for it. Flat reference
carries the same bar: "every rule applied" binds a rule set the way "every step done" binds a
sequence. When a vague criterion invites the agent to rush toward the visible next steps, sharpen
the criterion first. Split the sequence across a real context boundary only when sharpening fails
and you have seen the rush.

### Leading words

A leading word is a compact concept the model already holds and thinks with while it runs the
document: lesson, tracer bullet, red. Repeated as a token and never as a sentence, it anchors a
region of behavior in the fewest tokens. In the body it steadies execution. In a pointer it
steadies invocation, because the same word in your prompts, docs, and code links them. Prefer a
pretrained word to a coined one: a coined word recruits no prior and costs its definition. Hunt
for the passage that spells out a triad three times, or spends a sentence gesturing at one idea,
and collapse it.

State the target behavior. A prohibition drags the forbidden behavior into context and makes it
more available, so write "one-line comments" and the ban goes unspoken. A prohibition earns its
place only as a hard guardrail you cannot phrase positively, and even then it sits beside the
positive instruction so attention lands on what to do.

### Pruning

- One source of truth per meaning: change the behavior in one place. A drift-tested copy is not a
  second home.
- The environment is a source of truth too: config files, the directory layout, a command's help
  output. A document that restates it is a cache, worth keeping only when the lookup is expensive.
  Cache what the agent cannot find by looking: the unwritten convention, the reason behind a choice,
  the gotcha no config confesses.
- Check every line for relevance: does it still bear on what the document does? Stale layers settle
  because adding feels safe and removing feels risky. Shorter documents stay relevant longer.
- Apply the no-op test sentence by sentence: does this change behavior against the default? The
  test is model-relative, so settle a disagreement by running the document, not by debate. When a
  sentence fails, delete the sentence. A rule a script already enforces is not also written as prose.
- Put stable text first and volatile text last, so the part that changes does not invalidate the
  part that does not.

## The sentence layer

### Pick the mode first

One document, one mode. Two questions pick it: does the content serve action or understanding, and
does it serve learning or work?

- Reference: understanding, for work. Describe and only describe. Dry, complete, sure. State
  facts, options, limits, and errors with no hedging and no opinion. Mirror the structure of the
  thing described. Generate from code where possible, so the text stays true.
- Procedure (how-to): action, for work. Solve a problem a person has. Assume competence. Steps
  only, in order, with the condition in front of each step. Name it by the task.
- Explanation: understanding, for learning. One bounded topic, readable away from the product.
  Anchor on a real "why" question. Give the design decision, the constraint, the alternative.
  Opinion is allowed here and nowhere else.
- Tutorial: action, for learning. Rare in this plugin. The learner's success is your job, and every
  step shows a visible result.

Split and link where modes meet. A reference table inside a procedure, or an argument inside a
reference, is a document that has not decided what it is.

### Write to the reader

- Address the reader as "you", in the present tense. Use "will" only for what happens later.
- Say who does what. "The launcher records the pid", not "the pid is recorded". Passive is fine
  only when the actor is unknown or beside the point.
- Write instructions as commands, with the condition in front: "To relaunch, reap the worktree
  first." The reader skips what does not apply.
- Put the common case first and the exception after.
- Sound like a knowledgeable colleague. No buzzwords, no "please" in instructions, and never
  "simply", "easy", or "quickly" in a procedure.
- Link with words that say where the link goes. Prefer a sentence of context on the page to a link
  off it.
- Headings carry the point, in sentence case. A task heading is a verb phrase, and a concept heading is
  a noun phrase. One h1 per page, no skipped levels.
- Numbered lists for sequences, bullets for everything else, parallel items, a full sentence to
  introduce a list. Code in code font. Serial commas.

### One thought per sentence

- One instruction per sentence, and one thought per sentence everywhere else. Split an instruction
  longer than about twenty words and any other sentence longer than about twenty-five.
- Put the warning or the condition before the step it guards.
- Keep "the" and "a". "Remove backup file" reads two ways. "Remove the backup file" reads one.
- Give each word one meaning and one job, then keep it. One word per action, everywhere.
- Prefer a plain verb to an "-ing" form, because "-ing" words take too many grammatical jobs.

### One reading per sentence

- Keep "only" and "not" next to the word they change.
- Break up long noun strings into clauses.
- Make every "it", "they", and "this" point at one obvious thing. Repeat the noun when in doubt.
  Never point "this" or "which" at a whole clause.
- Give every clause its verb. Keep the small words that show structure: "that", the repeated
  article in a series, "both … and", "either … or".
- Say which parts "and" or "or" joins when a sentence can group two ways.
- Use periods, not semicolons. Where a thought needs separating, end the sentence. Make text in
  parentheses a full grammatical unit or its own sentence. Write "a, b, or both", never "a/b".
- Call each thing by one name, everywhere. A doc that says "the gate", "the check", and "the
  guard" for one thing teaches three things.

### Rhythm and voice

A document can obey every rule above and still read machine-written. Mix sentence lengths on
purpose: short sentences land a point, and a longer one carries a fact with its condition. Split the
sentence that carries two thoughts, and keep the long one that carries one. Have a view where the mode
allows it, which is explanation, where you weigh a trade-off and say what you make of it. Be specific over sterile:
not "schema changes can cause issues" but "a column rename fails the build". Ask of every sentence
what it tells the reader to do or know, and write that. A sentence that could sit unchanged in
another project's docs says nothing about this one.

### Patterns that read as generated

Remove these on sight. Each entry names the pattern and the fix.

- Puffery ("pivotal", "testament to", "landscape", "tapestry", "underscore", "delve",
  "crucial", "enhance", "foster", "showcase", "vibrant"): state what happened, in plain words.
- Fancy ways to say "is" ("serves as", "stands as", "boasts", "features"): say "is" or "has".
- "Not just X, but Y": state the point.
- Forced groups of three: use the natural number.
- Synonym cycling for one thing: pick one name and repeat it.
- Vague attribution ("experts believe", "it is widely held"): name the source or delete.
- Filler ("in order to", "due to the fact that", "it is important to note"): the short form or
  nothing.
- Stacked hedges ("could potentially possibly"): one hedge, or none.
- Adverbs propping a weak verb ("significantly improves"): the measured delta, or a stronger verb.
- Passive voice with a known actor: name the actor.
- Em dashes and dash substitutes: end the sentence, or use a comma. Colons only before a list or
  an example, never as a mid-sentence connector.
- Bold on every proper noun, or a bold label and colon that restate the line ("**Speed:** speed
  improved"): plain prose. A bold lead-in that ends in a period and is followed by new detail is
  fine.
- Title case headings, decorative emoji, curly quotes: sentence case, none, straight quotes.
- Chatbot phrases ("I hope this helps", "great question"): remove.
- Generic conclusions ("the future looks bright"): the specific plan or fact.

Metaphor is allowed when it is the shortest true word for the thing and the document says what it
means the first time. A named pattern the reader can look up is a leading word, not slop.

## Shipped surfaces carry no project provenance

A surface that ships in the plugin, or is a founding document (PHILOSOPHY, CONVENTIONS,
README, the rubric, the glossary, the charters and their reference docs) states its rules and
definitions and stops. It does not say where a rule was decided: no spec-section numbers, no
sitting or checkpoint codes, no dated rulings or renames, no issue or PR numbers except a pointer
the project's configuration supplies, and none of one project's own history (its measurements,
its accounts, its epic's work items). A reader outside the project has none of that record and
cannot use it. A reader inside it finds the record where it lives: the PR body that landed the
text, the spec's amendments log, and the ledger. The reason behind a counter-default rule may stay
beside the rule, because the reason helps every reader. Where the rule was decided may not.

## Rationale, prohibitions, and claims

- Rationale stays on counter-default rules: the rule a reader would not guess gets its reason in
  one sentence, and the rule every careful engineer already follows gets none.
- Trim for context cost only. Shortening a document that is already read once is churn, and
  rewording an unchanged sentence between edits costs the same way.
- No document claims adherence to a style as a property of itself. The text is the evidence.

## Sources

This file ports two MIT-licensed skills into one reference: mattpocock's writing-for-agents (the
document layer) and backnotprop's pstack technical-writing and unslop (the sentence layer, minus
unslop's ban on abstract metaphor). The technical-writing rules draw in turn on Diátaxis, the Google
developer documentation style guide, ASD-STE100, and Kohl's Global English Style Guide.
