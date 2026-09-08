# Project rules

This is a learning project for mechanical design knowledge and multidisciplinary
integration. Read README.md, docs/roadmap.md, and the relevant model assumptions
before substantive changes.

- Preserve the user's learning ownership. Provide inspectable examples and
  verification, and distinguish AI-assisted implementation from user understanding.
- Keep physical models separate from input handling, constraint evaluation, and UI.
- Use explicit SI units, finite inputs, model versions, and documented assumptions.
- Never convert unevaluated disciplines, unsupported conditions, or solver failures
  into a pass. A small set of passing calculations is not full product validation.
- Add meaningful analytical/benchmark or behavioral tests when extending models.
- Run pytest, Ruff check, Ruff format --check, and pip check before committing code.
- Do not introduce heavy solvers, external services, or automatic design decisions
  until the associated learning case and validation approach are specified.
- The user made GitHub public on 2026-09-08. License choice remains a user decision.

## KnowledgeBase bridge on the owner's PC

- Resolve cwd before project inspection. Development root is
  `%USERPROFILE%\dev\Projects`; stop with `WRONG_WORKSPACE` outside that root.
- Canonical Vault: `%USERPROFILE%\OneDrive\ドキュメント\KnowledgeBase`.
- Read `40_Structures\エージェント起動時メモリ.md` and
  `90_Projects\mech-design-study\agent_context.md` in the Vault before substantial work.
- Run the Vault's `95_System\scripts\agent_memory_io.py context-digest --project
  mech-design-study`; fold unfolded entries into the current state, then use
  `touch-context --project mech-design-study` after checking current reality.
- Keep executable files and artifacts here. Write decisions and next actions to
  the Vault via `agent_memory_io.py add-log --project mech-design-study`.
- Do not copy private Vault content, conversation logs, or personal data into Git.
- If the Vault is unavailable, report that fact; do not invent remembered context.
