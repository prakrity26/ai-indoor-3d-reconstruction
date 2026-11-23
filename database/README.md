# database

Project and job metadata shared by the API and the worker.

**Phase:** 11 · **Status:** implemented

Videos, frames, meshes, and splats stay on disk. The `jobs` table stores, per project: id, status,
stage and progress, name and description, file paths, error, visibility and share token, origin
(`upload` or `sample`), and timestamps.

SQLite is the default (`data/jobs/index.sqlite`, WAL mode, so the API and a worker can share it).
PostgreSQL is used when `DATABASE_URL` starts with `postgresql://` and needs the driver:

```bash
pip install -e ".[db]"
```

## Migrations

Numbered SQL files in `migrations/` are applied once each, in order, when a connection opens.
Applied versions are recorded in `schema_migrations`. A database created before version tracking
existed (only `001` applied) is upgraded in place by `002_projects.sql`.

| File | Adds |
|---|---|
| `001_jobs.sql` | The `jobs` table |
| `002_projects.sql` | Name, description, visibility, share token, stage, progress, mesh path, origin, updated time |

To change the schema, add `003_<name>.sql`; never edit an applied file.

Tests use a temporary SQLite file and do not start Postgres.
