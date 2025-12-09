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
# Enable pgvector extension
# =============================================================================

echo "Enabling pgvector extension..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable pgvector for vector similarity search
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Verify extension is enabled
    SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
EOSQL

echo "pgvector extension enabled"

# =============================================================================
# Create LIMA-specific tables (optional, can be done via n8n workflows)
# =============================================================================

echo "Creating LIMA schema..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Meetings table: stores meeting metadata
    CREATE TABLE IF NOT EXISTS meetings (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500),
        meeting_date TIMESTAMP WITH TIME ZONE,
        audio_file VARCHAR(1000),
        duration_seconds INTEGER,
        participants TEXT[],
        tags TEXT[],
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Transcripts table: stores full transcription text
    CREATE TABLE IF NOT EXISTS transcripts (
        id SERIAL PRIMARY KEY,
        meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        language VARCHAR(10) DEFAULT 'en',
        model_used VARCHAR(100),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Chunks table: stores transcript chunks with embeddings for semantic search
    CREATE TABLE IF NOT EXISTS chunks (
        id SERIAL PRIMARY KEY,
        transcript_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        start_time FLOAT,
        end_time FLOAT,
        speaker VARCHAR(200),
        embedding vector(1536),  -- OpenAI ada-002 compatible, adjust for your model
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create vector similarity search index (IVFFlat for large datasets)
    CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);

    -- Insights table: stores extracted insights (decisions, actions, risks, etc.)
    CREATE TABLE IF NOT EXISTS insights (
        id SERIAL PRIMARY KEY,
        meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
        insight_type VARCHAR(50) NOT NULL,  -- 'decision', 'action', 'risk', 'question', 'summary'
        content TEXT NOT NULL,
        assignee VARCHAR(200),
        due_date DATE,
        priority VARCHAR(20),
        status VARCHAR(50) DEFAULT 'open',
        source_chunk_id INTEGER REFERENCES chunks(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create indexes for common queries
    CREATE INDEX IF NOT EXISTS meetings_date_idx ON meetings(meeting_date DESC);
    CREATE INDEX IF NOT EXISTS meetings_tags_idx ON meetings USING GIN(tags);
    CREATE INDEX IF NOT EXISTS insights_type_idx ON insights(insight_type);
    CREATE INDEX IF NOT EXISTS insights_meeting_idx ON insights(meeting_id);
    CREATE INDEX IF NOT EXISTS insights_status_idx ON insights(status);

    -- Grant permissions to n8n user
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $N8N_DB_USER;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $N8N_DB_USER;
EOSQL

echo "LIMA schema created"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=== LIMA PostgreSQL Initialization Complete ==="
echo "Database: $POSTGRES_DB"
echo "n8n User: $N8N_DB_USER"
echo "Extensions: pgvector"
echo "Tables: meetings, transcripts, chunks, insights"
echo ""
