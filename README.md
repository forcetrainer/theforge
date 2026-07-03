# theforge

A token-efficient development flow for Claude Code. Personal fork of
[superpowers](https://github.com/obra/superpowers) v5.1.0, rebuilt for current
models and harness capabilities — roughly the same discipline at a fraction of
the token cost.

## The flow

**Brainstorm → spec → plan → implement**, with approval gates between each stage.
The flow operates in three gears: trivial edits bypass it entirely; changes to an already-specified system take a lightweight conversational gate straight to TDD (gear 2); new architecture invokes the full brainstorm → spec → plan → execute sequence (gear 3).
Brainstorming turns an idea into a user-reviewed spec (`docs/theforge/specs/`), drawing first-class input from `docs/theforge/ideas/` docs.
Specs are living documents: amendments are made in place and logged with a dated changelog entry.
Planning turns the spec into a plan of *what and where* — files, interfaces, test
cases, acceptance criteria, never implementation code (`docs/theforge/plans/`).
Execution runs task-by-task with strict TDD, inline for small plans or via a
Workflow for large ones, with review proportional to risk. A project-memory layer
(`ROADMAP.md`, `DECISIONS.md`, `DEFERRALS.md`) keeps durable context across
sessions: decisions are read before feature builds; agents may defer non-spec
scope but must log why.

## Skills

| Skill | Purpose |
|---|---|
| `brainstorming` | Gear routing, then idea → validated design → spec through batched-question dialogue. Includes the browser-based visual companion for mockups. |
| `planning` | Spec → implementation plan (what/where, no code) → execution. |
| `tdd` | Red-green-refactor discipline, cut to its operational core. |
| `project-memory` | Formats and rules for ROADMAP / DECISIONS / DEFERRALS. |

## Pipeline Scripts

Two Python 3 CLI scripts generate orchestration artifacts: `scripts/extract-brief.py` extracts worker briefs from plans and specs, and `scripts/review-packet.py` generates review packets from task diffs.

## Hooks

One conditional `SessionStart` hook: injects ~60 words of flow context, but only
in repos that use the flow (`docs/theforge/` or `.theforge/` exists). Everywhere
else it emits nothing. Skill discovery doesn't depend on it — frontmatter
descriptions handle that in every session.

## Install

### Claude Code

```bash
claude plugin marketplace add forcetrainer/theforge
claude plugin install theforge@theforge
```

To update later: `claude plugin update theforge@theforge` (or `git pull` in a
local clone).

### Codex CLI

```bash
codex plugin marketplace add /path/to/theforge
codex plugin install theforge@theforge
```

The `SessionStart` hook works on Codex with no extra wiring — the shared
`hooks/hooks.json` schema is compatible and Codex sets `CLAUDE_PLUGIN_ROOT`
for plugin-hook compatibility.

Then copy the tier agents to your Codex config:

```bash
cp codex/agents/*.toml ~/.codex/agents/
```

**On plugin update:** Re-run the copy command above to get the latest agent
definitions. The `.toml` files are not bundled in the marketplace; they live in
the repo and must be synced manually.

**Known Codex caveats:**
- Subagent selection has known regressions in CLI behavior (e.g., custom-agent
  selection broke in v0.137.0 and spawned agents silently inherited the parent
  model). If spawned agents run the wrong model, verify via acceptance commands
  rather than trusting the spawn.
- Worker accumulation: spawned subagents persist in the CLI's agent list, and
  completed workers keep counting against the thread limit
  ([openai/codex#19197](https://github.com/openai/codex/issues/19197),
  [openai/codex#22779](https://github.com/openai/codex/issues/22779)).
  Sequential dispatch (`skills/planning/codex-execution.md`) is the mitigation;
  theforge deliberately builds no cleanup machinery.

## Developing (editing skills)

On the machine where you edit the plugin, point the marketplace at your working
copy instead of GitHub so edits are picked up locally:

```bash
claude plugin marketplace add ~/development/theforge
```

The plugin cache only re-syncs on a **version bump**. After editing anything
under `skills/`, `agents/`, or `hooks/`:

```bash
# 1. bump "version" in .claude-plugin/plugin.json
# 2. then:
claude plugin update theforge@theforge
# 3. restart the session to apply
```

This repo dogfoods its own conventions: design decisions are logged in
`docs/theforge/DECISIONS.md` (read it before changing skill behavior) and
consciously-skipped work in `docs/theforge/DEFERRALS.md`. The presence of
`docs/theforge/` also opts this repo into its own session hook.

## What was cut from superpowers and why

See `docs/notes/superpowers-assessment.md` — the full skill-by-skill assessment.
Headlines: plans no longer embed implementation code (the single biggest token
sink), per-task review is proportional instead of three agents per task, and the
800-word every-session hook injection is gone.
