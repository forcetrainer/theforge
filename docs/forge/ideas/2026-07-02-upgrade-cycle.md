# theforge upgrade cycle — ideation doc

*Input for the official brainstorm. Distilled from a research + design conversation on 2026-07-02
(superpowers v6 analysis, native Claude Code overlap review, Codex CLI capability research).
Direction is agreed; the brainstorm should validate against the codebase, resolve open questions,
decompose into phases, and produce specs.*

## Verdict context (research conclusions, not proposals)

- theforge stays. Native CC covers subagents/review/memory; it does NOT cover staged gates,
  durable spec docs, TDD enforcement, or decision logs. Superpowers v6 rejected: still 14 skills,
  duplicates native harness, no project-memory subsystem. v6 independently converged on theforge's
  combined-reviewer and model-tiering designs — validation.
- Codex CLI now has: SKILL.md skills (agentskills.io standard, `.agents/skills`), TOML subagents
  with `model` + `model_reasoning_effort` (`.codex/agents/`), SessionStart hooks with
  `additionalContext`, MCP, `/plan`. Dual-harness theforge is feasible. Codex caveats: no Workflow
  tool; subagents spawn only on explicit request.

## 1. Three-gear pipeline (proportionality at pipeline level, not just task level)

- Gear 1 — doesn't fire: trivial/mechanical/content. Trigger floors already work; no change.
- Gear 2 — NEW, delta to an already-spec'd system: design presented in conversation, one gate,
  TDD execution. No spec file, no plan file. Documentation = spec amendment (§2) + DECISIONS
  entry only if something was genuinely decided.
- Gear 3 — full pipeline (brainstorm → spec → plan → execute): new systems, new subsystems,
  new architecture.
- Routing test: does the change create new architecture, or operate within existing architecture?
  Size is secondary (10-line change adding a dependency → gear 3; 100-line change filling
  spec-implied behavior → gear 2).
- Escalation tripwires, both mandatory: (a) can't name the owning spec → gear 3; (b) design stops
  fitting in a paragraph mid-conversation → escalate, don't stretch the conversational gate.

## 2. Living specs

- Specs are living per-system documents, not frozen design snapshots.
- Gear-2 change that alters anything a spec asserts → amend that spec in place.
- Dated one-line changelog inside the touched spec: `2026-07-02: sort by division, not date (commit abc123)`.
- No fourth memory file. Surface stays: specs, plans, DECISIONS, DEFERRALS, ROADMAP.
- Self-anchoring rule doubles as the gear-2/3 tripwire (§1).

## 3. Ideation handoff

- External ideation docs (like this one) are first-class brainstorm input. Location:
  `docs/forge/ideas/` or path handed at kickoff.
- Brainstorming treats the doc as pre-answered clarification: read, confirm understanding, flag
  DECISIONS conflicts, skip answered questions, go to approaches.
- Only applies when an idea graduates to "building this" — free-form ideation stays unprocessed.

## 4. Brainstorming flow edits

- Batch 2–3 independent clarifying questions per turn; single-question only when the answer forks
  the design.
- Section check-ins worded as decision digests: what was chosen, what it forecloses, what's assumed.
- Keep step 7 (agent self-review).
- Demote step 8: no mandatory file re-review. Close-out = "spec written to <path> and committed —
  flag changes, otherwise proceeding to planning." Sectioned walkthrough IS the gate.

## 5. Verbosity / style contract

- Specs and plans are agent-consumed. Telegraphic style: bullets, contracts, constraints. Test for
  every sentence: does it carry a requirement, contract, or decision? Cut narration, never
  information — edge-case naming, interfaces, acceptance criteria stay (substance rules unchanged).
- No narrative preamble, no restated codebase context, no justification prose (the why lives in
  DECISIONS).
- Chat output is exception-based: digests surface decisions, assumptions, risks, deviations.
  End-of-plan summaries lead with failures, deviations, deferrals — not achievements.
- Guard: trim toward decision-relevant, not short. Gates that rubber-stamp are dead controls.

## 6. Execution efficiency

- File-referenced briefs: workers get paths + their task block, never pasted content. Brief names
  the exact files: "read these N files and spec §X, nothing else" — kills per-worker codebase
  re-exploration (the bulk of observed 1M+-token phases).
