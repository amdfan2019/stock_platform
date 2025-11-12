"""remove aaii add news sentiment

Revision ID: remove_aaii_add_news
Revises: 3375f0036170
Create Date: 2025-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'remove_aaii_add_news'
down_revision = '3375f0036170'
branch_labels = None
depends_on = None


def upgrade():
    # This migration was for transitioning from AAII sentiment to news sentiment
    # For fresh databases (like Railway), this migration is not needed as the 
    # correct schema is created by later migrations. This is now a no-op.
    pass


def downgrade():
    # No-op migration, nothing to downgrade
    pass 