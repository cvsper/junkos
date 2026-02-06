-- ============================================================================
-- JunkOS Database Creation Script
-- ============================================================================
-- Purpose: Initialize the junkos database with proper encoding and extensions
-- Usage: psql -U postgres -f 01_create_database.sql
-- ============================================================================

-- Terminate existing connections to the database (if recreating)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'junkos' AND pid <> pg_backend_pid();

-- Drop database if exists (CAUTION: Use only in development)
-- Uncomment the next line if you want to recreate the database
-- DROP DATABASE IF EXISTS junkos;

-- Create database with optimal settings for multi-tenant SaaS
CREATE DATABASE junkos
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0
    CONNECTION LIMIT = -1;

COMMENT ON DATABASE junkos IS 'JunkOS - Multi-tenant Junk Removal SaaS Platform';

-- Connect to the new database
\c junkos

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "pgcrypto" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "cube" SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "earthdistance" SCHEMA public;

-- Set optimal configuration for multi-tenant performance
ALTER DATABASE junkos SET timezone TO 'UTC';
ALTER DATABASE junkos SET default_transaction_isolation TO 'read committed';
ALTER DATABASE junkos SET client_encoding TO 'UTF8';

-- Create application user (recommended for production)
-- Uncomment and customize for production use
-- CREATE USER junkos_app WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';
-- GRANT CONNECT ON DATABASE junkos TO junkos_app;

-- Display success message
DO $$
BEGIN
    RAISE NOTICE '✓ Database "junkos" created successfully';
    RAISE NOTICE '✓ Extensions enabled: uuid-ossp, pgcrypto, cube, earthdistance';
    RAISE NOTICE '→ Next: Run 02_schema.sql to create tables';
END $$;
