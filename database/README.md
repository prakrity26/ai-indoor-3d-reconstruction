# database

Job metadata and result persistence.

**Phase:** 11  
**Status:** placeholder

Planned layout:

- `models/` — ORM / table definitions
- `repositories/` — query helpers used by API and worker
- `migrations/` — schema versions

PostgreSQL is declared in Compose. No tables or SQLAlchemy code in Phase 0.
