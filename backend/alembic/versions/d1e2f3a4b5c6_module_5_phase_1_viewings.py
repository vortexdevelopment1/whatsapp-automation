"""module_5_phase_1_viewings

Revision ID: d1e2f3a4b5c6
Revises: a47adf7bc7dc
Create Date: 2026-10-09 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create viewings table
    op.create_table(
        'viewings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('shortlist_id', sa.UUID(), nullable=True),
        sa.Column('shortlist_item_id', sa.UUID(), nullable=True),
        sa.Column('property_match_id', sa.UUID(), nullable=False),
        sa.Column('property_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('property_agent_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('scheduled_start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Singapore'),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('location_type', sa.String(50), nullable=False, server_default='IN_PERSON'),
        sa.Column('location_text', sa.String(500), nullable=True),
        sa.Column('meeting_url', sa.String(1024), nullable=True),
        sa.Column('tenant_confirmation_status', sa.String(50), nullable=False, server_default='NOT_REQUIRED'),
        sa.Column('agent_confirmation_status', sa.String(50), nullable=False, server_default='NOT_REQUIRED'),
        sa.Column('reschedule_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('previous_scheduled_start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('previous_scheduled_end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reschedule_reason', sa.String(500), nullable=True),
        sa.Column('cancellation_reason', sa.String(500), nullable=True),
        sa.Column('cancelled_by', sa.String(50), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('outcome', sa.String(50), nullable=True),
        sa.Column('outcome_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shortlist_id'], ['property_shortlists.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['shortlist_item_id'], ['property_shortlist_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['property_match_id'], ['property_matches.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['listing_id'], ['property_listings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['property_agent_id'], ['property_agents.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_viewings_lead_id'), 'viewings', ['lead_id'], unique=False)
    op.create_index(op.f('ix_viewings_property_match_id'), 'viewings', ['property_match_id'], unique=False)
    op.create_index(op.f('ix_viewings_property_id'), 'viewings', ['property_id'], unique=False)
    op.create_index(op.f('ix_viewings_listing_id'), 'viewings', ['listing_id'], unique=False)
    op.create_index(op.f('ix_viewings_property_agent_id'), 'viewings', ['property_agent_id'], unique=False)
    op.create_index(op.f('ix_viewings_status'), 'viewings', ['status'], unique=False)
    op.create_index(op.f('ix_viewings_scheduled_start_at'), 'viewings', ['scheduled_start_at'], unique=False)

    # 2. Create viewing_slots table
    op.create_table(
        'viewing_slots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('viewing_id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Singapore'),
        sa.Column('status', sa.String(50), nullable=False, server_default='AVAILABLE'),
        sa.Column('source_message_id', sa.UUID(), nullable=True),
        sa.Column('is_mutual_match', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_viewing_slots_viewing_id'), 'viewing_slots', ['viewing_id'], unique=False)
    op.create_index(op.f('ix_viewing_slots_start_at'), 'viewing_slots', ['start_at'], unique=False)
    op.create_index(op.f('ix_viewing_slots_status'), 'viewing_slots', ['status'], unique=False)

    # 3. Create viewing_events table
    op.create_table(
        'viewing_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('viewing_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('actor_type', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('actor_id', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_viewing_events_viewing_id'), 'viewing_events', ['viewing_id'], unique=False)
    op.create_index(op.f('ix_viewing_events_event_type'), 'viewing_events', ['event_type'], unique=False)


def downgrade() -> None:
    op.drop_table('viewing_events')
    op.drop_table('viewing_slots')
    op.drop_table('viewings')
