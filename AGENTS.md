# AGENTS.md (lf-smart-paper-service)

## Scope
- This git repo root is `lf-smart-paper-service/`.
- Only edit files under this repo.
- Do not create, modify, or delete files in parent directories (`../`), including workspace root.

## Working Rules
- Run backend commands from this repo root.
- Keep runtime artifacts inside this repo (`storage/`, `logs/`).
- Never introduce path logic that depends on external working directory.

## Temporary Rule (Frontend-First Coordination)
- During current phase, backend only handles user-requested blocking fixes.
- Do not proactively expand backend feature scope until frontend interaction/UI is confirmed complete.
- Remove this temporary rule when backend feature implementation officially starts.
