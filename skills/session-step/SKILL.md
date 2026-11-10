---
name: session-step
description: Runs one Plan.md step through the build loop — SPEC (design questions, file plan, the hole), BUILD (agent writes everything but the hole; the user fills it), REVIEW (per batch, a trace question then commit), CLOSE (journal + plan checkbox) — calling workflow_next.py at each transition. Also reviews the user's own code Socratically on request, outside the loop. Use for "design this step", "build step 3", "implement this", "review my code", "did I do this right". The only skill allowed to edit source/test files and reference.md.
---

# session-step

Runs one step through `SPEC → BUILD → REVIEW → CLOSE` (see "The build loop" in `~/.claude/CLAUDE.md`), and is the only skill that edits source/test files or `reference.md`.

Every message starts with `[STEP]`. In an active session, the response opens with the progress banner; the tag follows it.

## Calling `workflow_next.py`

At every transition, call it and follow `required_now`/`message` rather than reasoning the stage out from memory:
```bash
python3 ~/.claude/tools/session-ui/workflow_next.py '{"type": "build", "stage": "SPEC", "event": "enter", "has_logic": true}'
```
Full state table and field docs: the script's module docstring, or "`workflow_next.py`: the rules CLI" in `~/.claude/CLAUDE.md`. An `ok: false` result means the event doesn't fit the current stage — stop and resolve that with the user before doing anything else, don't paper over it.

## Process

