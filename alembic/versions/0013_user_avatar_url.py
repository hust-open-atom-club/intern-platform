"""users.avatar_url for profile photo

Revision ID: 0013_user_avatar_url
Revises: 0012_user_disabled
Create Date: 2026-10-09 22:20:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0013_user_avatar_url"
down_revision: Union[str, None] = "0012_user_disabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "avatar_url" in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "avatar_url" not in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("avatar_url")
