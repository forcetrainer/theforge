# Phase 10 — Codex inline execution branch — Implementation Plan

> **For agentic workers:** Execute task-by-task following the Execution section
> of the planning skill, with strict TDD per task. Checkboxes track progress.

**Goal:** Give Codex an inline execution branch — mode chosen before harness — reaching behavioral symmetry with Claude's current inline path.
**Architecture:** Prose/skill-only change to two files. `SKILL.md` restructures the execution offer so the inline/dispatch mode decision precedes any harness branch and describes inline once for both harnesses; `codex-execution.md` adds an inline branch and frames the runner as the dispatch branch. No scripts change; the runner is untouched.
**Tech stack:** Markdown skill documents (`skills/planning/`). No code, no test harness.
**Global Constraints:** No changes under `scripts/`. Runner mechanics in `codex-execution.md` (invocation, exit codes, receipts, `--status`, monitor) stay byte-unchanged — only add the inline framing. Claude inline behavior is unchanged (self-review + over-resolution persist to Phase 11). Spec: `docs/forge/specs/2026-07-17-phase10-codex-inline-design.md`.

### Task 1: SKILL.md mode-before-harness routing
- [x] Done

**Files:**
- Modify: `skills/planning/SKILL.md` (Execution section — restructure the offer to mode-first; add the shared inline execution contract)

**Spec:** Decision, Inline execution contract, Changes

**Interface:** The restructured Execution offer introduces three ordered elements later text and `codex-execution.md` reference: (1) a **mode selection** step (inline vs. dispatch, shared criterion), (2) an **Inline** description applying to both harnesses (TDD, orchestrator self-review, commit per task), (3) a **Dispatch** step whose harness branch routes Claude → Workflow, Codex → `codex-execution.md`.

**Tests:** No automated tests — markdown skill doc; verification is the doc-inspection acceptance below.

**Acceptance:**
- The mode decision (inline vs. dispatch) appears **before** any harness branch; the "Workflow tool unavailable → codex-execution.md" routing no longer sits as a peer of inline/dispatch but inside the dispatch branch.
- Inline is described **once**, applying to both harnesses, and states TDD + orchestrator self-review (no separate reviewer) + commit per task, consistent with the spec's inline execution contract.
- The "inline work runs on the session model; say so in the offer" disclosure is retained.
- Claude inline behavior is not changed — no new gating/disposition language (that is Phase 11).

**Tier:** standard

**Depends on:** nothing.

### Task 2: codex-execution.md inline branch
- [x] Done

**Files:**
- Modify: `skills/planning/codex-execution.md` (add a leading inline-branch section; frame existing runner content as the dispatch branch)

**Spec:** Inline execution contract, Changes

**Interface:** A new leading section stating that when the mode is inline (per `SKILL.md`) the Codex session executes directly — TDD, self-review, commit per task, clean tree — and does **not** invoke the runner; when the mode is dispatch, execution runs through `scripts/forge-run.py` as documented below.

**Tests:** No automated tests — markdown skill doc; verification is the doc-inspection acceptance below.

**Acceptance:**
- `codex-execution.md` states inline runs in-session (not the runner) and points to the `SKILL.md` mode decision; the runner is framed as the dispatch branch.
- `git diff` shows the existing runner content (invocation, exit codes, receipts, `--status`, monitor, resume) is unchanged except for the added inline framing — no edits to runner mechanics.
- Codex inline and Claude inline (Task 1) describe the **same** process, including the over-resolving finding-handling (symmetry bar).

**Tier:** standard

**Depends on:** Task 1.
