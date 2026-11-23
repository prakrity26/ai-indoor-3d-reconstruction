-- Projects: user-facing name, description, sharing, per-stage progress, and sample rows.
-- Applied once; database/session.py records the version in schema_migrations.

ALTER TABLE jobs ADD COLUMN name TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE jobs ADD COLUMN share_token TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN stage TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN mesh_path TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN origin TEXT NOT NULL DEFAULT 'upload';
ALTER TABLE jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS jobs_share_token ON jobs (share_token);
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs (status, created_at);
