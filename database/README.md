# database

Job status for the API and the worker.

**Phase:** 11  
**Status:** implemented

The video file and the splat stay on disk. The database stores the job id, status, filename, paths, and error.

On this laptop the table is SQLite at `data/jobs/index.sqlite`. That is the default, so the API runs without Postgres.

PostgreSQL uses the same table when `DATABASE_URL` starts with `postgresql://`. That needs the driver:

```bash
pip install -e ".[db]"
```

Schema version: `database/migrations/001_jobs.sql`. Tests use a temporary SQLite file and do not start Postgres.
