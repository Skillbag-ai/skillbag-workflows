---
name: skillbag-case-context
description: "Create and maintain bounded case contexts for non-routine incidents, requests, procedures, disputes, or follow-ups, with current state, source-document inventories, and chronological history. #use/skillbag-chrono-log"
dependencies:
  - name: skillbag-chrono-log
    source: git@github.com:Skillbag-ai/skillbag-workflows.git
    version: main
    required: true
  - name: skillbag-cronjobs
    source: git@github.com:Skillbag-ai/skillbag-workflows.git
    version: main
    required: false
  - name: skillbag-pdf-ocr
    source: git@github.com:Skillbag-ai/skillbag-docs.git
    version: main
    required: true
metadata:
  author: backupdev
  version: 1.0.0
---

## Purpose And Boundary

A case is a bounded, non-routine matter that may need to be understood or
handled across multiple sessions. It may originate from an incident, request,
procedure, dispute, decision, or follow-up.

- Use a case for one matter with its own evidence, current state, and history.
- Use a project for a goal-oriented workstream with a roadmap or multiple
  deliverables, a process for a recurring routine, and a task for one action.
- Create a case only when the user explicitly asks to open or create one.
  Existing cases may be resumed or maintained when the requested case is clear.
- Do not mix unrelated matters in one case.

## Location And Shape

Respect a case collection or exact case path configured by the user or the
surrounding workspace. Otherwise, create new cases at:

```text
cases/YYYY-MM-short-name/
├── CONTEXT.md
├── docs/
├── docs.md
└── log.md
```

Use the opening month for `YYYY-MM` unless the user or workspace specifies a
reference month. Choose a concise, stable, lowercase slug for `short-name`.
Write case artifacts in the language requested by the user or established by
the surrounding workspace; translate template headings when appropriate.

For an existing case, preserve its established names and layout. In
particular, treat `files/` and `files.md` as equivalents of `docs/` and
`docs.md`; continue using them and do not create a parallel structure, rename
them, or migrate their contents unless the user explicitly requests it.

The resolved case folder is the default write boundary. Do not update a parent
collection index or log, or create or move canonical artifacts outside the
case, unless the user or surrounding workspace requires it.

Keep agent-created analyses, working notes, drafts, transcripts, and similar
work products directly in the case folder or in an established local working
area, not among the source documents.

## Current Context

Use `CONTEXT.md` as the compact resume point for the current case, not as a
second chronological history. For a new case, start with:

```md
# Case: <title>

Status: active
Started: YYYY-MM-DD
Updated: YYYY-MM-DD

## Purpose and scope

## Current state

## Open questions

## Next action

## Related contexts

## Case-specific rules
```

The final two sections are optional. Keep the file current when material facts,
open questions, next actions, relationships, or status change. Put stable,
reusable workflow rules in this skill or the surrounding workspace rather than
copying them into every case.

## Resuming Work

Before substantive work on a case:

1. Read applicable instructions and context above the case.
2. Read the case `CONTEXT.md`.
3. Reconcile the document inventory recursively with the document folder.
4. Review recent and materially relevant entries in `log.md`.
5. Inspect the source documents needed for the current request.

Ask for clarification only when the case path or scope cannot be resolved
safely from the request and local context.

## Source Documents And Inventory

- Keep user-provided or external source material in `docs/`, or in the
  established equivalent such as `files/`.
- Preserve originals. Never overwrite an original with OCR, transcription,
  redaction, normalization, or edited content.
- Prefer a reference to a canonical source over an unnecessary copy. When a
  source is copied into the case, record its provenance when known.
- Keep `docs.md` synchronized with every file below `docs/`, recursively; apply
  the same rule to an established equivalent. Explicitly record when the
  document folder is empty.
- If a previously inventoried file is unexpectedly absent, flag it instead of
  silently dropping its entry. Reconcile whether the removal was intentional,
  record a meaningful removal in `log.md`, and then update the inventory to
  reflect the resolved state.
- Record at least each file's relative path, intake date, and concise role in
  the case. Use `unknown` rather than inventing an intake date. Add document
  date, provenance, readability, derivative relationship, or a content hash
  only when useful.
- Treat a technical derivative as another representation of its source, not as
  independent evidence.

## PDF Readability And OCR

During inventory reconciliation, identify every source PDF that is new,
changed, or not yet assessed. Assess its text layer before relying on its
contents; if the text layer is unusable, invoke `skillbag-pdf-ocr`.

- Keep the original PDF unchanged.
- Unless the case has another established convention, place the result beside
  the original as `<original-stem>_OCR.pdf`.
- Reuse an existing usable OCR derivative when it still corresponds to the
  current original. Regenerate it through `skillbag-pdf-ocr` only when stale or
  explicitly requested.
- After OCR, reconcile the inventory and identify the OCR file as a technical
  derivative of the original.
- Do not recursively treat an identified OCR derivative as a new independent
  source PDF.

## Evidence And History

Distinguish clearly between:

- facts supported by a document or other recorded evidence
- statements supplied by the user or another person
- assessments or inferences
- unresolved questions

Use `skillbag-chrono-log` to record meaningful events, decisions,
communications, actions, and state changes in `log.md`, with the newest dated
section first. Do not log every trivial file inspection or technical command.
Record who performed an external action when that is known. If later evidence
invalidates an earlier assumption, preserve the historical entry and mark the
assumption as superseded in a new entry; update `CONTEXT.md` to the current
state without rewriting history.

## Lifecycle And Relationships

Use only the lightweight statuses `active`, `waiting`, and `closed` unless the
workspace already defines another scheme.

- When waiting, state what is awaited and keep a concrete next action when one
  exists.
- When closing, record the outcome and closure date in the context and log.
  Closing does not delete, move, or automatically archive the case.
- A closed case may be reopened; update its context and log the reason.
- Link related cases instead of merging their histories. Split a matter when a
  part gains an independent scope, responsible party, or resolution path.
- When the user or surrounding workspace requires a durable final artifact in
  a canonical domain location, link it from the case and retain the case as
  working and audit history.

## Authority And Reminders

Do not contact third parties, submit documents, install a scheduler, or perform
another external action without the authority required for that action. A plan
or due date in a case is not authorization to act.

Create a scheduled reminder only when the user explicitly requests one. Use
`skillbag-cronjobs` when it is available and follow its confirmation and
scheduler rules. If the optional skill is unavailable, keep the due item visible
in `CONTEXT.md`, state that no scheduled reminder was created, and offer to
install the optional skill rather than implying that a reminder exists.

Keep the default case lean. Do not add a task file, decision log, central case
index, metadata manifest, complex status model, or archive automation unless
the user or surrounding workspace has a concrete need for it.
