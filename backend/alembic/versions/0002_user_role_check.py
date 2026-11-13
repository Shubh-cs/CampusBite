"""Restrict user roles to the three supported values.

Revision ID: 0002_user_role_check
Revises: 0001_initial_schema
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "0002_user_role_check"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        invalid_roles = connection.execute(
            sa.text(
                "SELECT DISTINCT role FROM users "
                "WHERE role NOT IN ('CUSTOMER', 'OWNER', 'DELIVERY_PARTNER')"
            )
        ).scalars().all()
        if invalid_roles:
            invalid_values = ", ".join(sorted(str(role) for role in invalid_roles))
            raise RuntimeError(
                "Cannot add the user-role constraint because existing users have "
                f"unsupported role values: {invalid_values}. No user rows were changed."
            )

    op.create_check_constraint(
        "ck_users_role_allowed",
        "users",
        "role IN ('CUSTOMER', 'OWNER', 'DELIVERY_PARTNER')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_allowed", "users", type_="check")
