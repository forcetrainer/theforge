# Decisions

## 2026-07-02 — Three-gear pipeline; gear 2 lives inside the brainstorming skill
**Why:** Proportionality at pipeline level: gear 1 = trigger floors (unchanged), gear 2 = delta to an already-spec'd system (conversational design, one gate, straight to tdd — no spec/plan files), gear 3 = full flow for new architecture. Routing test is architectural (creates vs. operates within), not size. Rejected: a separate gear-2 skill (fourth trigger surface that must not mis-fire against brainstorming's) and putting the gear-2 procedure in planning (the gate is design dialogue, which brainstorming owns). Tripwires: no nameable owning spec → gear 3; design outgrows a paragraph → escalate, never stretch the conversational gate.
**Where:** docs/theforge/specs/2026-07-02-phase1-pipeline-skill-edits-design.md, skills/brainstorming/SKILL.md

## 2026-07-02 — Living specs: amend in place, dated changelog inside the spec, no fourth memory file
**Why:** Specs are per-system documents, not frozen snapshots — a gear-2 change that alters what a spec asserts amends that spec, with a one-line dated changelog entry at the spec's end. Keeps the memory surface at specs/plans/DECISIONS/DEFERRALS/ROADMAP; the self-anchoring rule ("which spec owns this?") doubles as the gear-2/3 tripwire.
**Where:** docs/theforge/specs/2026-07-02-phase1-pipeline-skill-edits-design.md

## 2026-07-02 — Specs/plans are agent-consumed: telegraphic style contract; spec re-review demoted
**Why:** Every sentence must carry a requirement, contract, or decision — cut narration, never information (edge cases, interfaces, acceptance criteria stay). Clarifying questions batch 2–3 per turn (single only on design forks); check-ins are decision digests; the sectioned walkthrough IS the approval gate, so the mandatory end-of-brainstorm file re-review is demoted to a close-out notification. Guard: trim toward decision-relevant, not short — gates that rubber-stamp are dead controls.
**Where:** docs/theforge/specs/2026-07-02-phase1-pipeline-skill-edits-design.md, skills/brainstorming/SKILL.md, skills/planning/SKILL.md

## 2026-07-02 — TDD skill cut to operational core (~600 words); anti-rationalization armor dropped
**Why:** The rationalization tables, sunk-cost lectures, and good/bad code examples were written to police weaker models, and the text loads into every implementing worker on every task. Iron Law, infrastructure gate, verify-red/verify-green, and the final checklist carry the entire discipline; testing-anti-patterns.md stays as on-demand reference.
**Where:** docs/theforge/specs/2026-07-02-phase1-pipeline-skill-edits-design.md, skills/tdd/SKILL.md

## 2026-06-10 — TDD infrastructure gate: harness creation is plan-level work, never drive-by
**Why:** Third superpowers sink (after embedded code and 3-agent review): the near-verbatim tdd skill had no trigger floor, so a trivial edit to an untested artifact ran the full Iron Law — observed in Codex as 1.5 hours bootstrapping a test stack for a single 67kb HTML file. The gate keys on sanctioned scope, not harness existence: existing suite → use it, never a parallel stack; approved plan including test setup → build it (new codebases get tests this way, through the plan gate); ad-hoc edit with no harness → ask one question (set up testing vs. verify manually). Trivial mechanical edits don't trigger the skill at all, and the don't-trigger exclusions now live in the frontmatter descriptions — the always-loaded trigger surface — not just the skill bodies.
**Where:** skills/tdd/SKILL.md, skills/brainstorming/SKILL.md

## 2026-06-10 — Session-independent model/effort routing via per-task tiers and three depth-profile agents
**Why:** Subagents inherit the session's model *and* effort by default, so an accidental `/model` switch (or a deliberately cheap session) silently degrades plan execution. The planner tags each task trivial/standard/complex by characteristics — not category — at plan time (re-checked in self-review), and tags route absolutely: forge-light (haiku), forge-standard (sonnet/high), forge-deep (opus/xhigh). Agent frontmatter is the only mechanism that can pin effort, which is why the plugin ships agent definitions despite the lean ethos. Routing is disclosed in the execution offer; the user overrides at the gate. A dedicated router agent was considered and rejected — it has less context than the planner and adds a hop.
**Where:** skills/planning/SKILL.md, agents/

## 2026-06-10 — Plans specify what/where, never implementation code
**Why:** Embedded code was superpowers' single biggest token sink — written without compiler/test feedback, usually wrong by execution time, written twice. The contract rule governs exceptions: signatures, schemas, wire formats, and requirement-algorithms are decisions and belong; bodies and test code are solutions and don't.
**Where:** skills/planning/SKILL.md, docs/notes/superpowers-assessment.md

## 2026-06-10 — Conditional session hook, ~60 words, opt-in by signal
**Why:** Discovery doesn't need a hook (frontmatter descriptions are always loaded); the hook is for continuity only. Signal = `docs/theforge/` or `.theforge/` exists; self-bootstrapping because the first spec creates the signal. Scratch sessions pay zero.
**Where:** hooks/session-start

## 2026-06-10 — Visual companion is display-only with a refinement checkpoint
**Why:** Click-to-select was never used — choices happen in the CLI anyway (~360 lines removed). After the user picks a direction, ask "refine further, or good enough?" — the question hands the user the brake; never build straight from a selection.
**Where:** skills/brainstorming/visual-companion.md

## 2026-06-10 — Proportional review replaces 3-agents-per-task
**Why:** No proportionality was superpowers' second-biggest sink. Trivial tasks: acceptance commands only. Substantive: one combined spec+quality review, second reviewer only on real findings.
**Where:** skills/planning/SKILL.md (Execution)

## 2026-06-10 — Two memory files + roadmap on decomposition; fourth skill owns formats
**Why:** Decisions (read before builds) and deferrals (read when revisiting scope) serve different reads — separate files keep DECISIONS high-signal. Roadmap only when brainstorming decomposes into phases. project-memory skill triggers on ad-hoc "log this decision."
**Where:** skills/project-memory/SKILL.md

## 2026-06-10 — Agents may defer non-spec scope only
**Why:** Gives implementers agency over nice-to-haves/refactors/polish (logged with reasons), while spec'd requirements can only be flagged at the review gate, never silently skipped.
**Where:** skills/planning/SKILL.md, skills/project-memory/SKILL.md

## 2026-06-10 — Dropped: using-superpowers, SDD, executing-plans, worktrees, code-review skills, verification, writing-skills, systematic-debugging
**Why:** Redundant with the current harness (native Workflow tool, worktree isolation, /code-review, evidence-before-claims in system prompts) or marginal on current models.
**Where:** docs/notes/superpowers-assessment.md (full skill-by-skill verdict)
