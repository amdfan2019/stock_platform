"""merge heads before adding market news summaries table

Revision ID: 283dd16a563c
Revises: d411a1f4f95a, remove_aaii_add_news
Create Date: 2025-07-01 20:19:45.118234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '283dd16a563c'
down_revision: Union[str, None] = ('d411a1f4f95a', 'remove_aaii_add_news')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
