---
name: skillbag-chrono-log
description: Create or update a folder-local chronological Markdown log with the newest dated section first. #use/skillbag-python-ensure
dependencies:
  - name: skillbag-python-ensure
metadata:
  author: backupdev
  version: 1.0.0
---

## Parameters

```yaml
required:
  - name: target-folder
  - name: text
optional:
  - name: filename
    default: log.md
  - name: date
    default: today
  - name: mode
    default: append
    values:
      - append
      - replace
  - name: weekday-locale
    default: en
    values:
      - en
      - de
      - es
      - fr
      - it
      - nl
      - pt
      - none
```

## Instructions

- Use this skill when the user asks to maintain a local chronological log,
  journal, changelog-like note, incident history, progress log, or dated
  folder record.
- Invoke `skillbag-python-ensure` with `minimum-version=3.9` before running
  the bundled Python helper.
- Treat `target-folder` as the only write boundary. Write only
  `<target-folder>/<filename>` and create `target-folder` when needed.
- Ask only for missing required inputs. If the target folder and log text are
  already clear, update the log directly.
- Keep entries concise unless the user provides longer Markdown content.
- Preserve existing Markdown formatting inside the log as much as possible.
- Use `mode=append` to add new content at the top of an existing date section.
  Use `mode=replace` only when the user asks to replace or consolidate that
  date's section.
- Use `weekday-locale` for the weekday label in headings. Use `none` when the
  log should avoid language-specific weekday names.

## Log Format

The default heading format is:

```md
## YYYY-MM-DD, Weekday
entry text
```

With `weekday-locale=none`, headings are:

```md
## YYYY-MM-DD
entry text
```

Rules:

- the newest dated section stays at the top
- new content for an existing date is inserted directly under that date heading
- replacing a date rewrites only that date section
- sections are separated by exactly one blank line

## Execution

From the SkillBag source root:

```bash
python3 .skills/skillbag-chrono-log/scripts/update_log.py <target-folder> --text "New entry"
```

With options:

```bash
python3 .skills/skillbag-chrono-log/scripts/update_log.py <target-folder> --filename history.md --date 2026-05-08 --mode replace --weekday-locale en --text "Consolidated daily summary"
```
