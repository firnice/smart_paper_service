# Backend Code Layout Convention

## Goal
Keep runtime code, docs, tests, scripts, and local artifacts clearly separated.

## Directory Standard

```text
lf-smart-paper-service/
  app/                # FastAPI runtime code
  alembic/            # Database migrations
  docs/               # Product/technical documents
  scripts/            # Developer utility scripts
  tests/              # Smoke/manual test scripts
  logs/               # Local runtime logs (gitignored)
  storage/            # Local runtime file storage (gitignored)
```

## Placement Rules

- Put all business code under `app/`; avoid adding executable code at repo root.
- Put migration versions only under `alembic/versions/`.
- Put one-off scripts under `scripts/`.
- Put smoke/integration helper tests under `tests/`.
- Put markdown documents under `docs/` (do not scatter docs at root).
- Always run backend commands from the `lf-smart-paper-service/` root.
- Runtime defaults (DB/storage) are bound to `lf-smart-paper-service/storage/`, not parent directories.

## Git Rules

- Never commit local runtime artifacts:
  - `*.db`, `*.sqlite3`
  - `logs/*`
  - `storage/*`
  - temporary exported files (test PDF/Word)
- Keep folder placeholders with `.gitkeep` when needed.

## File Naming

- Python files: snake_case (`wrong_questions.py`).
- Markdown files: kebab-case or numeric prefix for sequenced docs (`01-juyifansan-mvp.md`).
- Test scripts: `test_*.py`.
