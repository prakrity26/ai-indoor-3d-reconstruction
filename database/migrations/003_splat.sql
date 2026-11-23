-- Gaussian splat training runs on a GPU worker, separately from the mesh pipeline.
-- splat_status: none | queued | running | succeeded | failed

ALTER TABLE jobs ADD COLUMN splat_status TEXT NOT NULL DEFAULT 'none';
ALTER TABLE jobs ADD COLUMN splat_stage TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN splat_progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN splat_error TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN splat_worker TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN splat_updated_at TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS jobs_splat_status ON jobs (splat_status, created_at);
