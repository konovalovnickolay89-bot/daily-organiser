"""Idempotent SQL for Sprint 2.

The process applies this on boot so a database stamped at 0001 still starts.
Alembic revision 0002 runs the same statements. Either order is safe.
"""

SPRINT2_UPGRADE: tuple[str, ...] = (
    "ALTER TABLE system_state ADD COLUMN IF NOT EXISTS assistant_enabled BOOLEAN NOT NULL DEFAULT true",
    """
    CREATE TABLE IF NOT EXISTS shopping_items (
        id UUID PRIMARY KEY,
        name VARCHAR(80) NOT NULL,
        ticked BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT ck_shopping_items_name CHECK (char_length(name) > 0)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_shopping_items_ticked ON shopping_items (ticked)",
    """
    CREATE TABLE IF NOT EXISTS calendar_subscriptions (
        id UUID PRIMARY KEY,
        provider VARCHAR(16) NOT NULL DEFAULT 'google',
        calendar_id VARCHAR(200) NOT NULL,
        display_name VARCHAR(200) NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT uq_calendar_subscriptions_calendar UNIQUE (provider, calendar_id),
        CONSTRAINT ck_calendar_subscriptions_provider CHECK (provider = 'google'),
        CONSTRAINT ck_calendar_subscriptions_name CHECK (char_length(display_name) > 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS integration_status (
        name VARCHAR(32) PRIMARY KEY,
        last_ok_at TIMESTAMP WITH TIME ZONE,
        last_error_class VARCHAR(40),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT ck_integration_status_name CHECK (name in ('weather', 'diary'))
    )
    """,
    "ALTER TABLE agent_proposals DROP CONSTRAINT IF EXISTS ck_agent_proposals_action",
    """
    ALTER TABLE agent_proposals ADD CONSTRAINT ck_agent_proposals_action
    CHECK (action in (
        'create_task', 'update_task', 'create_commitment', 'update_commitment',
        'add_note', 'create_shopping_item'
    ))
    """,
)

SPRINT2_DOWNGRADE: tuple[str, ...] = (
    "ALTER TABLE agent_proposals DROP CONSTRAINT IF EXISTS ck_agent_proposals_action",
    """
    ALTER TABLE agent_proposals ADD CONSTRAINT ck_agent_proposals_action
    CHECK (action in (
        'create_task', 'update_task', 'create_commitment', 'update_commitment', 'add_note'
    ))
    """,
    "DROP TABLE IF EXISTS integration_status",
    "DROP TABLE IF EXISTS calendar_subscriptions",
    "DROP TABLE IF EXISTS shopping_items",
    "ALTER TABLE system_state DROP COLUMN IF EXISTS assistant_enabled",
)


# Idempotent SQL for Sprint 3. The process applies this on boot. Alembic 0003
# runs the same statements. Either order is safe.
SPRINT3_UPGRADE: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS commute_shifts (
        id UUID PRIMARY KEY,
        start_at TIMESTAMP WITH TIME ZONE NOT NULL,
        end_at TIMESTAMP WITH TIME ZONE NOT NULL,
        location_label VARCHAR(40) NOT NULL,
        CONSTRAINT ck_commute_shifts_label CHECK (location_label = 'Wembley'),
        CONSTRAINT ck_commute_shifts_order CHECK (end_at > start_at)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_commute_shifts_start ON commute_shifts (start_at)",
    "ALTER TABLE catchup_items ADD COLUMN IF NOT EXISTS fallback_used BOOLEAN NOT NULL DEFAULT false",
)

SPRINT3_DOWNGRADE: tuple[str, ...] = (
    "ALTER TABLE catchup_items DROP COLUMN IF EXISTS fallback_used",
    "DROP TABLE IF EXISTS commute_shifts",
)


# Sprint 5 memory. Alembic 0004 runs these statements. The process also applies
# the upgrade on boot, after Sprint 2, so a database from 0003 still starts
# once the vector extension is installed. Either order is safe.
#
# The proposal action check is widened here and not in the Sprint 2 boot path.
# Re-applying the narrower Sprint 2 check would reject rows already saved.
MEMORY_UPGRADE: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS memory_items (
        id UUID PRIMARY KEY,
        kind VARCHAR(16) NOT NULL,
        text VARCHAR(400) NOT NULL,
        source VARCHAR(16) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        last_used_at TIMESTAMP WITH TIME ZONE,
        pinned BOOLEAN NOT NULL DEFAULT false,
        embedding vector(1024),
        CONSTRAINT ck_memory_items_kind CHECK (kind in ('preference', 'fact', 'routine')),
        CONSTRAINT ck_memory_items_source CHECK (source in ('remember', 'forget', 'smart-add', 'manual')),
        CONSTRAINT ck_memory_items_text CHECK (char_length(text) > 0)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_memory_items_pinned ON memory_items (pinned)",
    """
    CREATE INDEX IF NOT EXISTS ix_memory_items_embedding
    ON memory_items USING hnsw (embedding vector_cosine_ops)
    """,
    "ALTER TABLE agent_proposals ADD COLUMN IF NOT EXISTS memories_used INTEGER",
    "ALTER TABLE agent_proposals DROP CONSTRAINT IF EXISTS ck_agent_proposals_action",
    """
    ALTER TABLE agent_proposals ADD CONSTRAINT ck_agent_proposals_action
    CHECK (action in (
        'create_task', 'update_task', 'create_commitment', 'update_commitment',
        'add_note', 'create_shopping_item', 'remember', 'forget'
    ))
    """,
)

# Rollback drops the memories, the usage count, and the extension in this
# database. Remember and forget cards are removed first so the narrower action
# check can be restored. Restore a backup if those rows should come back.
MEMORY_DOWNGRADE: tuple[str, ...] = (
    "DELETE FROM agent_proposals WHERE action in ('remember', 'forget')",
    "ALTER TABLE agent_proposals DROP CONSTRAINT IF EXISTS ck_agent_proposals_action",
    """
    ALTER TABLE agent_proposals ADD CONSTRAINT ck_agent_proposals_action
    CHECK (action in (
        'create_task', 'update_task', 'create_commitment', 'update_commitment',
        'add_note', 'create_shopping_item'
    ))
    """,
    "ALTER TABLE agent_proposals DROP COLUMN IF EXISTS memories_used",
    "DROP INDEX IF EXISTS ix_memory_items_embedding",
    "DROP TABLE IF EXISTS memory_items",
    "DROP EXTENSION IF EXISTS vector",
)

# Sprint 6 alert dismissals. Alembic 0005 runs these statements. The process
# also applies them on boot. A dismissal hides one incident. It sends nothing.
ALERT_UPGRADE: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS alert_dismissals (
        kind VARCHAR(32) PRIMARY KEY,
        signature VARCHAR(80) NOT NULL,
        dismissed_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT ck_alert_dismissals_kind CHECK (
            kind in ('mistral_failing', 'activity_poll', 'database_error')
        )
    )
    """,
)

ALERT_DOWNGRADE: tuple[str, ...] = ("DROP TABLE IF EXISTS alert_dismissals",)


# Sprint 7. X rows and the post audit. Alembic 0006 runs these statements.
# The process also applies them on boot. Tokens in x_connection are ciphertext.
SPRINT7_UPGRADE: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS x_connection (
        id INTEGER PRIMARY KEY,
        x_user_id VARCHAR(32) NOT NULL,
        username VARCHAR(15) NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT NOT NULL,
        access_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        scopes VARCHAR(200) NOT NULL,
        connected_at TIMESTAMP WITH TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT ck_x_connection_singleton CHECK (id = 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS x_oauth_pending (
        state VARCHAR(80) PRIMARY KEY,
        verifier TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS x_watches (
        id UUID PRIMARY KEY,
        kind VARCHAR(16) NOT NULL,
        value VARCHAR(80) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT uq_x_watches_value UNIQUE (kind, value),
        CONSTRAINT ck_x_watches_kind CHECK (kind in ('account', 'keyword')),
        CONSTRAINT ck_x_watches_value CHECK (char_length(value) > 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS x_items (
        id UUID PRIMARY KEY,
        kind VARCHAR(16) NOT NULL,
        external_id VARCHAR(32),
        author VARCHAR(15),
        text TEXT NOT NULL,
        url VARCHAR(300),
        reason VARCHAR(300),
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        source VARCHAR(16) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE,
        decided_at TIMESTAMP WITH TIME ZONE,
        posted_tweet_id VARCHAR(32),
        CONSTRAINT uq_x_items_external UNIQUE (kind, external_id),
        CONSTRAINT ck_x_items_kind CHECK (kind in ('bookmark', 'watch_match', 'draft')),
        CONSTRAINT ck_x_items_status CHECK (
            status in ('pending', 'applied', 'dismissed', 'posted', 'expired')
        ),
        CONSTRAINT ck_x_items_source CHECK (source in ('poll', 'webhook', 'assistant')),
        CONSTRAINT ck_x_items_text CHECK (char_length(text) > 0)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_x_items_status ON x_items (status)",
    """
    CREATE TABLE IF NOT EXISTS x_cursors (
        name VARCHAR(80) PRIMARY KEY,
        since_id VARCHAR(32) NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS x_meter (
        id INTEGER PRIMARY KEY,
        credits_remaining INTEGER,
        rate_remaining INTEGER,
        rate_reset_at TIMESTAMP WITH TIME ZONE,
        backoff_until TIMESTAMP WITH TIME ZONE,
        last_poll_at TIMESTAMP WITH TIME ZONE,
        last_error_class VARCHAR(40),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT ck_x_meter_singleton CHECK (id = 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS x_post_audit (
        id UUID PRIMARY KEY,
        item_id UUID NOT NULL REFERENCES x_items (id),
        outcome VARCHAR(16) NOT NULL,
        tweet_id VARCHAR(32),
        error_class VARCHAR(40),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT ck_x_post_audit_outcome CHECK (outcome in ('posted', 'failed'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_x_post_audit_item ON x_post_audit (item_id)",
)

SPRINT7_DOWNGRADE: tuple[str, ...] = (
    "DROP TABLE IF EXISTS x_post_audit",
    "DROP TABLE IF EXISTS x_meter",
    "DROP TABLE IF EXISTS x_cursors",
    "DROP TABLE IF EXISTS x_items",
    "DROP TABLE IF EXISTS x_watches",
    "DROP TABLE IF EXISTS x_oauth_pending",
    "DROP TABLE IF EXISTS x_connection",
)
