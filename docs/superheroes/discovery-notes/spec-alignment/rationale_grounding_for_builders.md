# Rationale grounding for builders: does telling them "why" improve decisions when the spec is silent?

Light research pass, 2026-09-21. ~12 searches, ~10 raw page reads.

## Takeaway

Better supported than "just plausible," but the support is thin and indirect, and the one rigorous
test on AI agents is unencouraging within its own scope. For **human builders** there is a real
measured result — a 2006 controlled experiment found decision *correctness* improved when rationale
documentation was available and requirements changed — but it is a single small student experiment;
the rest of the design-rationale literature is argued, not measured. For **personas**, the measured
evidence shows they change what builders *believe* about users (81% of 31 professionals revised
preconceptions); a systematic review of 95 persona papers concludes the link from personas to design
*outcomes* is largely unquantified. For **AI agents**, the only rigorous independent study (ETH
Zurich) found repo-level context files produce no significant change in task success while adding
20%+ cost — but it measured well-specified bug-fix tasks with hidden tests, i.e. exactly the case
where the spec is *not* silent, so it doesn't test this question. The one study that does is
vendor-authored on a benchmark its authors designed to show a gap, and they say so. Net: **adding
product-level grounding is a reasonable bet with a plausible mechanism and no direct disconfirming
evidence, but nobody has measured it independently.** The strongest actionable signal is a negative
one: generic repository *overviews* demonstrably don't help agents, while *instructions* are
reliably followed — so a grounding doc should carry decisions and constraints, not narrative.

## Cited Findings

### Human builders — design rationale

**1. Recorded design rationale improved decision correctness under requirement change; efficiency unchanged.**
Falessi, Cantone & Becker, "Documenting design decision rationale to improve individual and team
design decision making: An experimental evaluation," ISESE 2006. Controlled experiment, 50
post-graduate students; for both individual and team decision-making, effectiveness (correctness of
decisions in the presence of requirement changes) significantly improved when the rationale
documentation technique was available; efficiency was unaltered.
URL https://dl.acm.org/doi/10.1145/1159733.1159769 · 2006 · Tier: **measured result** (small n, students)
Verification: **[UNVERIFIED: raw-page read failed]** — ACM DL and ResearchGate both blocked direct
fetch (bot challenge). Rests on two independently-worded search summaries agreeing on the specifics.
Treat the direction as credible, exact wording as unconfirmed. A follow-up exists — Falessi, Briand,
Cantone, Capilla & Kruchten, "The Value of Design Rationale Information," TOSEM 22(3), 2013,
https://dl.acm.org/doi/10.1145/2491509.2491515 — on *which* rationale is worth documenting per
activity; I could not obtain its full text in this pass.

**2. "Intent debt" — absence of externalized rationale — named as a risk AI agents amplify.**
Margaret-Anne Storey, "From Technical Debt to Cognitive and Intent Debt." Verbatim from the abstract:
"intent debt refers to the absence or erosion of explicit rationale, goals, and constraints that
guide how humans and agents evolve the system." The paper "proposes a Triple Debt Model" and
"surface[s] points of debate for practitioners."
URL https://arxiv.org/abs/2603.22106 (v4) · also ACM Queue https://queue.acm.org/detail.cfm?id=3807966
· Mar–Apr 2026 · Tier: **opinion / position paper** (proposes a model; no measurement)
Verification: read the arXiv abstract page raw via curl. Respected empirical-SE author, but argued, not measured.

### Human builders — personas

**3. Personas measurably changed what professionals believed about users — but the outcome measured is belief, not what got built.**
Salminen, Jung, Chowdhury, Ramirez Robillos & Jansen, IJHCS 2021. Within-participant experiment, 31
professionals. Verbatim from the authors' own summary: "81% of the participants changed their
preconceptions of the customers, and 94% of the participants maintained or increased the accuracy of
their perceptions of the customers after engaging with the personas. Moreover, the confidence of the
participants in their responses increased. However, two partici[pants did not change]…"
URL https://persona.qcri.org/blog/the-ability-of-personas-to-alter-incorrect-preconceptions-about-customers/
· paper https://www.sciencedirect.com/science/article/abs/pii/S107158192100063X · 2021 ·
Tier: **measured result** (small-n; DV is perception accuracy, not design output)
Verification: fetched the lab page raw via curl, grepped the verbatim sentence. Paywalled primary not read.

