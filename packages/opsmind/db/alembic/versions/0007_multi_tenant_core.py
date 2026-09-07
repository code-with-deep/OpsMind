"""Multi-tenant control plane, tenant_id columns, demo backfill, RLS (MT1).

Revision ID: 0007_multi_tenant_core
Revises: 0006_reviews_and_case_memory
Create Date: 2026-09-03

"""

from __future__ import annotations

import hashlib
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_multi_tenant_core"
down_revision: Union[str, None] = "0006_reviews_and_case_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DEMO_API_KEY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DEFAULT_BOOTSTRAP_KEY = "change-me-opsmind-dev-key"
DEFAULT_KEY_HASH = hashlib.sha256(DEFAULT_BOOTSTRAP_KEY.encode("utf-8")).hexdigest()

TENANT_TABLES = (
    "investigations",
    "investigation_events",
    "tool_invocations",
    "findings",
    "reviews",
    "case_summaries",
    "documents",
    "document_chunks",
    "products",
    "carriers",
    "campaigns",
    "orders",
    "order_items",
    "inventory_snapshots",
    "shipments",
    "returns",
    "daily_metrics",
)


def _add_tenant_id(table: str) -> None:
    op.add_column(
        table,
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL").bindparams(
            tid=str(DEMO_TENANT_ID)
        )
    )
    op.alter_column(table, "tenant_id", nullable=False)
    op.create_foreign_key(
        f"fk_{table}_tenant_id",
        table,
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_modify ON {table}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "domain_profile",
            sa.String(length=64),
            nullable=False,
            server_default="ecommerce",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])

    op.create_table(
        "tenant_settings",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            primary_key=True,
        ),
        sa.Column(
            "supported_domains",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "enabled_sql_templates",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("max_tool_calls", sa.Integer(), nullable=False, server_default="40"),
        sa.Column(
            "soft_limits",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tenants (id, name, slug, status, domain_profile)
            VALUES (:id, 'OpsMind Demo', 'demo', 'active', 'ecommerce')
            """
        ).bindparams(id=str(DEMO_TENANT_ID))
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenant_settings (tenant_id, supported_domains, enabled_sql_templates)
            VALUES (
                :tid,
                '["revenue","inventory","fulfillment","returns","campaigns"]'::jsonb,
                '[]'::jsonb
            )
            """
        ).bindparams(tid=str(DEMO_TENANT_ID))
    )
    op.execute(
        sa.text(
            """
            INSERT INTO api_keys (id, tenant_id, name, key_hash, key_prefix, scopes, created_by)
            VALUES (
                :id,
                :tid,
                'bootstrap',
                :key_hash,
                'change-m…',
                '{}'::jsonb,
                'migration'
            )
            """
        ).bindparams(
            id=str(DEMO_API_KEY_ID),
            tid=str(DEMO_TENANT_ID),
            key_hash=DEFAULT_KEY_HASH,
        )
    )

    for table in TENANT_TABLES:
        _add_tenant_id(table)

    op.create_index(
        "ix_investigations_tenant_created",
        "investigations",
        ["tenant_id", "created_at"],
    )

    op.drop_index("ix_products_sku", table_name="products")
    op.create_unique_constraint("uq_products_tenant_sku", "products", ["tenant_id", "sku"])

    op.drop_constraint("carriers_name_key", "carriers", type_="unique")
    op.create_unique_constraint("uq_carriers_tenant_name", "carriers", ["tenant_id", "name"])

    op.drop_constraint("uq_inventory_day_product", "inventory_snapshots", type_="unique")
    op.create_unique_constraint(
        "uq_inventory_tenant_day_product",
        "inventory_snapshots",
        ["tenant_id", "snapshot_date", "product_id"],
    )

    op.drop_constraint("daily_metrics_pkey", "daily_metrics", type_="primary")
    op.create_primary_key(
        "daily_metrics_pkey",
        "daily_metrics",
        ["tenant_id", "metric_date"],
    )

    op.drop_constraint("documents_doc_key_key", "documents", type_="unique")
    op.create_unique_constraint(
        "uq_documents_tenant_doc_key",
        "documents",
        ["tenant_id", "doc_key"],
    )

    op.drop_constraint("tool_invocations_source_id_key", "tool_invocations", type_="unique")
    op.create_unique_constraint(
        "uq_tool_invocations_tenant_source_id",
        "tool_invocations",
        ["tenant_id", "source_id"],
    )

    for table in TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_select ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_index("ix_investigations_tenant_created", table_name="investigations")

    op.drop_constraint("uq_tool_invocations_tenant_source_id", "tool_invocations", type_="unique")
    op.create_unique_constraint(
        "tool_invocations_source_id_key", "tool_invocations", ["source_id"]
    )

    op.drop_constraint("uq_documents_tenant_doc_key", "documents", type_="unique")
    op.create_unique_constraint("documents_doc_key_key", "documents", ["doc_key"])

    op.drop_constraint("daily_metrics_pkey", "daily_metrics", type_="primary")
    op.create_primary_key("daily_metrics_pkey", "daily_metrics", ["metric_date"])

    op.drop_constraint("uq_inventory_tenant_day_product", "inventory_snapshots", type_="unique")
    op.create_unique_constraint(
        "uq_inventory_day_product",
        "inventory_snapshots",
        ["snapshot_date", "product_id"],
    )

    op.drop_constraint("uq_carriers_tenant_name", "carriers", type_="unique")
    op.create_unique_constraint("carriers_name_key", "carriers", ["name"])

    op.drop_constraint("uq_products_tenant_sku", "products", type_="unique")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.drop_table("tenant_settings")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("tenants")
