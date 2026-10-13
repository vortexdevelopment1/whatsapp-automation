"""module_4_phase_8_shortlist_tables

Revision ID: b7c8d9e0f1a2
Revises: a47adf7bc7dc
Create Date: 2026-10-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a47adf7bc7dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'property_shortlists',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lead_id', 'version', name='uq_lead_shortlist_version'),
    )
    op.create_index('ix_property_shortlists_lead_id', 'property_shortlists', ['lead_id'])
    op.create_index('ix_property_shortlists_status', 'property_shortlists', ['status'])

    op.create_table(
        'property_shortlist_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('shortlist_id', sa.UUID(), nullable=False),
        sa.Column('property_match_id', sa.UUID(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='READY'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('excluded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('exclusion_reason', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['property_match_id'], ['property_matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shortlist_id'], ['property_shortlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shortlist_id', 'property_match_id', name='uq_shortlist_item_match'),
    )
    op.create_index('ix_property_shortlist_items_shortlist_id', 'property_shortlist_items', ['shortlist_id'])
    op.create_index('ix_property_shortlist_items_property_match_id', 'property_shortlist_items', ['property_match_id'])
    op.create_index('ix_property_shortlist_items_status', 'property_shortlist_items', ['status'])


def downgrade() -> None:
    op.drop_index('ix_property_shortlist_items_status', table_name='property_shortlist_items')
    op.drop_index('ix_property_shortlist_items_property_match_id', table_name='property_shortlist_items')
    op.drop_index('ix_property_shortlist_items_shortlist_id', table_name='property_shortlist_items')
    op.drop_table('property_shortlist_items')

    op.drop_index('ix_property_shortlists_status', table_name='property_shortlists')
    op.drop_index('ix_property_shortlists_lead_id', table_name='property_shortlists')
    op.drop_table('property_shortlists')
