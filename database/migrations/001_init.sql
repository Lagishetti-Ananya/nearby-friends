-- Initial schema. Applied automatically on first Postgres container start via schema.sql.
-- Kept here so the migration history is explicit for the hackathon write-up.

\i /docker-entrypoint-initdb.d/001_schema.sql