1. Resolve the session. Read `Plan.md`; find the step in focus (ask if not given). Read its type; `has_logic` is true iff the tag is `[build+hole]` (false for plain `[build]`). No type → propose one (session-plan's rule of thumb) and ask. Also read `Design.md`: if it already names this step, resume from its `Status:` line — the SPEC answers are already there, don't re-ask.
2. **Lessons prompt.** Run the due check from `session-learn` (section "Lessons: the file"). Due and not drilled today → ask "N lessons due (<topics>). Drill now, or skip?" Drill → invoke `session-learn`. Skip → move on.
3. `quick` → skip to **BUILD (quick)** below. `spike` → skip to **BUILD (spike)** below.
4. **SPEC.** Call `workflow_next.py` with `event: "enter"`, `has_logic` from the step. Explore the code read-only in the target repo. Then, in one message (chat, ≤10 lines — a draft file only if this SPEC is unusually large, per "Drafts go in files, not chat"):
   - 1-2 concrete design questions that actually decide the shape: an edge input ("a tick at exactly 00:00Z: which slot?"), a choice between two shapes, a failure path. Not "what could break?", and never the answer inside the question. You may share hard facts the user cannot know (e.g. "the repo already has a resolver in X").
   - The file plan (files to create/edit, yours vs. the user's).
   - If `has_logic`: **the hole** — the riskiest 10-40 line unit, named, with its own failing test. Not a getter, not the whole step. Ask how the user owns it: `code` (hand-write) or `pseudo` (dictate it; you turn it into code and list every detail you filled in that they didn't say).
   Wait for answers. When they differ from what you'd have picked, say so plainly in the same message you move on with — don't flatter a weak answer or invent a difference that isn't there. As soon as the answers are in, write `Design.md` (format in `~/.claude/CLAUDE.md`) — this is a record, not a gate, so it needs no approval of its own.
5. User says **"go"** → call `workflow_next.py` with `event: "go"`, update `Design.md`'s `Status:` line. Proceed to BUILD.

### BUILD

Write everything except the hole (if any); stub it with a signature and a failing test. Say that you're writing the file plan agreed at SPEC; it needs no new approval.

For a `has_logic` step, write `reference.md` in the session folder before handing the hole to the user (overwrite the previous one): three-part shape — Concepts, Intuition, Deep dives, the same shape `session-learn`'s explainers use, Mermaid for any diagram per `~/.claude/CLAUDE.md` — no solution in it. Run `code <path>/reference.md`.

```markdown
# Reference — Phase 2 / Step 1 [build+hole]: per-entity JDBC extract
Repo: acme/dataops/payments-pipeline

## Your hole
`extract_and_load(spark, entity) -> int` in `glue/extract.py:42`.
Must: read one entity, write parquet, return rows written, raise on zero rows.
Tests: `tests/test_extract.py::test_happy`, `::test_empty_entity`, `::test_jdbc_error`.

## File map
- `glue/extract.py` — your hole + build_query(), write_parquet() (agent-written)
- `tests/test_extract.py` — 5 tests; run: `pytest tests/test_extract.py -q`

## Concepts
- **Lazy DataFrames** — nothing runs until an action (count, write); each action replays the lineage.

## Intuition
A toy, not your hole, showing why two actions cost two reads.

## Deep dives
### JDBC partitioning
Without partitionColumn, Spark reads the table in one task. https://spark.apache.org/docs/latest/sql-data-sources-jdbc.html
```

For a deeper detour, use `session-learn` (background) and link the file from `reference.md`.

If `has_logic` and `code`: leave the hole as a stub with a short TODO (never the algorithm). If `pseudo`: ask for the pseudocode for that one unit, turn it into code staying inside what it says (ask, don't guess, where it's silent on a detail that changes behavior — an error case, an ordering, a default), then list every detail filled in that the user didn't say, one line each ("Added `MaxResults=50` and a NextToken loop"). That list is what the trace question in REVIEW will probe.

While the user writes a `code` hole, follow the **help ladder**, one rung at a time, only when asked again:
1. A question pointing at the concept ("What does GetUserProfile return when the user is not in the domain?").
2. The exact API/doc section, with a link.
3. A small example of the same idea that is *not* their code.
4. Only on "show me" / "just write it": write it yourself and say plainly that the hole was assisted, not owned — the CLOSE journal line records it.

Run the tests.
- All pass, hole filled/waived → call `workflow_next.py` with `event` = `hole_filled`, `hole_waived`, or `no_hole` (no logic). Update `Design.md`'s `Status:` line. Move to REVIEW.
- A test fails → call with `event: "fail"`. Hand to `session-debug`: give it the failure, nothing more. The user names the cause; the fix then follows the hole rule (inside the hole, the user writes it; elsewhere, the agent does). Call `workflow_next.py` with `event: "cause_found"` and resume BUILD.

If state is hard to read mid-build (a long JSON, a synth diff, an IAM/LF grant list), offer once: "Want a lens for this?" (see "Lens" in `~/.claude/CLAUDE.md`). Build it in `<session>/lenses/<name>/`, run it, show the output, stop — the user draws the conclusion.

### BUILD (quick)

Build from the `Plan.md` step text. No file-plan approval beyond what the step already says, no hole. Run or synth.
- Behavior change: run the tests, report the result → call `workflow_next.py` with `event: "done", "behavior_change": true`.
- No behavior change (the plan's reason says so): give one proof fitting the change (build passes + test count unchanged; `ast.dump`/`tsc --removeComments` identical; CDK asset hash identical; `git diff -M` shows pure renames) → call with `"behavior_change": false`. If the proof fails, the step wasn't behavior-free: stop, ask whether to retype it.
- A failure (either type): no `session-debug` — get the user's one-line guess, diagnose and fix it yourself, then say whether the guess was right.

### BUILD (spike)

Work on a throwaway branch or in the scratchpad, never the main branch. Before each experiment, the user states what result would answer the question. On timebox-up, call `workflow_next.py` with `event: "timebox_up"`. Write a short findings list (question, what was tried, result, what it means for the plan) — the user reads it and names what it means. Throwaway code is not merged. Invoke `session-plan` to re-plan from the findings.

### REVIEW

Stage a batch (≤~300 code lines; a bigger `BUILD` is split into several batches, each reviewed before the next is written). Call `workflow_next.py` with `event: "batch_ready"`. In chat: a 3-line summary of the batch, plus **one trace question** anchored to a real line and the behavior just built — not "do you understand X?", and the answer is never inside the question. Good: "fixture X at tick 00:00 — which bin does `b` land in, and which line decides?" If the hole was `pseudo`, the trace question should probe one of the filled-in details from BUILD.

The user answers, may ask or change anything, then says **"commit"**. Grade the answer honestly in one line (right / partial / wrong — for partial/wrong, give the answer and point to the line; don't just say "correct" to move on). Keep the commit message plain — a normal summary of what changed, not the SPEC/REVIEW Q&A; that's already durably recorded in `Design.md`. Call `workflow_next.py` with `event: "commit"` and `more_batches` true/false, update `Design.md`'s `Status:` line.
- More batches → loop: stage the next one, ask its trace question.
- Last batch → proceed to CLOSE.

### CLOSE

1. Append one `code` (or `spike`) `Journal.md` line in session-plan's format (heredoc, no Read) — name the repo, the test result, and whether the hole was owned/waived/assisted. For a `build` step: date-stamp `Design.md`'s `## Phase ...` heading, set its `Status:` line to `REVIEW, last batch committed`, and append the whole thing to `DesignDone.md` (heredoc, no Read — exact shape in `~/.claude/CLAUDE.md`), then reset `Design.md` to its empty scaffold.
2. Ask whether `session-plan` should check off the step. Yes → invoke it.
3. If a design answer was off, a trace answer was wrong, or a gotcha came up: name it in one line, ask "Got it, or save it as a lesson?" Save → invoke `session-learn` (lesson-add mode).
4. **Deploy handoff.** A real AWS action: say what to run and what to check in the result. The user runs it, never you. Read the outcome together when they report back.

## Reviewing the user's own code (on request, outside the loop)

For code the user wrote — their hole, or their own diff — on "review my code", "did I do this right":
1. Scope: default the uncommitted diff (`git diff`, `git diff --staged`), or the file/function named.
2. Read it with the code around it. Find real issues, in order: correctness, edge cases/error handling, security, then design/naming. Don't invent nitpicks; silence on a good section is fine.
3. Ask toward each issue; don't state the fix. Give the direct answer only if asked twice or they say they're stuck.
4. Name the concept so it carries over ("this is an N+1 query"); link a doc if not obvious.
5. Close with fix-before-merge vs. good-to-know.

**Never Edit or Write the reviewed files in this mode.** "Just fix it" for one spot is an override for that spot only; keep reviewing the rest Socratically after.

## Explainer + quiz, on request (not a mandatory gate here)

If the user wants a deeper explainer+quiz on code already written — beyond the in-loop trace question, e.g. catching up on an old step or wanting more rigor — that's `session-learn` (code mode), not this skill. Point them there rather than writing one yourself.

## Examples

**Good, build+hole:**
```
[STEP] SPEC: 1. per-entity catch-and-continue, or fail the whole job on one bad entity? 2. The hole:
       extract_and_load(spark, entity) -> int, raises on zero rows. File plan: glue/extract.py (you
       write the hole; I write build_query/write_parquet), tests/test_extract.py. code or pseudo?
user: 1. catch-and-continue, raise at the end if any failed. 2. code
[STEP] I'd have raised on the first bad entity too, but catch-and-continue is fine for the POC. go?
user: go
[STEP] Written everything but extract_and_load(), stubbed with a failing test. reference.md covers
       JDBC options and df.cache() semantics.
user: (writes it) done
[STEP] 4/5 pass. The hole's test "empty entity -> raise" fails: KeyError at extract.py:58.
[DEBUG] ...
user: cause found: empty DataFrame has no 'count' column under this schema
[STEP] Fixed. 5/5 pass. Batch ready: extract.py + its test, 61 lines. Trace question: why does count()
       after write() still cost a second JDBC read here?
user: because nothing executes until an action, and each action replays the lineage
[STEP] Right. commit?
user: commit
[STEP] Last batch. Journal line written, Design.md archived to DesignDone.md. Check step off in Plan.md?
user: yes
```

**Bad:**
```
[STEP] Implemented all files, tests pass, journaled and checked off.
```
Wrong: no file-plan agreement, no design questions, no trace question. The user could approve this without reading a line.

## Hard rule

Never edit `Plan.md`, `PlanDone.md`, or `Lessons.md` — invoke the owning skill. `Journal.md`: append only. No file write before SPEC is answered (for `build`) or before the quick/spike plan text exists. Never run real AWS actions (deploy, triggers, live queries); those are the user's.
