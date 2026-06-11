# Decisions

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
