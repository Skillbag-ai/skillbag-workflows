# SkillBag Workflows Governance

SkillBag Workflows is a companion repository for reusable local workflow
skills. It is not the normative standard. The normative specification lives in
the core SkillBag repository.

## Scope

This repository may define recurring work routines such as logs, handoffs,
decision records, status updates, review packets, checklists, and session
recaps.

It should not define low-level runtime utilities, document conversion
mechanics, media processing mechanics, or resource-store semantics when those
belong in another SkillBag companion repository.

## Relationship to the Standard

Workflow skills should:

- follow the current `SKILLBAG.md` rules
- keep `.skills/SKILLS.md` synchronized
- avoid hidden normative behavior
- document parameters and write boundaries clearly
- preserve compatibility with the base skill format where practical

## Maintainer Decisions

Maintainers may merge workflow changes when they are focused, documented, and
compatible with the core standard.

Changes should be moved to another repository when they:

- primarily provide utility bootstrapping or runtime checks
- primarily transform document or media formats
- primarily define resource-store layout, indexing, or query behavior
- encode one organization's private process as a default for all users
- alter core SkillBag semantics

## Releases

Release notes should identify:

- new workflow skills
- breaking parameter or behavior changes
- compatibility updates required by the core standard
- security-relevant changes

## Sponsorship

Sponsorship can fund workflow maintenance, tests, and documentation. It does
not grant private control over workflows or the core standard.

See [SUSTAINABILITY.md](./SUSTAINABILITY.md) for funding principles.
