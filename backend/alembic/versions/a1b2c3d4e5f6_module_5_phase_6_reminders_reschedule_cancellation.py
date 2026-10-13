"""module_5_phase_6_reminders_reschedule_cancellation

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-10-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add schedule_version to viewings
    op.add_column(
        'viewings',
        sa.Column('schedule_version', sa.Integer(), nullable=False, server_default='1'),
    )

    # 2. Create viewing_reminders table
    op.create_table(
        'viewing_reminders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('viewing_id', sa.UUID(), nullable=False),
        sa.Column('party', sa.String(50), nullable=False),
        sa.Column('reminder_type', sa.String(50), nullable=False, server_default='UPCOMING_VIEWING'),
        sa.Column('offset_minutes', sa.Integer(), nullable=True),
        sa.Column('booking_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Singapore'),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('message_id', sa.UUID(), nullable=True),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['whatsapp_messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_viewing_reminders_idempotency'),
    )
    op.create_index('ix_viewing_reminders_viewing_id', 'viewing_reminders', ['viewing_id'])
    op.create_index('ix_viewing_reminders_scheduled_for', 'viewing_reminders', ['scheduled_for'])
    op.create_index('ix_viewing_reminders_status', 'viewing_reminders', ['status'])
    op.create_index('ix_viewing_reminders_idempotency_key', 'viewing_reminders', ['idempotency_key'])

    # 3. Create viewing_schedule_histories table
    op.create_table(
        'viewing_schedule_histories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('viewing_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('scheduled_start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('slot_id', sa.UUID(), nullable=True),
        sa.Column('changed_by', sa.String(50), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['viewing_id'], ['viewings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'], ['viewing_slots.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_viewing_schedule_histories_viewing_id', 'viewing_schedule_histories', ['viewing_id'])


def downgrade() -> None:
    op.drop_table('viewing_schedule_histories')
    op.drop_table('viewing_reminders')
    op.drop_column('viewings', 'schedule_version')
