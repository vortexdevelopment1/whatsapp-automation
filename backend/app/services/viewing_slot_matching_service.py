"""
Viewing Slot Matching Service - Module 5 Phase 4
Purely deterministic calculation of overlapping viewing slots between property-agent slots
and tenant availability. NO LLM decides overlap math or candidate slot times.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Optional, Dict, Any, Union
import zoneinfo
from sqlalchemy.orm import Session

from app.models.viewing import Viewing, ViewingSlot
from app.models.enums import (
    ViewingSlotSource,
    ViewingSlotStatus,
    SlotMatchType,
    ViewingStatus,
)
from app.schemas.viewing_availability import (
    TenantAvailabilityWindowItem,
    MutualSlotMatchItem,
    ViewingSlotMatchingResult,
)
from app.services.viewing_config import ViewingConfig

logger = logging.getLogger(__name__)


class ViewingSlotMatchingService:
    """
    Deterministic slot matching engine.
    - Loads active property-agent slots for a viewing.
    - Normalizes timestamps to UTC for safe overlap math.
    - Strictly rejects expired slots (start_at <= now in UTC).
    - Supports exact slot matches, tenant window overlaps, and duration-based discretization.
    - Preserves local timezone for presentation.
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def to_utc(dt: datetime, tz_str: str = "Asia/Singapore") -> datetime:
        """Converts any datetime to UTC timezone-aware datetime."""
        if dt.tzinfo is None:
            local_tz = zoneinfo.ZoneInfo(tz_str)
            dt = dt.replace(tzinfo=local_tz)
        return dt.astimezone(dt_timezone.utc)

    @staticmethod
    def to_display_tz(dt_utc: datetime, tz_str: str = "Asia/Singapore") -> datetime:
        """Converts a UTC datetime to local display timezone."""
        target_tz = zoneinfo.ZoneInfo(tz_str)
        return dt_utc.astimezone(target_tz)

    def get_active_agent_slots(
        self,
        viewing_id: uuid.UUID,
        include_proposed: bool = True,
    ) -> List[ViewingSlot]:
        """
        Loads valid property-agent slots for the viewing.
        Filters out CANCELLED, REJECTED, and EXPIRED slots.
        Filters out slots that have already passed in UTC.
        """
        now_utc = datetime.now(dt_timezone.utc)
        allowed_statuses = [ViewingSlotStatus.AVAILABLE]
        if include_proposed:
            allowed_statuses.append(ViewingSlotStatus.PROPOSED)

        slots = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing_id,
                ViewingSlot.source == ViewingSlotSource.PROPERTY_AGENT,
                ViewingSlot.status.in_(allowed_statuses),
            )
            .order_by(ViewingSlot.start_at.asc())
            .all()
        )

        valid_slots = []
        for s in slots:
            s_start_utc = self.to_utc(s.start_at, s.timezone)
            if s_start_utc > now_utc:
                valid_slots.append(s)
            else:
                # Mark as expired if past
                if s.status == ViewingSlotStatus.AVAILABLE:
                    s.status = ViewingSlotStatus.EXPIRED
                    self.db.add(s)
        self.db.commit()
        return valid_slots

    def match_direct_selection(
        self,
        viewing: Viewing,
        selected_slot_id: uuid.UUID,
    ) -> MutualSlotMatchItem:
        """
        Matches when tenant selects an exact agent slot.
        Revalidates:
        - Slot belongs to viewing
        - Slot source is PROPERTY_AGENT
        - Slot status is AVAILABLE or PROPOSED
        - Slot is not expired
        - Viewing is active
        """
        now_utc = datetime.now(dt_timezone.utc)

        slot = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.id == selected_slot_id,
                ViewingSlot.viewing_id == viewing.id,
            )
            .first()
        )
        if not slot:
            raise ValueError(f"Slot {selected_slot_id} not found for viewing {viewing.id}")

        if slot.source != ViewingSlotSource.PROPERTY_AGENT:
            raise ValueError(f"Slot {selected_slot_id} is not an agent-provided slot (source={slot.source})")

        slot_start_utc = self.to_utc(slot.start_at, slot.timezone)
        if slot_start_utc <= now_utc or slot.status == ViewingSlotStatus.EXPIRED:
            slot.status = ViewingSlotStatus.EXPIRED
            self.db.commit()
            raise ValueError(f"Selected slot {selected_slot_id} has expired.")

        if slot.status not in [ViewingSlotStatus.AVAILABLE, ViewingSlotStatus.PROPOSED]:
            raise ValueError(f"Slot {selected_slot_id} is not available (status={slot.status}).")

        duration = viewing.duration_minutes or ViewingConfig.DEFAULT_VIEWING_DURATION_MINUTES
        end_at = slot.end_at
        if not end_at:
            end_at = slot.start_at + timedelta(minutes=duration)

        display_tz = viewing.timezone or slot.timezone or ViewingConfig.DEFAULT_TIMEZONE
        start_local = self.to_display_tz(self.to_utc(slot.start_at, slot.timezone), display_tz)
        end_local = self.to_display_tz(self.to_utc(end_at, slot.timezone), display_tz)

        reason = (
            f"Tenant directly selected agent slot on "
            f"{start_local.strftime('%A, %d %b %Y at %I:%M %p')} - {end_local.strftime('%I:%M %p')}."
        )

        return MutualSlotMatchItem(
            start_at=start_local,
            end_at=end_local,
            timezone=display_tz,
            match_type=SlotMatchType.TENANT_SELECTED,
            agent_slot_id=slot.id,
            tenant_slot_id=None,
            reason=reason,
            is_proposed=(slot.status == ViewingSlotStatus.PROPOSED),
        )

    def match_slots(
        self,
        viewing_id: uuid.UUID,
        tenant_windows: Optional[List[TenantAvailabilityWindowItem]] = None,
        selected_slot_id: Optional[uuid.UUID] = None,
        duration_minutes: Optional[int] = None,
        interval_minutes: Optional[int] = None,
    ) -> ViewingSlotMatchingResult:
        """
        Calculates mutually valid viewing slots deterministically.
        Handles:
        1. Direct slot selection by ID.
        2. Window overlap calculation with discretizing into candidate slots.
        3. Sorting with deterministic priority:
           - Explicit selection first
           - Earliest mutual valid slot ascending
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        duration = duration_minutes or viewing.duration_minutes or ViewingConfig.DEFAULT_VIEWING_DURATION_MINUTES
        interval = interval_minutes or ViewingConfig.DEFAULT_SLOT_INTERVAL_MINUTES
        display_tz = viewing.timezone or ViewingConfig.DEFAULT_TIMEZONE
        now_utc = datetime.now(dt_timezone.utc)

        # 1. Direct Selection
        if selected_slot_id:
            try:
                direct_match = self.match_direct_selection(viewing, selected_slot_id)
                return ViewingSlotMatchingResult(
                    viewing_id=viewing.id,
                    total_mutual_slots=1,
                    mutual_slots=[direct_match],
                    agent_slots_count=1,
                    tenant_windows_count=0,
                    status="MUTUAL_MATCH_FOUND",
                    recommended_slot=direct_match,
                )
            except ValueError as e:
                logger.warning(f"Direct slot selection failed for viewing {viewing.id}: {e}")
                return ViewingSlotMatchingResult(
                    viewing_id=viewing.id,
                    total_mutual_slots=0,
                    mutual_slots=[],
                    agent_slots_count=0,
                    tenant_windows_count=0,
                    status=f"SELECTION_FAILED: {str(e)}",
                    recommended_slot=None,
                )

        # 2. Window Matching
        agent_slots = self.get_active_agent_slots(viewing.id)
        if not agent_slots:
            return ViewingSlotMatchingResult(
                viewing_id=viewing.id,
                total_mutual_slots=0,
                mutual_slots=[],
                agent_slots_count=0,
                tenant_windows_count=len(tenant_windows) if tenant_windows else 0,
                status="NO_AGENT_SLOTS_AVAILABLE",
                recommended_slot=None,
            )

        if not tenant_windows:
            # If no tenant windows provided, all active agent slots are candidate options for tenant
            candidate_matches: List[MutualSlotMatchItem] = []
            for s in agent_slots:
                s_start_utc = self.to_utc(s.start_at, s.timezone)
                s_end_utc = self.to_utc(s.end_at or (s.start_at + timedelta(minutes=duration)), s.timezone)
                start_local = self.to_display_tz(s_start_utc, display_tz)
                end_local = self.to_display_tz(s_end_utc, display_tz)
                candidate_matches.append(
                    MutualSlotMatchItem(
                        start_at=start_local,
                        end_at=end_local,
                        timezone=display_tz,
                        match_type=SlotMatchType.EXACT,
                        agent_slot_id=s.id,
                        tenant_slot_id=None,
                        reason=f"Agent offered slot on {start_local.strftime('%A, %d %b %Y at %I:%M %p')}.",
                        is_proposed=(s.status == ViewingSlotStatus.PROPOSED),
                    )
                )

            recommended = candidate_matches[0] if candidate_matches else None
            return ViewingSlotMatchingResult(
                viewing_id=viewing.id,
                total_mutual_slots=len(candidate_matches),
                mutual_slots=candidate_matches,
                agent_slots_count=len(agent_slots),
                tenant_windows_count=0,
                status="AGENT_SLOTS_OFFERED",
                recommended_slot=recommended,
            )

        mutual_slots: List[MutualSlotMatchItem] = []
        max_candidates = ViewingConfig.MAX_CANDIDATE_SLOTS_PER_MATCH

        for a_slot in agent_slots:
            a_start_utc = self.to_utc(a_slot.start_at, a_slot.timezone)
            a_end_utc = self.to_utc(
                a_slot.end_at or (a_slot.start_at + timedelta(minutes=duration)),
                a_slot.timezone,
            )

            for t_win in tenant_windows:
                t_start_utc = self.to_utc(t_win.start_at, t_win.timezone)
                t_end_utc = self.to_utc(t_win.end_at, t_win.timezone)

                overlap_start = max(a_start_utc, t_start_utc)
                overlap_end = min(a_end_utc, t_end_utc)

                if overlap_start < overlap_end:
                    overlap_duration_mins = (overlap_end - overlap_start).total_seconds() / 60.0
                    if overlap_duration_mins >= duration:
                        # Determine if this was an exact slot match or broad window overlap
                        is_agent_exact = ((a_end_utc - a_start_utc).total_seconds() / 60.0) <= (duration + 15)
                        is_tenant_exact = ((t_end_utc - t_start_utc).total_seconds() / 60.0) <= (duration + 15)

                        if is_agent_exact and is_tenant_exact:
                            # Exact Match
                            start_local = self.to_display_tz(a_start_utc, display_tz)
                            end_local = self.to_display_tz(a_end_utc, display_tz)
                            reason = (
                                f"Exact mutual match on "
                                f"{start_local.strftime('%A, %d %b %Y at %I:%M %p')}."
                            )
                            mutual_slots.append(
                                MutualSlotMatchItem(
                                    start_at=start_local,
                                    end_at=end_local,
                                    timezone=display_tz,
                                    match_type=SlotMatchType.EXACT,
                                    agent_slot_id=a_slot.id,
                                    tenant_slot_id=None,
                                    reason=reason,
                                    is_proposed=(a_slot.status == ViewingSlotStatus.PROPOSED),
                                )
                            )
                        elif is_agent_exact and not is_tenant_exact:
                            # Agent slot is exact, tenant window covers it
                            start_local = self.to_display_tz(a_start_utc, display_tz)
                            end_local = self.to_display_tz(a_end_utc, display_tz)
                            reason = (
                                f"Agent slot on {start_local.strftime('%A, %d %b %Y at %I:%M %p')} "
                                f"falls inside tenant availability window."
                            )
                            mutual_slots.append(
                                MutualSlotMatchItem(
                                    start_at=start_local,
                                    end_at=end_local,
                                    timezone=display_tz,
                                    match_type=SlotMatchType.OVERLAP,
                                    agent_slot_id=a_slot.id,
                                    tenant_slot_id=None,
                                    reason=reason,
                                    is_proposed=(a_slot.status == ViewingSlotStatus.PROPOSED),
                                )
                            )
                        else:
                            # Discretize window overlap into candidate viewing slots
                            cand_start = overlap_start
                            generated_count = 0
                            while (
                                cand_start + timedelta(minutes=duration) <= overlap_end
                                and len(mutual_slots) < max_candidates
                                and generated_count < 4
                            ):
                                cand_end = cand_start + timedelta(minutes=duration)
                                start_local = self.to_display_tz(cand_start, display_tz)
                                end_local = self.to_display_tz(cand_end, display_tz)
                                reason = (
                                    f"Tenant and agent are both available on "
                                    f"{start_local.strftime('%A, %d %b')} between "
                                    f"{self.to_display_tz(overlap_start, display_tz).strftime('%I:%M %p')} and "
                                    f"{self.to_display_tz(overlap_end, display_tz).strftime('%I:%M %p')}."
                                )
                                # Avoid duplicate candidate timestamps
                                if not any(m.start_at == start_local for m in mutual_slots):
                                    mutual_slots.append(
                                        MutualSlotMatchItem(
                                            start_at=start_local,
                                            end_at=end_local,
                                            timezone=display_tz,
                                            match_type=SlotMatchType.OVERLAP,
                                            agent_slot_id=a_slot.id,
                                            tenant_slot_id=None,
                                            reason=reason,
                                            is_proposed=False,
                                        )
                                    )
                                    generated_count += 1
                                cand_start += timedelta(minutes=interval)

        # Sort mutually available slots deterministically: earliest start_at first
        mutual_slots.sort(key=lambda m: m.start_at)

        # Deduplicate identical start times
        unique_matches: List[MutualSlotMatchItem] = []
        seen_starts = set()
        for m in mutual_slots:
            if m.start_at not in seen_starts:
                unique_matches.append(m)
                seen_starts.add(m.start_at)

        match_status = "MUTUAL_MATCH_FOUND" if unique_matches else "NO_MUTUAL_MATCH"
        recommended = unique_matches[0] if unique_matches else None

        return ViewingSlotMatchingResult(
            viewing_id=viewing.id,
            total_mutual_slots=len(unique_matches),
            mutual_slots=unique_matches,
            agent_slots_count=len(agent_slots),
            tenant_windows_count=len(tenant_windows),
            status=match_status,
            recommended_slot=recommended,
        )
