-- Least-privilege PostgreSQL role separation for local production stack.
-- Migrator owns schema; argus_app and argus_worker are non-superuser, NOBYPASSRLS roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'argus_app') THEN
        CREATE ROLE argus_app LOGIN PASSWORD 'argus_app_local_dev' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'argus_worker') THEN
        CREATE ROLE argus_worker LOGIN PASSWORD 'argus_worker_local_dev' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;

GRANT CONNECT ON DATABASE argus TO argus_app, argus_worker;
GRANT USAGE ON SCHEMA public TO argus_app, argus_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO argus_app, argus_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO argus_app, argus_worker;
