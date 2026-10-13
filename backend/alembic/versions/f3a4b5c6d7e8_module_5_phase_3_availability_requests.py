"""module_5_phase_3_availability_requests

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-10 00:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'viewing_availability_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('viewing_id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('property_match_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('property_agent_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('outbound_message_text', sa.Text(), nullable=True),
        sa.Column('raw_response_text', sa.Text(), nullable=True),
        sa.Column('response_intent', sa.String(50), nullable=True),
        sa.Column('correlation_status', sa.String(50), nullable=False, server_default='RESOLVED'),
        sa.Column('agent_notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_match_id'], ['property_matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['listing_id'], ['property_listings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['property_agent_id'], ['property_agents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id'], ['property_agent_conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_viewing_availability_request_idempotency'),
    )
    op.create_index('ix_viewing_availability_requests_viewing_id', 'viewing_availability_requests', ['viewing_id'])
    op.create_index('ix_viewing_availability_requests_lead_id', 'viewing_availability_requests', ['lead_id'])
    op.create_index('ix_viewing_availability_requests_property_match_id', 'viewing_availability_requests', ['property_match_id'])
    op.create_index('ix_viewing_availability_requests_listing_id', 'viewing_availability_requests', ['listing_id'])
    op.create_index('ix_viewing_availability_requests_property_agent_id', 'viewing_availability_requests', ['property_agent_id'])
    op.create_index('ix_viewing_availability_requests_conversation_id', 'viewing_availability_requests', ['conversation_id'])
    op.create_index('ix_viewing_availability_requests_status', 'viewing_availability_requests', ['status'])
    op.create_index('ix_viewing_availability_requests_provider_message_id', 'viewing_availability_requests', ['provider_message_id'])
    op.create_index('ix_viewing_availability_requests_response_intent', 'viewing_availability_requests', ['response_intent'])
    op.create_index('ix_viewing_availability_requests_correlation_status', 'viewing_availability_requests', ['correlation_status'])


def downgrade() -> None:
    op.drop_index('ix_viewing_availability_requests_correlation_status', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_response_intent', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_provider_message_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_status', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_conversation_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_property_agent_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_listing_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_property_match_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_lead_id', table_name='viewing_availability_requests')
    op.drop_index('ix_viewing_availability_requests_viewing_id', table_name='viewing_availability_requests')
    op.drop_table('viewing_availability_requests')
