"""
Centralized Viewing State Machine and Workflow Transition Rules
"""
from typing import Dict, Set, Optional, Any
from app.models.enums import ViewingStatus


class ViewingStateMachine:
    """
    Authoritative state machine governing viewing lifecycle.
    Prevents illegal, out-of-order, or invalid status jumps.
    """

    ALLOWED_TRANSITIONS: Dict[ViewingStatus, Set[ViewingStatus]] = {
        ViewingStatus.DRAFT: {
            ViewingStatus.AWAITING_AGENT_AVAILABILITY,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.AWAITING_AGENT_AVAILABILITY: {
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.AWAITING_TENANT_AVAILABILITY: {
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.SLOT_PROPOSED,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.SLOTS_AVAILABLE: {
            ViewingStatus.SLOT_PROPOSED,
            ViewingStatus.AWAITING_AGENT_AVAILABILITY,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.SLOT_PROPOSED: {
            ViewingStatus.AWAITING_TENANT_CONFIRMATION,
            ViewingStatus.AWAITING_AGENT_CONFIRMATION,
            ViewingStatus.CONFIRMED,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.AWAITING_TENANT_CONFIRMATION: {
            ViewingStatus.AWAITING_AGENT_CONFIRMATION,
            ViewingStatus.CONFIRMED,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.REJECTED,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.AWAITING_AGENT_CONFIRMATION: {
            ViewingStatus.CONFIRMED,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.REJECTED,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.CONFIRMED: {
            ViewingStatus.RESCHEDULE_REQUESTED,
            ViewingStatus.COMPLETED,
            ViewingStatus.NO_SHOW,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.RESCHEDULE_REQUESTED: {
            ViewingStatus.AWAITING_AGENT_AVAILABILITY,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.SLOT_PROPOSED,
            ViewingStatus.AWAITING_TENANT_CONFIRMATION,
            ViewingStatus.AWAITING_AGENT_CONFIRMATION,
            ViewingStatus.CONFIRMED,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.NEEDS_HUMAN_REVIEW: {
            ViewingStatus.DRAFT,
            ViewingStatus.AWAITING_AGENT_AVAILABILITY,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.SLOT_PROPOSED,
            ViewingStatus.AWAITING_TENANT_CONFIRMATION,
            ViewingStatus.AWAITING_AGENT_CONFIRMATION,
            ViewingStatus.CONFIRMED,
            ViewingStatus.CANCELLED,
        },
        ViewingStatus.NO_SHOW: {
            ViewingStatus.RESCHEDULE_REQUESTED,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.REJECTED: {
            ViewingStatus.SLOTS_AVAILABLE,
            ViewingStatus.CANCELLED,
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.COMPLETED: {
            # Completed is terminal for scheduling; may be escalated to review if disputed
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
        ViewingStatus.CANCELLED: {
            # Cancelled is terminal for this record; may be escalated to review if disputed
            ViewingStatus.NEEDS_HUMAN_REVIEW,
        },
    }

    @classmethod
    def can_transition(
        cls,
        current_status: ViewingStatus,
        target_status: ViewingStatus,
    ) -> bool:
        if current_status == target_status:
            return True
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def validate_transition(
        cls,
        current_status: ViewingStatus,
        target_status: ViewingStatus,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if current_status == target_status:
            return
        if not cls.can_transition(current_status, target_status):
            raise ValueError(
                f"Invalid viewing state transition: cannot move from {current_status.value} to {target_status.value}"
            )
