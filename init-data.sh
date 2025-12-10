#!/bin/bash
# LIMA - PostgreSQL Initialization Script
# Creates non-root user for n8n and enables pgvector extension
#
# This script runs automatically on first container start via
# /docker-entrypoint-initdb.d/

set -e

echo "=== LIMA PostgreSQL Initialization ==="

# =============================================================================
# Create non-root user for n8n (principle of least privilege)
# =============================================================================

if [ -n "$N8N_DB_USER" ] && [ -n "$N8N_DB_PASSWORD" ]; then
    echo "Creating n8n database user: $N8N_DB_USER"

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        -- Create n8n user if not exists
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$N8N_DB_USER') THEN
                CREATE USER $N8N_DB_USER WITH PASSWORD '$N8N_DB_PASSWORD';
            END IF;
        END
        \$\$;

        -- Grant privileges on database
        GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $N8N_DB_USER;

        -- Grant schema privileges
        GRANT ALL ON SCHEMA public TO $N8N_DB_USER;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $N8N_DB_USER;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $N8N_DB_USER;

        -- Set default privileges for future objects
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $N8N_DB_USER;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $N8N_DB_USER;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $N8N_DB_USER;
EOSQL

    echo "n8n user created successfully"
else
    echo "WARNING: N8N_DB_USER or N8N_DB_PASSWORD not set, skipping user creation"
fi

# =============================================================================
# Enable pgvector extension (for future semantic search features)
# =============================================================================

echo "Enabling pgvector extension..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "pgvector extension enabled"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=== LIMA PostgreSQL Initialization Complete ==="
echo "Database: $POSTGRES_DB"
echo "n8n User: $N8N_DB_USER"
echo "Extensions: pgvector"
echo ""
