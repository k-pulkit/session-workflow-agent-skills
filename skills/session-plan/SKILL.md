---
name: session-plan
description: Creates or resumes a session folder (Journal.md, Plan.md, empty Design.md/DesignDone.md, a .claude/CLAUDE.md index) and breaks the task into phases of typed steps (build / quick / spike), writing them to Plan.md after explicit approval. Checks off finished steps, moves finished phases to PlanDone.md, retypes steps, re-plans after a spike, and owns the Journal.md line format (other skills append their own line in that format directly). Use for "start a session", "plan this feature", "let's plan out X", "revise the plan", "check off step N", "log that", "how am I doing". The only skill allowed to write Plan.md, PlanDone.md or create the session folder.
---

# session-plan

Creates the session (including the empty `Design.md`/`DesignDone.md` scaffolds `session-step` fills in later), turns the task into a typed plan in `Plan.md`, archives finished phases into `PlanDone.md`, and defines the one-line `Journal.md` format every skill appends to. Only this skill writes `Plan.md`/`PlanDone.md`, or creates a new session folder. Shared rules (principles, the build loop, `workflow_next.py`, file ownership, session resolution) are in `~/.claude/CLAUDE.md`.

Every message starts with `[PLAN]`. In an active session, the response opens with the progress banner; the tag follows it.

## Creating or resuming a session

Run the session-resolution steps in `~/.claude/CLAUDE.md`. If none exists:

