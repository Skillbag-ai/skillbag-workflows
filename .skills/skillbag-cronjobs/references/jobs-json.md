# jobs.json Format

`jobs.json` is the durable state file for one cronjobs installation.

```json
{
  "schema_version": 1,
  "installation": {
    "id": "root",
    "type": "root",
    "cronjobs_folder": "cronjobs",
    "timezone": "local",
    "versioned": true,
    "check_interval_seconds": 3600,
    "agent": {
      "command": "codex",
      "args": ["exec", "--ask-for-approval", "never"],
      "prompt_mode": "argument",
      "timeout_seconds": 1800,
      "detected_path": null
    },
    "scheduler": {
      "installed": true,
      "platform": "linux",
      "timer": "skillbag-cronjobs.timer",
      "installed_at": "2026-05-28T09:00:00+02:00"
    }
  },
  "children": ["projects/example/cronjobs/jobs.json"],
  "runtime": {
    "last_checked_at": null
  },
  "jobs": []
}
```

Child installations use `"type": "child"` and do not define
`check_interval_seconds`. The root installation owns the scheduler and checks
all child `jobs.json` files listed in `children`. Root installation should
install the scheduler immediately, before any background jobs exist.

## Job Object

```json
{
  "id": "check-work-emails",
  "enabled": true,
  "background": false,
  "prompt": "Check work emails and summarize urgent items.",
  "schedule": {
    "type": "cron",
    "expression": "0 9 * * 1-5"
  },
  "catch_up": true,
  "misfire_grace_seconds": 3600,
  "created_at": "2026-05-28T09:00:00+02:00",
  "last_due_at": null,
  "last_run_at": null,
  "last_status": "never",
  "last_result": null
}
```

One-time jobs use:

```json
"schedule": {
  "type": "once",
  "at": "2026-06-01T09:00:00+02:00"
}
```

## Field Rules

- `id` MUST match `[a-z0-9]+(-[a-z0-9]+)*`, be at most 64 characters, and not
  be a Windows reserved filename such as `con`, `nul`, `com1`, or `lpt1`.
- `background: true` jobs are run by the root background runner only.
- `background: false` jobs are only run after the user explicitly says GO.
- `catch_up: true` runs one consolidated execution for missed recurring runs.
- `catch_up: false` marks missed runs as `delayed` once they exceed
  `misfire_grace_seconds`.
- `last_due_at` records the last scheduled occurrence that was handled.
- `last_run_at` records the last actual execution attempt.
- `last_status` SHOULD be one of `never`, `executed`, `failed`, `delayed`,
  `aborted`, `timeout`, `needs-input`, or `skipped`.
- Cleanup MAY remove one-time jobs with `executed` status, or failed one-time
  jobs only after the latest job log entry is checked.

## Cron Expressions

The helper supports classic five-field cron expressions:

```text
minute hour day-of-month month day-of-week
```

Supported syntax:

- wildcards: `*`
- lists: `1,15,30`
- ranges: `1-5`
- steps: `*/15`, `1-10/2`
- month names: `JAN` through `DEC`
- weekday names: `SUN` through `SAT`

Weekday `0` and `7` both mean Sunday. When both day-of-month and day-of-week
are restricted, classic cron OR semantics apply.