- Context-lifetime rule replaces the ≤3-task inline threshold: inline only when accumulated context
  is an asset (few tasks, later tasks build on seeing earlier work); otherwise dispatch, even for
  serial phases — worker context is born, used, discarded; inline context compounds forever.
- Thin orchestrator: workers return one-paragraph reports; diffs and review packets flow
  reviewer↔file, never through the orchestrating context.
- Plans engineered for width: minimize dependency chains (wall-clock = critical path, not task
  count); prefer decompositions sharing interfaces over sequence.
- Batch all trivial-tier tasks into one forge-light dispatch.
- Reviewer integrity (from v6): reviewers read-only; "can't verify from diff" is a valid verdict;
  implementer rationales cannot suppress findings; orchestrator cannot pre-rate severity.
- One broad final review on the strongest tier for multi-task plans (integration issues per-task
  review can't see). End-of-plan step currently only runs the test suite.
- Rework guardrails, two sentences total: review loops cap at 2 iterations then escalate to user
  with findings; end-of-plan summary reports review-cycle counts per task (this is the entire
  monitoring system).
- Tier-down preference: when interfaces and test cases are fully enumerated, prefer the lower tier.
  Rationale: observed defects are taste-misses (tier-insensitive, unspec'd choices), not bugs;
  review pass backstops real errors.
- Taste-miss capture: recurring "I wouldn't have done it that way" calls become written conventions
  (CLAUDE.md or DECISIONS when architectural) — converts unspec'd losses into spec'd behavior.

## 7. Scripts (exactly two)

- task-brief extractor: task N + referenced spec sections → single brief file.
- review-packet generator: formatted diff + task metadata → file for reviewer.
- Inclusion test: script must eliminate model READING, not model typing. No CRUD tooling for
  memory files — DECISIONS/ROADMAP stay plain markdown edited directly. A third script is a
  signal to stop and re-justify.

## 8. TDD skill trim

- Cut to operational core (~600 words): Iron Law, test-infrastructure gate, verify-red/verify-green,
  final checklist. Drop anti-rationalization armor (rationalization tables, sunk-cost lectures) —
  written for weaker models; loads into every implementing worker on every task.
- Keep testing-anti-patterns.md as on-demand reference (already load-on-need).

## 9. Plan header addition

- Global Constraints block: version floors, dependency limits, naming rules. Prevents mid-plan
  drift; complements existing per-task Interface blocks.

## 10. Dual-harness (Codex) packaging

- Skills port as-is (SKILL.md standard). Ship Codex marketplace manifest
  (`.agents/plugins/marketplace.json` pattern — superpowers v6 precedent).
- Tier agents mirrored as Codex TOML subagents (`.codex/agents/`, `model` +
  `model_reasoning_effort`).
- Session-start hook ported to Codex hooks.json SessionStart (`additionalContext` output; existing
  bash script nearly compatible).
- Execution section becomes harness-conditional: Workflow pipeline on Claude Code; sequential
  explicit subagent dispatch on Codex (no Workflow tool, no auto-delegation).
- Verify skill-path discrepancy in current Codex release (`.agents/skills` vs legacy
  `~/.codex/skills`).

## Explicitly rejected / deferred

- Adopting superpowers v6 wholesale — rejected (heavier, no project memory).
- GH automation — rejected; conventions only (branch per feature, commit per task, PR links spec).
- CRUD script layer for memory files — rejected (flat-file-database trap).
- Spec-first + single digest for gear 3 — rejected; sectioned walkthrough retained (mid-design
  steering worth more than the round trips on genuinely ambiguous work).
- Dropping tier agents for native routing — rejected; frontmatter is the only session-independent
  model+effort pin (existing DECISIONS entry stands).

## Open questions for the brainstorm

- Gear-2 skill mechanics: routing rule lives at top of brainstorming skill? Separate lightweight
  skill? How does the conversational gate hand off to tdd without planning?
- Script location and invocation (plugin `scripts/`? called by Workflow? by orchestrator prompt?).
- Codex packaging: same repo with per-harness manifests, or split?
- Harness-conditional execution wording: one skill with branches vs. harness-notes reference file.
- Tier-down boundary specifics; whether to run the two-run pipeline-depth experiment first.
- Sequencing: likely phases (A) skill-text edits, (B) scripts, (C) Codex packaging — brainstorm
  should decompose and create ROADMAP entries.
