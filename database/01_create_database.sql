-- ============================================================================
-- Umuve Database Creation Script
-- ============================================================================
-- Purpose: Initialize the umuve database with proper encoding and extensions
-- Usage: psql -U postgres -f 01_create_database.sql
-- ============================================================================

-- Terminate existing connections to the database (if recreating)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'umuve' AND pid <> pg_backend_pid();

-- Drop database if exists (CAUTION: Use only in development)
-- Uncomment the next line if you want to recreate the database
-- DROP DATABASE IF EXISTS umuve;

-- Create database with optimal settings for multi-tenant SaaS
CREATE DATABASE umuve
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0
    CONNECTION LIMIT = -1;

COMMENT ON DATABASE umuve IS 'Umuve - Multi-tenant Junk Removal SaaS Platform';

-- Connect to the new database
\c umuve

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "pgcrypto" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "cube" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "earthdistance" SCHEMA public;

-- Set optimal configuration for multi-tenant performance
ALTER DATABASE umuve SET timezone TO 'UTC';
ALTER DATABASE umuve SET default_transaction_isolation TO 'read committed';
ALTER DATABASE umuve SET client_encoding TO 'UTF8';

-- Create application user (recommended for production)
-- Uncomment and customize for production use
-- CREATE USER umuve_app WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';
-- GRANT CONNECT ON DATABASE umuve TO umuve_app;

-- Display success message
DO $$
BEGIN
    RAISE NOTICE '✓ Database "umuve" created successfully';
    RAISE NOTICE '✓ Extensions enabled: uuid-ossp, pgcrypto, cube, earthdistance';
    RAISE NOTICE '→ Next: Run 02_schema.sql to create tables';
END $$;
