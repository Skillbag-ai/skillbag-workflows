# SkillBag Workflows

connect it with git@github.com:Skillbag-ai/skillbag-workflows.git.

Use it when a workspace needs small, composable procedures that maintain local
work products over time: bounded case contexts, chronological logs, handoff
notes, status reports, decision records, checklists, lightweight
retrospectives, or recurring review packets.

It is meant for prompts like:

- "open a case for this matter"
- "resume this case and reconcile its document inventory"
- "add this to the project log"
- "create a dated progress note for this folder"
- "remind me when local agent cron jobs are due"
- "turn today's work into a handoff note"
- "capture this decision in the local decision log"
- "prepare a weekly status summary from recent notes"

The skills here sit between low-level utilities and domain-specific document,
resource, or media processing. They should describe durable ways of working
rather than one-off file transformations.

This repository is itself a valid SkillBag source:

- repository instructions live in [AGENTS.md](./AGENTS.md)
- installed skills live under [`.skills/`](./.skills/)
- the skill catalog lives at [`.skills/SKILLS.md`](./.skills/SKILLS.md)

The skills here are meant to be installed into other workspaces as
dependencies. They should stay generic, local-first, and independent of one
organization's reporting cadence, folder taxonomy, or note-taking style.

## Available Skills

### [skillbag-case-context](./.skills/skillbag-case-context/SKILL.md)

Creates and maintains a bounded, resumable context for a non-routine matter
without turning it into a full project-management system.

Key behavior:

- defaults new cases to `cases/YYYY-MM-short-name/`, while respecting a
  configured collection, exact case path, or established layout
- separates compact current state in `CONTEXT.md`, recursively inventoried
  source documents, and chronological history in `log.md`
- preserves existing `files/` and `files.md` conventions without automatic
  migration
- uses `skillbag-pdf-ocr` for unreadable source PDFs while preserving originals
- distinguishes evidence, user-provided statements, inferences, and unresolved
  questions
- supports lightweight `active`, `waiting`, and `closed` states
- creates reminders only on explicit request and uses `skillbag-cronjobs` when
  available

Use this for incidents, administrative procedures, disputes, requests,
decisions, or follow-ups that need evidence and history across multiple
sessions, but do not need a roadmap or recurring process model.

### [skillbag-chrono-log](./.skills/skillbag-chrono-log/SKILL.md)

Creates or updates a folder-local chronological Markdown log while keeping the
newest dated section first.

Key parameters:

- `target-folder` and `text` are required
- `filename` defaults to `log.md`
- `date` defaults to today
- `mode` supports `append` and `replace`
- `weekday-locale` supports English by default, several common weekday-label
  languages, or `none`

Behavior:

- writes only `<target-folder>/<filename>` and creates the target folder when
  needed
- adds new dated sections in reverse chronological order
- inserts same-day entries at the top of the existing day section
- can replace a single date section for consolidated daily summaries
- uses `skillbag-python-ensure` before running the bundled Python helper

Use this for project journals, incident histories, progress logs, dated folder
records, or other local notes where the newest entry should stay easy to find.

### [skillbag-cronjobs](./.skills/skillbag-cronjobs/SKILL.md)

Maintains local cron-style agent jobs from a versioned `jobs.json`, with
immediate scheduler installation, interactive reminders, background execution,
child cronjobs folders, lock files to prevent parallel runs, cleanup for
finished one-time jobs, and chronological per-job result logs.

Key behavior:

- supports classic five-field cron expressions and one-time jobs
- installs and uses the root installation's OS scheduler to check root and
  child jobs
- runs background jobs through a configured agent command, defaulting to
  discovered or confirmed `codex`
- reminds about interactive jobs but waits for the user's explicit GO
- lists cleanup candidates before removing one-time jobs and their logs
- logs each job result to `<cronjobs-folder>/<job-id>.md` with newest entries
  first
- uses `skillbag-python-ensure` before running the bundled Python helper

