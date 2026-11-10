---
name: session-flow
description: Re-anchors the main agent on the session workflow. Default mode is read-only — re-derives the current stage of the active session from Plan.md, Journal.md, git status and workflow_next.py, prints the progress banner, lists any drift (edits with no SPEC, a missed journal line, a trace question skipped silently), and names the next move and the skill that owns it. Also: help mode (which skill fits a situation, read-only), tidy mode (background scan + archive-only cleanup of one session folder, after a zip snapshot), and starts the local /session-ui dashboard. Use for "/session-flow", "where are we", "back to the process", "/session-help", "which skill should I use", "/session-tidy", "tidy the session", "/session-ui", "open the UI".
---

# session-flow

The reset button, the skill picker, the folder tidy-up, and the UI launcher — four modes in one skill because none of them move a step's stage or write source/Plan/Journal content; the one exception (tidy) writes only archive moves, its `MANIFEST.md`, its own draft, and one Journal `note` line. Rules it checks against are in `~/.claude/CLAUDE.md`.

In an active session the response opens with the banner, then `[FLOW]`. `help` mode may run with no session in focus, so has no banner to show.

## Hard rule

**Read-only in `flow` and `help` modes.** Never Edit or Write anything there, and never invoke another skill on your own — name the next move, the user starts it. `tidy` mode may move files to `archive/` after explicit approval and a zip snapshot (see below); it never edits an owned file. `ui` mode starts a process; it writes nothing itself.

## Mode: flow (default, `/session-flow`)

1. **Resolve the session** (see `~/.claude/CLAUDE.md`). Use a name the user passed (`/session-flow landing-pipeline`).
2. **Read the state**, cheaply:
   ```bash
   S=.claude/sessions/<name>
   grep -nE '^\*\*Repos|^## |^- \[( |x)\]' $S/Plan.md
   grep -cE '^- \[x\]' $S/PlanDone.md 2>/dev/null || echo "PlanDone.md: none"
   grep -E '^## |^Repo:|^Status:' $S/Design.md     # empty scaffold vs. the step in focus + exact stage
   tail -n 6 $S/Journal.md
   ls $S/reference.md $S/learnings $S/drafts 2>/dev/null   # explain-*/walk-*/*.answers.md show a session-learn code/walk detour
   git -C <each target repo> status --short
   git -C <each target repo> log -1 --format='%h %cr %s'
   git -C <each target repo> diff --stat          # size of the current unreviewed batch, if any
   ```
