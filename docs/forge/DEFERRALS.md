# Deferrals

## 2026-07-11 — review-packet untracked-file handling
**Why:** `git diff <base>` omits untracked files, so a dispatch-path task whose only output is new uncommitted files yields a packet honestly reporting `no changes vs <base>` (exit 0) — thin by workflow, not by parsing. The inline execution path commits per task; the dispatch path doesn't state it. Handling deferred to a docstring note in review-packet.py rather than code: detecting/including untracked files guesses at workflow state the script can't verify.
**From:** parser-family audit after #8/#9 (issue #13)
**Follow-up:** revisit-if-a-dispatch-run-produces-an-empty-packet-for-a-real-change; candidate fix is a stderr warning when `git status --porcelain` shows untracked files

**Why:** The tier-down preference (fully enumerated interfaces + tests → lower tier) ships as two sentences in phase 2 without the proposed two-run A/B experiment; observed defects are taste-misses, which are tier-insensitive, and the review pass backstops real errors.
**From:** docs/forge/ideas/2026-07-02-upgrade-cycle.md (§6 open question)
**Follow-up:** revisit-when-phase-2-execution-shows-tier-related-defects

## 2026-06-10 — Skill test harness
**Why:** Superpowers' `tests/` drives the `claude` CLI to verify skills trigger and behave; valuable for continual refinement but heavy to maintain.
**From:** Initial fork plan
**Follow-up:** revisit-when-first-month-of-real-use-shows-trigger-or-behavior-drift

## 2026-06-10 — systematic-debugging port
**Why:** Current models do hypothesis-driven debugging natively; keep the fork lean.
**From:** Initial fork plan
**Follow-up:** revisit-when-debugging-quality-regresses

## 2026-06-10 — Workflow script template for large-plan execution
**Why:** Planning skill describes the shape (implementer + combined review, pipelined); a reusable template is premature before a large plan actually runs.
**From:** Initial fork plan
**Follow-up:** revisit-when-first-large-plan-executes

## 2026-06-10 — Windows/cross-platform hook shim
**Why:** macOS-only environment; superpowers' run-hook.cmd complexity not needed.
**From:** Initial fork plan
**Follow-up:** drop

## 2026-06-10 — foundation-lacrosse legacy path migration
**Why:** Repo still has `docs/superpowers/`; skills offer a one-time `git mv docs/superpowers docs/forge` when the flow next runs there. In-flight Phase 4a plan executes fine under either regime.
**From:** Initial fork plan
**Follow-up:** revisit-when-flow-next-used-in-foundation-lacrosse
