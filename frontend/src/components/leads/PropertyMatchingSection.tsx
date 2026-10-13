"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Building2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  RotateCcw,
  ShieldCheck,
  ChevronRight,
  Filter,
  DollarSign,
  Home,
  Calendar,
  Layers,
  Info,
  Award,
  Sparkles,
  Sliders,
  Clock,
  Send,
  MessageSquare,
  Users,
  CheckCheck,
  Eye,
  ShieldAlert,
  ArrowUp,
  ArrowDown,
  Trash2,
  Columns,
  Search,
  FileText,
  Check,
  HelpCircle,
  ExternalLink,
  Copy,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  PropertyMatch,
  PropertyMatchingRun,
  PropertyMatchStatus,
  PropertyAgentOutreach,
  OutreachMessagePreview,
  BulkAgentOutreachRunResponse,
  PropertyAgentConversationDetail,
  PropertyAvailabilityVerification,
  PropertyAgentFollowUp,
  FallbackPreviewResponse,
  ExecuteFallbackResponse,
  PropertyShortlist,
  PropertyShortlistItem,
  PropertyMatchingDashboardResponse,
  CandidateDetailItem,
  Module5HandoffPayload,
  CandidateComparisonItem,
} from "@/types";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";

interface PropertyMatchingSectionProps {
  leadId: string;
  qualificationStatus?: string;
  onRefreshLead?: () => void;
}

