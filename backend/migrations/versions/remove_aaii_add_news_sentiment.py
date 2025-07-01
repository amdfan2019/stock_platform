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
    # Create news_sentiment table
    op.create_table(
        'news_sentiment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_date', sa.Date(), nullable=True),
        sa.Column('overall_sentiment', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(length=20), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('articles_analyzed', sa.Integer(), nullable=True),
        sa.Column('source_breakdown', sa.JSON(), nullable=True),
        sa.Column('data_source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_news_sentiment_analysis_date'), 'news_sentiment', ['analysis_date'], unique=False)
    op.create_index(op.f('ix_news_sentiment_id'), 'news_sentiment', ['id'], unique=False)

    # Update market_sentiment table - remove AAII columns and add news sentiment columns
    op.drop_column('market_sentiment', 'aaii_neutral_pct')
    op.drop_column('market_sentiment', 'aaii_bearish_pct') 
    op.drop_column('market_sentiment', 'aaii_bullish_pct')
    
    op.add_column('market_sentiment', sa.Column('news_sentiment_score', sa.Float(), nullable=True))
    op.add_column('market_sentiment', sa.Column('news_sentiment_label', sa.String(length=20), nullable=True))
    op.add_column('market_sentiment', sa.Column('news_confidence', sa.Float(), nullable=True))

    # Drop aaii_sentiment table
    op.drop_table('aaii_sentiment')


def downgrade():
    # Recreate aaii_sentiment table
    op.create_table(
        'aaii_sentiment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_date', sa.Date(), nullable=True),
        sa.Column('bullish_pct', sa.Float(), nullable=True),
        sa.Column('bearish_pct', sa.Float(), nullable=True),
        sa.Column('neutral_pct', sa.Float(), nullable=True),
        sa.Column('total_responses', sa.Integer(), nullable=True),
        sa.Column('data_source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_aaii_sentiment_id'), 'aaii_sentiment', ['id'], unique=False)
    op.create_index(op.f('ix_aaii_sentiment_survey_date'), 'aaii_sentiment', ['survey_date'], unique=False)

    # Revert market_sentiment table changes
    op.drop_column('market_sentiment', 'news_confidence')
    op.drop_column('market_sentiment', 'news_sentiment_label')
    op.drop_column('market_sentiment', 'news_sentiment_score')
    
    op.add_column('market_sentiment', sa.Column('aaii_bullish_pct', sa.Float(), nullable=True))
    op.add_column('market_sentiment', sa.Column('aaii_bearish_pct', sa.Float(), nullable=True))
    op.add_column('market_sentiment', sa.Column('aaii_neutral_pct', sa.Float(), nullable=True))

    # Drop news_sentiment table
    op.drop_index(op.f('ix_news_sentiment_analysis_date'), table_name='news_sentiment')
    op.drop_index(op.f('ix_news_sentiment_id'), table_name='news_sentiment')
    op.drop_table('news_sentiment') 