**4. Systematic review of 95 persona-application papers: impact on design outcomes is essentially unquantified.**
Salminen, Guan, Jung & Jansen, CHI 2022. Verbatim: "The conclusion from our findings is that while
personas intuitively make sense, quantifying their precise impact remains a scientific challenge."
On the evaluation studies reviewed: "the direct ties to personas themselves are often questionable."
One of five named challenges in persona research is "lack of robust evaluation methods."
URL https://dl.acm.org/doi/10.1145/3491102.3517589 · open copy
https://osuva.uwasa.fi/bitstreams/1e9a1d39-6bab-414e-a097-16e9abee0f1f/download · 2022 ·
Tier: **measured result** (systematic review), reporting an evidence *gap*
Verification: downloaded the PDF, extracted text with pypdf, read the passages directly.

**5. Long-standing critique: personas cannot be verified or falsified.**
Chapman & Milham, "The Personas' New Clothes," HFES 2006. Argues there is no reliable procedure from
data to a specific persona, so it is not subject to reproducible validation, and it is hard to know
how many real users a persona represents.
URL https://www.researchgate.net/publication/253427652 · 2006 · Tier: **opinion / methodological argument**
Verification: **[UNVERIFIED: search-snippet only]** — ResearchGate blocked fetch; thrust well
established in the literature, exact wording unconfirmed.

### AI coding agents

**6. Counter-evidence, and the most rigorous study here: repo-level context files did not improve task success and cost 20%+ more.**
Gloaguen, Mündler, Müller, Raychev & Vechev (ETH Zurich SRI Lab + LogicStar.ai), "Evaluating
AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?" Across SWE-bench and a new
CTXbench (real issues from repos shipping developer-written context files), four agents (incl. Claude
Code, Codex, Qwen Code) and several models. Numbers read from the paper:
- LLM-generated context files: resolution down 0.5% (SWE-bench) / 2% (CTXbench); p = 0.87 and 0.37 —
  "no significant effect on performance."
- Developer-written: "improve agent performance by 2.4% on average (p=21%)", beating LLM-generated (p=3.8%).
- Cost: "+20% and 23% on average", p < 0.001%.
- Mechanism split: "instructions provided in context files are well followed" (`uv` used 1.6×/instance
  when mentioned vs <0.01× when not) but "they do not provide effective repository overviews."
- Conclusion: context files "should only contain specific additional instructions beyond what is
  already available in the codebase."
URL https://arxiv.org/abs/2602.11988 (v2) · full text https://arxiv.org/html/2602.11988v2 ·
submitted Feb 2026, revised Jun 2026 · Tier: **measured result** (large, independent)
Verification: fetched abstract page and full HTML raw via curl; read results, ablations, limitations directly.
**Scope caveat that matters here:** the DV is task resolution on GitHub issues with hidden tests — the
spec is *precisely specified*, so this cannot detect value from context that only pays off when the
spec is silent. Authors' own limitations note Python-only scope and that code efficiency and security
were not measured.

**7. When requirements are ambiguous, agents degrade and silently diverge — the mechanism grounding is meant to address.**
Yang et al., "Clarity Is Not Assumed" (Orchid benchmark, 1,304 function-level tasks, four ambiguity
types). Verbatim: "ambiguity consistently degrades the performance of all evaluated LLMs, with the
most pronounced negative effects observed in highly advanced models. Furthermore, we observe that
LLMs frequently produce functionally divergent implementations for the same ambiguous requirement and
lack the capability to identify or resolve such ambiguity autonomously."
URL https://arxiv.org/abs/2604.21505 · Apr 2026 · Tier: **measured result** (benchmark study)
Verification: read the arXiv abstract page raw via curl. A search summary attributed a ">30% drop for
GPT-4" to this paper; that number was **not** in the abstract I read — do not cite it.
Caveat: establishes ambiguity hurts; does not test whether product grounding is a good way to reduce it.

