# Changelog

All notable changes to this repository should be documented in this file.

The format is intentionally simple while the project remains a draft.

## v0.2.2

- Fixed the default `skillbag-cronjobs` Codex invocation so it uses
  `codex exec` options that are accepted in noninteractive runs.
- Added validation warnings for Codex background job args that can fail under
  `codex exec`, including `--ask-for-approval` after `exec`.

## v0.2.1

- Updated `skillbag-cronjobs` so root installation installs the OS scheduler
  immediately after confirmation.
- Added cleanup support that lists removable one-time jobs across root and
  child cronjobs folders before removing approved jobs and their Markdown logs.

## v0.2.0

- Added `skillbag-cronjobs` for maintaining local `jobs.json` cron-style
  agent jobs, pending-job reminders, background execution, child job files,
  lock-based run protection, job logs, and scheduler setup helpers.

## v0.1.0

- Created `skillbag-workflows` as a SkillBag source for reusable local
  workflow skills.
- Added `skillbag-chrono-log` for maintaining folder-local chronological
  Markdown logs with configurable weekday labels and a
  `skillbag-python-ensure` dependency.
