"""make repository owner_id nullable for webhook auto-registration

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16

Webhook-registered repositories don't have a known owner (the webhook
payload doesn't tell us which PRScope user owns the repo). Making
owner_id nullable allows auto-registration, and the FK action changes
from CASCADE to SET NULL so deleting a user doesn't delete their repos.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "repositories",
        "owner_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    # Drop the old CASCADE FK and recreate with SET NULL
    op.drop_constraint("repositories_owner_id_fkey", "repositories", type_="foreignkey")
    op.create_foreign_key(
        "repositories_owner_id_fkey",
        "repositories",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Set any NULL owner_ids to avoid constraint violations on downgrade
    op.execute("UPDATE repositories SET owner_id = (SELECT id FROM users LIMIT 1) WHERE owner_id IS NULL")
    op.drop_constraint("repositories_owner_id_fkey", "repositories", type_="foreignkey")
    op.create_foreign_key(
        "repositories_owner_id_fkey",
        "repositories",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "repositories",
        "owner_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