**8. The only direct test of product context on agent decisions — and it is vendor-authored.**
Dillon & Varanasi (both affiliation: **Brief**), "Context-Augmented Code Generation: How Product
Context Improves AI Coding Agent Decision Compliance by 49%." 8 tasks, 41 weighted decision points,
3 runs per configuration (48 runs), Claude Opus 4.6 planning + Sonnet 4.6 coding. Augmented config
(Brief's retrieval of "recorded decisions, persona pain points, customer signals, and competitive
intelligence") hit 95% decision compliance vs 46% baseline. Most useful number: baseline scored "100%
compliance on decisions visible in the codebase and 0–33% on decisions requiring product context."
Authors' own limitations, verbatim: the decisions and tasks "were designed by the authors to create a
measurable gap between configurations … the benchmark measures a best-case scenario"; "Partially
circular evaluation … it effectively asks 'does retrieval of external decisions improve adherence to
external decisions?'"; "No stronger baselines … the paper cannot attribute the full improvement to
Brief's specific product-context retrieval rather than to the general value of structured planning.
We view this as the most important limitation"; "Small scale. Eight tasks, one repository, and one
model family"; "Single human reviewer."
URL https://arxiv.org/abs/2605.08112 · full text https://arxiv.org/html/2605.08112v1 · 27 Apr 2026 ·
Tier: **vendor claim** (unusually candid; benchmark and PRs released for reproduction)
Verification: read abstract page and full HTML raw via curl; quoted limitations verbatim.

**9. Anthropic's own CLAUDE.md guidance recommends technical context only — not product rationale.**
"Using CLAUDE.MD files: Customizing Claude Code for your codebase." Recommended contents, verbatim:
"common bash commands, core utilities, code style guidelines, testing instructions, repository
conventions, developer environment setup, and project-specific warnings," plus a project summary /
directory map, custom tooling, and standard workflows. Guidance is to "keep this file concise," and:
"One option: break up information into separate markdown files and reference them inside the
CLAUDE.md file." No mention of personas, target users, product rationale, or non-goals.
URL https://claude.com/blog/using-claude-md-files · 2025-11-25 · Tier: **vendor guidance**
Verification: fetched raw via curl, read the full text.

**10. GitHub Spec Kit's "constitution" is a real project-level grounding pattern — but its template is engineering governance, not product rationale.**
`constitution.md` is created once per project and dependent templates "read the constitution at
runtime." The shipped template's example principles are Library-First, CLI Interface, Test-First
(NON-NEGOTIABLE), Integration Testing, Observability/Versioning/Simplicity, plus slots for
"Additional Constraints, Security Requirements, Performance Standards" and "Development Workflow,
Review Process, Quality Gates."
URLs https://raw.githubusercontent.com/github/spec-kit/main/templates/constitution-template.md and
.../templates/commands/constitution.md · retrieved 2026-09-21 (main) ·
Tier: **practitioner artifact with specifics**
Verification: fetched both raw files via curl and read them.

**11. Practitioner report that does advocate the "why," with a caution attached.**
Addy Osmani, "How to write a good spec for AI agents." Verbatim: "Writing it like a PRD ensures you
include user-centric context ('the why behind each feature') so the AI doesn't optimize for the wrong
thing." And: "A high-level spec for an AI agent should focus on what and why, more than the
nitty-gritty how." Counterweight from the same post, verbatim: "as you pile on more instructions or
data into the prompt, the model's performance in adhering to each one drops significantly. One study
dubbed this the 'curse of instructions'"; "small, focused context beats one giant prompt"; "For
relatively simple, isolated tasks, an overbearing spec can actually confuse more than help."
URL https://addyosmani.com/blog/good-spec/ · undated on page, retrieved 2026-09-21 ·
Tier: **practitioner report with specifics** (experience-based, no measurement)
Verification: fetched raw via curl, read the relevant passages.

## Counter-evidence summary (where more context hurt)

- **Measured:** finding 6 — context files cost 20–23% more with no significant success-rate gain;
  repository *overviews* specifically failed to help agents find relevant files faster, and one model
  wasted steps re-reading a file already in its context. LLM-*generated* context files trended
  negative and were significantly worse than developer-written ones (p=3.8%).
- **Measured, indirect:** the "curse of instructions" effect Osmani cites (instruction-following
  degrades as instruction count rises) — underlying study not verified in this pass.
- **Design implication:** the split between "instructions are followed" and "overviews are ignored"
  is the most actionable thing here. A grounding doc that reads as narrative background is the
  failure mode; one that reads as decisions, constraints and non-goals is the mode that lands.

## Gaps — looked for, did not find

- **No independent study varying product-level context (principles, personas, non-goals, rationale)
  for coding agents and measuring output quality.** The only direct test (finding 8) is by the vendor
  of the product under test, on a benchmark its authors built to show a gap, with no spec-only or
  "read the ADRs" intermediate baseline — an omission the authors name as their top priority.
- **No study isolating *persona* context for agents.** Persona material was bundled into the Brief
  condition alongside decisions, customer signals and competitive intel, so its contribution is
  unattributable.
- **No measured evidence that personas change what gets built** (human or agent). Finding 3 measures
  belief accuracy; finding 4 says the outcome link is unquantified across 95 papers.
- **Could not read the two core design-rationale primary sources.** ACM DL, ResearchGate and
  Academia.edu all blocked direct fetch; the Simula PDF link for the 2013 TOSEM paper returned HTML.
  Finding 1 is therefore search-summary-grade only.
- **No evidence on the specific hypothesis in question** — that grounding helps *specifically where a
  per-spec document is silent*. Every measured study either supplies a precise spec (finding 6) or
  seeds the gaps deliberately (finding 8). The natural experiment — same team, same specs, grounding
  doc on vs off, measured on choices the spec didn't cover — has not been run publicly.
- **Did not search:** OpenAI's project-level context guidance, or the requirements-engineering
  goal-model literature (i*, KAOS), which may carry older measured results on rationale traceability.
