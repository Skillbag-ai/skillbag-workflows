---
name: skillbag-cronjobs
description: Maintain, run, and clean up local SkillBag cron-style agent jobs from jobs.json, including scheduler installation, pending-job reminders, and background execution. #run/always #use/skillbag-python-ensure
dependencies:
  - name: skillbag-python-ensure
metadata:
  author: backupdev
  version: 1.1.1
---

## Parameters

```yaml
optional:
  - name: context-root
    default: .
  - name: cronjobs-folder
    default: cronjobs
  - name: scope
    default: interactive
    values:
      - all
      - background
      - interactive
  - name: agent-command
    default: codex
```

## Instructions

- Use this skill to install, maintain, check, or run local agent cron jobs
  stored in `<context-root>/<cronjobs-folder>/jobs.json`.
- Invoke `skillbag-python-ensure` with `minimum-version=3.9` before running
  the bundled Python helper.
- Treat each cronjobs folder as the write boundary for its `jobs.json`,
  `.locks/`, and `<job-id>.md` job logs. Installing a child cronjobs folder MAY
  update the root `jobs.json` `children` array.
- Root installation MUST install the OS scheduler immediately after creating or
  confirming the root `jobs.json`. Ask the user before running the install
  command because it writes outside the workspace.
- Use classic five-field cron expressions:
  `minute hour day-of-month month day-of-week`.
- Do not use a persistent `running` field. The helper uses `.locks/<job-id>.lock`
  files to prevent parallel runs and to detect stale runs after a timeout.
- Background jobs are run only by the background runner. Interactive jobs are
  run only after the user gives an explicit GO in a separate user message.
- Keep job result logs concise. Summarize enough to preserve important output,
  but do not paste long raw transcripts unless the user explicitly asks.
- Read `references/jobs-json.md` when creating or reviewing `jobs.json`.

## Workspace Entry And User Interaction

Because this skill is tagged `#run/always`, at workspace entry and before each
response:

1. Run the helper's pending check for interactive jobs.
2. If interactive jobs are pending, briefly remind the user and ask for an
   explicit GO before running them.
3. Prioritize the user's current request. Do not block unrelated work while
   waiting for cronjob approval.
4. Do not run background jobs in the current conversation unless the user
   explicitly asks to debug or manually run a background job.

Example:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py pending . --scope interactive
```

## Installation

Confirm these choices with the user before initializing:

- `cronjobs-folder`, default `cronjobs`
- whether the cronjobs folder should be versioned, default yes
- root or child installation
- root scheduler interval, default once per hour
- background agent command, default discovered/confirmed `codex`
- background agent arguments, default
  `exec --sandbox workspace-write --skip-git-repo-check --ephemeral`

Initialize a root installation and install the OS scheduler:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py init . --cronjobs-folder cronjobs --install-scheduler
```

Initialize a child installation and register it in the root installation:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py init projects/example --cronjobs-folder cronjobs --child --parent-context-root . --parent-jobs-json cronjobs/jobs.json
```

Only the root installation owns the OS scheduler. Child installations are
referenced from the root `children` array and are checked by the root runner.

## Background Runner

The OS scheduler MUST call the root runner at startup and on the configured
interval:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py run-due . --scope background
```

Use the scheduler helper to print or install setup for the current platform:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py scheduler print .
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py scheduler install .
```

Ask before installing scheduler artifacts because this writes outside the
workspace on Linux, macOS, and Windows.

For Codex background jobs, validate the configured `agent.args` before relying
on the scheduler. `codex exec` does not accept `--ask-for-approval`; use
`--sandbox workspace-write`, `--ephemeral`, `--skip-git-repo-check`, or a
user-approved `--dangerously-bypass-approvals-and-sandbox` instead. Prefer
`prompt_mode=stdin` so long prompts are not passed through the process
argument list.

## Cleanup

Use cleanup to remove finished one-time jobs from the root and all child
`jobs.json` files. Cleanup candidates are:

- one-time jobs with `last_status=executed`
- one-time jobs with failed, delayed, aborted, timeout, needs-input, or skipped
  status only after the latest job log entry has `Checked: true`

Always list candidates before deleting anything:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py cleanup .
```

After the user approves the displayed list, apply cleanup:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py cleanup . --apply --confirm
```

Cleanup removes each candidate from its `jobs.json` and removes the matching
`<job-id>.md` result log. Do not run cleanup without explicit user approval.

## Interactive Runs

When the user gives GO for an interactive job:

1. Run the job prompt directly in the current conversation.
2. Report the result to the user.
3. Record the concise result in the job log:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py record-result . --job-id check-work-emails --status executed --checked true --result "Concise result."
```

If the user acknowledges a failed, delayed, or skipped job reminder, mark the
latest unchecked log entry as checked:

```bash
python3 .skills/skillbag-cronjobs/scripts/cronjobs.py ack . --job-id check-work-emails
```

## Log Format

Each job writes to `<cronjobs-folder>/<job-id>.md` with newest entries first:

```md
# YYYY-MM-DD HH:MM:SS DAY-OF-WEEK
**Status**: Executed
**Checked**: true
**Results**:
Concise result text.
```
