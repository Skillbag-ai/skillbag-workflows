# Contributing to SkillBag Workflows

Thanks for contributing.

This repository contains reusable workflow skills for SkillBag workspaces.
Good contributions keep recurring work clear, local-first, and easy to
compose.

## Before You Start

- Read [README.md](./README.md).
- Read [AGENTS.md](./AGENTS.md).
- Review the current workflow skills in [`.skills/`](./.skills/).

## What Good Contributions Look Like

Strong contributions usually do at least one of the following:

- add a reusable workflow for maintaining local work artifacts over time
- clarify a workflow's inputs, write boundaries, or failure behavior
- improve composition with `skillbag-utils`, `skillbag-docs`,
  `skillbag-media`, or `skillbag-resources`
- reduce hidden assumptions about project management, reporting, or note
  structures
- keep `SKILLS.md` and skill metadata synchronized

## Skill Editing Rules

When editing or adding a workflow skill:

- keep the canonical skill name stable unless a rename is intentional
- keep the `description` concise because it is part of the discovery surface
- preserve valid YAML frontmatter followed by Markdown instructions
- keep `metadata.version` in semantic version format
- update [`.skills/SKILLS.md`](./.skills/SKILLS.md) so it stays exact and sorted
- move large secondary detail into `references/`, `scripts/`, or `assets/`
  only when needed
- declare dependencies and `#use/<skill-name>` tags when a workflow relies on
  another skill

## What To Avoid

Avoid changes that:

- duplicate rules that belong in the core SkillBag standard
- turn local workflow guidance into a rigid organization-specific process
- silently write outside the documented workflow boundaries
- leave skill descriptions or catalog entries out of sync
- add broad skills that overlap existing document, media, resource, or utility
  repositories

## Pull Requests

Pull requests should:

- stay focused on one workflow or one logical behavior change
- update documentation affected by the change
- call out any parameter, metadata, dependency, or behavior change clearly

## Changelog

If the change is meaningful for users of this repository, add a short entry to
[CHANGELOG.md](./CHANGELOG.md).