Use this for local recurring agent tasks that should stay visible, auditable,
and under user control.

## Planned Skill Areas

These areas are intentionally documented as roadmap, not as installed skills.
Only skills listed in [`.skills/SKILLS.md`](./.skills/SKILLS.md) are currently
available.

- handoff-note: summarize current state, next steps, blockers, and useful
  links for another person or a later agent session
- decision-log: append or update lightweight architecture, product, project,
  or operations decisions with context, options, outcome, and follow-up
- status-report: create weekly, sprint, or milestone status updates from local
  logs and notes without imposing one organization's reporting template
- work-session-recap: convert a coding, research, or operations session into
  concise outcomes, changed files, open questions, and next actions
- checklist-runner: execute a local Markdown checklist, mark completed items,
  and capture notes or exceptions without hiding unfinished work
- retrospective-note: collect what changed, what worked, what was difficult,
  and what should be adjusted next time
- review-packet: gather relevant local files, links, logs, and summaries into
  a review-ready Markdown brief
- follow-up-tracker: maintain a local follow-up list with owners, due dates,
  status, and source context

## Repository Direction

Workflow skills should be durable routines that help agents keep work
organized across time. A good workflow skill usually:

- produces or maintains a human-readable local artifact
- has clear write boundaries
- separates current state, source evidence, and historical events when those
  roles would otherwise become confused
- composes with more specialized repositories such as `skillbag-docs`,
  `skillbag-media`, `skillbag-resources`, and `skillbag-utils`
- avoids assuming a specific company process, meeting format, or folder naming
  scheme
- records uncertainty and unfinished work instead of smoothing it away

Skills that only provide runtime helpers belong in
[`skillbag-utils`](https://github.com/Skillbag-ai/skillbag-utils). Skills that
primarily transform file formats belong in
[`skillbag-docs`](https://github.com/Skillbag-ai/skillbag-docs) or
[`skillbag-media`](https://github.com/Skillbag-ai/skillbag-media). Skills that
organize corpora and search stores belong in
[`skillbag-resources`](https://github.com/Skillbag-ai/skillbag-resources).

## How To Use

Typical usage is to add this repository as a SkillBag dependency from another
workspace, usually alongside
[`skillbag-utils`](https://github.com/Skillbag-ai/skillbag-utils) for shared
runtime helpers such as Python checks.

Example dependency declaration:

```yaml
dependencies:
  - name: skillbag-chrono-log
    version: main
    source: git@github.com:Skillbag-ai/skillbag-workflows.git
```

Once installed, users can ask in natural language. For example, an agent with
these skills available can understand that "open a case for this matter" maps
to `skillbag-case-context`, while "add this to the project log", "append
today's note", and "replace today's progress summary" map to
`skillbag-chrono-log`.

## Design Notes

Workflow skills should make ongoing work easier to resume, audit, and hand off.
They should not decide the user's project management system for them. Prefer
small Markdown artifacts, explicit parameters, and local conventions that can
be overridden by the consuming workspace.

When a workflow depends on a deterministic helper script, declare that
relationship explicitly with dependencies and `#use/<skill-name>` tags.

## Repository Layout

- [AGENTS.md](./AGENTS.md): repository-level installation metadata
- [README.md](./README.md): project overview
- [CONTRIBUTING.md](./CONTRIBUTING.md): contribution guidance
- [GOVERNANCE.md](./GOVERNANCE.md): workflow-skill repository governance
- [SUSTAINABILITY.md](./SUSTAINABILITY.md): funding and maintenance model
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md): collaboration standards
- [SECURITY.md](./SECURITY.md): security reporting guidance
- [CHANGELOG.md](./CHANGELOG.md): notable repository changes
- [LICENSE.md](./LICENSE.md): MIT license
- [`.skills/SKILLS.md`](./.skills/SKILLS.md): low-cost skill discovery catalog

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

See [SECURITY.md](./SECURITY.md).

## License

Released under the MIT license. See [LICENSE.md](./LICENSE.md).