export function PropertyMatchingSection({
  leadId,
  qualificationStatus,
  onRefreshLead,
}: PropertyMatchingSectionProps) {
  const [runs, setRuns] = useState<PropertyMatchingRun[]>([]);
  const [matches, setMatches] = useState<PropertyMatch[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [scoring, setScoring] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    | "VERIFIED"
    | "READY_FOR_OUTREACH"
    | "AWAITING_AGENT"
    | "UNRESPONSIVE"
    | "SCORED"
    | "BELOW_THRESHOLD"
    | "ELIGIBLE"
    | "FILTERED_OUT"
    | "NEEDS_REVIEW"
    | "ALL"
  >("READY_FOR_OUTREACH");

  // Manual Override / Forward Modal
  const [overrideModalOpen, setOverrideModalOpen] = useState<boolean>(false);
  const [selectedMatch, setSelectedMatch] = useState<PropertyMatch | null>(null);
  const [overrideStatus, setOverrideStatus] = useState<PropertyMatchStatus>("READY_FOR_AGENT_VERIFICATION");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [overrideSubmitting, setOverrideSubmitting] = useState<boolean>(false);

  // Mark Stale Modal
  const [staleModalOpen, setStaleModalOpen] = useState<boolean>(false);
  const [staleMatch, setStaleMatch] = useState<PropertyMatch | null>(null);
  const [staleReason, setStaleReason] = useState<string>("");
  const [staleSubmitting, setStaleSubmitting] = useState<boolean>(false);

  // Score Breakdown Detail Modal
  const [breakdownModalOpen, setBreakdownModalOpen] = useState<boolean>(false);
  const [inspectedMatch, setInspectedMatch] = useState<PropertyMatch | null>(null);

  // Phase 5: Outreach Message Preview & Send Modal
  const [previewModalOpen, setPreviewModalOpen] = useState<boolean>(false);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<OutreachMessagePreview | null>(null);
  const [previewMatch, setPreviewMatch] = useState<PropertyMatch | null>(null);
  const [sendingOutreach, setSendingOutreach] = useState<boolean>(false);

  // Phase 5: Bulk Outreach Modal
  const [bulkModalOpen, setBulkModalOpen] = useState<boolean>(false);
  const [bulkSubmitting, setBulkSubmitting] = useState<boolean>(false);
  const [bulkResult, setBulkResult] = useState<BulkAgentOutreachRunResponse | null>(null);

  // Phase 5: Agent Conversation Thread Modal
  const [convModalOpen, setConvModalOpen] = useState<boolean>(false);
  const [convLoading, setConvLoading] = useState<boolean>(false);
  const [convDetail, setConvDetail] = useState<PropertyAgentConversationDetail | null>(null);
  const [convOutreaches, setConvOutreaches] = useState<PropertyAgentOutreach[]>([]);

  // Phase 6: Verification History Modal
  const [historyModalOpen, setHistoryModalOpen] = useState<boolean>(false);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyRecords, setHistoryRecords] = useState<PropertyAvailabilityVerification[]>([]);
  const [historyMatch, setHistoryMatch] = useState<PropertyMatch | null>(null);

  // Phase 6: Manual Availability Override Modal
  const [manualAvailModalOpen, setManualAvailModalOpen] = useState<boolean>(false);
  const [manualAvailMatch, setManualAvailMatch] = useState<PropertyMatch | null>(null);
  const [manualAvailStatus, setManualAvailStatus] = useState<string>("AVAILABLE");
  const [manualAvailPrice, setManualAvailPrice] = useState<string>("");
  const [manualAvailDate, setManualAvailDate] = useState<string>("");
  const [manualAvailLease, setManualAvailLease] = useState<string>("");
  const [manualAvailReason, setManualAvailReason] = useState<string>("");
  const [manualAvailSubmitting, setManualAvailSubmitting] = useState<boolean>(false);

  // Phase 7: Fallback Strategy Modal
  const [fallbackModalOpen, setFallbackModalOpen] = useState<boolean>(false);
  const [fallbackLoading, setFallbackLoading] = useState<boolean>(false);
  const [fallbackMatch, setFallbackMatch] = useState<PropertyMatch | null>(null);
  const [fallbackPreview, setFallbackPreview] = useState<FallbackPreviewResponse | null>(null);
  const [fallbackExecuting, setFallbackExecuting] = useState<boolean>(false);

  // Phase 7: Follow-up Tasks Modal
  const [followupsModalOpen, setFollowupsModalOpen] = useState<boolean>(false);
  const [followupsLoading, setFollowupsLoading] = useState<boolean>(false);
  const [followupsMatch, setFollowupsMatch] = useState<PropertyMatch | null>(null);
  const [followupTasks, setFollowupTasks] = useState<PropertyAgentFollowUp[]>([]);
  const [followupActionLoading, setFollowupActionLoading] = useState<boolean>(false);

  // Phase 8/10: Shortlist & Dashboard State
  const [dashboardData, setDashboardData] = useState<PropertyMatchingDashboardResponse | null>(null);
  const [shortlist, setShortlist] = useState<PropertyShortlist | null>(null);
  const [buildShortlistLoading, setBuildShortlistLoading] = useState<boolean>(false);
  const [refreshShortlistLoading, setRefreshShortlistLoading] = useState<boolean>(false);

  // Phase 10: Module 5 Handoff Contract Modal
  const [handoffModalOpen, setHandoffModalOpen] = useState<boolean>(false);
  const [handoffLoading, setHandoffLoading] = useState<boolean>(false);
  const [handoffPayload, setHandoffPayload] = useState<Module5HandoffPayload | null>(null);
  const [handoffCopied, setHandoffCopied] = useState<boolean>(false);

  // Phase 10: Side-by-Side Comparison Modal
  const [compareModalOpen, setCompareModalOpen] = useState<boolean>(false);
  const [selectedCompareIds, setSelectedCompareIds] = useState<string[]>([]);

  // Phase 10: Tenant Requirement Comparison Modal
  const [tenantCompareModalOpen, setTenantCompareModalOpen] = useState<boolean>(false);
  const [inspectedCandidate, setInspectedCandidate] = useState<CandidateDetailItem | null>(null);

  // Phase 10: Search, Filter & Sort on Candidate Table
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sortField, setSortField] = useState<"rank" | "score" | "price">("rank");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const isQualified = qualificationStatus === "QUALIFIED";

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [runsData, matchesData, dashData] = await Promise.all([
        api.listPropertyMatchingRuns(leadId),
        api.listPropertyMatches(leadId, { limit: 100 }),
        api.getPropertyMatchingDashboard(leadId).catch(() => null),
      ]);
      setRuns(runsData);
      setMatches(matchesData);
      setDashboardData(dashData);
      if (dashData && dashData.shortlist) {
        setShortlist(dashData.shortlist);
      }
    } catch (err: any) {
      console.error("Error loading property matching data:", err);
      setError(err.message || "Failed to load matching candidates.");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Phase 3 Candidate Search & Hard Filters
  const handleRunCandidateSearch = async () => {
    if (!isQualified) {
      alert("Tenant must be in QUALIFIED status before running candidate property search.");
      return;
    }
    try {
      setRunning(true);
      setError(null);
      await api.runPropertyMatching(leadId);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      console.error("Candidate search failed:", err);
      setError(err.message || "Failed to search candidates.");
    } finally {
      setRunning(false);
    }
  };

  // Phase 4 Scoring & Ranking
  const handleScoreCandidates = async () => {
    if (!isQualified) {
      alert("Tenant must be in QUALIFIED status before scoring candidate properties.");
      return;
    }
    try {
      setScoring(true);
      setError(null);
      await api.scorePropertyMatches(leadId);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      console.error("Scoring failed:", err);
      setError(err.message || "Failed to score candidates.");
    } finally {
      setScoring(false);
    }
  };

  const handleOpenOverride = (match: PropertyMatch) => {
    setSelectedMatch(match);
    setOverrideStatus("READY_FOR_AGENT_VERIFICATION");
    setOverrideReason("");
    setOverrideModalOpen(true);
  };

  const handleSubmitOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMatch || !overrideReason.trim()) return;

    try {
      setOverrideSubmitting(true);
      await api.overridePropertyMatch(selectedMatch.id, {
        target_status: overrideStatus,
        reason: overrideReason.trim(),
      });
      setOverrideModalOpen(false);
      setSelectedMatch(null);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to apply manual override.");
    } finally {
      setOverrideSubmitting(false);
    }
  };

  const handleOpenStale = (match: PropertyMatch) => {
    setStaleMatch(match);
    setStaleReason("Property listing price or availability updated in source feed");
    setStaleModalOpen(true);
  };

  const handleSubmitStale = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!staleMatch || !staleReason.trim()) return;

    try {
      setStaleSubmitting(true);
      await api.markPropertyMatchStale(staleMatch.id, staleReason.trim());
      setStaleModalOpen(false);
      setStaleMatch(null);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to mark match as stale.");
    } finally {
      setStaleSubmitting(false);
    }
  };

  // Phase 5: Open Message Preview
  const handleOpenPreview = async (match: PropertyMatch) => {
    try {
      setPreviewMatch(match);
      setPreviewLoading(true);
      setPreviewModalOpen(true);
      const preview = await api.previewAgentOutreach(match.id);
      setPreviewData(preview);
    } catch (err: any) {
      alert(err.message || "Failed to generate outreach preview.");
      setPreviewModalOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Phase 5: Confirm and Send Outreach
  const handleSendSingleOutreach = async () => {
    if (!previewMatch) return;
    try {
      setSendingOutreach(true);
      await api.sendAgentOutreach(previewMatch.id, {
        manual_reason: previewMatch.manual_override ? "Manual operator forward override" : undefined,
      });
      setPreviewModalOpen(false);
      setPreviewMatch(null);
      setPreviewData(null);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      alert(err.message || "Failed to dispatch agent outreach.");
    } finally {
      setSendingOutreach(false);
    }
  };

  // Phase 5: Bulk Verify Top Candidates
  const handleRunBulkVerify = async () => {
    try {
      setBulkSubmitting(true);
      const res = await api.runBulkAgentOutreach(leadId);
      setBulkResult(res);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      alert(err.message || "Failed to execute bulk outreach.");
    } finally {
      setBulkSubmitting(false);
    }
  };

  // Phase 5: View Conversation / Outreach Detail
  const handleViewConversation = async (match: PropertyMatch) => {
    try {
      setConvLoading(true);
      setConvModalOpen(true);
      setConvDetail(null);
      const history = await api.getMatchOutreachHistory(match.id);
      setConvOutreaches(history);

      if (history.length > 0 && history[0].conversation_id) {
        const detail = await api.getPropertyAgentConversation(history[0].conversation_id);
        setConvDetail(detail);
      }
    } catch (err: any) {
      console.error("Failed to load conversation details:", err);
    } finally {
      setConvLoading(false);
    }
  };

  const handleOpenHistory = async (m: PropertyMatch) => {
    setHistoryMatch(m);
    setHistoryModalOpen(true);
    setHistoryLoading(true);
    try {
      const records = await api.getPropertyMatchVerificationHistory(m.id);
      setHistoryRecords(records);
    } catch (err: any) {
      console.error("Failed to load verification history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleOpenManualAvail = (m: PropertyMatch) => {
    setManualAvailMatch(m);
    setManualAvailStatus(m.match_status === "UNAVAILABLE" ? "UNAVAILABLE" : m.match_status === "CONDITIONAL" ? "CONDITIONAL" : "AVAILABLE");
    setManualAvailPrice(m.listing_data?.asking_price ? String(m.listing_data.asking_price) : "");
    setManualAvailDate(m.listing_data?.available_from || "");
    setManualAvailLease("");
    setManualAvailReason("");
    setManualAvailModalOpen(true);
  };

  const handleSubmitManualAvail = async () => {
    if (!manualAvailMatch) return;
    if (!manualAvailReason || manualAvailReason.trim().length < 3) {
      alert("Please provide a valid operator reason (min 3 characters).");
      return;
    }
    setManualAvailSubmitting(true);
    try {
      await api.overridePropertyMatchAvailability(manualAvailMatch.id, {
        availability_status: manualAvailStatus,
        asking_price: manualAvailPrice ? Number(manualAvailPrice) : null,
        available_from: manualAvailDate || null,
        minimum_lease_months: manualAvailLease ? Number(manualAvailLease) : null,
        reason: manualAvailReason,
      });
      setManualAvailModalOpen(false);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to update availability verification.");
    } finally {
      setManualAvailSubmitting(false);
    }
  };

  // Phase 7 Handlers
  const handleOpenFallback = async (m: PropertyMatch) => {
    setFallbackMatch(m);
    setFallbackPreview(null);
    setFallbackModalOpen(true);
    setFallbackLoading(true);
    try {
      const prev = await api.getFallbackPreview(m.id);
      setFallbackPreview(prev);
    } catch (err: any) {
      console.error("Failed to load fallback preview:", err);
    } finally {
      setFallbackLoading(false);
    }
  };

  const handleExecuteFallback = async () => {
    if (!fallbackMatch) return;
    setFallbackExecuting(true);
    try {
      await api.executeFallback(fallbackMatch.id);
      setFallbackModalOpen(false);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to execute fallback strategy.");
    } finally {
      setFallbackExecuting(false);
    }
  };

  const handleOpenFollowups = async (m: PropertyMatch) => {
    setFollowupsMatch(m);
    setFollowupTasks([]);
    setFollowupsModalOpen(true);
    setFollowupsLoading(true);
    try {
      const tasks = await api.getPropertyMatchFollowUps(m.id);
      setFollowupTasks(tasks);
    } catch (err: any) {
      console.error("Failed to load follow-up tasks:", err);
    } finally {
      setFollowupsLoading(false);
    }
  };

  const handleSendManualFollowup = async (outreachId: string) => {
    setFollowupActionLoading(true);
    try {
      await api.sendManualPropertyAgentFollowUp(outreachId, "Operator sent manual follow-up");
      if (followupsMatch) {
        const tasks = await api.getPropertyMatchFollowUps(followupsMatch.id);
        setFollowupTasks(tasks);
      }
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to send manual follow-up.");
    } finally {
      setFollowupActionLoading(false);
    }
  };

  const handleCancelFollowup = async (followupId: string) => {
    setFollowupActionLoading(true);
    try {
      await api.cancelPropertyAgentFollowUp(followupId, "Operator cancelled task");
      if (followupsMatch) {
        const tasks = await api.getPropertyMatchFollowUps(followupsMatch.id);
        setFollowupTasks(tasks);
      }
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to cancel follow-up task.");
    } finally {
      setFollowupActionLoading(false);
    }
  };

  // Phase 8/10 Shortlist Actions
  const handleBuildShortlist = async () => {
    if (!isQualified) {
      alert("Tenant must be in QUALIFIED status before generating property shortlist.");
      return;
    }
    try {
      setBuildShortlistLoading(true);
      const res = await api.buildPropertyShortlist(leadId);
      setShortlist(res);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      alert(err.message || "Failed to generate shortlist.");
    } finally {
      setBuildShortlistLoading(false);
    }
  };

  const handleRefreshShortlist = async () => {
    try {
      setRefreshShortlistLoading(true);
      const res = await api.refreshPropertyShortlist(leadId);
      setShortlist(res);
      await loadData();
      if (onRefreshLead) onRefreshLead();
    } catch (err: any) {
      alert(err.message || "Failed to refresh shortlist.");
    } finally {
      setRefreshShortlistLoading(false);
    }
  };

  const handleRemoveShortlistItem = async (matchId: string) => {
    if (!shortlist) return;
    if (!confirm("Are you sure you want to remove this candidate from the verified shortlist?")) return;
    try {
      const updated = await api.removeShortlistItem(shortlist.id, matchId);
      setShortlist(updated);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to remove candidate from shortlist.");
    }
  };

  const handleMoveShortlistItem = async (matchId: string, direction: "up" | "down") => {
    if (!shortlist || !shortlist.items || shortlist.items.length <= 1) return;
    const items = [...shortlist.items].sort((a, b) => a.position - b.position);
    const index = items.findIndex((it) => it.property_match_id === matchId);
    if (index === -1) return;
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === items.length - 1) return;

    const targetIndex = direction === "up" ? index - 1 : index + 1;
    const temp = items[index];
    items[index] = items[targetIndex];
    items[targetIndex] = temp;

    const reorderedPayload = items.map((it, idx) => ({
      property_match_id: it.property_match_id,
      position: idx + 1,
    }));

    try {
      const updated = await api.reorderShortlist(shortlist.id, reorderedPayload);
      setShortlist(updated);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to reorder shortlist items.");
    }
  };

  const handleOpenModule5Handoff = async () => {
    try {
      setHandoffLoading(true);
      setHandoffModalOpen(true);
      setHandoffCopied(false);
      const payload = await api.getModule5Handoff(leadId);
      setHandoffPayload(payload);
    } catch (err: any) {
      alert(err.message || "Failed to generate Module 5 handoff payload.");
      setHandoffModalOpen(false);
    } finally {
      setHandoffLoading(false);
    }
  };

  const handleToggleCompare = (matchId: string) => {
    setSelectedCompareIds((prev) =>
      prev.includes(matchId) ? prev.filter((id) => id !== matchId) : [...prev, matchId]
    );
  };


  const latestRun = runs.length > 0 ? runs[0] : null;

  const verifiedMatches = matches.filter(
    (m) =>
      m.match_status === "AVAILABLE" ||
      m.match_status === "VERIFIED_CANDIDATE" ||
      m.match_status === "CONDITIONAL" ||
      m.availability_status === "AVAILABLE"
  );
  const readyForOutreachMatches = matches.filter(
    (m) => m.match_status === "READY_FOR_AGENT_VERIFICATION"
  );
  const awaitingAgentMatches = matches.filter(
    (m) => m.match_status === "AWAITING_AGENT"
  );
  const scoredMatches = matches.filter(
    (m) =>
      m.match_status === "SCORED" ||
      m.match_status === "READY_FOR_AGENT_VERIFICATION" ||
      m.match_status === "AWAITING_AGENT" ||
      m.match_status === "AVAILABLE" ||
      m.match_status === "CONDITIONAL"
  );
  const belowThresholdMatches = matches.filter(
    (m) => m.match_status === "BELOW_OUTREACH_THRESHOLD"
  );
  const eligibleMatches = matches.filter(
    (m) => m.match_status === "ELIGIBLE_FOR_SCORING" || m.hard_filter_passed === true
  );
  const filteredMatches = matches.filter(
    (m) => m.match_status === "FILTERED_OUT"
  );
  const needsReviewMatches = matches.filter(
    (m) => m.match_status === "NEEDS_REVIEW"
  );
  const unresponsiveMatches = matches.filter(
    (m) => m.match_status === "AGENT_UNRESPONSIVE" || (m as any).agent_verification_status === "UNRESPONSIVE"
  );

  const tabFilteredMatches =
    activeTab === "VERIFIED"
      ? verifiedMatches
      : activeTab === "READY_FOR_OUTREACH"
      ? readyForOutreachMatches
      : activeTab === "AWAITING_AGENT"
      ? awaitingAgentMatches
      : activeTab === "UNRESPONSIVE"
      ? unresponsiveMatches
      : activeTab === "SCORED"
      ? scoredMatches
      : activeTab === "BELOW_THRESHOLD"
      ? belowThresholdMatches
      : activeTab === "ELIGIBLE"
      ? eligibleMatches
      : activeTab === "FILTERED_OUT"
      ? filteredMatches
      : activeTab === "NEEDS_REVIEW"
      ? needsReviewMatches
      : matches;

  const displayedMatches = useMemo(() => {
    let list = [...tabFilteredMatches];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((m) => {
        const pName = m.property_data?.canonical_name?.toLowerCase() || "";
        const pDist = m.property_data?.district?.toLowerCase() || "";
        const aName = (m as any).agent_name?.toLowerCase() || "";
        return pName.includes(q) || pDist.includes(q) || aName.includes(q);
      });
    }
    if (sortField === "rank") {
      list.sort((a, b) => (a.rank || 999) - (b.rank || 999));
    } else if (sortField === "score") {
      list.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
    } else if (sortField === "price") {
      list.sort((a, b) => {
        const pa = a.listing_data?.asking_price || 0;
        const pb = b.listing_data?.asking_price || 0;
        return pa - pb;
      });
    }
    return list;
  }, [tabFilteredMatches, searchQuery, sortField]);

  return (
    <Card className="border border-slate-200 shadow-xs overflow-hidden">
      <CardHeader className="bg-slate-50/70 border-b border-slate-200/80 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-indigo-600" />
              <CardTitle className="text-base font-bold text-slate-900">
                Property Candidate Matching & Shortlist Dashboard
              </CardTitle>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                Module 4 Phase 10 — Production Hardened
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Deterministic scoring, agent outreach via WhatsApp, verified availability, operator shortlist curation, and Module 5 handoff.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRunCandidateSearch}
              disabled={!isQualified || running || scoring}
              isLoading={running}
              className="text-xs gap-1 font-semibold border-slate-300"
            >
              <Play className="w-3.5 h-3.5" />
              1. Search Inventory
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleScoreCandidates}
              disabled={!isQualified || running || scoring || eligibleMatches.length === 0}
              isLoading={scoring}
              className="text-xs gap-1.5 font-semibold text-emerald-700 border-emerald-300 hover:bg-emerald-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              2. Score & Rank
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setBulkResult(null);
                setBulkModalOpen(true);
              }}
              disabled={!isQualified || running || scoring || readyForOutreachMatches.length === 0}
              className="text-xs gap-1.5 font-semibold text-indigo-700 border-indigo-300 hover:bg-indigo-50"
            >
              <Send className="w-3.5 h-3.5" />
              3. Verify Top Candidates ({readyForOutreachMatches.length})
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={handleBuildShortlist}
              disabled={!isQualified || buildShortlistLoading || verifiedMatches.length === 0}
              isLoading={buildShortlistLoading}
              className="text-xs gap-1.5 font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs"
            >
              <Award className="w-3.5 h-3.5" />
              4. Generate Shortlist ({verifiedMatches.length})
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenModule5Handoff}
              className="text-xs gap-1.5 font-semibold text-purple-700 border-purple-300 hover:bg-purple-50"
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-600" />
              Module 5 Handoff
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={loading}
              className="text-xs h-8 px-2.5 text-slate-600"
              title="Refresh results"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {dashboardData?.module5_ready && (
          <div className="mt-3 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 flex items-center justify-between gap-2 shadow-2xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                <strong>READY FOR MODULE 5 VIEWING COORDINATION:</strong> Tenant remains qualified and {shortlist?.items?.length || 0} verified candidate(s) are ready for viewing slot coordination.
              </span>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-600 text-white shrink-0">
              GATE PASSED
            </span>
          </div>
        )}

        {!isQualified && (
          <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
            <span>
              Tenant qualification status is currently <strong>{qualificationStatus || "NOT_STARTED"}</strong>.
              Automated property matching, outreach, and shortlisting are strictly gated to <strong>QUALIFIED</strong> leads.
            </span>
          </div>
        )}

        {error && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
            <XCircle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        {/* KPI Metric Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-center">
            <div className="text-xs font-medium text-slate-500">Inventory Evaluated</div>
            <div className="text-2xl font-bold text-slate-800 mt-1">
              {latestRun ? latestRun.total_inventory_considered : matches.length}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">Active Listings</div>
          </div>

          <div className="p-3.5 bg-emerald-50/80 rounded-xl border border-emerald-200 text-center">
            <div className="text-xs font-medium text-emerald-800 flex items-center justify-center gap-1">
              <Award className="w-3 h-3 text-emerald-600" />
              Ready for Outreach
            </div>
            <div className="text-2xl font-bold text-emerald-700 mt-1">
              {readyForOutreachMatches.length}
            </div>
            <div className="text-[10px] text-emerald-600 mt-0.5">Top-N Scored</div>
          </div>

          <div className="p-3.5 bg-indigo-50/80 rounded-xl border border-indigo-200 text-center">
            <div className="text-xs font-medium text-indigo-900 flex items-center justify-center gap-1">
              <Send className="w-3 h-3 text-indigo-600" />
              Awaiting Agent
            </div>
            <div className="text-2xl font-bold text-indigo-700 mt-1">
              {awaitingAgentMatches.length}
            </div>
            <div className="text-[10px] text-indigo-600 mt-0.5">Outreach Dispatched</div>
          </div>

          <div className="p-3.5 bg-amber-50/80 rounded-xl border border-amber-200 text-center">
            <div className="text-xs font-medium text-amber-800">Below Threshold</div>
            <div className="text-2xl font-bold text-amber-700 mt-1">
              {belowThresholdMatches.length}
            </div>
            <div className="text-[10px] text-amber-600 mt-0.5">Score &lt; 75.0</div>
          </div>

          <div className="col-span-2 md:col-span-1 p-3.5 bg-purple-50/60 rounded-xl border border-purple-200 text-center">
            <div className="text-xs font-medium text-purple-900">Top Match Score</div>
            <div className="text-2xl font-bold text-purple-700 mt-1">
              {latestRun?.top_score !== null && latestRun?.top_score !== undefined
                ? `${Number(latestRun.top_score).toFixed(1)}`
                : "—"}
            </div>
            <div className="text-[10px] text-purple-600 mt-0.5">Scale: 0 – 100</div>
          </div>
        </div>

        {/* PROMINENT SHORTLIST PANEL (Phase 8/10) */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-md border border-indigo-900/40 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-indigo-800/40 pb-3">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100">
                  Verified Property Shortlist (Tenant Ready)
                </h3>
                {shortlist?.status && (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase border ${
                      shortlist.status === "READY"
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                        : shortlist.status === "STALE"
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                        : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                    }`}
                  >
                    {shortlist.status}
                  </span>
                )}
                {shortlist?.version && (
                  <span className="text-[10px] text-indigo-300/80 font-mono">v{shortlist.version}</span>
                )}
              </div>
              <p className="text-[11px] text-slate-300">
                Top agent-verified units ranked deterministically. Free of hard-filter violations and stale pricing.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshShortlist}
                disabled={!shortlist || refreshShortlistLoading}
                isLoading={refreshShortlistLoading}
                className="text-xs h-8 border-indigo-700 bg-indigo-900/40 text-indigo-200 hover:bg-indigo-800/60"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Refresh Shortlist
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setCompareModalOpen(true)}
                disabled={!shortlist || !shortlist.items || shortlist.items.length < 2}
                className="text-xs h-8 border-indigo-700 bg-indigo-900/40 text-indigo-200 hover:bg-indigo-800/60"
              >
                <Columns className="w-3.5 h-3.5" />
                Compare Shortlisted
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={handleOpenModule5Handoff}
                className="text-xs h-8 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold shadow-xs"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Module 5 Handoff Preview
              </Button>
            </div>
          </div>

          {/* Shortlist Items Cards Grid */}
          {!shortlist || !shortlist.items || shortlist.items.length === 0 ? (
            <div className="py-6 text-center text-indigo-300/70 text-xs bg-indigo-950/30 rounded-xl border border-indigo-900/30">
              <Award className="w-8 h-8 mx-auto mb-2 text-indigo-400/40" />
              {verifiedMatches.length > 0 ? (
                <div>
                  <p className="font-semibold text-slate-200">
                    {verifiedMatches.length} candidate(s) verified available by agent.
                  </p>
                  <p className="text-[11px] mt-1 text-slate-400">
                    Click '4. Generate Shortlist' above to produce the official shortlist.
                  </p>
                </div>
              ) : (
                <p>No verified candidates yet. Complete agent outreach and confirmation first.</p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {shortlist.items.map((item) => {
                const hasLateWarning = item.warnings?.some((w) =>
                  w.includes("LATE") || w.includes("DELAY")
                );

                return (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-xl bg-slate-900/80 border border-indigo-800/60 hover:border-indigo-600 transition-all flex flex-col justify-between space-y-3"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded-full bg-amber-400 text-slate-950 font-bold text-[11px] flex items-center justify-center font-mono">
                            #{item.position}
                          </span>
                          <span className="font-bold text-xs text-white truncate max-w-[160px]">
                            {item.property_name || "Shortlisted Property"}
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                          Score: {item.score_at_selection ? Number(item.score_at_selection).toFixed(0) : "—"}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-300">
                        <div className="font-bold text-sm text-amber-300 font-mono">
                          SGD {Number(item.asking_price || 0).toLocaleString()} / mo
                        </div>
                        <div className="text-slate-400 mt-0.5">
                          {item.district || "District"} • {item.bedrooms || 2} Bed {item.property_type || "Condo"}
                        </div>
                      </div>

                      {/* Status Badges */}
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          {item.shortlist_status.replace(/_/g, " ")}
                        </span>
                        {item.agent_name && (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                            {item.agent_name} ({item.agent_agency || "Verified"})
                          </span>
                        )}
                      </div>

                      {/* Warnings Banner (Section 11) */}
                      {item.warnings && item.warnings.length > 0 && (
                        <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 flex items-start gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                          <span>
                            {hasLateWarning
                              ? "Move-in date is slightly later than tenant preference."
                              : item.warnings.join(", ")}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Actions Toolbar */}
                    <div className="flex items-center justify-between pt-2 border-t border-indigo-900/60">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleMoveShortlistItem(item.property_match_id, "up")}
                          disabled={item.position === 1}
                          className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
                          title="Move rank up"
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleMoveShortlistItem(item.property_match_id, "down")}
                          disabled={item.position === shortlist.items.length}
                          className="p-1 rounded text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
                          title="Move rank down"
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => {
                            const cDetail = dashboardData?.candidates.find(
                              (c) => c.property_match_id === item.property_match_id
                            );
                            if (cDetail) {
                              setInspectedCandidate(cDetail);
                              setTenantCompareModalOpen(true);
                            }
                          }}
                          className="px-2 py-1 rounded text-[10px] bg-indigo-900/60 text-indigo-200 hover:bg-indigo-800 transition-colors font-medium"
                        >
                          Verify Match
                        </button>
                        <button
                          onClick={() => handleRemoveShortlistItem(item.property_match_id)}
                          className="p-1 rounded text-rose-400 hover:text-rose-300 transition-colors"
                          title="Remove from shortlist"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Tab Filter Switcher */}
        <div className="flex flex-wrap items-center justify-between border-b border-slate-200 pb-2 gap-2">
          <div className="flex flex-wrap items-center gap-1">
            <button
              onClick={() => setActiveTab("VERIFIED")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "VERIFIED"
                  ? "bg-emerald-600 text-white font-bold shadow-xs"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-200" />
              Verified Available ({verifiedMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("READY_FOR_OUTREACH")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "READY_FOR_OUTREACH"
                  ? "bg-emerald-100 text-emerald-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Award className="w-3.5 h-3.5 text-emerald-600" />
              Ready for Verification ({readyForOutreachMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("AWAITING_AGENT")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "AWAITING_AGENT"
                  ? "bg-indigo-100 text-indigo-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Send className="w-3.5 h-3.5 text-indigo-600" />
              Awaiting Agent ({awaitingAgentMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("UNRESPONSIVE")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "UNRESPONSIVE"
                  ? "bg-rose-100 text-rose-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              Unresponsive ({unresponsiveMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("SCORED")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "SCORED"
                  ? "bg-slate-200 text-slate-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All Scored ({scoredMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("NEEDS_REVIEW")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "NEEDS_REVIEW"
                  ? "bg-amber-500 text-white font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-200" />
              Human Review Issues ({needsReviewMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("BELOW_THRESHOLD")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "BELOW_THRESHOLD"
                  ? "bg-amber-100 text-amber-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Below Threshold ({belowThresholdMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("FILTERED_OUT")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "FILTERED_OUT"
                  ? "bg-rose-100 text-rose-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <XCircle className="w-3.5 h-3.5 text-rose-600" />
              Filtered Out ({filteredMatches.length})
            </button>
            <button
              onClick={() => setActiveTab("ALL")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === "ALL"
                  ? "bg-slate-200 text-slate-800 font-bold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All Records ({matches.length})
            </button>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search candidates..."
                className="pl-8 pr-2.5 py-1 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500 w-36 sm:w-48"
              />
            </div>
            <select
              value={sortField}
              onChange={(e: any) => setSortField(e.target.value)}
              className="text-xs bg-white border border-slate-300 rounded-lg px-2 py-1 text-slate-700"
              aria-label="Sort candidates"
            >
              <option value="rank">Sort: System Rank</option>
              <option value="score">Sort: Match Score</option>
              <option value="price">Sort: Asking Price</option>
            </select>
          </div>
        </div>

        {/* Candidate List / Cards */}
        {displayedMatches.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs">
            <Building2 className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            {matches.length === 0
              ? isQualified
                ? "No matching runs executed yet. Click '1. Search Inventory' to generate candidate set."
                : "Tenant must be QUALIFIED before running property matching."
              : `No candidates in '${activeTab.replace(/_/g, " ")}' category.`}
          </div>
        ) : (
          <div className="space-y-3">
            {displayedMatches.map((m) => {
              const p = m.property_data;
              const l = m.listing_data;
              const b = m.score_breakdown;

              return (
                <div
                  key={m.id}
                  className={`p-4 rounded-xl border transition-all ${
                    m.is_stale
                      ? "bg-amber-50/40 border-amber-300"
                      : m.match_status === "AWAITING_AGENT"
                      ? "bg-indigo-50/30 border-indigo-300 shadow-xs"
                      : m.match_status === "READY_FOR_AGENT_VERIFICATION"
                      ? "bg-white border-emerald-300 shadow-xs hover:border-emerald-400"
                      : "bg-white border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {m.rank !== null && m.rank !== undefined && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-slate-900 text-white font-mono">
                            #{m.rank}
                          </span>
                        )}

                        <span className="font-bold text-sm text-slate-900">
                          {p?.canonical_name || "Property Candidate"}
                        </span>

                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                            m.match_status === "AVAILABLE" || m.match_status === "VERIFIED_CANDIDATE"
                              ? "bg-emerald-600 text-white border border-emerald-700 shadow-xs"
                              : m.match_status === "UNAVAILABLE"
                              ? "bg-rose-600 text-white border border-rose-700"
                              : m.match_status === "CONDITIONAL"
                              ? "bg-purple-100 text-purple-900 border border-purple-300 font-bold"
                              : m.match_status === "AWAITING_AGENT"
                              ? "bg-indigo-100 text-indigo-800 border border-indigo-200"
                              : m.match_status === "READY_FOR_AGENT_VERIFICATION"
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                              : m.match_status === "BELOW_OUTREACH_THRESHOLD"
                              ? "bg-amber-100 text-amber-800 border border-amber-200"
                              : m.match_status === "FILTERED_OUT"
                              ? "bg-rose-100 text-rose-800 border border-rose-200"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {m.match_status === "AVAILABLE" ? "AVAILABLE (AGENT CONFIRMED)" : m.match_status.replace(/_/g, " ")}
                        </span>

                        {m.agent_verification_status === "INCOMPATIBLE_WITH_TENANT" ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-100 text-rose-900 font-bold border border-rose-300">
                            AVAILABLE, BUT NO LONGER MATCHES TENANT REQUIREMENTS
                          </span>
                        ) : m.agent_verification_status && m.agent_verification_status !== "NOT_CHECKED" ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                            Verification: {m.agent_verification_status.replace(/_/g, " ")}
                          </span>
                        ) : null}

                        {m.manual_override && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 font-semibold border border-purple-200">
                            Manual Override
                          </span>
                        )}

                        {m.is_stale && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-200 text-amber-900 font-bold border border-amber-300">
                            STALE ({m.stale_reason || "Re-score required"})
                          </span>
                        )}
                      </div>

                      {/* Property & Listing Specs */}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                        {p?.district && <span>District: {p.district}</span>}
                        {p?.property_type && <span>Type: {p.property_type}</span>}
                        {p?.bedrooms !== undefined && <span>{p.bedrooms} Beds</span>}
                        {l?.asking_price && (
                          <span className="font-bold text-slate-900 font-mono">
                            SGD {Number(l.asking_price).toLocaleString()} / mo
                          </span>
                        )}
                        {l?.availability_status && (
                          <span className="text-slate-500">
                            Listing: {l.availability_status}
                          </span>
                        )}
                      </div>

                      {/* Why this property matched */}
                      {b?.positive_factors && b.positive_factors.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-100">
                          <span className="text-[11px] font-bold text-slate-700 block mb-1">
                            Why this property matched:
                          </span>
                          <ul className="text-xs text-slate-600 space-y-0.5 list-disc list-inside">
                            {b.positive_factors.map((factor: string, idx: number) => (
                              <li key={idx}>{factor}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Risks and Warnings */}
                      {b?.risks && b.risks.length > 0 && (
                        <div className="mt-2 p-2 rounded-md bg-amber-50/70 border border-amber-200 text-xs text-amber-900 flex items-start gap-1.5">
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold">Risks & Unverified Items: </span>
                            {b.risks.join("; ")}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Right column: Match score & actions */}
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      {m.match_score !== null && m.match_score !== undefined ? (
                        <div className="text-right">
                          <div className="text-2xl font-extrabold text-slate-900 font-mono">
                            {Number(m.match_score).toFixed(1)}
                            <span className="text-xs text-slate-400 font-normal"> / 100</span>
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">
                            Config {m.scoring_config_version || "v1.0"}
                          </div>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-400 italic">Not scored</div>
                      )}

                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        {/* Phase 5 Action: Contact Agent */}
                        {(m.match_status === "READY_FOR_AGENT_VERIFICATION" || m.manual_override) &&
                          m.match_status !== "AWAITING_AGENT" && (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleOpenPreview(m)}
                              className="h-7 px-2.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white gap-1"
                            >
                              <Send className="w-3 h-3" />
                              Contact Agent
                            </Button>
                          )}

                        {/* Phase 5 Action: View Outreach / Conversation */}
                        {m.match_status === "AWAITING_AGENT" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleViewConversation(m)}
                            className="h-7 px-2 text-xs border-indigo-300 text-indigo-700 bg-indigo-50/50 hover:bg-indigo-100 gap-1"
                          >
                            <MessageSquare className="w-3 h-3 text-indigo-600" />
                            Agent Outreach
                          </Button>
                        )}

                        {m.match_score !== null && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setInspectedMatch(m);
                              setBreakdownModalOpen(true);
                            }}
                            className="h-7 px-2 text-xs border-slate-200 text-slate-700 hover:bg-slate-50"
                          >
                            Breakdown
                          </Button>
                        )}

                        {/* Phase 7 Action: Follow-ups & SLA */}
                        {m.match_status === "AWAITING_AGENT" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenFollowups(m)}
                            className="h-7 px-2 text-xs border-amber-300 text-amber-800 hover:bg-amber-50 gap-1"
                            title="Manage Follow-up Tasks & SLA"
                          >
                            <Clock className="w-3 h-3 text-amber-600" />
                            Follow-ups
                          </Button>
                        )}

                        {/* Phase 7 Action: Fallback */}
                        {(m.match_status === "AGENT_UNRESPONSIVE" || m.match_status === "AWAITING_AGENT") && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenFallback(m)}
                            className="h-7 px-2 text-xs border-rose-300 text-rose-800 hover:bg-rose-50 gap-1 font-semibold"
                            title="Preview and Execute Fallback Strategy"
                          >
                            <RotateCcw className="w-3 h-3 text-rose-600" />
                            Fallback
                          </Button>
                        )}

                        {/* Phase 6 Action: Verification History */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenHistory(m)}
                          className="h-7 px-2 text-xs border-slate-200 text-slate-700 hover:bg-slate-50 gap-1"
                          title="View Availability Verification History"
                        >
                          <Clock className="w-3 h-3 text-slate-500" />
                          History
                        </Button>

                        {/* Phase 6 Action: Manual Availability Verification */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenManualAvail(m)}
                          className="h-7 px-2 text-xs border-purple-200 text-purple-700 hover:bg-purple-50"
                          title="Manual Availability Override"
                        >
                          Verify Avail
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenOverride(m)}
                          className="h-7 px-2 text-xs text-purple-700 hover:bg-purple-50"
                          title="Workflow Override"
                        >
                          Override
                        </Button>

                        {!m.is_stale && m.match_score !== null && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenStale(m)}
                            className="h-7 px-2 text-xs text-slate-400 hover:text-amber-700"
                            title="Mark Stale"
                          >
                            Mark Stale
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* MODAL 1: SCORE BREAKDOWN INSPECTION */}
      <Modal
        isOpen={breakdownModalOpen}
        onClose={() => setBreakdownModalOpen(false)}
        title="Candidate Match Score Breakdown"
      >
        {inspectedMatch && (
          <div className="space-y-4 max-h-[75vh] overflow-y-auto px-1 text-xs">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
              <div>
                <div className="font-bold text-sm text-slate-900">
                  {inspectedMatch.property_data?.canonical_name || "Property Candidate"}
                </div>
                <div className="text-slate-500 mt-0.5">
                  Rank #{inspectedMatch.rank || "—"} • Config {inspectedMatch.scoring_config_version || "v1.0"}
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-extrabold text-emerald-700 font-mono">
                  {inspectedMatch.match_score !== null ? Number(inspectedMatch.match_score).toFixed(1) : "—"}
                </div>
                <div className="text-[10px] text-slate-400">Total Score (Max 100)</div>
              </div>
            </div>

            {inspectedMatch.scoring_explanation && (
              <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-200 text-indigo-900">
                <span className="font-bold block mb-1">Human-Readable Explanation:</span>
                <p>{inspectedMatch.scoring_explanation}</p>
              </div>
            )}

            <div>
              <div className="font-bold text-slate-800 mb-2">Multidimensional Weighted Points</div>
              <div className="space-y-2">
                {inspectedMatch.score_breakdown?.dimensions &&
                  Object.entries(inspectedMatch.score_breakdown.dimensions).map(([dimKey, dimVal]: any) => (
                    <div
                      key={dimKey}
                      className="p-2.5 rounded-lg border border-slate-200 bg-white flex items-center justify-between"
                    >
                      <div>
                        <span className="font-bold text-slate-800 uppercase tracking-wide font-mono text-[11px]">
                          {dimKey.replace(/_/g, " ")}
                        </span>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          Raw Score: <strong>{(dimVal.raw_score * 100).toFixed(0)}%</strong> • Weight:{" "}
                          <strong>{dimVal.weight} pts</strong>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-sm text-slate-900 font-mono">
                          {Number(dimVal.weighted_score).toFixed(1)}
                        </span>
                        <span className="text-[10px] text-slate-400"> / {dimVal.weight}</span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* MODAL 2: PHASE 5 OUTREACH PREVIEW & SEND */}
      <Modal
        isOpen={previewModalOpen}
        onClose={() => setPreviewModalOpen(false)}
        title="Listing Agent Availability Outreach Preview"
      >
        <div className="space-y-4 max-h-[75vh] overflow-y-auto px-1 text-xs">
          {previewLoading ? (
            <div className="py-8 text-center text-slate-500">
              <RotateCcw className="w-5 h-5 mx-auto mb-2 animate-spin text-indigo-600" />
              Resolving listing agent and formatting minimal context...
            </div>
          ) : previewData ? (
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-700">Recipient Phone:</span>
                  <span className="font-mono font-bold text-indigo-700">{previewData.recipient_phone}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-700">Reference Code:</span>
                  <span className="font-mono bg-slate-200 px-1.5 py-0.5 rounded text-slate-800 font-bold">
                    {previewData.reference_code}
                  </span>
                </div>
              </div>

              {/* Data Minimization Banner */}
              <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-900 flex items-start gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Tenant Privacy Protected: </span>
                  No tenant names, contact numbers, email addresses, internal scores, or chat histories are exposed to the agent.
                </div>
              </div>

              {/* Message Content Preview */}
              <div>
                <span className="font-bold text-slate-800 block mb-1">WhatsApp Message Preview:</span>
                <div className="p-3.5 rounded-xl bg-white border border-slate-300 font-sans text-slate-800 whitespace-pre-wrap leading-relaxed shadow-inner">
                  {previewData.message_content}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setPreviewModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSendSingleOutreach}
                  isLoading={sendingOutreach}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  Dispatch WhatsApp Message
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-500 py-4">No preview available.</div>
          )}
        </div>
      </Modal>

      {/* MODAL 3: BULK OUTREACH VERIFICATION */}
      <Modal
        isOpen={bulkModalOpen}
        onClose={() => setBulkModalOpen(false)}
        title="Verify Top Candidates via Listing Agent Outreach"
      >
        <div className="space-y-4 text-xs">
          {!bulkResult ? (
            <>
              <div className="p-3.5 rounded-xl bg-indigo-50/70 border border-indigo-200 text-indigo-900 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <Send className="w-4 h-4 text-indigo-600" />
                  Automated Outreach Dispatch
                </div>
                <p>
                  You are about to send automated WhatsApp availability verification inquiries to listing agents for the top-ranked candidates.
                </p>
                <div className="pt-2 border-t border-indigo-200/80 flex justify-between font-mono">
                  <span>Selected Candidates:</span>
                  <strong>{readyForOutreachMatches.length}</strong>
                </div>
                <div className="flex justify-between font-mono">
                  <span>Estimated WhatsApp Messages:</span>
                  <strong>{readyForOutreachMatches.length}</strong>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span>
                  Only candidates exceeding the verification threshold (Score &ge; 75.0) are targeted. Duplicate messages are strictly prevented by system idempotency.
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={() => setBulkModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleRunBulkVerify}
                  isLoading={bulkSubmitting}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  Confirm & Dispatch Outreach
                </Button>
              </div>
            </>
          ) : (
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900">
                <div className="font-bold text-sm mb-1 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Bulk Outreach Run Complete
                </div>
                <div className="space-y-1 font-mono text-[11px] mt-2">
                  <div>Selected candidates: {bulkResult.selected}</div>
                  <div>Messages dispatched: {bulkResult.sent}</div>
                  <div>Queued: {bulkResult.queued}</div>
                  {bulkResult.failed > 0 && <div className="text-rose-600">Failed: {bulkResult.failed}</div>}
                </div>
              </div>

              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={() => setBulkModalOpen(false)}>
                  Done
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* MODAL 4: AGENT OUTREACH CONVERSATION THREAD */}
      <Modal
        isOpen={convModalOpen}
        onClose={() => setConvModalOpen(false)}
        title="Property Agent Conversation Thread"
      >
        <div className="space-y-4 max-h-[75vh] overflow-y-auto px-1 text-xs">
          {convLoading ? (
            <div className="py-8 text-center text-slate-500">
              <RotateCcw className="w-5 h-5 mx-auto mb-2 animate-spin text-indigo-600" />
              Loading agent communication thread...
            </div>
          ) : convDetail ? (
            <div className="space-y-3">
              {/* Agent & Property Header */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <div className="flex justify-between">
                  <span className="font-bold text-slate-800">{convDetail.agent_name || "Listing Agent"}</span>
                  <span className="font-mono text-slate-500">{convDetail.agency_name || "Agency"}</span>
                </div>
                <div className="flex justify-between text-slate-600 text-[11px]">
                  <span>Phone: {convDetail.agent_phone || "—"}</span>
                  <span className="font-mono font-bold text-indigo-700">Ref: {convDetail.reference_code}</span>
                </div>
                <div className="text-slate-500 text-[11px] pt-1 border-t border-slate-200">
                  Property: {convDetail.property_title || "Listing Reference"}
                </div>
              </div>

              {/* Message History Bubble Thread */}
              <div className="space-y-2 p-3 bg-slate-100 rounded-xl border border-slate-200 max-h-[40vh] overflow-y-auto">
                {convDetail.messages && convDetail.messages.length > 0 ? (
                  convDetail.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${
                        msg.direction === "OUTBOUND" ? "items-end" : "items-start"
                      }`}
                    >
                      <div
                        className={`p-3 rounded-xl max-w-[85%] whitespace-pre-wrap leading-relaxed shadow-xs text-xs ${
                          msg.direction === "OUTBOUND"
                            ? "bg-indigo-600 text-white rounded-br-xs"
                            : "bg-white text-slate-900 border border-slate-200 rounded-bl-xs"
                        }`}
                      >
                        {msg.content}
                      </div>
                      <div className="flex items-center gap-1 text-[10px] text-slate-400 mt-0.5 px-1 font-mono">
                        <span>{formatDate(msg.created_at)}</span>
                        {msg.direction === "OUTBOUND" && (
                          <span className="uppercase text-[9px] font-bold text-indigo-500">
                            • {msg.provider_status || "SENT"}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-slate-400 py-4">No messages recorded in thread.</div>
                )}
              </div>

              <div className="p-2.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-900 text-[11px]">
                <strong>Phase 5 Status:</strong> Outreach and replies are tracked chronologically.
                Final availability parsing and calendar scheduling will proceed in subsequent phases.
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-500 py-4">No conversation details available.</div>
          )}
        </div>
      </Modal>

      {/* MODAL 5: WORKFLOW FORWARD OVERRIDE */}
      <Modal
        isOpen={overrideModalOpen}
        onClose={() => setOverrideModalOpen(false)}
        title="Workflow Status Override"
      >
        <form onSubmit={handleSubmitOverride} className="space-y-4 text-xs">
          <p className="text-slate-600">
            Authorized operators can promote a candidate to <strong>READY_FOR_AGENT_VERIFICATION</strong>.
            The system score remains unchanged and the manual action is fully audited.
          </p>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">Target Status:</label>
            <select
              value={overrideStatus}
              onChange={(e) => setOverrideStatus(e.target.value as PropertyMatchStatus)}
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            >
              <option value="READY_FOR_AGENT_VERIFICATION">READY_FOR_AGENT_VERIFICATION (Promote to Outreach)</option>
              <option value="SCORED">SCORED</option>
              <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">Override Rationale / Reason:</label>
            <textarea
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              required
              rows={3}
              placeholder="e.g. Tenant explicitly authorized Newton secondary area; verified with operator..."
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <Button variant="outline" size="sm" type="button" onClick={() => setOverrideModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={overrideSubmitting}>
              Apply Override
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 6: MARK STALE */}
      <Modal
        isOpen={staleModalOpen}
        onClose={() => setStaleModalOpen(false)}
        title="Mark Candidate Match Stale"
      >
        <form onSubmit={handleSubmitStale} className="space-y-4 text-xs">
          <p className="text-slate-600">
            Marking a match as stale prevents automatic verification until re-scoring is performed.
          </p>
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Stale Reason:</label>
            <textarea
              value={staleReason}
              onChange={(e) => setStaleReason(e.target.value)}
              required
              rows={3}
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <Button variant="outline" size="sm" type="button" onClick={() => setStaleModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={staleSubmitting}>
              Confirm Stale
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL 5: PHASE 6 AVAILABILITY VERIFICATION HISTORY */}
      <Modal
        isOpen={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        title="Availability Verification History & Provenance"
      >
        <div className="space-y-4 text-xs">
          {historyLoading ? (
            <div className="py-6 text-center text-slate-500">Loading verification records...</div>
          ) : historyRecords.length === 0 ? (
            <div className="py-6 text-center text-slate-400 italic">
              No verification records recorded yet for this candidate match.
            </div>
          ) : (
            <div className="space-y-3">
              {historyRecords.map((rec) => (
                <div key={rec.id} className="p-3 rounded-xl border border-slate-200 bg-white shadow-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                      rec.availability_status === "AVAILABLE"
                        ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                        : rec.availability_status === "UNAVAILABLE"
                        ? "bg-rose-100 text-rose-800 border border-rose-200"
                        : "bg-purple-100 text-purple-800 border border-purple-200"
                    }`}>
                      {rec.availability_status}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(rec.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-slate-700 font-mono text-[11px] pt-1">
                    {rec.asking_price && <div>Rent: SGD {Number(rec.asking_price).toLocaleString()}/mo</div>}
                    {rec.available_from && <div>Avail Date: {rec.available_from}</div>}
                    {rec.minimum_lease_months && <div>Min Lease: {rec.minimum_lease_months} mo</div>}
                    {rec.furnishing && <div>Furnishing: {rec.furnishing}</div>}
                  </div>
                  {rec.viewing_notes && (
                    <div className="text-[11px] text-indigo-700 bg-indigo-50/60 p-1.5 rounded">
                      Viewing Note: {rec.viewing_notes}
                    </div>
                  )}
                  {rec.notes && (
                    <div className="text-[11px] text-slate-500 italic">
                      {rec.notes}
                    </div>
                  )}
                  <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-100 flex justify-between">
                    <span>Source: {rec.verification_source}</span>
                    <span>Status: {rec.verification_status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end pt-2 border-t border-slate-200">
            <Button variant="outline" size="sm" onClick={() => setHistoryModalOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 6: PHASE 6 MANUAL AVAILABILITY OVERRIDE */}
      <Modal
        isOpen={manualAvailModalOpen}
        onClose={() => setManualAvailModalOpen(false)}
        title="Manual Availability Verification Override"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Availability Status:</label>
            <select
              value={manualAvailStatus}
              onChange={(e) => setManualAvailStatus(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            >
              <option value="AVAILABLE">AVAILABLE (Verified by Operator)</option>
              <option value="UNAVAILABLE">UNAVAILABLE (Already Rented/Taken)</option>
              <option value="CONDITIONAL">CONDITIONAL (Subject to Restrictions)</option>
              <option value="NEEDS_REVIEW">NEEDS REVIEW (Requires Verification)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Confirmed Rent (SGD):</label>
              <input
                type="number"
                placeholder="e.g. 3900"
                value={manualAvailPrice}
                onChange={(e) => setManualAvailPrice(e.target.value)}
                className="w-full p-2 border border-slate-300 rounded-lg text-xs"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Available Date:</label>
              <input
                type="date"
                value={manualAvailDate}
                onChange={(e) => setManualAvailDate(e.target.value)}
                className="w-full p-2 border border-slate-300 rounded-lg text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">Minimum Lease (Months):</label>
            <input
              type="number"
              placeholder="e.g. 12 or 24"
              value={manualAvailLease}
              onChange={(e) => setManualAvailLease(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            />
          </div>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">Operator Reason (Mandatory Audit):</label>
            <textarea
              value={manualAvailReason}
              onChange={(e) => setManualAvailReason(e.target.value)}
              required
              rows={3}
              placeholder="e.g. Agent confirmed availability via phone call on Oct 9"
              className="w-full p-2 border border-slate-300 rounded-lg text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <Button variant="outline" size="sm" onClick={() => setManualAvailModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSubmitManualAvail}
              isLoading={manualAvailSubmitting}
            >
              Save Verification Override
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 7: PHASE 7 FALLBACK PREVIEW & EXECUTION */}
      <Modal
        isOpen={fallbackModalOpen}
        onClose={() => setFallbackModalOpen(false)}
        title="Agent Unresponsive — Fallback Strategy"
      >
        <div className="space-y-4 text-xs">
          {fallbackLoading ? (
            <div className="py-8 text-center text-slate-400">Loading fallback recommendation...</div>
          ) : fallbackPreview ? (
            <div className="space-y-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                <div className="font-bold text-slate-800">Contact Policy Status</div>
                <div className="text-slate-600">
                  Total Agent Contacts for Lead: <span className="font-mono font-bold">{fallbackPreview.total_agent_contacts} / {fallbackPreview.max_total_agent_contacts}</span>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-indigo-200 bg-indigo-50/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-indigo-900">Recommended Action:</span>
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-600 text-white font-mono">
                    {fallbackPreview.recommended_action}
                  </span>
                </div>
                {fallbackPreview.reason && (
                  <p className="text-indigo-800 text-[11px] italic">{fallbackPreview.reason}</p>
                )}
              </div>

              {fallbackPreview.alternate_listing && (
                <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 space-y-1.5 text-emerald-950">
                  <div className="font-bold">Alternate Active Listing for Same Property</div>
                  <div>Agent: <span className="font-semibold">{fallbackPreview.alternate_listing.agent_name || "Agent"}</span> ({fallbackPreview.alternate_listing.agent_phone})</div>
                  {fallbackPreview.alternate_listing.asking_price && (
                    <div>Price: <span className="font-mono font-bold">SGD {fallbackPreview.alternate_listing.asking_price}</span></div>
                  )}
                </div>
              )}

              {fallbackPreview.next_property_match && (
                <div className="p-3 bg-blue-50 rounded-xl border border-blue-200 space-y-1.5 text-blue-950">
                  <div className="font-bold">Next Highest-Ranked Eligible Property</div>
                  <div>Candidate Rank: <span className="font-mono font-bold">#{fallbackPreview.next_property_match.rank || "—"}</span></div>
                  <div>Score: <span className="font-mono font-bold">{fallbackPreview.next_property_match.match_score} pts</span></div>
                </div>
              )}

              {fallbackPreview.recommended_action === "HUMAN_REVIEW" && (
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-300 text-amber-900 space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Human Review Required
                  </div>
                  <p>All automated fallback paths are exhausted or contact limit reached. Operator will review the candidate pool manually.</p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <Button variant="outline" size="sm" onClick={() => setFallbackModalOpen(false)}>
                  Close
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleExecuteFallback}
                  isLoading={fallbackExecuting}
                >
                  Execute Fallback Action
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-slate-400 text-center py-4">No fallback preview available.</div>
          )}
        </div>
      </Modal>

      {/* MODAL 8: PHASE 7 FOLLOW-UP TASKS & SLA */}
      <Modal
        isOpen={followupsModalOpen}
        onClose={() => setFollowupsModalOpen(false)}
        title="Agent Follow-up Tasks & SLA Schedule"
      >
        <div className="space-y-4 text-xs">
          {followupsLoading ? (
            <div className="py-8 text-center text-slate-400">Loading follow-up tasks...</div>
          ) : (
            <div className="space-y-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-800">
                    {followupsMatch?.property_data?.canonical_name || "Property Candidate"}
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    Status: <span className="font-semibold">{followupsMatch?.match_status}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {followupTasks.length === 0 ? (
                  <div className="py-6 text-center text-slate-400">No scheduled follow-up tasks for this match.</div>
                ) : (
                  followupTasks.map((t) => (
                    <div
                      key={t.id}
                      className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between gap-3"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">
                            Attempt #{t.attempt_number} ({t.followup_type})
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            t.status === "SENT" || t.status === "COMPLETED"
                              ? "bg-emerald-100 text-emerald-800"
                              : t.status === "CANCELLED"
                              ? "bg-slate-100 text-slate-600"
                              : t.status === "FAILED"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-amber-100 text-amber-800"
                          }`}>
                            {t.status}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Due: {formatDate(t.due_at)} {t.sent_at && `• Sent: ${formatDate(t.sent_at)}`}
                        </div>
                        {t.cancellation_reason && (
                          <div className="text-[10px] text-slate-400 italic">
                            Cancelled: {t.cancellation_reason}
                          </div>
                        )}
                      </div>

                      {(t.status === "PENDING" || t.status === "DUE") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCancelFollowup(t.id)}
                          isLoading={followupActionLoading}
                          className="h-6 px-2 text-[10px] text-rose-600 hover:bg-rose-50"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  ))
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <Button variant="outline" size="sm" onClick={() => setFollowupsModalOpen(false)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* MODAL 9: PHASE 10 MODULE 5 HANDOFF CONTRACT PREVIEW */}
      <Modal
        isOpen={handoffModalOpen}
        onClose={() => setHandoffModalOpen(false)}
        title="Module 5 Handoff Contract (Strict Boundary)"
      >
        <div className="space-y-4 text-xs max-h-[80vh] overflow-y-auto px-1">
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-emerald-800 text-sm">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              Ready for Module 5 Ingestion
            </div>
            <p className="text-[11px] text-emerald-800">
              This contract payload packages verified tenant requirements and agent-confirmed candidate properties for downstream viewing scheduling.
            </p>
            <div className="p-2 bg-emerald-50 rounded-lg border border-emerald-200 text-[10px] text-emerald-950 font-medium">
              <strong>Strict Boundary Notice:</strong> No viewings have been scheduled. Viewing time slots, slot negotiation, and reminders will begin in Module 5.
            </div>
          </div>

          {handoffLoading ? (
            <div className="py-12 text-center text-slate-400">
              <RotateCcw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
              Generating handoff contract payload...
            </div>
          ) : handoffPayload ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-700">Contract Payload</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-700">
                    {handoffPayload.properties?.length || 0} Candidate(s)
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(handoffPayload, null, 2));
                    setHandoffCopied(true);
                    setTimeout(() => setHandoffCopied(false), 2000);
                  }}
                  className="text-xs h-7 gap-1"
                >
                  {handoffCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-500" />
                      Copy JSON
                    </>
                  )}
                </Button>
              </div>

              <pre className="p-3 bg-slate-950 text-emerald-400 font-mono text-[11px] rounded-xl overflow-x-auto max-h-72 border border-slate-800 leading-relaxed">
                {JSON.stringify(handoffPayload, null, 2)}
              </pre>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block">Lead Qualification</span>
                  <span className="font-bold text-slate-800 font-mono">
                    {handoffPayload.qualification_status || "QUALIFIED"}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block">Shortlist Status</span>
                  <span className="font-bold text-emerald-700 font-mono">
                    {handoffPayload.shortlist_status || "READY"}
                  </span>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <Button variant="outline" size="sm" onClick={() => setHandoffModalOpen(false)}>
                  Close
                </Button>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-slate-400">Failed to load handoff payload.</div>
          )}
        </div>
      </Modal>

      {/* MODAL 10: SHORTLISTED PROPERTIES SIDE-BY-SIDE COMPARISON */}
      <Modal
        isOpen={compareModalOpen}
        onClose={() => setCompareModalOpen(false)}
        title="Shortlisted Properties — Side-by-Side Comparison"
      >
        <div className="space-y-4 text-xs max-h-[80vh] overflow-y-auto px-1">
          <p className="text-slate-600 text-[11px]">
            Direct attribute comparison across verified shortlisted candidate units for operator evaluation.
          </p>

          {shortlist && shortlist.items && shortlist.items.length > 0 ? (
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-[11px]">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-700">
                    <th className="p-2.5 font-bold sticky left-0 bg-slate-50 z-10 w-32 border-r border-slate-200">
                      Attribute
                    </th>
                    {shortlist.items.map((item) => (
                      <th key={item.id} className="p-2.5 font-bold min-w-[160px] border-r border-slate-200 last:border-r-0">
                        <div className="flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded-full bg-amber-400 text-slate-950 font-bold text-[10px] flex items-center justify-center font-mono">
                            #{item.position}
                          </span>
                          <span className="truncate">{item.property_name || "Property"}</span>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Asking Price
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 font-bold text-amber-600 font-mono border-r border-slate-200 last:border-r-0">
                        SGD {Number(item.asking_price || 0).toLocaleString()} / mo
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Match Score
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 font-bold text-indigo-700 font-mono border-r border-slate-200 last:border-r-0">
                        {item.score_at_selection ? Number(item.score_at_selection).toFixed(0) : "—"} pts
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Location / District
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 text-slate-800 border-r border-slate-200 last:border-r-0">
                        {item.district || "Singapore"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Type & Bedrooms
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 text-slate-800 border-r border-slate-200 last:border-r-0">
                        {item.bedrooms || 2} BR {item.property_type || "Condo"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Availability
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 border-r border-slate-200 last:border-r-0">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          {item.shortlist_status}
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Available From
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 font-mono text-slate-800 border-r border-slate-200 last:border-r-0">
                        {item.available_from ? formatDate(item.available_from) : "Immediate"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Listing Agent
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 text-slate-800 border-r border-slate-200 last:border-r-0">
                        <div className="font-semibold">{item.agent_name || "Agent"}</div>
                        <div className="text-[10px] text-slate-500">{item.agent_agency || "Agency"}</div>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-2.5 font-semibold text-slate-600 sticky left-0 bg-white border-r border-slate-200">
                      Conditions / Warnings
                    </td>
                    {shortlist.items.map((item) => (
                      <td key={item.id} className="p-2.5 border-r border-slate-200 last:border-r-0">
                        {item.warnings && item.warnings.length > 0 ? (
                          <div className="text-amber-700 text-[10px] font-medium">
                            {item.warnings.join(", ")}
                          </div>
                        ) : (
                          <span className="text-emerald-700 font-semibold text-[10px]">None (Clean Match)</span>
                        )}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-6 text-center text-slate-400">At least 2 shortlisted items required for comparison.</div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <Button variant="outline" size="sm" onClick={() => setCompareModalOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 11: TENANT REQUIREMENTS VS CANDIDATE COMPARISON */}
      <Modal
        isOpen={tenantCompareModalOpen}
        onClose={() => setTenantCompareModalOpen(false)}
        title="Tenant Requirements vs Property Candidate Comparison"
      >
        <div className="space-y-4 text-xs max-h-[80vh] overflow-y-auto px-1">
          {inspectedCandidate ? (
            <div className="space-y-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-900 text-sm">
                    {inspectedCandidate.property_name || "Candidate Property"}
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    System Rank #{inspectedCandidate.system_rank || "—"} • Score:{" "}
                    <span className="font-bold text-indigo-700 font-mono">
                      {inspectedCandidate.match_score ? Number(inspectedCandidate.match_score).toFixed(0) : "—"} pts
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                  {inspectedCandidate.shortlist_status}
                </span>
              </div>

              {/* Requirements Comparison Table */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-left border-collapse text-[11px]">
                  <thead>
                    <tr className="bg-slate-100/70 border-b border-slate-200 text-slate-700">
                      <th className="p-2.5 font-bold w-1/4">Requirement Field</th>
                      <th className="p-2.5 font-bold w-1/3">Tenant Preference</th>
                      <th className="p-2.5 font-bold w-1/4">Property Value</th>
                      <th className="p-2.5 font-bold w-1/6">Assessment</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {inspectedCandidate.comparison && inspectedCandidate.comparison.length > 0 ? (
                      inspectedCandidate.comparison.map((c, idx) => (
                        <tr key={idx}>
                          <td className="p-2.5 font-semibold text-slate-700 uppercase font-mono text-[10px]">
                            {c.field_name.replace(/_/g, " ")}
                          </td>
                          <td className="p-2.5 text-slate-800 font-medium">
                            {c.tenant_requirement || "—"}
                          </td>
                          <td className="p-2.5 text-slate-900 font-mono">
                            {c.property_value || "—"}
                          </td>
                          <td className="p-2.5">
                            {c.status === "MATCH" || c.status === "COMPATIBLE" ? (
                              <span className="text-emerald-600 font-bold flex items-center gap-1 text-[10px]">
                                <Check className="w-3.5 h-3.5" /> Matched
                              </span>
                            ) : c.status === "WARNING" || c.status === "CONDITIONAL" ? (
                              <span className="text-amber-600 font-bold flex items-center gap-1 text-[10px]">
                                <AlertTriangle className="w-3.5 h-3.5" /> Conditional
                              </span>
                            ) : (
                              <span className="text-slate-500 font-medium text-[10px]">
                                {c.status}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="p-4 text-center text-slate-400">
                          No direct criteria comparison available for this candidate.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Explanatory notes */}
              {inspectedCandidate.explanation && (
                <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-900 text-[11px]">
                  <strong>Scoring Summary:</strong> {inspectedCandidate.explanation}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <Button variant="outline" size="sm" onClick={() => setTenantCompareModalOpen(false)}>
                  Close
                </Button>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-slate-400">No candidate selected for comparison.</div>
          )}
        </div>
      </Modal>
    </Card>
  );
}
