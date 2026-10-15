"""users.password_enc for committee-visible org passwords

Revision ID: 0014_user_password_enc
Revises: 0013_user_avatar_url
Create Date: 2026-10-09 23:15:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0014_user_password_enc"
down_revision: Union[str, None] = "0013_user_avatar_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "password_enc" in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "password_enc" not in cols:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_enc")
