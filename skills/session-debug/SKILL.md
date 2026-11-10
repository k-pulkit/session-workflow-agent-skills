---
name: session-debug
description: Socratic bug hunt — the agent does the tedious read-only diagnostics (reproduce, grep logs and stack traces, git bisect/blame, read config) but the user interprets the evidence, names the root cause and writes the fix. Entered from session-step on a build step's fail event (in tests or in a real deploy the user ran), which resumes BUILD once the cause is found. Use for "help me debug X", "why is this failing", "brainstorm this bug with me". Different from session-learn's review mode (reviews finished code) and from just fixing it.
---

# session-debug

The agent removes the tedium of investigation. The user keeps the part that builds skill: reading the evidence and naming the cause. Real failures teach the most, so this skill matters. Shared principles are in `~/.claude/CLAUDE.md`.

Every message starts with `[DEBUG]`. In an active session, the response opens with the progress banner (see `~/.claude/CLAUDE.md`); the tag follows it.

## Hard rule

**Never Edit or Write source, test or session files during this skill** (lens files, and this skill's own `Journal.md` boundary line at close, are the exceptions). If a fix becomes clear, name it as a possibility; do not apply it. "Just fix it" is an override for that one spot: apply it, then return to diagnosis for anything left.

Never run real AWS actions (deploys, triggers, live queries that change anything). Ask the user to run them and paste the output. Read-only local work is fine.

## What the agent does freely

- Run and re-run the failing local command or test.
- Grep logs, stack traces, `git log`, `git blame`, bisect steps.
- Read code, config, synthesized templates, env vars.
- Report what a command printed, verbatim or condensed. Reporting is not diagnosing.
- **Offer a lens** when the evidence is hard to read (a long JSON, a grant list, a trace). Build it in `<session>/lenses/<name>/` (the only place this skill may write; rules in "Lens" in `~/.claude/CLAUDE.md`). Show the view and ask what the user reads from it. Do not interpret it first.

## What stays with the user

- **The first guess.** Before any evidence: "Your guess at the cause, one line?"
- **What the evidence means.** Ask toward it: "The trace ends in the retry loop. What does that loop do when the response is empty?"
- **The next move.** Offer 2 or 3 next diagnostic moves and let the user pick.
- **The fix.** Once the cause is confirmed, point at `file:line`. It follows the hole rule: inside the step's hole, the user writes it; anywhere else, the agent does.

## Process

1. **Symptom and repro.** Get the exact command, input, actual vs expected output. For a deploy failure, ask for the error text and the stack/resource name.
2. **First guess** from the user (one line).
3. **Reproduce** it yourself if it is local.
4. **Evidence in rounds.** One batch of read-only diagnostics, report plainly, then ask what they make of it or which thread to pull. Do not chain several tool calls into a conclusion.
5. **Hypothesis together**, phrased as a question.
6. **Confirm** with one more piece of evidence (a targeted log line, a minimal repro, a synth diff).
7. **Hand off the fix.** What must change and why. The hole rule decides who writes it (see "What stays with the user" above).
8. **Close.** Compare the first guess with the real cause in one line. If it's a real gotcha, ask: "Got it, or save it as a lesson to drill?" Save → invoke `session-learn` in lesson-add mode.
   - **Mid-step** (a test failed during `BUILD`): tell `session-step` the cause is found so it can call `workflow_next.py` with `event: "cause_found"` and resume `BUILD`; the step's own `code` journal line at `CLOSE` covers this failure, so append nothing here.
   - **A real deploy the user already ran, after the step closed**: there's no step to resume (`workflow_next.py` returns `already_closed`). Append a `bugfix` `Journal.md` line yourself, in session-plan's format (heredoc, no Read) — the line and the user's fix are the whole record.

## quick / spike steps

Neither has a `DEBUG` stage in `workflow_next.py`. `session-step` gets the user's one-line guess, diagnoses and fixes inline, and reports whether the guess was right, without invoking this skill. If the user asks for the full Socratic process anyway, run it.

## Examples

**Good:**
```
[DEBUG] Deploy failed: "CREATE_FAILED ReservedConcurrentExecutions". Your guess at the cause, one line?
user: we hit the account concurrency limit
[DEBUG] Close. Evidence: the function asks for 10 reserved; `aws lambda get-account-settings` (you ran it)
        shows UnreservedConcurrentExecutions minimum 100 and total 110. What does reserving 10 leave?
user: 100... oh it can't go below 100 unreserved, so any reservation fails
[DEBUG] Confirmed. Fix: lib/handler.ts:33. Your call: drop the reservation or raise the account limit.
        Lesson candidate: reserved concurrency vs the 100 unreserved minimum. Add it?
```

**Bad:**
```
[DEBUG] The issue is the account concurrency limit. I removed reservedConcurrentExecutions in handler.ts. Redeploy.
```
Wrong: no guess, no evidence round, the agent named the cause and edited the file.

## Format

Plain chat. Keep evidence dumps short: the relevant lines, not the whole log.
