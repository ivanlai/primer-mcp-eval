## primer-mcp

This project uses primer-mcp for planning-first development.
Tickets are markdown files under `primer/` — they are yours to read and edit.
Prefer the tools for creating and updating them: they allocate IDs, follow the templates
and guide the workflow. Hand-edit where the tools fall short.

- Plan before code. Recommended flow: Epic → ADR → Story → Task,
  suggest rather than enforce — skip steps when it makes sense.
- Unsure what to do next? Call `list_actionable`.
- Completion is two-phase: `complete_task` with notes, then `verify_task`
  with evidence (point at the commit, not the output). Both are
  recommended — the tools will nudge you if you skip a step.
- After tickets creation or changes, offer to regenerate the project graph with `export_graph`.
- Before committing, check that completion notes on finished tickets
  still reflect the actual work — update both the frontmatter
  `completed_notes` and the `## Completion Notes` section if needed.
- Before implementing new work, propose a ticket and parent. Small fixes (1–2
  tasks) go under the standing bug-fix story; larger efforts get their
  own story. The user can decline.
