"""module_5_phase_2_property_interests

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-10 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'property_interests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('property_match_id', sa.UUID(), nullable=False),
        sa.Column('shortlist_id', sa.UUID(), nullable=True),
        sa.Column('shortlist_item_id', sa.UUID(), nullable=True),
        sa.Column('viewing_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='NOT_PRESENTED'),
        sa.Column('source_message_id', sa.UUID(), nullable=True),
        sa.Column('presented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('presented_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('presented_currency', sa.String(10), nullable=False, server_default='SGD'),
        sa.Column('presented_availability', sa.String(100), nullable=True),
        sa.Column('presentation_notes', sa.Text(), nullable=True),
        sa.Column('last_intent', sa.String(50), nullable=True),
        sa.Column('tenant_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_match_id'], ['property_matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shortlist_id'], ['property_shortlists.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['shortlist_item_id'], ['property_shortlist_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_message_id'], ['whatsapp_messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lead_id', 'property_match_id', name='uq_lead_property_match_interest'),
    )
    op.create_index('ix_property_interests_lead_id', 'property_interests', ['lead_id'])
    op.create_index('ix_property_interests_property_match_id', 'property_interests', ['property_match_id'])
    op.create_index('ix_property_interests_shortlist_id', 'property_interests', ['shortlist_id'])
    op.create_index('ix_property_interests_shortlist_item_id', 'property_interests', ['shortlist_item_id'])
    op.create_index('ix_property_interests_viewing_id', 'property_interests', ['viewing_id'])
    op.create_index('ix_property_interests_status', 'property_interests', ['status'])


def downgrade() -> None:
    op.drop_index('ix_property_interests_status', table_name='property_interests')
    op.drop_index('ix_property_interests_viewing_id', table_name='property_interests')
    op.drop_index('ix_property_interests_shortlist_item_id', table_name='property_interests')
    op.drop_index('ix_property_interests_shortlist_id', table_name='property_interests')
    op.drop_index('ix_property_interests_property_match_id', table_name='property_interests')
    op.drop_index('ix_property_interests_lead_id', table_name='property_interests')
    op.drop_table('property_interests')
