---
name: planning
description: Use after a spec is approved, or for any multi-step implementation task, to write an implementation plan — and when executing an existing plan from docs/theforge/plans/.
---

# Planning

**Trigger:** a spec was just approved (handoff from brainstorming); the user asks to plan a multi-step task; or you're executing an existing plan from `docs/theforge/plans/`. **Don't trigger:** non-trivial creative work with no spec yet — brainstorm first.

A plan specifies **what and where — never implementation code**. It locks in design decisions: files touched, interfaces and signatures, the test cases to write, acceptance criteria, ordering. The code itself is written once, during execution, with compiler and test feedback. Writing it earlier in the plan means writing it twice and getting it wrong the first time.

Plan prose is agent-consumed, not narrative: apply the brainstorming skill's sentence test — every sentence carries a requirement, contract, or decision, else cut.

**Save to:** `docs/theforge/plans/YYYY-MM-DD-<feature>.md` and commit. (User/project preferences for plan location override this default.)

**Before writing:** read `docs/theforge/DECISIONS.md` if present — the plan must not contradict logged decisions; surface conflicts to the user. Code in the plan follows the same contract rule as specs: signatures, schemas, and wire formats are decisions and belong; bodies, test code, and boilerplate are solutions and don't.

## Scope

One plan per subsystem. Each plan must produce working, testable software on its own. If the spec covers multiple independent subsystems, split into separate plans.

## File structure first

Before defining tasks, map which files will be created or modified and what each is responsible for — one clear responsibility per file, smaller focused files over large ones, split by responsibility not technical layer. In existing codebases follow established patterns. This map drives the task decomposition.

## Plan header

```markdown
# [Feature] Implementation Plan

> **For agentic workers:** Execute task-by-task following the Execution section
> of the planning skill, with strict TDD per task. Checkboxes track progress.

**Goal:** [one sentence]
**Architecture:** [2–3 sentences]
**Tech stack:** [key technologies/libraries]
**Global Constraints:** [version floors, dependency limits, naming rules]
```

Omit `**Global Constraints:**` entirely when the plan has none — never an empty block.

## Task structure

```markdown
### Task N: [Component]
- [ ] Done

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py` (what changes)
- Test: `tests/exact/path/to/test.py`

**Interface:** signatures, types, and names this task introduces or changes —
declarations only, no bodies. Later tasks must use these exact names.

**Tests:** the list of test cases, by behavior — "rejects empty email",
"retries 3 times then throws". Descriptions, not code.

**Acceptance:** the commands to run and what must pass.

**Tier:** trivial | standard | complex.

**Depends on:** Task M, or nothing.
```

No placeholders at this level: never "TBD", "handle edge cases", or "add validation" — *name* the edge cases and the validation rules. The line is: name **what** to handle; don't write **how**.

**Tier** is judged by what the task demands, not its category: a mechanical edit with no design content is trivial; a well-specified change with a clear test path is standard; novel design, cross-file impact, or ambiguous spec territory is complex. A "code implementation" task that's really one field threaded through one call site is trivial, whatever its name. The tier drives model routing and review depth at execution.

## Self-review

Check the finished plan against the spec with fresh eyes: every spec requirement maps to a task (add tasks for gaps); nothing contradicts DECISIONS.md; names and signatures are consistent across tasks; dependency order is sound; no placeholder language; each tier holds in both directions — would a smaller model handle this cleanly, and does any "trivial" task hide a design decision? Fix inline and move on. Log any design decisions the plan locked in to DECISIONS.md.

## Execution

Each task's tier routes to a shipped worker agent. Routing is absolute — the session's model and effort settings never apply to subagent execution:

| Tier | Agent | Profile |
|---|---|---|
| trivial | `theforge:forge-light` | haiku |
| standard | `theforge:forge-standard` | sonnet · high effort |
| complex | `theforge:forge-deep` | opus · xhigh effort |

Offer the user the choice, with a recommendation by size, and **disclose the resolved routing** in the offer (e.g. "4 standard → forge-standard, 1 complex → forge-deep") so tiers can be overridden before anything runs:

- **Small plans (≤3 tasks, or low-risk throughout): inline.** Execute task-by-task in this session using the **tdd** skill — inline work runs on the session model; say so in the offer. Check off steps, commit per task.
- **Larger plans: a Workflow script.** One worker per task, spawned as the task's tier agent via `agentType` (give it the task text, spec path, relevant DECISIONS.md content, the deferral rule below, and TDD discipline), pipelined so independent tasks overlap and `Depends on` is respected. After each standard or complex task, **one combined review** by `theforge:forge-standard` covering spec compliance and code quality together; dispatch a second reviewer on `theforge:forge-deep` only if the first finds substantive issues, and loop the implementer until clean.

**Proportional review:** trivial-tier tasks skip subagent review entirely; passing their acceptance commands is verification enough. Standard and complex tasks get the combined review.

**Deferral rule:** implementers may skip **non-spec scope** (nice-to-haves, refactors, edge polish) with a `docs/theforge/DEFERRALS.md` entry explaining why (formats: project-memory skill). Spec'd requirements are never silently deferred — flag them at the review gate. List all new deferrals in the end-of-plan summary.

Plans written before this fork (embedded implementation code, subagent-driven-development headers) execute fine under this section: treat embedded code as a suggestion to re-derive via TDD, not text to paste.

When all tasks are done: run the full test suite, mark the roadmap phase `done` if a roadmap exists, then follow the branch-finishing preferences in CLAUDE.md. The end-of-plan summary leads with failures, deviations, deferrals — not achievements.
