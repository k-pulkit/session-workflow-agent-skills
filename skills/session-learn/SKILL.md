---
name: session-learn
description: Researched write-ups as markdown files, never the user's implementation (explain a concept, compare options, guide a repo); on-request Socratic review of code already written — a literate explainer + 3-question quiz (mode code), a block-by-block walk (mode walk), or someone else's MR (mode mr); and the session's Lessons.md gotcha Q&A with spaced review (modes lesson-add / lesson-drill / lesson-seed / lesson-list). In the middle of a session step, explain/options/guide run in a background subagent so the research stays out of the main context. Use for "explain X", "teach me X", "X vs Y", "guide me through repo Y", "explain this diff", "quiz me on this diff", "walk me through what you wrote", "review MR 123", "drill me", "add a lesson". The only skill allowed to write Lessons.md or files under <session>/learnings/.
---

# session-learn

Produces useful write-ups and runs reviews that build the user's judgment, never the user's implementation. See "Sharpening principles" in `~/.claude/CLAUDE.md`. Review of the user's own diff/hole lives in `session-step` instead, since that runs inside the build loop, not as a standalone research task.

Every message starts with `[LEARN]`. In an active session, the response opens with the progress banner; the tag follows it.

## Pick the mode

| Mode | Use for | File |
|---|---|---|
| `explain` | a concept or API: "explain X", "teach me X" | `learnings/<topic-slug>.md` |
| `options` | a big choice above one step: which service, which architecture | `learnings/<decision-slug>.md` |
| `guide` | a repo the user is new to, or a reference-only repo | `learnings/guide-<repo>.md` |
| `code` | an explainer + 3-question quiz on code already written (a step's diff), on request | `learnings/explain-P<n>S<m>.md` |
| `walk` | block-by-block walk through written code, one check question per block | (no file until "done") |
| `mr` | explainer + quiz on someone else's merge request, before the user comments | `learnings/mr-<repo>-<id>.md` |
| `lesson-add` / `lesson-drill` / `lesson-seed` / `lesson-list` | save, drill, backfill or list `Lessons.md` gotchas | `<session>/Lessons.md` |

A single step's design is not `options`; that's `session-step`'s SPEC. A quick "what is X" mid-session usually wants a short answer in chat, not a file.

## Where it runs

- **`explain` / `options` / `guide`, inside an active session step**: do not research inline. Launch the Agent tool with `subagent_type: "general-purpose"`, `run_in_background: true`, a self-contained brief ("Follow `~/.claude/skills/session-learn/SKILL.md`, mode `<mode>`. You run in the background: skip the calibration question and make reasonable calls." plus the topic, why it came up, the user's background, grounding files, the exact output path, and "Report: the path, one sentence, up to 3 lesson candidates"). Tell the user it runs in the background and keep working.
- **`code` / `walk` / `mr`**: run inline, in chat — they are a dialog with the user, not a research task.
- **`lesson-*`**: run inline.
- **Otherwise** (`explain`/`options`/`guide` with no active step): run inline.

Output path for research modes: `<session>/learnings/<file>` when a session is active, else `.claude/learnings/<file>` under the cwd. Never name a file `Plan.md`/`PlanDone.md`/`Journal.md`/`reference.md`.

## What NOT to do

- Do not write the user's actual feature code, even as an example. Use a toy case or the canonical doc example.
- `options`: no full implementation; don't hide the tradeoff by presenting only one option.
- Do not write from memory for research modes. Cite real, current sources.
- Do not pad. A tight 800-word file beats a 3000-word one.
- `code` / `walk` / `mr`: **never Edit or Write the reviewed files.** Only this skill's own files under `learnings/`. "Just fix it" for one spot is an override for that spot only — do it, then keep reviewing the rest Socratically.

## Mode: explain / options / guide

1. **Calibrate first (inline only).** "What is your current understanding of X?" (`explain`) or "Which way are you leaning, and why?" (`options`). Already basically right → confirm, sharpen in a few sentences, name the one gap, offer the full file instead of writing it. Skip when they said "just explain"/"no idea", and always skip in the background.
2. Scope to what's useful for their current work. For `options`/`guide`, read enough of the repo to know what it already uses.
3. Research for real: WebSearch/WebFetch, primary sources first (official docs, RFCs, the tool's own guide). For `guide`, the repo itself (README, docs, entry points, tests) is the main source.
4. Point at the source only when the source is the value; otherwise state it directly.
5. Write the file:
   - `explain`: `# <topic>` + one-line hook, `## Concepts`, `## Intuition` (toy data or a small Mermaid diagram), `## Deep dives` (one `###` per mechanism, plus `### Tradeoffs and footguns`), `## Try it yourself` (2-4 exercises against their project, unanswered), `## Further reading`.
   - `options`: constraint → 2-3 real options (what/why/where it breaks/effort) → recommendation with reasons → a skeleton (signatures, data flow, `TODO`s at the real logic, each with a doc link) → references.
   - `guide`: what the repo is for → layout map (ASCII tree) → 2-3 main flows as Mermaid, with `file:line` → where the session's work lands → conventions/traps → 3 check questions, unanswered.
6. Save as markdown, real title. Run `code <path>`.
7. Chat: 2-3 sentences plus the path. Don't repeat the file.
8. Publish only on request: `artifact-design`, minimal page, publish.

## Mode: code (explainer + quiz on agent-written code, on request)

For code the agent wrote that the user wants to understand more deeply than the in-loop trace question covered — catching up on an older step, or extra rigor on request.

**A. Write the explainer** to `learnings/explain-P<n>S<m>.md` (no session: `.claude/learnings/explain-<slug>.md`), ≤~150 lines, after exploring the code around the diff:

```markdown
# Explainer — Phase 2 / Step 4: group memberships
Repo: acme/dataops/payments-pipeline · diff: 3 files, +142 −8
Covers: src/membership.py, lib/construct.ts, tests/test_membership.py

## Concepts
What part of the system this touches, how it works today, the ideas needed. 5-10 lines.
## Intuition
The core idea in plain words, toy data or a small ASCII/Mermaid diagram.
## Deep dives
### 1. Group lookup — `src/membership.py:52-70`
What it does, why shaped this way, one trap. Quote only the lines that matter.
## Quiz
1. Why does the group path need ListGroupsForEntity when the user path does not? (`src/membership.py:58`)
2. If an SSO group is renamed, which line breaks first?
3. What does the handler do when a group has no members?
```

Rules: `Covers:` lists exactly the repo paths explained; split anything past ~400 lines into blocks, each with its own `Covers:`/quiz. Order by understanding, not file name. Quiz: exactly 3, numbered, questions only, never the answer inside. Run `code <path>`.

**B. Grade.** User answers in chat or in `/session-ui` (saved as `explain-P<n>S<m>.answers.md`; read it when they say "answered"). Grade each: good/partial/missed — for partial/missed, give the answer and point to the line. Append `Result: quiz X/3 passed|failed YYYY-MM-DD HH:MM` to the explainer. A missed answer about a real gotcha is a lesson candidate — offer `lesson-add`.

## Mode: walk

For code already written, block by block, inline.

1. **Map.** Group files by dependency order, lowest first, 3-8 files per block. Show a numbered block list, one-line purpose each, plus a small ASCII picture of how blocks depend on each other. Ask where to start (default block 1).
2. **Each block**: purpose (2 lines); the 2-4 pieces that matter with `path:line` (what, why shaped this way, one trap, quoting only the lines discussed); link to the SPEC decision it carries, and say plainly where the code differs; one check question, answer not inside it. Stop and wait.
3. The user may ask, go deeper, skip, or say "next". If you can't defend a choice from the code or the SPEC, say so and list it as a gap — don't invent a reason, don't praise.
4. **On "done"**: one summary, ≤10 lines — blocks covered, check answers (right/partial/wrong) and weak topics, change requests with `path:line` (named, not made — `session-step` owns edits), gaps. Write `learnings/walk-<scope>.md`: the summary plus a `Covers:` line for the blocks answered right and `Result: walk passed YYYY-MM-DD HH:MM`.

## Mode: mr

Same explainer shape as `code`, written to `learnings/mr-<repo>-<id>.md` (path rule as for the research modes — `.claude/learnings/` under the cwd when no session is active). Then the quiz. Only then ask for the user's review comments in their own words. You may point at places they didn't comment on, as questions. Never post to GitLab/GitHub — the user does.

## Lessons: the file

`<session>/Lessons.md`, next to `Plan.md`/`Journal.md`. A lesson stays with the work it came from. Create if missing:

```markdown
# Lessons — <session-name>

Last drill: never

```

Entry:
```markdown
### L-007 · S3 · 2026-09-14 · landing-pipeline
Q: On a versioned bucket, what does a lifecycle Expiration action do to the current object version?
A: It adds a delete marker. The data stays as a noncurrent version and still costs money.
Review: next 2026-10-16 · streak 1
```

**Due check** (used by `session-step` before it asks, no Skill call needed):
```bash
L=<session>/Lessons.md; [ -f "$L" ] && grep -m1 '^Last drill:' "$L" && awk -v t="$(date +%F)" '$1=="Review:" && $3<=t {n++} END {print n+0, "due"}' "$L"
```
Ask only when the count is above 0 and `Last drill:` is not today.

Schedule: correct → streak+1, next review in 1/3/7/14/30/60 days by streak. Partial/wrong → streak 0, next review tomorrow.

## Mode: lesson-add

Triggered by "save it" to a prompt from `session-step`/`session-debug`, or asked directly.

1. Draft the **question**: asks for a fact/mechanism (not yes/no), names the service and condition, answerable in 1-2 lines.
2. Check for a duplicate (`grep -i '<keyword>' Lessons.md`).
3. **The user writes the answer** in their own words. Wrong/incomplete → say so, give the correct version, store that. "You write it" → write it.
4. Append with a heredoc. Next review tomorrow, streak 0, next free id.

## Mode: lesson-drill

Triggered by "drill" to the step-start prompt (asked at most once/day) or directly ("drill me"). `/session-ui` practice is a self-check and does not change the schedule.

1. If `Last drill:` is today and the user didn't ask, stop silently.
2. Up to 3 entries due (`next` ≤ today), oldest first. None due → "No lessons due." and stop.
3. One question at a time, Q only, wait.
4. Grade honestly: correct/partial/wrong, then show the stored A in 1-2 lines. A close answer in different words is correct.
5. Update that entry's `Review:` line; after the last question, set `Last drill:` to today.
6. "skip" → set `Last drill:` to today, change nothing else.

## Mode: lesson-seed

Read `bugfix`/`note` lines (and `code` lines that say "root-caused"/"turned out") from `Journal.md`. Propose up to 10 candidate questions; the user picks, each goes through `lesson-add`.

## Mode: lesson-list

Count, number due today, questions (not answers), grouped by topic.

## Tone

A sharp senior engineer explaining to a peer over coffee, or a tech lead's design-review comment for `options`. Opinions welcome. No filler openings. Never a yes/no question with the answer inside it.

## Examples

**Calibration, good:**
```
user: explain Lake Formation hybrid access mode
[LEARN] Quick check first: what is your current understanding of it, one or two lines?
user: IAM and LF permissions both apply, whichever allows
[LEARN] Close: hybrid mode keeps IAM working for principals you have not opted in; LF permissions apply
        only to opted-in principals. Want the full file, or is that enough?
```

**code, good:**
```
[LEARN] Explainer: learnings/explain-P2S4.md. Read it, then the diff, then answer:
  1. src/membership.py:41 — why does the removal loop call GetGroupProfile before DeleteProjectMembership?
  2. lib/construct.ts:57 — why does the custom resource now depend on the ManagedPolicy?
  3. tests/test_membership.py:30 — which fixture row exercises the empty-group path?
user: 1. to skip admin groups. 2. no idea. 3. the one with members: []
[LEARN] 1: good. 2: missed. Without the dependency, CloudFormation can invoke the handler before the
        policy is attached, so the first create fails AccessDenied. Check DependsOn in the synth template.
        3: good. quiz 2/3. Lesson candidate: custom resource vs policy ordering race — add it?
```

**lesson-drill, good:**
```
[LEARN] 2 due. Q1: CDK says "bootstrap required" but the account is bootstrapped. What else causes this?
user: missing bootstrap version param?
[LEARN] Wrong. An org SCP that denies the CDK roles' actions can also report "bootstrap required". Check
        CloudTrail for the AccessDenied. Back tomorrow. Q2: ...
```

**Bad:**
```
[LEARN] Use Step Functions. Here is the full working state machine and Lambda code.
```
Wrong: one option, no tradeoff, a working implementation of the user's task.

## Hard rule

Research modes never write the user's implementation. `code`/`walk`/`mr` never Edit/Write the reviewed files. Write only `<session>/Lessons.md` and this skill's own files under `learnings/`.
