"""module_3_phase_7_confidence_clarification_faq_escalation

Revision ID: 05306f6d10f6
Revises: 07b9999b4f1d
Create Date: 2026-10-08 17:06:14.480532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '05306f6d10f6'
down_revision: Union[str, None] = '07b9999b4f1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Enums
    clarification_status_enum = postgresql.ENUM(
        'OPEN', 'WAITING_FOR_TENANT', 'RESOLVED', 'ESCALATED', 'CANCELLED',
        name='clarification_status_enum'
    )
    clarification_status_enum.create(op.get_bind(), checkfirst=True)

    faq_status_enum = postgresql.ENUM(
        'DRAFT', 'ACTIVE', 'INACTIVE',
        name='faq_status_enum'
    )
    faq_status_enum.create(op.get_bind(), checkfirst=True)

    escalation_status_enum = postgresql.ENUM(
        'OPEN', 'ASSIGNED', 'RESOLVED', 'CANCELLED',
        name='escalation_status_enum'
    )
    escalation_status_enum.create(op.get_bind(), checkfirst=True)

    escalation_reason_enum = postgresql.ENUM(
        'TENANT_REQUESTED_HUMAN',
        'MAX_CLARIFICATION_EXCEEDED',
        'UNRESOLVED_CONFLICT',
        'REPEATED_AI_FAILURE',
        'UNSUPPORTED_FAQ',
        'OPERATOR_TAKEOVER',
        'COMPLAINT_DISPUTE',
        'QUALIFICATION_NEEDS_REVIEW',
        'OTHER',
        name='escalation_reason_enum'
    )
    escalation_reason_enum.create(op.get_bind(), checkfirst=True)

    # 2. Table: qualification_clarifications
    op.create_table(
        'qualification_clarifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('reason', sa.String(255), nullable=False),
        sa.Column('proposed_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', postgresql.ENUM('OPEN', 'WAITING_FOR_TENANT', 'RESOLVED', 'ESCALATED', 'CANCELLED', name='clarification_status_enum', create_type=False), nullable=False, server_default='OPEN'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('qualification_questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_qualification_clarifications_lead_id', 'qualification_clarifications', ['lead_id'])
    op.create_index('ix_qualification_clarifications_field_name', 'qualification_clarifications', ['field_name'])
    op.create_index('ix_qualification_clarifications_status', 'qualification_clarifications', ['status'])

    # 3. Table: faq_entries
    op.create_table(
        'faq_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('question', sa.String(500), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False, server_default='GENERAL'),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('status', postgresql.ENUM('DRAFT', 'ACTIVE', 'INACTIVE', name='faq_status_enum', create_type=False), nullable=False, server_default='ACTIVE'),
        sa.Column('version', sa.String(50), nullable=False, server_default='v1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_faq_entries_question', 'faq_entries', ['question'])
    op.create_index('ix_faq_entries_category', 'faq_entries', ['category'])
    op.create_index('ix_faq_entries_status', 'faq_entries', ['status'])

    # 4. Table: conversation_escalations
    op.create_table(
        'conversation_escalations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason_code', postgresql.ENUM('TENANT_REQUESTED_HUMAN', 'MAX_CLARIFICATION_EXCEEDED', 'UNRESOLVED_CONFLICT', 'REPEATED_AI_FAILURE', 'UNSUPPORTED_FAQ', 'OPERATOR_TAKEOVER', 'COMPLAINT_DISPUTE', 'QUALIFICATION_NEEDS_REVIEW', 'OTHER', name='escalation_reason_enum', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('OPEN', 'ASSIGNED', 'RESOLVED', 'CANCELLED', name='escalation_status_enum', create_type=False), nullable=False, server_default='OPEN'),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=False, server_default='system'),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_conversation_escalations_lead_id', 'conversation_escalations', ['lead_id'])
    op.create_index('ix_conversation_escalations_status', 'conversation_escalations', ['status'])
    op.create_index('ix_conversation_escalations_reason_code', 'conversation_escalations', ['reason_code'])


def downgrade() -> None:
    op.drop_table('conversation_escalations')
    op.drop_table('faq_entries')
    op.drop_table('qualification_clarifications')

    op.execute("DROP TYPE IF EXISTS escalation_reason_enum")
    op.execute("DROP TYPE IF EXISTS escalation_status_enum")
    op.execute("DROP TYPE IF EXISTS faq_status_enum")
    op.execute("DROP TYPE IF EXISTS clarification_status_enum")