1. **Single-repo** (cwd is a git repo): one session = one branch, `.claude/sessions/<branch>/`. On `main`/`master`, ask (AskUserQuestion) for a branch type (feature/fix/release/chore) and a short kebab-case name, build `<type>/<name>`, `git checkout -b <type>/<name>`; that becomes the session name.
2. **Multi-repo workspace** (cwd is not a repo, holds repos as subfolders): sessions are flat and feature-named. Ask for a kebab-case feature name and the repo(s)/branch(es) it touches.
3. **Resume check**: if the folder already exists, report what's there (phases/steps done, open) and stop — never overwrite.
4. Otherwise create the folder and:
   - `Journal.md`: `# Journal — <session-name>` + blank line.
   - `Plan.md`: `# Plan — <session-name>`, a `**Repos:**` line (multi-repo, or any single-repo case where the session name doesn't match the branch — name repo path(s) and branch(es)), then `_No plan yet — run session-plan._`.
   - `Design.md` and `DesignDone.md`: the empty scaffolds from "`Design.md`: the record of the step in focus" in `~/.claude/CLAUDE.md`.
   - Update `.claude/CLAUDE.md` (the workspace/project root index, not the session folder): create it if missing, with a short header; append an entry in this exact shape, matching every other entry already there:
     ```markdown
     ### <session-name>
     Repo: `<repo-path>` (branch `<branch-name>`)
     - [Journal.md](sessions/<session-name>/Journal.md)
     - [Plan.md](sessions/<session-name>/Plan.md)
     - [Design.md](sessions/<session-name>/Design.md)
     - [DesignDone.md](sessions/<session-name>/DesignDone.md)
     - `reference.md` may also appear on a `build` step with a hole.
     ```
     Drop the `Repo:` line only in the plain single-repo case (session name matches the branch). Append-only — never touch other sessions' entries.
5. **Codebase guide offer.** If the session names reference-only repos, or one the user hasn't worked in, offer once to run `session-learn` in guide mode (background) for each.
6. Report the structure in a couple of lines, then move to planning (below) if the user wants it now.

## Plan.md on disk

```markdown
# Plan — landing-pipeline

**Repos:** acme/dataops/payments-pipeline (branch feature/x), acme/infra/payments-infra (branch feature/y)

## Phase 1 — Landing bucket
- [ ] Step 1 (payments-infra) [build+hole]: bucket with lifecycle rules — why: first versioned-bucket lifecycle
- [ ] Step 2 (payments-infra) [quick]: SSM param for the bucket name — why quick: one config line

## Phase 2 — Glue job
- [x] Step 1 (payments-pipeline) [build]: job config from the staging account's template — why: known pattern, no hole. Outcome 2026-10-15: 4/4 tests, commit 3f2a1bc
```

Keep the title and `**Repos:**` line. Replace `_No plan yet_` on the first write. Keep the numbering style already in use. On a refinement, edit only the steps that changed; never uncheck a `[x]` without asking.

## Planning process

1. Resolve/create the session (above). Read `Plan.md`; content present → this is a refinement pass.
2. Understand the task: read the relevant code (read-only). Ask (AskUserQuestion) if scope is unclear — do not guess requirements you can ask about.
3. **Ask for the user's split first**: "How would you split this? Rough phases are enough." Draft from their split; if they say "you draft", go ahead.
4. Draft into `<session>/drafts/Plan.draft.md` (see "Drafts go in files, not chat" in `~/.claude/CLAUDE.md`). Each step: small enough for one SPEC→BUILD→REVIEW pass; names its target repo in a multi-repo session; has a **type** (tagged `[build+hole]`, `[build]`, `[quick]` or `[spike]` — the tag itself is what `session-step` reads as `has_logic`) and a **one-line reason**:
   - No behavior change at all, any size → `quick`, reason `no behavior change`. Check this first.
   - Config/docs only, ~30 min → `quick`.
   - Not clear what the right steps are → `spike`, plan only to the end of the spike.
   - Otherwise → `build`. Tag it `[build+hole]` when the user hasn't built this pattern before or it's real logic; tag it plain `[build]` for routine wiring.
   Aim for at least one `build+hole` step per phase that covers new ground. An all-`quick`/no-hole plan: say so, ask if that's intended.
5. **Feedback loop**: the user edits the draft (answers markers, says "reviewed") until explicit approval ("approved", "ship it"). Silence is not approval.
6. On approval, write `Plan.md`, run `code <path>/Plan.md`, then append one `Journal.md` line for the Plan boundary (format below).

**Exploratory work: plan less.** Plan one `spike` step with a time box and one question. Re-plan from its findings after. Do not write 20 steps up front for unclear work.

## Checking off a step

session-step (or the user) asks after a step closes. No approval loop — the SPEC/REVIEW stops already happened.

1. Flip the step to `- [x]` in `Plan.md`, add a one-line outcome (commit hash, or what changed from plan). It stays in its phase for now.
2. Phase still has open steps → confirm in one line, stop.
3. Last open step in the phase → move the whole phase (heading, intro, all `[x]` steps, numbers unchanged) to `PlanDone.md`, appended at the end (create it on first move: `# PlanDone — <session-name>`, one line saying it's the append-only archive). Remove it from `Plan.md`. Append with a heredoc, no Read. On this first move only, also append `- [PlanDone.md](sessions/<session-name>/PlanDone.md)` to this session's entry in `.claude/CLAUDE.md`, right after its `Plan.md` line.
4. Confirm: phase moved, open phases/steps left.

A step closed without being done (dropped, deferred) is flipped to `- [x]` with an outcome saying why. Never delete a step without a trace.

## Retyping a step

The user may retype anytime ("make step 4 build+hole", "drop the hole on step 2"). Change the tag/reason, confirm in one line, journal it as a `note`. An older Plan.md with `learn`/`ship` tags: `learn`→`build+hole`, `ship`→`build` (no hole) — propose this mapping for all untyped/old-typed steps in one message, write after approval.

## Journal.md: the line format every skill uses

`Journal.md` on disk: `# Journal — <session-name>` + blank line, then a flat, append-only, one-line-per-entry list, oldest first, never edited:

```markdown
- [2026-10-15 09:40] plan: Plan approved: 3 phases / 6 steps (4 build, 1 quick, 1 spike) for the landing bucket and 15-min Glue job.
- [2026-10-15 11:40] code: (payments-pipeline) Phase 2/Step 1 [build+hole] done: per-entity extract, row-count guard; 5/5 tests; hole owned (code).
- [2026-10-15 14:05] bugfix: (payments-pipeline) deploy failed: logs in /aws-glue/jobs/error; switched to Python logging. User diagnosed.
- [2026-10-15 14:20] note: Phase 2/Step 2 retyped build (no hole) -> build+hole.
```

Format: `- [YYYY-MM-DD HH:MM] <type>: (<repo>, when needed) <one sentence>`. Types: `plan`, `code` (a step closed — name the step as `Phase N/Step M [type]`, the test result, and whether the hole was owned/waived/assisted), `bugfix`, `spike`, `note`. No line breaks, no sub-bullets, no headings after the title, no trailing bracketed counters on a new line. A line that already ends with one (e.g. `[quiz 2/3]`) is append-only like every other line: leave it exactly as written, never recompute or rewrite it.

Append with a heredoc, no Read:
```bash
cat >> Journal.md <<'EOF'
- [2026-10-15 11:40] code: (payments-pipeline) Phase 2/Step 4 [build+hole] done: per-entity extract with row-count guard; 5/5 tests; hole owned (code).
EOF
```
Get the time with `date '+%Y-%m-%d %H:%M'`. One sentence, the decision not the reasoning.

Boundary lines, appended by the owning skill, once per boundary:
1. **Plan approved** — session-plan, after `Plan.md` is written.
2. **Step closed** — session-step, at `CLOSE`.
3. **Debug resolved** — session-debug, when the cause is found (folds into the step's `code` line if it closes the same turn; otherwise its own `bugfix`/`note` line).

The user can log a `note` or `bugfix` directly anytime (a real deploy result, for example).

## Stats ("how am I doing")

Read (do not write) `Journal.md` across `.claude/sessions/`. Report, in 5-6 lines: steps by type over the last 30 days, holes owned vs. waived/assisted, open `note`s that look like unresolved gotchas. Do not praise or scold — state it. The journal text is the only record; say so plainly if a line is ambiguous rather than guessing counters.

## Examples

**Good:**
```
[PLAN] Your rough split first? One line is fine.
user: infra bucket first, then the glue job, then the schedule
[PLAN] Draft in drafts/Plan.draft.md, built on your split (2 [DECIDE] open). In short:
  Phase 1 — Landing bucket (payments-infra)
   - Step 1 [build+hole]: bucket with lifecycle rules — why: first versioned-bucket lifecycle
   - Step 2 [quick]: SSM param for the bucket name — why: one config line
  Phase 2 — Glue job (payments-pipeline)
   - Step 1 [build]: job config from the staging account's template — why: known pattern, no hole
   - Step 2 [build+hole]: JDBC extract with per-entity error handling — why: new failure modes
  One change from your split: SSM param before the job, since the job reads it. Change anything?
```

**Bad:**
```
[PLAN] Here is the plan: 12 steps, all [build]. Approve and I'll start step 1.
```
Wrong: the user was not asked for their split, nothing says which steps get a hole, and "I'll start" ties plan approval to execution.

## Hard rule

Never touch source/test files, `reference.md`, or `Lessons.md`. Never write a draft into `Plan.md` before explicit approval. Never keep a fully finished phase in `Plan.md`, and never edit or reorder older `PlanDone.md`/`Journal.md` entries.
