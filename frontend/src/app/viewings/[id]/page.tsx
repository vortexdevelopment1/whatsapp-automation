"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Calendar,
  Clock,
  UserCheck,
  Building2,
  Phone,
  RefreshCw,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  CalendarDays,
  ShieldAlert,
  Plus,
  Check,
  X,
  History,
  FileText,
  User,
  Info,
  ExternalLink,
  ChevronRight,
  RotateCcw,
  Ban,
  CheckCheck,
  Bell,
  CalendarClock,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  ViewingDetail,
  ViewingSlot,
  ViewingEvent,
  ViewingStatus,
  ViewingSlotSource,
  ViewingLocationType,
  ViewingReminder,
  ViewingScheduleHistory,
} from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";

export default function ViewingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const viewingId = params.id as string;

  const [viewing, setViewing] = useState<ViewingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Modals state
  const [addSlotOpen, setAddSlotOpen] = useState(false);
  const [slotStartTime, setSlotStartTime] = useState("");
  const [slotEndTime, setSlotEndTime] = useState("");
  const [slotSource, setSlotSource] = useState<ViewingSlotSource>("HUMAN_OPERATOR");
  const [slotTimezone, setSlotTimezone] = useState("Asia/Singapore");

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [completeNotes, setCompleteNotes] = useState("");

  const [noShowModalOpen, setNoShowModalOpen] = useState(false);
  const [noShowActor, setNoShowActor] = useState<"TENANT" | "PROPERTY_AGENT">("TENANT");
  const [noShowNotes, setNoShowNotes] = useState("");

  const [transitionModalOpen, setTransitionModalOpen] = useState(false);
  const [targetStatus, setTargetStatus] = useState<ViewingStatus>("SLOTS_AVAILABLE");
  const [transitionReason, setTransitionReason] = useState("");

  // Module 5 Phase 4 state
  const [tenantStatus, setTenantStatus] = useState<import("@/types").ViewingTenantAvailabilityStatus | null>(null);
  const [matchingResult, setMatchingResult] = useState<import("@/types").ViewingSlotMatchingResult | null>(null);
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [manualStart, setManualStart] = useState("");
  const [manualEnd, setManualEnd] = useState("");
  const [manualNotes, setManualNotes] = useState("");
  const [strategy, setStrategy] = useState<"OFFER_AGENT_SLOTS" | "ASK_GENERAL">("OFFER_AGENT_SLOTS");

  // Module 5 Phase 5 state
  const [confirmationOverview, setConfirmationOverview] = useState<import("@/types").ViewingConfirmationStatusOverview | null>(null);
  const [manualConfirmModalOpen, setManualConfirmModalOpen] = useState(false);
  const [manualConfirmParty, setManualConfirmParty] = useState<"TENANT" | "PROPERTY_AGENT">("TENANT");
  const [manualConfirmReason, setManualConfirmReason] = useState("");
  const [declineModalOpen, setDeclineModalOpen] = useState(false);
  const [declineParty, setDeclineParty] = useState<"TENANT" | "PROPERTY_AGENT">("TENANT");
  const [declineReason, setDeclineReason] = useState("");

  // Module 5 Phase 6 state
  const [reminders, setReminders] = useState<ViewingReminder[]>([]);
  const [scheduleHistory, setScheduleHistory] = useState<ViewingScheduleHistory[]>([]);
  const [rescheduleModalOpen, setRescheduleModalOpen] = useState(false);
  const [rescheduleRequester, setRescheduleRequester] = useState<"TENANT" | "PROPERTY_AGENT" | "HUMAN_OPERATOR">("TENANT");
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [cancelReasonCode, setCancelReasonCode] = useState<string>("TENANT_REQUEST");
  const [cancelParty, setCancelParty] = useState<string>("TENANT");

  const loadViewing = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getViewingDetail(viewingId);
      setViewing(res);
      setSlotTimezone(res.timezone || "Asia/Singapore");

      try {
        const tRes = await api.getViewingTenantAvailabilityStatus(viewingId);
        setTenantStatus(tRes);
      } catch (e) {
        // Ignored if viewing not in eligible status
      }

      try {
        const cRes = await api.getViewingConfirmationStatus(viewingId);
        setConfirmationOverview(cRes);
      } catch (e) {
        // Ignored if viewing not in eligible status
      }

      try {
        const rRes = await api.listViewingReminders(viewingId);
        setReminders(rRes || []);
      } catch (e) {
        // Ignored if viewing has no reminders yet
      }

      try {
        const hRes = await api.getViewingScheduleHistory(viewingId);
        setScheduleHistory(hRes || []);
      } catch (e) {
        // Ignored if viewing has no history yet
      }
    } catch (err: any) {
      setError(err.message || "Failed to load viewing details");
    } finally {
      setLoading(false);
    }
  }, [viewingId]);

  const handleRequestTenantAvailability = async () => {
    try {
      setActionLoading(true);
      await api.requestTenantAvailability(viewingId, { strategy });
      await loadViewing();
      alert("Tenant availability request dispatched via WhatsApp.");
    } catch (e: any) {
      alert(e.message || "Failed to send tenant availability request");
    } finally {
      setActionLoading(false);
    }
  };

  const handleMatchSlots = async () => {
    try {
      setActionLoading(true);
      const res = await api.matchViewingSlots(viewingId);
      setMatchingResult(res);
      await loadViewing();
    } catch (e: any) {
      alert(e.message || "Failed to run slot matching");
    } finally {
      setActionLoading(false);
    }
  };

  const handleProposeSlot = async (slotId: string, reason?: string) => {
    try {
      setActionLoading(true);
      await api.proposeCandidateSlot(viewingId, slotId, { reason });
      await loadViewing();
    } catch (e: any) {
      alert(e.message || "Failed to propose candidate slot");
    } finally {
      setActionLoading(false);
    }
  };

  const handleManualAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualStart || !manualEnd) return;
    try {
      setActionLoading(true);
      await api.recordManualTenantAvailability(viewingId, {
        windows: [
          {
            start_at: new Date(manualStart).toISOString(),
            end_at: new Date(manualEnd).toISOString(),
            timezone: slotTimezone,
          },
        ],
        notes: manualNotes,
      });
      setManualModalOpen(false);
      setManualStart("");
      setManualEnd("");
      setManualNotes("");
      await loadViewing();
    } catch (e: any) {
      alert(e.message || "Failed to record manual availability");
    } finally {
      setActionLoading(false);
    }
  };

  // Module 5 Phase 5 Handlers
  const handleRequestTenantConfirmation = async () => {
    try {
      setActionLoading(true);
      await api.requestTenantConfirmation(viewingId);
      await loadViewing();
      alert("Tenant confirmation request sent via WhatsApp.");
    } catch (e: any) {
      alert(e.message || "Failed to send tenant confirmation request");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestAgentConfirmation = async () => {
    try {
      setActionLoading(true);
      await api.requestAgentConfirmation(viewingId);
      await loadViewing();
      alert("Agent confirmation request sent via WhatsApp.");
    } catch (e: any) {
      alert(e.message || "Failed to send agent confirmation request");
    } finally {
      setActionLoading(false);
    }
  };

  const handleFinalizeBooking = async () => {
    if (!confirm("Finalize viewing booking? This will lock the slot as BOOKED and update viewing status to CONFIRMED.")) return;
    try {
      setActionLoading(true);
      const res = await api.finalizeViewingBooking(viewingId);
      await loadViewing();
      alert(`🎉 Viewing Confirmed! Reference: ${res.booking_reference}`);
    } catch (e: any) {
      alert(e.message || "Failed to finalize booking");
    } finally {
      setActionLoading(false);
    }
  };

  const handleManualConfirmSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualConfirmReason.trim()) return;
    try {
      setActionLoading(true);
      if (manualConfirmParty === "TENANT") {
        await api.confirmTenant(viewingId, { reason: manualConfirmReason });
      } else {
        await api.confirmAgent(viewingId, { reason: manualConfirmReason });
      }
      setManualConfirmModalOpen(false);
      setManualConfirmReason("");
      await loadViewing();
      alert(`Manual confirmation recorded for ${manualConfirmParty}.`);
    } catch (e: any) {
      alert(e.message || "Failed to record manual confirmation");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeclineSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!declineReason.trim()) return;
    try {
      setActionLoading(true);
      if (declineParty === "TENANT") {
        await api.declineTenant(viewingId, { reason: declineReason });
      } else {
        await api.declineAgent(viewingId, { reason: declineReason });
      }
      setDeclineModalOpen(false);
      setDeclineReason("");
      await loadViewing();
      alert(`Decline recorded for ${declineParty}.`);
    } catch (e: any) {
      alert(e.message || "Failed to record decline");
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    loadViewing();
  }, [loadViewing]);

  // Handle Add Slot
  const handleAddSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slotStartTime) return;
    try {
      setActionLoading(true);
      await api.addViewingSlot(viewingId, {
        start_at: new Date(slotStartTime).toISOString(),
        end_at: slotEndTime ? new Date(slotEndTime).toISOString() : undefined,
        source: slotSource,
        timezone: slotTimezone,
      });
      setAddSlotOpen(false);
      setSlotStartTime("");
      setSlotEndTime("");
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to add slot");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Select Slot
  const handleSelectSlot = async (slotId: string) => {
    if (!confirm("Are you sure you want to select this viewing slot?")) return;
    try {
      setActionLoading(true);
      await api.selectViewingSlot(viewingId, slotId);
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to select slot");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle State Transition
  const handleTransition = async () => {
    try {
      setActionLoading(true);
      await api.transitionViewing(viewingId, {
        target_status: targetStatus,
        reason: transitionReason || undefined,
      });
      setTransitionModalOpen(false);
      setTransitionReason("");
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to transition state");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Rebuild Reminders (Phase 6)
  const handleRebuildReminders = async () => {
    try {
      setActionLoading(true);
      const res = await api.rebuildViewingReminders(viewingId);
      setReminders(res || []);
      alert("Viewing reminders rebuilt successfully.");
    } catch (e: any) {
      alert(e.message || "Failed to rebuild reminders");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Reschedule Request (Phase 6)
  const handleRescheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setActionLoading(true);
      await api.rescheduleViewing(viewingId, {
        requested_by: rescheduleRequester,
        reason: rescheduleReason || undefined,
      });
      setRescheduleModalOpen(false);
      setRescheduleReason("");
      await loadViewing();
      alert("Reschedule request submitted successfully.");
    } catch (e: any) {
      alert(e.message || "Failed to request reschedule");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Cancel (Phase 6)
  const handleCancel = async () => {
    if (!cancelReason.trim()) {
      alert("Please enter a cancellation reason.");
      return;
    }
    try {
      setActionLoading(true);
      await api.cancelViewing(viewingId, {
        reason_code: cancelReasonCode,
        reason: cancelReason,
        cancelled_by: cancelParty,
      });
      setCancelModalOpen(false);
      setCancelReason("");
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to cancel viewing");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Complete
  const handleComplete = async () => {
    try {
      setActionLoading(true);
      await api.completeViewing(viewingId, { notes: completeNotes || undefined });
      setCompleteModalOpen(false);
      setCompleteNotes("");
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to complete viewing");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle No-Show
  const handleNoShow = async () => {
    try {
      setActionLoading(true);
      await api.recordViewingNoShow(viewingId, {
        actor: noShowActor,
        notes: noShowNotes || undefined,
      });
      setNoShowModalOpen(false);
      setNoShowNotes("");
      await loadViewing();
    } catch (err: any) {
      alert(err.message || "Failed to record no-show");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
        <RefreshCw className="w-8 h-8 animate-spin text-sky-600" />
        <p className="text-base font-medium">Loading viewing details...</p>
      </div>
    );
  }

  if (error || !viewing) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-rose-600">
        <AlertTriangle className="w-10 h-10 mx-auto mb-3 text-rose-500" />
        <h2 className="text-lg font-bold">Error loading viewing</h2>
        <p className="text-sm mt-1">{error || "Viewing not found."}</p>
        <Link href="/viewings" className="mt-4 inline-block">
          <Button variant="outline" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Viewings
          </Button>
        </Link>
      </div>
    );
  }

  const isTerminal =
    viewing.status === "COMPLETED" ||
    viewing.status === "CANCELLED" ||
    viewing.status === "NO_SHOW" ||
    viewing.status === "REJECTED";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Navigation & Header */}
      <div>
        <Link
          href="/viewings"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" />
          Back to Viewings List
        </Link>
        <PageHeader
          title={
            viewing.property_summary?.canonical_name ||
            viewing.property_summary?.building_name ||
            "Viewing Coordination"
          }
          description={`Lead ID: ${viewing.lead_id} · Match ID: ${viewing.property_match_id}`}
          badges={<StatusBadge status={viewing.status} />}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={loadViewing}
                disabled={actionLoading}
                className="gap-1.5"
              >
                <RefreshCw className={`w-4 h-4 ${actionLoading ? "animate-spin text-sky-600" : ""}`} />
                Refresh
              </Button>
            </div>
          }
        />
      </div>

      {/* Top Banner: Confirmed Viewing (Phase 5 & 6) */}
      {viewing.status === "CONFIRMED" && (
        <div className="p-5 bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 text-white rounded-2xl shadow-md border border-emerald-500/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-white/20 backdrop-blur-xs text-white shrink-0 mt-0.5">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold uppercase tracking-widest bg-white/25 px-2.5 py-0.5 rounded-full">
                  UPCOMING VIEWING CONFIRMED
                </span>
                <span className="font-mono text-xs font-bold text-emerald-100 bg-emerald-800/40 px-2 py-0.5 rounded">
                  Ref: {confirmationOverview?.booking_reference || `VW-2026-${viewing.id.slice(0, 8).toUpperCase()}`}
                </span>
                <span className="text-xs font-mono font-bold bg-white/20 text-emerald-50 px-2 py-0.5 rounded">
                  Version {viewing.schedule_version || 1}
                </span>
              </div>
              <div className="text-xl font-extrabold text-white">
                {viewing.scheduled_start_at ? formatDate(viewing.scheduled_start_at) : "Date & Time Confirmed"}
                {viewing.scheduled_end_at && ` – ${formatDate(viewing.scheduled_end_at)}`}
              </div>
              <div className="text-xs text-emerald-100 flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>📍 Location: {viewing.location_text || viewing.property_summary?.address || "At Property"}</span>
                <span>⏱️ Timezone: {viewing.timezone}</span>
                <span>🔔 Reminders: {reminders.length} scheduled ({reminders.filter(r => r.status === 'SENT').length} sent, {reminders.filter(r => r.status === 'PENDING').length} pending)</span>
              </div>
            </div>
          </div>
          <div className="shrink-0 flex items-center gap-2 self-start md:self-center">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setRescheduleRequester("TENANT");
                setRescheduleReason("");
                setRescheduleModalOpen(true);
              }}
              className="bg-white/20 hover:bg-white/30 text-white border-white/40 text-xs gap-1.5"
            >
              <CalendarClock className="w-3.5 h-3.5" />
              Request Reschedule
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setCancelModalOpen(true)}
              className="bg-rose-500/80 hover:bg-rose-600 text-white border-rose-400 text-xs gap-1.5"
            >
              <Ban className="w-3.5 h-3.5" />
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Top Banner: Reschedule Requested (Phase 6) */}
      {viewing.status === "RESCHEDULE_REQUESTED" && (
        <div className="p-5 bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 text-white rounded-2xl shadow-md border border-amber-500/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-white/20 backdrop-blur-xs text-white shrink-0 mt-0.5">
              <CalendarClock className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold uppercase tracking-widest bg-white/25 px-2.5 py-0.5 rounded-full">
                  RESCHEDULE REQUESTED
                </span>
                <span className="text-xs font-mono font-bold bg-white/20 text-amber-50 px-2 py-0.5 rounded">
                  Version {viewing.schedule_version || 1}
                </span>
              </div>
              <div className="text-lg font-bold text-white">
                Reschedule Requested {viewing.reschedule_reason ? `— "${viewing.reschedule_reason}"` : ""}
              </div>
              <div className="text-xs text-amber-100 flex flex-wrap items-center gap-x-4 gap-y-1">
                {viewing.previous_scheduled_start_at && (
                  <span>🕒 Previous Slot: {formatDate(viewing.previous_scheduled_start_at)}</span>
                )}
                <span>📋 Reschedule Count: {viewing.reschedule_count}x</span>
                <span>🔄 Status: Awaiting new availability & slot re-matching</span>
              </div>
            </div>
          </div>
          <div className="shrink-0 flex items-center gap-2 self-start md:self-center">
            <Button
              size="sm"
              onClick={() => {
                const el = document.getElementById("tenant-availability-section");
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }}
              className="bg-white text-amber-900 hover:bg-amber-50 font-bold text-xs shadow-xs gap-1.5"
            >
              Continue Scheduling
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Top Banner: Viewing Cancelled (Phase 6) */}
      {viewing.status === "CANCELLED" && (
        <div className="p-5 bg-gradient-to-r from-rose-700 via-rose-800 to-slate-800 text-white rounded-2xl shadow-md border border-rose-600/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-white/20 backdrop-blur-xs text-white shrink-0 mt-0.5">
              <Ban className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold uppercase tracking-widest bg-white/25 px-2.5 py-0.5 rounded-full">
                  VIEWING CANCELLED
                </span>
                <span className="text-xs font-mono font-bold bg-white/20 text-rose-100 px-2 py-0.5 rounded">
                  Version {viewing.schedule_version || 1}
                </span>
              </div>
              <div className="text-lg font-bold text-white">
                Cancelled by {viewing.cancelled_by || "System"}
                {viewing.cancellation_reason ? ` · Reason: ${viewing.cancellation_reason}` : ""}
              </div>
              <div className="text-xs text-rose-200 flex flex-wrap items-center gap-x-4 gap-y-1">
                {(viewing.previous_scheduled_start_at || viewing.scheduled_start_at) && (
                  <span>🕒 Original Slot: {formatDate(viewing.previous_scheduled_start_at || viewing.scheduled_start_at!)}</span>
                )}
                {viewing.cancelled_at && <span>📅 Cancelled At: {formatDate(viewing.cancelled_at)}</span>}
                <span>🛑 All scheduled reminders have been cancelled</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Property & Tenant Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Key Entities Card */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <Building2 className="w-4 h-4 text-sky-600" />
                Entities & Parties
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Tenant / Lead */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Tenant / Lead
                  </span>
                  <Link
                    href={`/leads/${viewing.lead_id}`}
                    className="text-xs text-sky-600 hover:underline flex items-center gap-0.5"
                  >
                    View Lead <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
                <div className="text-base font-bold text-slate-900">
                  {viewing.lead_name || "Lead Record"}
                </div>
                <div className="flex items-center gap-2 pt-2 border-t border-slate-200 text-xs">
                  <span className="text-slate-500">Tenant Confirmation:</span>
                  <StatusBadge status={viewing.tenant_confirmation_status} />
                </div>
              </div>

              {/* Listing Agent */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Listing Agent
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    ID: {viewing.property_agent_id.slice(0, 8)}...
                  </span>
                </div>
                <div className="text-base font-bold text-slate-900">
                  {viewing.agent_summary?.full_name || "Agent"}
                </div>
                <div className="text-xs text-slate-600">
                  Agency: {viewing.agent_summary?.agency_name || "Independent"}
                </div>
                {viewing.agent_summary?.phone && (
                  <div className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                    <Phone className="w-3 h-3 text-slate-400" />
                    {viewing.agent_summary.phone}
                  </div>
                )}
                <div className="flex items-center gap-2 pt-2 border-t border-slate-200 text-xs">
                  <span className="text-slate-500">Agent Confirmation:</span>
                  <StatusBadge status={viewing.agent_confirmation_status} />
                </div>
              </div>

              {/* Property Details */}
              <div className="md:col-span-2 bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Property & Listing Summary
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                  <div>
                    <div className="text-xs text-slate-500">Address / Location</div>
                    <div className="text-sm font-semibold text-slate-800">
                      {viewing.property_summary?.address || viewing.property_summary?.district || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Bedrooms / Type</div>
                    <div className="text-sm font-semibold text-slate-800">
                      {viewing.property_summary?.bedrooms
                        ? `${viewing.property_summary.bedrooms} Beds`
                        : "—"}{" "}
                      · {viewing.property_summary?.property_type || "Condo"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Asking Price</div>
                    <div className="text-sm font-semibold text-slate-800 font-mono">
                      {viewing.listing_summary?.asking_price
                        ? `$${viewing.listing_summary.asking_price.toLocaleString()}/mo`
                        : "—"}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Module 5 Phase 3: AGENT AVAILABILITY CARD */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <Clock className="w-4 h-4 text-sky-600" />
                Property Agent Availability Collection
              </CardTitle>
              {viewing.status === "DRAFT" || viewing.status === "AWAITING_AGENT_AVAILABILITY" ? (
                <Button
                  size="sm"
                  onClick={async () => {
                    try {
                      setActionLoading(true);
                      await api.requestAgentAvailability(viewingId);
                      await loadViewing();
                    } catch (e: any) {
                      alert(e.message || "Failed to request agent availability");
                    } finally {
                      setActionLoading(false);
                    }
                  }}
                  disabled={actionLoading}
                  className="gap-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs h-8"
                >
                  <Phone className="w-3.5 h-3.5" />
                  {viewing.status === "AWAITING_AGENT_AVAILABILITY" ? "Resend Request" : "Request Agent Slots"}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
                  <span className="text-2xs font-semibold text-slate-500 uppercase">Property Agent</span>
                  <div className="text-sm font-bold text-slate-900 mt-0.5">
                    {viewing.agent_summary?.full_name || "Assigned Listing Agent"}
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    {viewing.agent_summary?.phone || "No phone registered"}
                  </div>
                </div>

                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
                  <span className="text-2xs font-semibold text-slate-500 uppercase">Request Status</span>
                  <div className="mt-1">
                    <StatusBadge status={viewing.status} />
                  </div>
                </div>

                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
                  <span className="text-2xs font-semibold text-slate-500 uppercase">Available Agent Slots</span>
                  <div className="text-sm font-bold text-emerald-700 mt-0.5">
                    {viewing.slots?.filter(s => s.source === "PROPERTY_AGENT").length || 0} candidate slots
                  </div>
                  <div className="text-2xs text-slate-500">
                    Phase 4 will match with tenant
                  </div>
                </div>
              </div>

              {viewing.status === "AWAITING_AGENT_AVAILABILITY" && (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-800 flex items-start gap-2">
                  <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Awaiting Listing Agent Reply</div>
                    <div className="text-amber-700 mt-0.5">
                      Outbound availability request dispatched via WhatsApp concierge. When the agent replies with viewing times, slots will be extracted and verified automatically.
                    </div>
                  </div>
                </div>
              )}

              {viewing.status === "SLOTS_AVAILABLE" && (
                <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Candidate Slots Collected</div>
                    <div className="text-emerald-700 mt-0.5">
                      Agent availability received and candidate slots stored. Ready for Phase 4 tenant availability capture & matching.
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Module 5 Phase 4: TENANT AVAILABILITY & MUTUAL SLOT MATCHING CARD */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <Calendar className="w-4 h-4 text-emerald-600" />
                Tenant Availability & Mutual Slot Matching
              </CardTitle>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setManualModalOpen(true)}
                  disabled={actionLoading}
                  className="gap-1 text-xs h-8 border-slate-300"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Manual Availability
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleMatchSlots}
                  disabled={actionLoading}
                  className="gap-1 text-xs h-8 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? "animate-spin" : ""}`} />
                  Match Slots
                </Button>
                {(viewing.status === "SLOTS_AVAILABLE" || viewing.status === "AWAITING_TENANT_AVAILABILITY") && (
                  <Button
                    size="sm"
                    onClick={handleRequestTenantAvailability}
                    disabled={actionLoading}
                    className="gap-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8"
                  >
                    <Phone className="w-3.5 h-3.5" />
                    Ask Tenant
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-5 space-y-5">
              {/* Current Proposed Slot Banner */}
              {viewing.status === "SLOT_PROPOSED" && viewing.scheduled_start_at && (
                <div className="p-4 bg-emerald-50 border-2 border-emerald-500/40 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-emerald-600 text-white shrink-0 mt-0.5">
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs uppercase font-bold text-emerald-800 tracking-wider">
                        Current Proposed Candidate Slot
                      </div>
                      <div className="text-base font-bold text-slate-900 mt-0.5">
                        {formatDate(viewing.scheduled_start_at)}
                        {viewing.scheduled_end_at && ` – ${formatDate(viewing.scheduled_end_at)}`}
                      </div>
                      <div className="text-xs text-emerald-700 mt-0.5">
                        Mutually agreed candidate slot proposed. Status is <strong>SLOT_PROPOSED</strong>.
                        Ready for Phase 5 confirmation sequence (Not confirmed yet).
                      </div>
                    </div>
                  </div>
                  <span className="text-xs font-semibold px-3 py-1 rounded-full bg-emerald-200 text-emerald-900 self-start sm:self-center">
                    PROPOSED CANDIDATE
                  </span>
                </div>
              )}

              {/* Grid: Agent vs Tenant Availability */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Agent Slots */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                      <UserCheck className="w-3.5 h-3.5 text-sky-600" /> Agent Available Slots
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-sky-100 text-sky-800">
                      {tenantStatus?.agent_slots?.length || viewing.slots?.filter(s => s.source === "PROPERTY_AGENT").length || 0} slots
                    </span>
                  </div>
                  <div className="space-y-1.5 mt-2">
                    {((tenantStatus?.agent_slots && tenantStatus.agent_slots.length > 0)
                      ? tenantStatus.agent_slots
                      : (viewing.slots?.filter(s => s.source === "PROPERTY_AGENT") || [])
                    ).map((s) => (
                      <div key={s.id} className="text-xs p-2 rounded bg-white border border-slate-200 flex items-center justify-between">
                        <span className="font-medium text-slate-800">{formatDate(s.start_at)}</span>
                        <StatusBadge status={s.status} />
                      </div>
                    ))}
                    {(!viewing.slots?.some(s => s.source === "PROPERTY_AGENT")) && (
                      <div className="text-xs text-slate-400 italic py-2">No agent slots recorded yet.</div>
                    )}
                  </div>
                </div>

                {/* Tenant Windows */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-emerald-600" /> Tenant Availability
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      {tenantStatus?.tenant_slots?.length || viewing.slots?.filter(s => s.source === "TENANT" || s.source === "HUMAN_OPERATOR").length || 0} entries
                    </span>
                  </div>
                  <div className="space-y-1.5 mt-2">
                    {((tenantStatus?.tenant_slots && tenantStatus.tenant_slots.length > 0)
                      ? tenantStatus.tenant_slots
                      : (viewing.slots?.filter(s => s.source === "TENANT" || s.source === "HUMAN_OPERATOR") || [])
                    ).map((s) => (
                      <div key={s.id} className="text-xs p-2 rounded bg-white border border-slate-200 flex items-center justify-between">
                        <span className="font-medium text-slate-800">
                          {formatDate(s.start_at)} {s.end_at ? `– ${formatDate(s.end_at)}` : ""}
                        </span>
                        <span className="text-2xs font-mono text-slate-500 uppercase">{s.source}</span>
                      </div>
                    ))}
                    {(!viewing.slots?.some(s => s.source === "TENANT" || s.source === "HUMAN_OPERATOR")) && (
                      <div className="text-xs text-slate-400 italic py-2">
                        Awaiting tenant reply. Use "Ask Tenant" to prompt via WhatsApp or "Manual Availability" to input phone notes.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Mutual Options Section */}
              <div className="pt-2 border-t border-slate-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
                    <CalendarDays className="w-4 h-4 text-emerald-600" />
                    Mutual Viewing Options (Deterministic Overlap Engine)
                  </div>
                  <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-slate-100 text-slate-700">
                    {(matchingResult?.mutual_slots?.length || tenantStatus?.mutual_slots?.length || 0)} mutual match(es)
                  </span>
                </div>

                {((matchingResult?.mutual_slots && matchingResult.mutual_slots.length > 0) ||
                  (tenantStatus?.mutual_slots && tenantStatus.mutual_slots.length > 0)) ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(matchingResult?.mutual_slots || tenantStatus?.mutual_slots || []).map((m, idx) => (
                      <div
                        key={idx}
                        className={`p-3.5 rounded-xl border flex flex-col justify-between gap-2.5 ${
                          m.is_proposed
                            ? "bg-emerald-50/50 border-emerald-400"
                            : "bg-white border-slate-200 hover:border-emerald-300"
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-sm text-slate-900">
                              {formatDate(m.start_at)}
                            </span>
                            <span className="text-2xs font-bold px-2 py-0.5 rounded uppercase bg-emerald-100 text-emerald-800">
                              {m.match_type}
                            </span>
                          </div>
                          <div className="text-xs text-slate-600 mt-1">
                            {m.reason}
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                          {m.agent_slot_id ? (
                            <Button
                              size="sm"
                              onClick={() => handleProposeSlot(m.agent_slot_id!, m.reason)}
                              disabled={actionLoading}
                              className="text-xs h-7 gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                            >
                              <Check className="w-3 h-3" /> Propose Slot
                            </Button>
                          ) : (
                            <span className="text-2xs text-slate-400 italic">Discretized Overlap</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 bg-slate-50 rounded-xl border border-dashed border-slate-300 text-center text-xs text-slate-500">
                    <p className="font-semibold text-slate-700">NO MUTUAL SLOT FOUND YET</p>
                    <p className="mt-1">
                      No matching slots overlap between the agent and tenant availability.
                      Suggested action: Request additional agent slots or ask tenant for other availability times.
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Module 5 Phase 5: VIEWING CONFIRMATION & BOOKING CARD */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                Viewing Confirmation & Final Booking
              </CardTitle>
              <div className="flex items-center gap-2">
                <StatusBadge status={viewing.status} />
                {(viewing.tenant_confirmation_status === "CONFIRMED" && viewing.agent_confirmation_status === "CONFIRMED" && viewing.status !== "CONFIRMED") && (
                  <Button
                    size="sm"
                    onClick={handleFinalizeBooking}
                    disabled={actionLoading}
                    className="gap-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8 shadow-xs"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    Finalize Booking (Lock Slot)
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-5 space-y-5">
              {/* If Declined */}
              {(viewing.tenant_confirmation_status === "DECLINED" || viewing.agent_confirmation_status === "DECLINED") && (
                <div className="p-4 bg-amber-50 border border-amber-300 rounded-xl flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <div className="text-sm font-bold text-amber-900">
                      SLOT DECLINED
                    </div>
                    <div className="text-xs text-amber-800">
                      Proposed slot was declined by {viewing.tenant_confirmation_status === "DECLINED" ? "Tenant" : "Property Agent"}.
                      The proposed slot has been released.
                    </div>
                    <div className="text-xs font-semibold text-amber-900 pt-1">
                      Suggested next action: Choose another mutual slot above or collect new availability windows.
                    </div>
                  </div>
                </div>
              )}

              {/* Proposed Slot Info */}
              {viewing.scheduled_start_at && (
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-sky-600" /> Selected / Proposed Viewing Slot
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-700">
                      Ref: {confirmationOverview?.booking_reference || `VW-2026-${viewing.id.slice(0, 8).toUpperCase()}`}
                    </span>
                  </div>
                  <div className="text-base font-extrabold text-slate-900">
                    {formatDate(viewing.scheduled_start_at)}
                    {viewing.scheduled_end_at && ` – ${formatDate(viewing.scheduled_end_at)}`}
                  </div>
                  <div className="text-xs text-slate-500">
                    Location: {viewing.location_text || viewing.property_summary?.address || "At Property"} ({viewing.location_type}) · Timezone: {viewing.timezone}
                  </div>
                </div>
              )}

              {/* Two-Column Confirmation Status Panel */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Tenant Confirmation Status */}
                <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-emerald-600" /> Tenant Confirmation
                    </span>
                    <StatusBadge status={viewing.tenant_confirmation_status} />
                  </div>

                  <div className="text-xs text-slate-500">
                    {viewing.tenant_confirmation_status === "CONFIRMED" ? (
                      <span className="text-emerald-700 font-semibold flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Tenant confirmed proposed slot.
                      </span>
                    ) : viewing.tenant_confirmation_status === "DECLINED" ? (
                      <span className="text-rose-600 font-semibold">Tenant declined proposed slot.</span>
                    ) : (
                      <span>Awaiting tenant final response via WhatsApp.</span>
                    )}
                  </div>

                  {viewing.status !== "CONFIRMED" && !isTerminal && (
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleRequestTenantConfirmation}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 border-slate-300"
                      >
                        <Phone className="w-3 h-3 text-slate-500" /> Send Request
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setManualConfirmParty("TENANT");
                          setManualConfirmReason("Confirmed via phone call");
                          setManualConfirmModalOpen(true);
                        }}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                      >
                        <Check className="w-3 h-3" /> Manual Confirm
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setDeclineParty("TENANT");
                          setDeclineReason("Tenant requested different time");
                          setDeclineModalOpen(true);
                        }}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 text-rose-600 border-rose-200 hover:bg-rose-50"
                      >
                        <X className="w-3 h-3" /> Decline
                      </Button>
                    </div>
                  )}
                </div>

                {/* Agent Confirmation Status */}
                <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <UserCheck className="w-3.5 h-3.5 text-sky-600" /> Property Agent Confirmation
                    </span>
                    <StatusBadge status={viewing.agent_confirmation_status} />
                  </div>

                  <div className="text-xs text-slate-500">
                    {viewing.agent_confirmation_status === "CONFIRMED" ? (
                      <span className="text-emerald-700 font-semibold flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Listing agent confirmed slot availability.
                      </span>
                    ) : viewing.agent_confirmation_status === "DECLINED" ? (
                      <span className="text-rose-600 font-semibold">Agent declined slot.</span>
                    ) : (
                      <span>Awaiting agent final confirmation via WhatsApp.</span>
                    )}
                  </div>

                  {viewing.status !== "CONFIRMED" && !isTerminal && (
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleRequestAgentConfirmation}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 border-slate-300"
                      >
                        <Phone className="w-3 h-3 text-slate-500" /> Send Request
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setManualConfirmParty("PROPERTY_AGENT");
                          setManualConfirmReason("Agent confirmed availability via phone call");
                          setManualConfirmModalOpen(true);
                        }}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                      >
                        <Check className="w-3 h-3" /> Manual Confirm
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setDeclineParty("PROPERTY_AGENT");
                          setDeclineReason("Slot no longer available");
                          setDeclineModalOpen(true);
                        }}
                        disabled={actionLoading}
                        className="text-2xs h-7 gap-1 text-rose-600 border-rose-200 hover:bg-rose-50"
                      >
                        <X className="w-3 h-3" /> Decline
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              {/* Ready to Finalize Banner */}
              {viewing.tenant_confirmation_status === "CONFIRMED" && viewing.agent_confirmation_status === "CONFIRMED" && viewing.status !== "CONFIRMED" && (
                <div className="p-4 bg-emerald-50 border-2 border-emerald-500 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-emerald-600 text-white shrink-0 mt-0.5">
                      <CheckCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-emerald-950">
                        Both Parties Have Confirmed
                      </div>
                      <div className="text-xs text-emerald-800">
                        Confirmation policy requirements are fully satisfied. Ready to lock the selected slot and mark the viewing <strong>CONFIRMED</strong>.
                      </div>
                    </div>
                  </div>
                  <Button
                    onClick={handleFinalizeBooking}
                    disabled={actionLoading}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 shadow-sm shrink-0"
                  >
                    Lock Slot & Finalize Booking
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Module 5 Phase 6: VIEWING REMINDERS & AUTOMATION CARD */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <Bell className="w-4 h-4 text-sky-600" />
                Viewing Reminders & Automation ({reminders.length})
              </CardTitle>
              <div className="flex items-center gap-2">
                {viewing.status === "CONFIRMED" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleRebuildReminders}
                    disabled={actionLoading}
                    className="gap-1.5 text-xs h-8 border-sky-300 text-sky-700 hover:bg-sky-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? "animate-spin" : ""}`} />
                    Rebuild Reminders
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              {reminders.length === 0 ? (
                <div className="p-6 bg-slate-50 rounded-xl border border-dashed border-slate-300 text-center text-xs text-slate-500">
                  <Bell className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="font-semibold text-slate-700">NO REMINDER JOBS SCHEDULED</p>
                  <p className="mt-1 max-w-md mx-auto text-slate-500">
                    Reminders are automatically created when a viewing is confirmed. If the viewing is confirmed, you can click "Rebuild Reminders" above to generate configured offsets.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {reminders.map((rem) => {
                    const isTenant = rem.party === "TENANT";
                    return (
                      <div
                        key={rem.id}
                        className="p-4 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 transition-colors space-y-2.5 shadow-2xs"
                      >
                        <div className="flex items-center justify-between">
                          <span
                            className={`text-2xs font-extrabold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                              isTenant
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-sky-100 text-sky-800"
                            }`}
                          >
                            {isTenant ? "Tenant Reminder" : "Agent Reminder"}
                          </span>
                          <StatusBadge status={rem.status} />
                        </div>

                        <div>
                          <div className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            {formatDate(rem.scheduled_for)}
                          </div>
                          <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                            {rem.offset_minutes && (
                              <span>
                                {rem.offset_minutes >= 60
                                  ? `${Math.round(rem.offset_minutes / 60)}h before`
                                  : `${rem.offset_minutes}m before`}
                              </span>
                            )}
                            <span>·</span>
                            <span className="font-mono text-2xs text-slate-500">
                              Schedule v{rem.booking_version}
                            </span>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-slate-100 text-2xs text-slate-500 flex flex-wrap items-center justify-between gap-1">
                          <span>Attempts: {rem.attempt_count}/{rem.max_attempts}</span>
                          {rem.sent_at && (
                            <span className="text-emerald-700 font-medium">
                              Sent: {formatDate(rem.sent_at)}
                            </span>
                          )}
                          {rem.cancelled_at && (
                            <span className="text-rose-600 font-medium">
                              Cancelled: {formatDate(rem.cancelled_at)}
                            </span>
                          )}
                        </div>

                        {rem.error_message && (
                          <div className="text-2xs text-rose-600 bg-rose-50 p-2 rounded border border-rose-100">
                            {rem.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Module 5 Phase 6: SCHEDULE VERSION HISTORY CARD */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <History className="w-4 h-4 text-purple-600" />
                Schedule Version History
              </CardTitle>
              <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-purple-100 text-purple-800">
                Current: v{viewing.schedule_version || 1}
              </span>
            </CardHeader>
            <CardContent className="p-5">
              {scheduleHistory.length === 0 ? (
                <div className="text-xs text-slate-500 py-3">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-slate-800">Version 1 (Initial Booking)</span>
                      <div className="text-slate-600 mt-0.5">
                        {viewing.scheduled_start_at
                          ? formatDate(viewing.scheduled_start_at)
                          : "Initial Schedule"}
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-2xs font-bold">
                      CURRENT
                    </span>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {scheduleHistory.map((hist) => {
                    const isCurrent = hist.version === (viewing.schedule_version || 1);
                    return (
                      <div
                        key={hist.id}
                        className={`p-3.5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          isCurrent
                            ? "bg-purple-50/40 border-purple-300"
                            : "bg-slate-50 border-slate-200"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-extrabold font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-900">
                              v{hist.version}
                            </span>
                            <span className="text-sm font-bold text-slate-900">
                              {hist.scheduled_start_at
                                ? `${formatDate(hist.scheduled_start_at)}${
                                    hist.scheduled_end_at ? ` – ${formatDate(hist.scheduled_end_at)}` : ""
                                  }`
                                : "No slot associated"}
                            </span>
                          </div>
                          <div className="text-xs text-slate-600 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                            <span>Changed by: <strong>{hist.changed_by}</strong></span>
                            {hist.reason && <span>Reason: <em>"{hist.reason}"</em></span>}
                            <span>Recorded: {formatDate(hist.created_at)}</span>
                          </div>
                        </div>

                        <div>
                          {isCurrent ? (
                            <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-2xs font-bold">
                              CURRENT
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 rounded-full bg-slate-200 text-slate-600 text-2xs font-semibold">
                              ARCHIVED
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Slots Management Section */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <CalendarDays className="w-4 h-4 text-sky-600" />
                Viewing Slots ({viewing.slots?.length || 0})
              </CardTitle>
              {!isTerminal && (
                <Button
                  size="sm"
                  onClick={() => setAddSlotOpen(true)}
                  className="gap-1 bg-sky-600 hover:bg-sky-700 text-white text-xs h-8"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Slot
                </Button>
              )}
            </CardHeader>
            <CardContent className="p-5">
              {!viewing.slots || viewing.slots.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Calendar className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                  <p className="text-sm font-medium text-slate-600">No viewing slots added yet</p>
                  <p className="text-xs text-slate-400 mt-1">
                    Add proposed or available slots for the tenant and agent.
                  </p>
                  {!isTerminal && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setAddSlotOpen(true)}
                      className="mt-3 text-xs"
                    >
                      <Plus className="w-3 h-3 mr-1" /> Add First Slot
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {viewing.slots.map((slot) => {
                    const isSelected = slot.status === "SELECTED" || slot.status === "BOOKED";
                    return (
                      <div
                        key={slot.id}
                        className={`p-4 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          isSelected
                            ? "bg-emerald-50/40 border-emerald-300 shadow-2xs"
                            : "bg-white border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900 text-sm">
                              {formatDate(slot.start_at)}
                            </span>
                            <StatusBadge status={slot.status} />
                            <span className="text-2xs px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-mono">
                              Source: {slot.source}
                            </span>
                          </div>
                          <div className="text-xs text-slate-500 font-mono">
                            Timezone: {slot.timezone}
                            {slot.end_at && ` · Until ${formatDate(slot.end_at)}`}
                          </div>
                        </div>

                        {/* Slot Actions */}
                        <div className="flex items-center gap-2">
                          {!isSelected && !isTerminal && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleSelectSlot(slot.id)}
                              disabled={actionLoading}
                              className="text-xs gap-1 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                            >
                              <Check className="w-3.5 h-3.5" /> Select Slot
                            </Button>
                          )}
                          {isSelected && (
                            <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-md flex items-center gap-1">
                              <CheckCheck className="w-3.5 h-3.5" /> Selected Slot
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Audit & Event History */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <History className="w-4 h-4 text-slate-600" />
                Viewing Audit & Event History ({viewing.events?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              {!viewing.events || viewing.events.length === 0 ? (
                <p className="text-sm text-slate-400 py-4 text-center">No event history recorded.</p>
              ) : (
                <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                  {viewing.events.map((ev) => (
                    <div key={ev.id} className="relative group">
                      <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-sky-600 ring-4 ring-white" />
                      <div className="text-xs font-semibold text-slate-800 flex items-center gap-2">
                        <span>{ev.event_type.replace(/_/g, " ")}</span>
                        <span className="text-2xs text-slate-400 font-mono font-normal">
                          by {ev.actor_type} ({ev.actor_id || "system"})
                        </span>
                        <span className="text-2xs text-slate-400 font-normal ml-auto">
                          {formatDate(ev.created_at)}
                        </span>
                      </div>
                      {ev.old_status && ev.new_status && (
                        <div className="text-xs text-slate-600 mt-1 flex items-center gap-1.5 font-mono">
                          <StatusBadge status={ev.old_status} />
                          <span>→</span>
                          <StatusBadge status={ev.new_status} />
                        </div>
                      )}
                      {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                        <pre className="text-2xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 mt-1 font-mono overflow-x-auto max-w-xl">
                          {JSON.stringify(ev.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Schedule & Workflow Controls */}
        <div className="space-y-6">
          {/* Current Schedule Summary */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <Clock className="w-4 h-4 text-sky-600" />
                Schedule & Location
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-4 text-sm">
              <div>
                <span className="text-xs font-medium text-slate-500 uppercase">Scheduled Time</span>
                <div className="font-semibold text-slate-900 mt-0.5">
                  {viewing.scheduled_start_at
                    ? formatDate(viewing.scheduled_start_at)
                    : "Not scheduled yet"}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
                <div>
                  <span className="text-xs text-slate-500">Duration</span>
                  <div className="font-medium text-slate-800">{viewing.duration_minutes} mins</div>
                </div>
                <div>
                  <span className="text-xs text-slate-500">Timezone</span>
                  <div className="font-medium text-slate-800 font-mono text-xs">{viewing.timezone}</div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100">
                <span className="text-xs text-slate-500">Location Type</span>
                <div className="font-medium text-slate-800">{viewing.location_type}</div>
                {viewing.location_text && (
                  <p className="text-xs text-slate-600 mt-1">{viewing.location_text}</p>
                )}
                {viewing.meeting_url && (
                  <a
                    href={viewing.meeting_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-sky-600 hover:underline flex items-center gap-1 mt-1 font-mono"
                  >
                    {viewing.meeting_url} <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              {viewing.reschedule_count > 0 && (
                <div className="pt-2 border-t border-slate-100 bg-amber-50 p-3 rounded-lg text-xs space-y-1">
                  <div className="font-semibold text-amber-800">
                    Rescheduled ({viewing.reschedule_count}x)
                  </div>
                  {viewing.previous_scheduled_start_at && (
                    <div className="text-amber-700">
                      Previously: {formatDate(viewing.previous_scheduled_start_at)}
                    </div>
                  )}
                  {viewing.reschedule_reason && (
                    <div className="text-amber-600 italic">"{viewing.reschedule_reason}"</div>
                  )}
                </div>
              )}

              {viewing.cancellation_reason && (
                <div className="pt-2 border-t border-slate-100 bg-rose-50 p-3 rounded-lg text-xs space-y-1">
                  <div className="font-semibold text-rose-800">Cancelled</div>
                  <div className="text-rose-700">Reason: {viewing.cancellation_reason}</div>
                  <div className="text-rose-600 text-2xs">
                    By {viewing.cancelled_by} at {viewing.cancelled_at && formatDate(viewing.cancelled_at)}
                  </div>
                </div>
              )}

              {viewing.completed_at && (
                <div className="pt-2 border-t border-slate-100 bg-emerald-50 p-3 rounded-lg text-xs space-y-1">
                  <div className="font-semibold text-emerald-800">Completed</div>
                  <div className="text-emerald-700">
                    Completed at: {formatDate(viewing.completed_at)}
                  </div>
                  {viewing.outcome_notes && (
                    <div className="text-emerald-800 italic">"{viewing.outcome_notes}"</div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Workflow Action Controls */}
          <Card className="border-slate-200 shadow-2xs">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                <CheckCircle2 className="w-4 h-4 text-sky-600" />
                Workflow Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-3">
              {!isTerminal && (
                <>
                  <Button
                    variant="outline"
                    className="w-full justify-start text-xs font-semibold gap-2 border-sky-200 text-sky-700 hover:bg-sky-50"
                    onClick={() => {
                      setTargetStatus("SLOTS_AVAILABLE");
                      setTransitionModalOpen(true);
                    }}
                  >
                    <CalendarDays className="w-4 h-4" />
                    Transition State...
                  </Button>

                  {viewing.status === "CONFIRMED" && (
                    <>
                      <Button
                        className="w-full justify-start text-xs font-semibold gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
                        onClick={() => setCompleteModalOpen(true)}
                      >
                        <CheckCheck className="w-4 h-4" />
                        Complete Viewing
                      </Button>
                      <Button
                        variant="outline"
                        className="w-full justify-start text-xs font-semibold gap-2 border-amber-300 text-amber-800 hover:bg-amber-50"
                        onClick={() => {
                          setRescheduleRequester("TENANT");
                          setRescheduleReason("");
                          setRescheduleModalOpen(true);
                        }}
                      >
                        <CalendarClock className="w-4 h-4 text-amber-600" />
                        Request Reschedule...
                      </Button>
                      <Button
                        variant="outline"
                        className="w-full justify-start text-xs font-semibold gap-2 border-amber-300 text-amber-700 hover:bg-amber-50"
                        onClick={() => setNoShowModalOpen(true)}
                      >
                        <AlertTriangle className="w-4 h-4" />
                        Record No-Show
                      </Button>
                    </>
                  )}

                  <Button
                    variant="outline"
                    className="w-full justify-start text-xs font-semibold gap-2 border-rose-200 text-rose-700 hover:bg-rose-50"
                    onClick={() => setCancelModalOpen(true)}
                  >
                    <Ban className="w-4 h-4" />
                    Cancel Viewing
                  </Button>
                </>
              )}

              {isTerminal && (
                <div className="p-3 bg-slate-50 rounded-lg text-xs text-slate-500 text-center">
                  This viewing has reached terminal state (<strong>{viewing.status}</strong>).
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* MODAL 1: Add Slot */}
      <Modal
        isOpen={addSlotOpen}
        onClose={() => setAddSlotOpen(false)}
        title="Add Viewing Slot"
        description="Add a proposed or available viewing slot for this property."
      >
        <form onSubmit={handleAddSlot} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Slot Source</label>
            <select
              value={slotSource}
              onChange={(e) => setSlotSource(e.target.value as ViewingSlotSource)}
              className="w-full text-xs rounded-lg border border-slate-300 p-2"
            >
              <option value="HUMAN_OPERATOR">Human Operator</option>
              <option value="PROPERTY_AGENT">Property Agent</option>
              <option value="TENANT">Tenant</option>
              <option value="SYSTEM">System</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Start Time</label>
            <Input
              type="datetime-local"
              required
              value={slotStartTime}
              onChange={(e) => setSlotStartTime(e.target.value)}
              className="text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              End Time (Optional)
            </label>
            <Input
              type="datetime-local"
              value={slotEndTime}
              onChange={(e) => setSlotEndTime(e.target.value)}
              className="text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Timezone</label>
            <Input
              value={slotTimezone}
              onChange={(e) => setSlotTimezone(e.target.value)}
              className="text-xs font-mono"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddSlotOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={actionLoading || !slotStartTime}
              className="bg-sky-600 hover:bg-sky-700 text-white"
            >
              Add Slot
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 2: Transition State */}
      <Modal
        isOpen={transitionModalOpen}
        onClose={() => setTransitionModalOpen(false)}
        title="Transition Workflow State"
        description="Move viewing to the next validated state in the core workflow."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Target Status</label>
            <select
              value={targetStatus}
              onChange={(e) => setTargetStatus(e.target.value as ViewingStatus)}
              className="w-full text-xs rounded-lg border border-slate-300 p-2"
            >
              <option value="AWAITING_AGENT_AVAILABILITY">AWAITING_AGENT_AVAILABILITY</option>
              <option value="AWAITING_TENANT_AVAILABILITY">AWAITING_TENANT_AVAILABILITY</option>
              <option value="SLOTS_AVAILABLE">SLOTS_AVAILABLE</option>
              <option value="SLOT_PROPOSED">SLOT_PROPOSED</option>
              <option value="AWAITING_TENANT_CONFIRMATION">AWAITING_TENANT_CONFIRMATION</option>
              <option value="AWAITING_AGENT_CONFIRMATION">AWAITING_AGENT_CONFIRMATION</option>
              <option value="CONFIRMED">CONFIRMED</option>
              <option value="RESCHEDULE_REQUESTED">RESCHEDULE_REQUESTED</option>
              <option value="NEEDS_HUMAN_REVIEW">NEEDS_HUMAN_REVIEW</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Transition Reason / Context
            </label>
            <Input
              value={transitionReason}
              onChange={(e) => setTransitionReason(e.target.value)}
              placeholder="e.g. Verified with agent on phone"
              className="text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTransitionModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={actionLoading}
              onClick={handleTransition}
              className="bg-sky-600 hover:bg-sky-700 text-white"
            >
              Confirm Transition
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 3: Cancel Viewing (Phase 6) */}
      <Modal
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title="Cancel Viewing"
        description="Cancel this viewing workflow. All future reminders will be cancelled and relevant parties notified."
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Cancelled By *
              </label>
              <select
                value={cancelParty}
                onChange={(e) => setCancelParty(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-300 p-2"
              >
                <option value="TENANT">Tenant</option>
                <option value="PROPERTY_AGENT">Property Agent</option>
                <option value="HUMAN_OPERATOR">Human Operator</option>
                <option value="SYSTEM">System</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Reason Code *
              </label>
              <select
                value={cancelReasonCode}
                onChange={(e) => setCancelReasonCode(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-300 p-2"
              >
                <option value="TENANT_REQUEST">Tenant Request</option>
                <option value="AGENT_REQUEST">Agent Request</option>
                <option value="PROPERTY_UNAVAILABLE">Property Unavailable</option>
                <option value="SCHEDULING_CONFLICT">Scheduling Conflict</option>
                <option value="DUPLICATE_BOOKING">Duplicate Booking</option>
                <option value="OPERATOR_ACTION">Operator Action</option>
                <option value="OTHER">Other Reason</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Cancellation Reason Notes *
            </label>
            <textarea
              required
              rows={3}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="e.g. Tenant requested cancellation; found alternate property"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCancelModalOpen(false)}
            >
              Back
            </Button>
            <Button
              size="sm"
              disabled={actionLoading || !cancelReason.trim()}
              onClick={handleCancel}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              Confirm Cancellation
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 4: Complete Viewing */}
      <Modal
        isOpen={completeModalOpen}
        onClose={() => setCompleteModalOpen(false)}
        title="Complete Viewing"
        description="Mark that this viewing has successfully taken place."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Outcome Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={completeNotes}
              onChange={(e) => setCompleteNotes(e.target.value)}
              placeholder="e.g. Tenant attended viewing on time with agent"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCompleteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={actionLoading}
              onClick={handleComplete}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Mark Completed
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 5: Record No-Show */}
      <Modal
        isOpen={noShowModalOpen}
        onClose={() => setNoShowModalOpen(false)}
        title="Record Viewing No-Show"
        description="Record that a party failed to attend the confirmed viewing."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              No-Show Party *
            </label>
            <select
              value={noShowActor}
              onChange={(e) => setNoShowActor(e.target.value as "TENANT" | "PROPERTY_AGENT")}
              className="w-full text-xs rounded-lg border border-slate-300 p-2"
            >
              <option value="TENANT">Tenant</option>
              <option value="PROPERTY_AGENT">Property Agent</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Notes
            </label>
            <textarea
              rows={3}
              value={noShowNotes}
              onChange={(e) => setNoShowNotes(e.target.value)}
              placeholder="e.g. Tenant did not arrive at guardhouse, phone unanswered"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setNoShowModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={actionLoading}
              onClick={handleNoShow}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              Record No-Show
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 6: Record Manual Tenant Availability */}
      <Modal
        isOpen={manualModalOpen}
        onClose={() => setManualModalOpen(false)}
        title="Record Tenant Availability Manually"
        description="Enter viewing availability windows provided by tenant via phone call or direct chat."
      >
        <form onSubmit={handleManualAvailability} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Window Start Time *
              </label>
              <Input
                type="datetime-local"
                value={manualStart}
                onChange={(e) => setManualStart(e.target.value)}
                required
                className="text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Window End Time *
              </label>
              <Input
                type="datetime-local"
                value={manualEnd}
                onChange={(e) => setManualEnd(e.target.value)}
                required
                className="text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Operator Notes
            </label>
            <textarea
              rows={2}
              value={manualNotes}
              onChange={(e) => setManualNotes(e.target.value)}
              placeholder="e.g. Tenant phoned in, available Saturday afternoon"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setManualModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={actionLoading || !manualStart || !manualEnd}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Save Tenant Availability
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 7: Manual Confirmation Modal (Phase 5) */}
      <Modal
        isOpen={manualConfirmModalOpen}
        onClose={() => setManualConfirmModalOpen(false)}
        title={`Record Manual Confirmation (${manualConfirmParty === "TENANT" ? "Tenant" : "Property Agent"})`}
        description="Record confirmation obtained outside the automated WhatsApp channel (e.g., via phone call)."
      >
        <form onSubmit={handleManualConfirmSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Confirmation Reason / Notes *
            </label>
            <textarea
              rows={3}
              value={manualConfirmReason}
              onChange={(e) => setManualConfirmReason(e.target.value)}
              placeholder="e.g. Confirmed verbally via phone call with operator"
              required
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setManualConfirmModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={actionLoading || !manualConfirmReason.trim()}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Confirm on Behalf of {manualConfirmParty === "TENANT" ? "Tenant" : "Agent"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 8: Decline Modal (Phase 5) */}
      <Modal
        isOpen={declineModalOpen}
        onClose={() => setDeclineModalOpen(false)}
        title={`Record Slot Decline (${declineParty === "TENANT" ? "Tenant" : "Property Agent"})`}
        description="Record that a party has declined the proposed viewing slot."
      >
        <form onSubmit={handleDeclineSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Decline Reason *
            </label>
            <textarea
              rows={3}
              value={declineReason}
              onChange={(e) => setDeclineReason(e.target.value)}
              placeholder="e.g. Schedule clash, requested weekend slot instead"
              required
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:border-rose-500 focus:ring-1 focus:ring-rose-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setDeclineModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={actionLoading || !declineReason.trim()}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              Record Decline
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 9: Request Reschedule (Phase 6) */}
      <Modal
        isOpen={rescheduleModalOpen}
        onClose={() => setRescheduleModalOpen(false)}
        title="Request Viewing Reschedule"
        description="Re-open viewing scheduling safely. Existing booking slot will be released and preserved in history."
      >
        <form onSubmit={handleRescheduleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Requested By *
            </label>
            <select
              value={rescheduleRequester}
              onChange={(e) => setRescheduleRequester(e.target.value as any)}
              className="w-full text-xs rounded-lg border border-slate-300 p-2"
            >
              <option value="TENANT">Tenant</option>
              <option value="PROPERTY_AGENT">Property Agent</option>
              <option value="HUMAN_OPERATOR">Human Operator</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Reschedule Reason (Optional)
            </label>
            <textarea
              rows={3}
              value={rescheduleReason}
              onChange={(e) => setRescheduleReason(e.target.value)}
              placeholder="e.g. Tenant requested moving to weekend afternoon due to work schedule"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-2xs text-amber-800 space-y-1">
            <div className="font-semibold flex items-center gap-1">
              <CalendarClock className="w-3.5 h-3.5" />
              Automated Operations Note
            </div>
            <div>
              Current slot will be preserved in Schedule Version {viewing.schedule_version || 1}.
              Stale reminders will be cancelled, and viewing status will transition to RESCHEDULE_REQUESTED.
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRescheduleModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={actionLoading}
              className="bg-amber-600 hover:bg-amber-700 text-white font-medium"
            >
              Confirm Reschedule Request
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
