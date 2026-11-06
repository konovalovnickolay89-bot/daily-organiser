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
