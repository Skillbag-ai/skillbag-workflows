# Security

Please report security concerns privately to the maintainers instead of
opening a public issue.

Workflow skills often read and write local project notes. Those notes may
contain sensitive operational, business, personal, or customer information.

## Security Expectations

- Keep generated artifacts local unless a consuming workspace explicitly adds
  a remote publishing or sync policy.
- State write boundaries clearly in each skill.
- Do not add network upload defaults to workflow skills.
- Treat logs, handoffs, decisions, and summaries as potentially sensitive.
- Prefer explicit user confirmation before destructive or broad file changes.

## Reports

When reporting a security issue, include:

- affected skill or file
- expected behavior
- observed behavior
- steps to reproduce, if safe to share
- potential exposure or impact