3. **Derive the stage.** For a `build` step, `Design.md`'s `Status:` line names both the step in focus and its exact stage directly — trust it over guessing from diffs. Fall back to the table below when `Design.md` is empty (no `build` step started) or stale (its step is already `[x]` in `Plan.md` — a missed `CLOSE` reset; flag as drift, don't just overwrite it), and always for `quick`/`spike` (no `Design.md` entry).

   | Evidence | Stage |
   |---|---|
   | Plan.md has no steps | `PLAN*(approve)` |
   | No step in focus | `PLAN ok > pick a step` |
   | `quick`/`spike`, no `code`/`spike` line yet | `BUILD*` |
   | Target repo has uncommitted/unpushed diff, no `code`/`spike` line yet, `Design.md` empty or ambiguous | `BUILD*` or `REVIEW*` — check diff size against ~300 lines and whether a trace question was asked (ask the user if unclear; don't guess) |
   | `code`/`spike` line exists, step not `[x]` in Plan.md | `CLOSE*(check-off)` |
   | `code`/`spike` line exists, step `[x]` | `CLOSE ok` |

   To confirm a guess rather than assert it, call `workflow_next.py` with the guessed `(type, stage)` and `event: "enter"` and show the user its `required_now` — "is this what's outstanding?" — instead of listing requirements from memory.
4. **Check for drift.** Report each true item, with evidence: source changes in a target repo with no SPEC discussion for the step (and it's not `quick`); a `code` journal line with no repo name or test result; a batch of uncommitted changes past ~300 lines with no trace question asked yet; a step in `PlanDone.md` with no `code` line (fine if its outcome says why); a phase in `Plan.md` whose steps are all `[x]` (should have moved to `PlanDone.md`); steps with no type; a stale `Design.md` per step 3 above; any file or `## ` entry whose shape doesn't match what `~/.claude/CLAUDE.md` or its owning skill documents (don't try to interpret it yourself — name it and point at `tidy` mode, which archives it and keeps a dated record in `archive/<date>/MANIFEST.md`). No drift → say so.
5. **Report**, nothing more:
   ```
   [<session>] P2/S1 build | PLAN ok > SPEC ok > BUILD*(?) > REVIEW > CLOSE
   [FLOW] Step: Phase 2 / Step 1 [build+hole]: per-entity JDBC extract (payments-pipeline)
   [FLOW] Drift: <items, or "No drift found.">
   [FLOW] Open: <drafts with unanswered markers, an unanswered quiz, lessons due — or "nothing">
   [FLOW] Next: <the one move> — <owning skill>.
   [FLOW] Rules in force: no writes without approval · user produces every stop · one step at a time.
   ```
6. Ask (AskUserQuestion) whether to continue with the named skill, fix the drift first, or stop. Do nothing until answered.

### Fixing drift

Name the owning skill for each fix, never fix it yourself: missing journal line → the skill that owns that boundary (`session-step` for a step close, `session-plan` for a plan approval) appends it in session-plan's format, after the user confirms the text; unapproved source edits → show `git diff --stat`, the user picks keep-and-retro-approve or revert; untyped steps → `session-plan` retype; drafts with open markers or an unanswered quiz → the `/session-ui` deep link.

## Mode: help (`/session-help`)

1. **Suggest first** when there's anything to go on (text after `/session-help`, recent messages, the step in focus): 1-2 suggestions, one line each — the skill, why it fits, the exact words to say. If it's about where a step stands, suggest `flow` mode instead of guessing.
2. **Then the table below.** With `/session-help all`, also print "Called for you". Bare `/session-help`, no context → table plus "Tell me what you want to do and I'll pick."
3. Keep it to the tables and ≤3 lines of your own. If `/session-ui` is running, add one line pointing at `http://localhost:8765/#help`. Point to `~/.claude/CLAUDE.md` or `repos/.claude/skills-cheatsheet.md` for the rules themselves; don't restate them.

| Skill | Use when | Say |
|---|---|---|
| `session-plan` | Start/resume a feature; make or change phases/steps; check a step off. | "start a session for X", "plan this", "check off step 3" |
| `session-step` | Build the step you picked; review your own diff. | "build step 3", "review my code" |
| `session-debug` | Something failed and you want to find the cause. | "help me debug this" |
| `session-learn` | Understand a concept, compare options, get a repo guide, a deeper explainer+quiz or walk, review an MR, drill/save a lesson. | "teach me X", "walk me through what you wrote", "review MR 123", "drill me" |
| `/session-flow` | Lost track, or the agent drifted. | "where are we" |
| `/session-ui` | Dashboard; answer a quiz or draft markers in the browser. | "open the UI" |
| `/session-tidy` | Session folder is messy: stray, orphan or leftover files. | "tidy the session" |
| `/session-help` | This table, and a pick for your situation. | "/session-help I want to ..." |

**Called for you:**

| What runs | Started by | When |
|---|---|---|
| `session-debug` | session-step | a test fails on a `build` step |
| Re-plan / check-off (`session-plan`) | session-step | a spike finished / a step closes, on your yes |
| Journal lines | plan, step, debug, tidy | every boundary (plan approved, step closed, a debug resolved outside a step, a tidy applied) |
| "N lessons due. Drill now, or skip?" | step | step start, once a day |
| "Want a lens for this?" | step, debug | hard-to-read output |

## Mode: tidy (`/session-tidy`)

Two passes: **survey** (propose, change nothing) and **apply** (only what the user approved). The one rule: **lose nothing.**

- Never delete. A file that goes away is **moved** to `<session>/archive/<YYYY-MM-DD>/`, keeping its relative path.
- Before apply changes anything, take a zip snapshot of the whole session folder to `<session>/archive/tidy-<YYYYMMDD-HHMMSS>.zip` (Python `zipfile`, mode `"x"` — no `zip` binary here). Never overwrite a snapshot.
- Merging/condensing text only when every fact survives: the full original goes to `archive/`, the new file says where.
- `Journal.md` is append-only: never edit, reorder or condense it.
- Owned files (`Plan.md`, `PlanDone.md`, `Design.md`, `DesignDone.md`, `Lessons.md`, `reference.md`) are never edited directly — fixes there are hand-offs to the owning skill, run by the main session after the user agrees.
- Never touch source repos. Only inside `<session>/` and this session's link lines in `.claude/CLAUDE.md`.

**Where it runs.** Resolve the session, then launch the Agent tool with `subagent_type: "general-purpose"`, `run_in_background: true`, a self-contained brief ("Follow `~/.claude/skills/session-flow/SKILL.md`, tidy mode `<survey|apply>`, session folder `<abs path>`, workspace index `<abs path>`, today `<date>`. Report in ≤10 lines."). Tell the user it runs in the background.

**Survey**: read cheaply (`ls -R`, `wc -l`, `grep -c '^## '`, file heads; read a whole file only when a check needs it). Checks: stray top-level files, odd names/folders, leftovers of finished steps (reference.md for a closed step, lens folders of closed steps, already-approved drafts), orphans — nothing links to the file (`learnings/`, `lenses/` and `archive/` are exempt: nothing is meant to link to them), broken links, duplicates/overlap, `.answers.md` with no matching explainer, messy formatting (in `learnings/`, drafts, and user-added top-level files such as `Spec.md`/`PR*.md` only), owned-file issues (hand off, don't fix), index drift in `.claude/CLAUDE.md`, shape mismatches (an owned file whose content doesn't match what `~/.claude/CLAUDE.md` or its owning skill documents — propose archiving the mismatched entry under a dated folder; never migrate or reinterpret it yourself). Write `<session>/drafts/Tidy.draft.md` (drafts rules in `~/.claude/CLAUDE.md`): a Summary, numbered `[DECIDE]` Actions (what, why, links fixed, "lost facts: none" — if it can't say that, don't propose it), Hand-offs, Left as is.

**Apply**: re-read the draft, run only `A: ok` actions whose files are unchanged since survey (else skip + report); snapshot first; `mv` to `archive/<date>/`, renames, link fixes, merges; write `archive/<date>/MANIFEST.md` (one line per move/merge); append one `note` Journal.md line (format in session-plan); mark the draft `APPLIED <date>` and leave it in `drafts/`.

## Mode: ui (`/session-ui`)

1. Root = the cwd that holds `.claude/sessions/`.
2. `curl -s -o /dev/null -w '%{http_code}' localhost:8765/api/config` → `200` means already running, skip to 4.
3. Start it, Bash, `run_in_background: true`: `python3 ~/.claude/tools/session-ui/session_ui.py --root <root> --port 8765 --session <session>` (`--session` is the session the user asked for or the active one; omit if unknown; `--port 8766` if 8765 is taken).
4. Give the link: `http://localhost:8765`, plus a deep link when a file is in focus: `http://localhost:8765/#s=<session>&p=<path>` (URL-encode both). Help page: `http://localhost:8765/#help`.
5. WSL browser can't load it → suggest VS Code port forwarding (Ports panel → forward 8765), or `--host 0.0.0.0` on a trusted network only.

The tool lives at `~/.claude/tools/session-ui/` (`session_ui.py` + `index.html`, Python standard library only). It is a thin viewer over the session markdown files, kept deliberately minimal — deeper learning tooling lives in the separate Session Workbench app, not here. It shows: the step in focus (its `Design.md` SPEC, for a `build` step), Plan.md progress, the Journal.md tail, lessons due, and the file reader with answer boxes for quizzes (`learnings/*.answers.md`) and `[DECIDE]`/`[YOU]` draft markers. It writes only those answer files and draft `A:` lines, plus the same archive-only moves tidy mode does (an "archive N oldest" drafts button, a hover ✕ soft delete with confirm). It never writes `Plan.md`, `Journal.md`, `Lessons.md` or source files — those stay with their owning skills. A quiz saved in the UI still goes through `session-learn` grading; a marker answered there still goes through the drafting skill's review loop.

## Examples

**Drift found:**
```
[landing-pipeline] P2/S1 build | PLAN ok > SPEC ok > BUILD*(?) > REVIEW > CLOSE
[FLOW] Step: Phase 2 / Step 1 [build+hole]: per-entity JDBC extract (payments-pipeline)
[FLOW] Drift: glue/extract.py has 48 changed lines including extract_and_load() (the hole), and no
       `code` journal line. Looks like the agent wrote the hole.
[FLOW] Next: you choose — keep it and name it assisted, or revert extract_and_load() and write it yourself
       — session-step.
```

**Clean:**
```
[landing-pipeline] P2 done 3/6 | PLAN ok > pick a step
[FLOW] No step in focus. No drift found.
[FLOW] Next: pick a step — Phase 2 / Step 2 is next in order — session-plan, then session-step.
```

**Bad (help mode guessing the stage):**
```
[FLOW] You're in BUILD, hole gate. Fill it next.
```
Wrong: help guessed the stage from memory. Stage questions go to flow mode, which reads the files.

**Bad (tidy mode):**
```
[FLOW] Cleaned up: deleted 5 old md files and shortened Journal.md.
```
Wrong: deleted instead of archived, no snapshot, no approval, Journal.md rewritten.
