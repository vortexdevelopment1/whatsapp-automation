"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  UserCheck,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Phone,
  Mail,
  Copy,
  ExternalLink,
  RefreshCw,
  Ban,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowLeft,
  FileText,
  Home,
  DollarSign,
  Calendar,
  History,
  Edit3,
  ListChecks,
  Check,
  Bot,
  Sparkles,
  HelpCircle,
  Pause,
  Play,
  RotateCw,
  Scale,
  MessageSquare,
  Layers,
  ChevronDown,
  ChevronUp,
  Send,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  Lead,
  LeadDuplicateCheckResponse,
  LeadEligibilityCheckResponse,
  AuditLog,
  TenantRequirement,
  TenantRequirementHistory,
  QualificationProgress,
  NextQuestionResponse,
  QualificationPreviewResponse,
  QualificationLiveStatus,
  QualificationDecisionResponse,
  ConversationEscalation,
  QualificationClarification,
  QualificationDashboardData,
  ConversationSummary,
  ConversationNote,
} from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";
import { PropertyMatchingSection } from "@/components/leads/PropertyMatchingSection";
import { LeadViewingsSection } from "@/components/leads/LeadViewingsSection";
import { LeadPropertyPresentationSection } from "@/components/leads/LeadPropertyPresentationSection";

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const [lead, setLead] = useState<Lead | null>(null);
  const [duplicateInfo, setDuplicateInfo] = useState<LeadDuplicateCheckResponse | null>(null);
  const [eligibilityInfo, setEligibilityInfo] = useState<LeadEligibilityCheckResponse | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  // Module 3: Tenant Requirements State
  const [requirement, setRequirement] = useState<TenantRequirement | null>(null);
  const [requirementHistory, setRequirementHistory] = useState<TenantRequirementHistory[]>([]);
  const [progress, setProgress] = useState<QualificationProgress | null>(null);

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals state
  const [isOverrideModalOpen, setIsOverrideModalOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");

  const [isOptOutModalOpen, setIsOptOutModalOpen] = useState(false);
  const [optOutReason, setOptOutReason] = useState("");

  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [restoreAuthorizedBy, setRestoreAuthorizedBy] = useState("compliance_officer");
  const [restoreReason, setRestoreReason] = useState("");

  const [isEditReqModalOpen, setIsEditReqModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(false);
  const [analyzeText, setAnalyzeText] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState<any>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);

  // Module 3 Phase 4: Qualification Next Question State
  const [nextQuestion, setNextQuestion] = useState<NextQuestionResponse | null>(null);
  const [qualificationPreview, setQualificationPreview] = useState<QualificationPreviewResponse | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);

  // Module 3 Phase 5: Live Qualification Loop State
  const [liveStatus, setLiveStatus] = useState<QualificationLiveStatus | null>(null);
  const [pauseResumeLoading, setPauseResumeLoading] = useState(false);
  const [retryLoading, setRetryLoading] = useState(false);

  // Module 3 Phase 6: Qualification Decision State
  const [decisionHistory, setDecisionHistory] = useState<QualificationDecisionResponse[]>([]);
  const [latestDecision, setLatestDecision] = useState<QualificationDecisionResponse | null>(null);
  const [isEvalModalOpen, setIsEvalModalOpen] = useState(false);
  const [evalPreviewResult, setEvalPreviewResult] = useState<QualificationDecisionResponse | null>(null);
  const [evalModalLoading, setEvalModalLoading] = useState(false);
  const [isDecisionHistoryModalOpen, setIsDecisionHistoryModalOpen] = useState(false);
  const [isDecisionOverrideModalOpen, setIsDecisionOverrideModalOpen] = useState(false);
  const [overrideTargetStatus, setOverrideTargetStatus] = useState("QUALIFIED");
  const [overrideJustification, setOverrideJustification] = useState("");
  const [overrideEvaluatedBy, setOverrideEvaluatedBy] = useState("human_agent");
  const [overrideLoading, setOverrideLoading] = useState(false);

  // Module 3 Phase 7: Escalations, Clarifications & Human Takeover State
  const [escalations, setEscalations] = useState<ConversationEscalation[]>([]);
  const [clarifications, setClarifications] = useState<QualificationClarification[]>([]);
  const [isOperatorMsgModalOpen, setIsOperatorMsgModalOpen] = useState(false);
  const [operatorMsgContent, setOperatorMsgContent] = useState("");
  const [isEscalateModalOpen, setIsEscalateModalOpen] = useState(false);
  const [escalateReason, setEscalateReason] = useState("OPERATOR_TAKEOVER");
  const [escalateDescription, setEscalateDescription] = useState("");
  const [isResolveEscalationModalOpen, setIsResolveEscalationModalOpen] = useState(false);
  const [escalationResolutionNotes, setEscalationResolutionNotes] = useState("");

  // Module 3 Phase 8: Memory, Summary & Dashboard State
  const [dashboardData, setDashboardData] = useState<QualificationDashboardData | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [noteLoading, setNoteLoading] = useState(false);
  const [showAiDetails, setShowAiDetails] = useState(false);


  const [reqForm, setReqForm] = useState({
    preferred_locations: "",
    budget_min: "",
    budget_max: "",
    currency: "SGD",
    property_type: "Condo",
    bedrooms: "",
    move_in_date: "",
    lease_duration_months: "12",
    occupants: "1",
    furnishing: "FURNISHED",
    special_requirements: "",
  });

  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);

  const loadLeadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const leadData = await api.getLead(leadId);
      setLead(leadData);

      // Fetch duplicate check
      try {
        const dupRes = await api.checkLeadDuplicate(leadId);
        setDuplicateInfo(dupRes);
        if (dupRes.duplicate && !leadData.duplicate_override) {
          setShowDuplicateWarning(true);
        }
      } catch (e) {
        console.warn("Could not check duplicate", e);
      }

      // Fetch eligibility check
      try {
        const eligRes = await api.checkContactEligibility(leadId);
        setEligibilityInfo(eligRes);
      } catch (e) {
        console.warn("Could not check eligibility", e);
      }

      // Fetch Module 3: Tenant Requirements & Progress
      try {
        const reqData = await api.getTenantRequirements(leadId);
        setRequirement(reqData);

        // Populate edit form
        setReqForm({
          preferred_locations: reqData.preferred_locations ? reqData.preferred_locations.join(", ") : "",
          budget_min: reqData.budget_min !== null ? String(reqData.budget_min) : "",
          budget_max: reqData.budget_max !== null ? String(reqData.budget_max) : "",
          currency: reqData.currency || "SGD",
          property_type: reqData.property_type || "Condo",
          bedrooms: reqData.bedrooms !== null ? String(reqData.bedrooms) : "",
          move_in_date: reqData.move_in_date || "",
          lease_duration_months: reqData.lease_duration_months !== null ? String(reqData.lease_duration_months) : "12",
          occupants: reqData.occupants !== null ? String(reqData.occupants) : "1",
          furnishing: reqData.furnishing || "FURNISHED",
          special_requirements: reqData.special_requirements ? JSON.stringify(reqData.special_requirements) : "",
        });

        // Load progress
        try {
          const progData = await api.getQualificationProgress(leadId);
          setProgress(progData);
        } catch (e) {
          console.warn("Could not load qualification progress", e);
        }

        // Load history
        try {
          const histData = await api.getRequirementHistory(leadId);
          setRequirementHistory(histData);
        } catch (e) {
          console.warn("Could not load requirement history", e);
        }

        // Load qualification preview
        try {
          const prevData = await api.previewQualification(leadId);
          setQualificationPreview(prevData);
        } catch (e) {
          console.warn("Could not load qualification preview", e);
        }

        // Load qualification live status (Phase 5)
        try {
          const live = await api.getQualificationLiveStatus(leadId);
          setLiveStatus(live);
        } catch (e) {
          console.warn("Could not load qualification live status", e);
        }

        // Load qualification decision history (Phase 6)
        try {
          const history = await api.getQualificationDecisionHistory(leadId);
          setDecisionHistory(history);
          if (history && history.length > 0) {
            setLatestDecision(history[0]);
          } else {
            setLatestDecision(null);
          }
        } catch (e) {
          console.warn("Could not load qualification decision history", e);
        }
      } catch (e) {
        // Requirements profile may not exist yet
        setRequirement(null);
        setProgress(null);
        setRequirementHistory([]);
        setQualificationPreview(null);
        setLiveStatus(null);
        setDecisionHistory([]);
        setLatestDecision(null);
      }

      // Fetch Module 3 Phase 7: Escalations & Clarifications
      try {
        const escList = await api.getLeadEscalations(leadId);
        setEscalations(escList);
      } catch (e) {
        console.warn("Could not load escalations", e);
      }

      try {
        const clarList = await api.getLeadClarifications(leadId);
        setClarifications(clarList);
      } catch (e) {
        console.warn("Could not load clarifications", e);
      }

      // Fetch Module 3 Phase 8: Qualification Dashboard Aggregate
      try {
        const dData = await api.getQualificationDashboard(leadId);
        setDashboardData(dData);
      } catch (e) {
        console.warn("Could not load qualification dashboard", e);
      }

      // Fetch audit logs
      try {
        const logs = await api.listAuditLogs({ entity_id: leadId });
        setAuditLogs(logs);
      } catch (e) {
        console.warn("Could not load audit logs", e);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load lead details");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadLeadData();
  }, [loadLeadData]);

  const handleToggleAIPause = async () => {
    try {
      setPauseResumeLoading(true);
      setError(null);
      if (liveStatus?.ai_paused || requirement?.ai_paused) {
        await api.resumeAIQualification(leadId);
        setSuccessMsg("AI qualification resumed. Incoming messages will be processed automatically.");
      } else {
        await api.pauseAIQualification(leadId);
        setSuccessMsg("AI qualification paused. Messages will be stored without automated replies.");
      }
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to toggle AI pause state.");
    } finally {
      setPauseResumeLoading(false);
    }
  };

  const handleRetryProcessing = async (messageId: string) => {
    try {
      setRetryLoading(true);
      setError(null);
      await api.retryQualificationMessage(leadId, messageId);
      setSuccessMsg("Manual qualification retry queued and processed.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to retry message processing.");
    } finally {
      setRetryLoading(false);
    }
  };

  const handleGenerateNextQuestion = async (collectOptional = false) => {
    try {
      setQuestionLoading(true);
      setError(null);
      const res = await api.generateNextQuestion(leadId, collectOptional);
      setNextQuestion(res);
      setSuccessMsg(`Next question determined: ${res.field ? res.field.replace(/_/g, " ") : res.action}`);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to generate next question.");
    } finally {
      setQuestionLoading(false);
    }
  };

  // Module 3 Phase 6: Qualification Decision Handlers
  const handlePreviewEvaluation = async () => {
    try {
      setEvalModalLoading(true);
      setError(null);
      const res = await api.evaluateQualification(leadId, { apply: false });
      setEvalPreviewResult(res);
      setIsEvalModalOpen(true);
    } catch (err: any) {
      setError(err.message || "Failed to preview qualification decision.");
    } finally {
      setEvalModalLoading(false);
    }
  };

  const handleApplyEvaluation = async () => {
    try {
      setActionLoading(true);
      setError(null);
      const res = await api.evaluateQualification(leadId, { apply: true });
      setLatestDecision(res);
      setSuccessMsg(`Qualification evaluated & applied: ${res.decision}`);
      setIsEvalModalOpen(false);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to apply qualification decision.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleApplyOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideJustification.trim()) {
      setError("Reason is required for manual qualification override.");
      return;
    }
    try {
      setOverrideLoading(true);
      setError(null);
      const res = await api.evaluateQualification(leadId, {
        apply: true,
        human_override_status: overrideTargetStatus,
        override_reason: overrideJustification.trim(),
        evaluated_by: overrideEvaluatedBy.trim() || "operator",
      });
      setLatestDecision(res);
      setIsDecisionOverrideModalOpen(false);
      setOverrideJustification("");
      setSuccessMsg(`Human override applied: ${res.decision}`);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to apply human override.");
    } finally {
      setOverrideLoading(false);
    }
  };

  // Actions
  const handleValidatePhone = async () => {
    try {
      setActionLoading(true);
      setError(null);
      await api.validateLead(leadId);
      setSuccessMsg("Phone validation completed.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Validation failed.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckDuplicate = async () => {
    try {
      setActionLoading(true);
      setError(null);
      const res = await api.checkLeadDuplicate(leadId);
      setDuplicateInfo(res);
      if (res.duplicate) {
        setShowDuplicateWarning(true);
        setSuccessMsg("Duplicate check completed: Potential duplicate detected.");
      } else {
        setShowDuplicateWarning(false);
        setSuccessMsg("Duplicate check completed: No duplicates found.");
      }
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Duplicate check failed.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckEligibility = async () => {
    try {
      setActionLoading(true);
      setError(null);
      const res = await api.checkContactEligibility(leadId);
      setEligibilityInfo(res);
      setSuccessMsg(`Contact eligibility evaluated: ${res.eligibility}`);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Eligibility check failed.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleOverrideDuplicate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) {
      setError("Reason is required to override duplicate status.");
      return;
    }
    try {
      setActionLoading(true);
      setError(null);
      await api.overrideLeadDuplicate(leadId, overrideReason.trim());
      setIsOverrideModalOpen(false);
      setOverrideReason("");
      setShowDuplicateWarning(false);
      setSuccessMsg("Duplicate override successful. Lead status restored to validating.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to override duplicate.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleMarkOptOut = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setActionLoading(true);
      setError(null);
      await api.markLeadOptOut(leadId, optOutReason.trim() || undefined);
      setIsOptOutModalOpen(false);
      setOptOutReason("");
      setSuccessMsg("Lead marked as OPTED OUT. Outreach is blocked.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to mark lead as opted out.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestoreContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!restoreAuthorizedBy.trim()) {
      setError("Authorizer identifier is required to restore contact.");
      return;
    }
    try {
      setActionLoading(true);
      setError(null);
      await api.restoreLeadContact(leadId, {
        authorized_by: restoreAuthorizedBy.trim(),
        reason: restoreReason.trim() || undefined,
      });
      setIsRestoreModalOpen(false);
      setRestoreReason("");
      setSuccessMsg("Contact status successfully restored and re-evaluated.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to restore contact status.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveRequirements = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setActionLoading(true);
      setError(null);

      // Parse locations
      const locs = reqForm.preferred_locations
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean);

      // Parse special requirements JSON or text
      let specReq = null;
      if (reqForm.special_requirements.trim()) {
        try {
          specReq = JSON.parse(reqForm.special_requirements.trim());
        } catch {
          specReq = { notes: reqForm.special_requirements.trim() };
        }
      }

      const payload: any = {
        preferred_locations: locs.length > 0 ? locs : undefined,
        budget_min: reqForm.budget_min ? parseFloat(reqForm.budget_min) : undefined,
        budget_max: reqForm.budget_max ? parseFloat(reqForm.budget_max) : undefined,
        currency: reqForm.currency || "SGD",
        property_type: reqForm.property_type || undefined,
        bedrooms: reqForm.bedrooms ? parseInt(reqForm.bedrooms, 10) : undefined,
        move_in_date: reqForm.move_in_date || undefined,
        lease_duration_months: reqForm.lease_duration_months ? parseInt(reqForm.lease_duration_months, 10) : undefined,
        occupants: reqForm.occupants ? parseInt(reqForm.occupants, 10) : undefined,
        furnishing: reqForm.furnishing || undefined,
        special_requirements: specReq,
      };

      if (requirement) {
        await api.updateTenantRequirements(leadId, payload);
        setSuccessMsg("Tenant requirements updated successfully.");
      } else {
        await api.createTenantRequirements(leadId, payload);
        setSuccessMsg("Tenant requirements profile created successfully.");
      }

      setIsEditReqModalOpen(false);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to save tenant requirements.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAnalyzeMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!analyzeText.trim()) return;
    try {
      setAnalyzeLoading(true);
      setError(null);
      const res = await api.devExtractRequirements(analyzeText.trim());
      setAnalyzeResult(res);
      setSuccessMsg("Tenant message evaluated successfully.");
    } catch (err: any) {
      setError(err.message || "Failed to analyze tenant message.");
    } finally {
      setAnalyzeLoading(false);
    }
  };

  // Phase 7 Handlers
  const handleTakeover = async () => {
    try {
      setActionLoading(true);
      await api.takeoverConversation(leadId);
      setSuccessMsg("Operator took over conversation. AI paused.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Takeover failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReturnToAI = async (notes?: string) => {
    try {
      setActionLoading(true);
      await api.returnToAI(leadId, notes);
      setSuccessMsg("Returned to AI. Qualification state recalculated.");
      setIsResolveEscalationModalOpen(false);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to return conversation to AI");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendOperatorMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!operatorMsgContent.trim()) return;
    try {
      setActionLoading(true);
      await api.sendOperatorMessage(leadId, operatorMsgContent.trim());
      setSuccessMsg("Outbound message sent with HUMAN_OPERATOR attribution.");
      setOperatorMsgContent("");
      setIsOperatorMsgModalOpen(false);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to send operator message");
    } finally {
      setActionLoading(false);
    }
  };

  const handleManualEscalate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setActionLoading(true);
      await api.createLeadEscalation(leadId, {
        reason_code: escalateReason,
        description: escalateDescription,
      });
      setSuccessMsg("Lead escalated to human review. AI paused.");
      setIsEscalateModalOpen(false);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to escalate lead");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveClarification = async (clarId: string, action: "CONFIRM" | "REJECT", resolvedValue?: any) => {
    try {
      setActionLoading(true);
      await api.resolveClarification(leadId, clarId, { action, resolved_value: resolvedValue });
      setSuccessMsg(`Clarification ${action === "CONFIRM" ? "confirmed" : "cancelled"}.`);
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to update clarification");
    } finally {
      setActionLoading(false);
    }
  };

  // Phase 8 Handlers: Memory, Summary & Notes
  const handleRefreshSummary = async () => {
    try {
      setSummaryLoading(true);
      await api.refreshQualificationSummary(leadId);
      setSuccessMsg("Conversation summary refreshed successfully.");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to refresh conversation summary");
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;
    try {
      setNoteLoading(true);
      await api.createLeadNote(leadId, newNote.trim());
      setSuccessMsg("Internal operator note added.");
      setNewNote("");
      await loadLeadData();
    } catch (err: any) {
      setError(err.message || "Failed to add note");
    } finally {
      setNoteLoading(false);
    }
  };


  if (loading && !lead) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 text-slate-500">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span>Loading lead details...</span>
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl">
          Lead not found or error loading data: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/leads"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Leads
        </Link>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadLeadData}
            isLoading={actionLoading}
            className="gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 text-sm">Dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 text-sm">Dismiss</button>
        </div>
      )}

      {/* POTENTIAL DUPLICATE LEAD WARNING BANNER */}
      {showDuplicateWarning && duplicateInfo?.duplicate && duplicateInfo.existing_lead && (
        <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-5 shadow-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-3">
              <div>
                <h3 className="text-base font-bold text-amber-900 tracking-tight">
                  POTENTIAL DUPLICATE LEAD
                </h3>
                <p className="text-xs text-amber-800 mt-0.5">
                  This lead shares contact details with an existing non-archived record in the system.
                  Matched reasons: <span className="font-semibold">{duplicateInfo.match_reasons.join(", ")}</span>
                </p>
              </div>

              {/* Existing Lead Details Box */}
              <div className="bg-white/80 border border-amber-200 rounded-lg p-3.5 text-sm text-slate-800 grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div>
                  <span className="text-xs text-slate-500 block">Existing Name</span>
                  <span className="font-semibold">{duplicateInfo.existing_lead.full_name || "—"}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Existing Phone</span>
                  <span className="font-semibold font-mono">{duplicateInfo.existing_lead.phone_normalized}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Lead ID</span>
                  <span className="font-mono text-xs text-slate-600 truncate block">
                    {duplicateInfo.existing_lead.id}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Status</span>
                  <StatusBadge status={duplicateInfo.existing_lead.status} />
                </div>
              </div>

              {/* Duplicate Actions */}
              <div className="flex flex-wrap items-center gap-2.5 pt-1">
                <Link
                  href={`/leads/${duplicateInfo.existing_lead.id}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white border border-amber-400 text-amber-900 rounded-lg hover:bg-amber-100 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open Existing Lead
                </Link>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setIsOverrideModalOpen(true)}
                  className="text-xs bg-amber-600 hover:bg-amber-700 text-white"
                >
                  Create Anyway
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDuplicateWarning(false)}
                  className="text-xs text-amber-800 hover:bg-amber-100/50"
                >
                  Dismiss Warning
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Lead Header Overview */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              {lead.full_name || "Unnamed Lead"}
            </h1>
            <StatusBadge status={lead.status} />
            {lead.duplicate_override && (
              <span className="bg-purple-50 text-purple-700 border border-purple-200 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                Duplicate Overridden
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 mt-2">
            <span className="flex items-center gap-1 font-mono">
              <Phone className="w-3.5 h-3.5 text-slate-400" />
              {lead.phone_normalized}
            </span>
            {lead.email && (
              <span className="flex items-center gap-1">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                {lead.email}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              Created {formatDate(lead.created_at)}
            </span>
          </div>
        </div>

        {/* Quick Check Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCheckDuplicate}
            isLoading={actionLoading}
            className="text-xs gap-1.5"
          >
            <Copy className="w-3.5 h-3.5 text-slate-500" />
            Check Duplicate
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCheckEligibility}
            isLoading={actionLoading}
            className="text-xs gap-1.5"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-slate-500" />
            Check Eligibility
          </Button>
        </div>
      </div>

      {/* Grid of Key Lead Management Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* 1. Phone Validation Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-sky-600" />
                Phone Validation
              </span>
              <StatusBadge status={lead.phone_normalized ? "VERIFIED" : "ERROR"} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Raw Phone Input</span>
              <span className="font-mono text-slate-700">{lead.phone}</span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Normalized (E.164)</span>
              <span className="font-mono font-semibold text-slate-900">{lead.phone_normalized}</span>
            </div>
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleValidatePhone}
                isLoading={actionLoading}
                className="w-full text-xs"
              >
                Re-validate Phone
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 2. Duplicate Status Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Copy className="w-4 h-4 text-amber-600" />
                Duplicate Status
              </span>
              <StatusBadge
                status={
                  lead.duplicate_override
                    ? "APPROVED"
                    : lead.status === "DUPLICATE" || duplicateInfo?.duplicate
                    ? "DUPLICATE"
                    : "ACTIVE"
                }
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">State</span>
              <span className="font-medium text-slate-800">
                {lead.duplicate_override
                  ? "Overridden by operator"
                  : duplicateInfo?.duplicate
                  ? "Potential duplicate flagged"
                  : "Unique lead"}
              </span>
            </div>
            {lead.duplicate_override && lead.duplicate_override_reason && (
              <div>
                <span className="text-xs text-slate-400 block">Override Reason</span>
                <p className="text-xs text-purple-900 bg-purple-50 p-2 rounded-lg border border-purple-200 mt-1">
                  {lead.duplicate_override_reason}
                </p>
              </div>
            )}
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCheckDuplicate}
                isLoading={actionLoading}
                className="w-full text-xs"
              >
                Re-check Duplicates
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 3. Contact Eligibility Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                Contact Eligibility
              </span>
              <StatusBadge status={lead.contact_eligibility} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Status</span>
              <span className="font-semibold text-slate-800">{lead.contact_eligibility}</span>
            </div>
            {eligibilityInfo?.reasons && eligibilityInfo.reasons.length > 0 && (
              <div>
                <span className="text-xs text-slate-400 block">Evaluation Signals</span>
                <ul className="text-xs space-y-1 text-slate-600 mt-1">
                  {eligibilityInfo.reasons.map((r, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                      {r.replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCheckEligibility}
                isLoading={actionLoading}
                className="w-full text-xs"
              >
                Re-evaluate Eligibility
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 4. Consent Status Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-indigo-600" />
                Consent Status
              </span>
              <StatusBadge status={lead.consent_status} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Recorded Consent</span>
              <span className="font-semibold text-slate-800">{lead.consent_status}</span>
            </div>
            <p className="text-xs text-slate-500">
              {lead.consent_status === "CONSENTED"
                ? "Lead explicitly consented to contact."
                : lead.consent_status === "NOT_CONSENTED"
                ? "Lead declined consent. Automated outreach blocked."
                : "Consent unknown. Cannot automatically qualify for outreach."}
            </p>
          </CardContent>
        </Card>

        {/* 5. Opt-Out Status Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Ban className="w-4 h-4 text-rose-600" />
                Opt-Out Status
              </span>
              <StatusBadge status={lead.opt_out_status} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Communication Channel</span>
              <span className="font-semibold text-slate-800">
                {lead.opt_out_status === "ACTIVE" ? "Active (Can Receive)" : "Opted Out (Blocked)"}
              </span>
            </div>
            <div className="pt-2 flex gap-2">
              {lead.opt_out_status === "ACTIVE" ? (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setIsOptOutModalOpen(true)}
                  className="w-full text-xs"
                >
                  Mark Opt-Out
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setIsRestoreModalOpen(true)}
                  className="w-full text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  Restore Contact
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 6. Lead Source Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-600" />
                Lead Source
              </span>
              {lead.source && <StatusBadge status={lead.source.source_type} />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Channel / Source</span>
              <span className="font-semibold text-slate-800">
                {lead.source ? lead.source.name : "Direct Intake (Manual)"}
              </span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Last Updated</span>
              <span className="text-slate-600">{formatDate(lead.updated_at)}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* MODULE 3: TENANT REQUIREMENTS & QUALIFICATION SECTION */}
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <Home className="w-5 h-5 text-sky-600" />
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Tenant Requirements & Qualification
            </h2>
            {liveStatus && <StatusBadge status={liveStatus.qualification_mode} />}
            {requirement && <StatusBadge status={requirement.qualification_status} />}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {requirement && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleToggleAIPause}
                isLoading={pauseResumeLoading}
                className={`text-xs gap-1.5 ${
                  liveStatus?.ai_paused || requirement.ai_paused
                    ? "border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                    : "border-amber-300 text-amber-700 hover:bg-amber-50"
                }`}
              >
                {liveStatus?.ai_paused || requirement.ai_paused ? (
                  <>
                    <Play className="w-3.5 h-3.5 text-emerald-600" />
                    Resume AI
                  </>
                ) : (
                  <>
                    <Pause className="w-3.5 h-3.5 text-amber-600" />
                    Pause AI
                  </>
                )}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setAnalyzeResult(null);
                setIsAnalyzeModalOpen(true);
              }}
              className="text-xs gap-1.5 border-sky-200 text-sky-700 hover:bg-sky-50"
            >
              <Bot className="w-3.5 h-3.5 text-sky-600" />
              Analyze Message (AI)
            </Button>
            {requirement && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsHistoryModalOpen(true)}
                className="text-xs gap-1.5"
              >
                <History className="w-3.5 h-3.5 text-slate-500" />
                View Field History
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsEditReqModalOpen(true)}
              className="text-xs gap-1.5"
            >
              <Edit3 className="w-3.5 h-3.5" />
              {requirement ? "Edit Requirements" : "Create Requirements"}
            </Button>
          </div>
        </div>

        {/* Live Qualification Status Card (Module 3 Phase 5) */}
        {liveStatus && (
          <div className="bg-gradient-to-r from-slate-50 to-sky-50/40 border border-sky-200/80 rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-sky-600" />
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Live Qualification Loop Status
                </span>
                <StatusBadge status={liveStatus.qualification_mode} />
                <StatusBadge status={liveStatus.qualification_status} />
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-600">
                <span>
                  Completion: <strong className="text-sky-700 font-mono">{liveStatus.completion_percentage}%</strong>
                </span>
                {liveStatus.last_ai_processing?.status === "FAILED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRetryProcessing(liveStatus.last_tenant_message?.id || liveStatus.last_ai_processing?.id!)}
                    isLoading={retryLoading}
                    className="text-2xs h-7 gap-1 border-rose-300 text-rose-700 hover:bg-rose-50"
                  >
                    <RotateCw className="w-3 h-3 text-rose-600" />
                    Retry Processing
                  </Button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 text-xs">
              <div className="bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
                <span className="text-2xs font-semibold text-slate-400 block mb-1 uppercase tracking-wider">
                  Last Tenant Message
                </span>
                {liveStatus.last_tenant_message ? (
                  <div className="space-y-1">
                    <p className="text-slate-800 font-medium italic">
                      &ldquo;{liveStatus.last_tenant_message.content}&rdquo;
                    </p>
                    <span className="text-2xs text-slate-400 block">
                      {formatDate(liveStatus.last_tenant_message.created_at)}
                    </span>
                  </div>
                ) : (
                  <span className="text-slate-400 italic">No inbound messages received yet</span>
                )}
              </div>

              <div className="bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
                <span className="text-2xs font-semibold text-slate-400 block mb-1 uppercase tracking-wider">
                  Last AI Processing Result
                </span>
                {liveStatus.last_ai_processing ? (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600">
                        Status: <strong className="text-slate-800">{liveStatus.last_ai_processing.status}</strong>
                      </span>
                      {liveStatus.last_ai_processing.intent && (
                        <span className="bg-sky-50 text-sky-700 px-1.5 py-0.5 rounded text-2xs font-mono font-semibold">
                          {liveStatus.last_ai_processing.intent}
                        </span>
                      )}
                    </div>
                    {liveStatus.last_ai_processing.error_code && (
                      <span className="text-2xs text-rose-600 block">
                        Error: {liveStatus.last_ai_processing.error_code}
                      </span>
                    )}
                    <span className="text-2xs text-slate-400 block">
                      {formatDate(liveStatus.last_ai_processing.created_at)}
                    </span>
                  </div>
                ) : (
                  <span className="text-slate-400 italic">No AI processing history</span>
                )}
              </div>

              <div className="bg-white p-3 rounded-xl border border-slate-200/80 shadow-xs">
                <span className="text-2xs font-semibold text-slate-400 block mb-1 uppercase tracking-wider">
                  Last Outbound Question Sent
                </span>
                {liveStatus.last_outbound_question ? (
                  <div className="space-y-1">
                    <p className="text-slate-800 font-medium italic">
                      &ldquo;{liveStatus.last_outbound_question.content}&rdquo;
                    </p>
                    <span className="text-2xs text-slate-400 block">
                      {formatDate(liveStatus.last_outbound_question.created_at)}
                    </span>
                  </div>
                ) : (
                  <span className="text-slate-400 italic">No outbound question sent yet</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Module 3 Phase 7: Human Escalation & Review Banner */}
        {(() => {
          const activeEsc = escalations.find((e) => e.status === "OPEN" || e.status === "ASSIGNED");
          const isHumanReview = requirement?.qualification_status === "NEEDS_HUMAN_REVIEW" || !!activeEsc;
          const aiMode = requirement?.ai_paused
            ? "PAUSED"
            : activeEsc?.status === "ASSIGNED"
            ? "HUMAN_TAKEOVER"
            : "ACTIVE";

          return (
            <div className={`p-5 rounded-2xl border shadow-xs space-y-3 ${
              isHumanReview
                ? "bg-amber-50/70 border-amber-300 dark:bg-amber-950/20 dark:border-amber-800"
                : "bg-white border-slate-200"
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <ShieldAlert className={`w-5 h-5 ${isHumanReview ? "text-amber-600" : "text-slate-400"}`} />
                  <span className="text-sm font-bold text-slate-900">
                    Human Escalation & Review Controls
                  </span>
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                    aiMode === "ACTIVE"
                      ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                      : aiMode === "HUMAN_TAKEOVER"
                      ? "bg-purple-100 text-purple-800 border border-purple-200"
                      : "bg-rose-100 text-rose-800 border border-rose-200"
                  }`}>
                    AI Mode: {aiMode}
                  </span>
                  <span className={`text-xs px-2.5 py-0.5 rounded-full ${
                    isHumanReview ? "bg-amber-100 text-amber-800 font-bold" : "bg-slate-100 text-slate-600"
                  }`}>
                    Human Review: {isHumanReview ? "YES" : "NO"}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {aiMode !== "HUMAN_TAKEOVER" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleTakeover}
                      disabled={actionLoading}
                      className="text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
                    >
                      <UserCheck className="w-3.5 h-3.5 mr-1" />
                      Take Over
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setOperatorMsgContent("");
                      setIsOperatorMsgModalOpen(true);
                    }}
                    className="text-xs border-sky-300 text-sky-700 hover:bg-sky-50"
                  >
                    <MessageSquare className="w-3.5 h-3.5 mr-1" />
                    Send Operator Message
                  </Button>
                  {isHumanReview && (
                    <Button
                      size="sm"
                      className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => {
                        setEscalationResolutionNotes("");
                        setIsResolveEscalationModalOpen(true);
                      }}
                      disabled={actionLoading}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                      Return to AI
                    </Button>
                  )}
                  {!activeEsc && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEscalateReason("OPERATOR_TAKEOVER");
                        setEscalateDescription("");
                        setIsEscalateModalOpen(true);
                      }}
                      className="text-xs text-slate-500"
                    >
                      Escalate Lead
                    </Button>
                  )}
                </div>
              </div>

              {activeEsc && (
                <div className="bg-white/90 p-3 rounded-xl border border-amber-200 text-xs text-slate-800 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <span className="font-semibold text-amber-900">Escalation Reason: </span>
                    <span className="font-mono">{activeEsc.reason_code}</span>
                    {activeEsc.description && <span className="ml-2 italic text-slate-500">({activeEsc.description})</span>}
                  </div>
                  <div>
                    <span className="text-slate-500">Assigned: </span>
                    <strong>{activeEsc.assigned_to || "Unassigned"}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Opened: </span>
                    <span>{formatDate(activeEsc.created_at)}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* Module 3 Phase 8: Operational Memory & Conversation Summary Dashboard */}
        <div className="mb-6 space-y-4">
          <div className="bg-gradient-to-r from-slate-900 to-indigo-950 text-white p-5 rounded-2xl shadow-sm border border-slate-800">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-300">
                  <Sparkles className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold tracking-wide flex items-center gap-2">
                    Operational Conversation Summary
                    {dashboardData?.summary && (
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-white/10 text-indigo-200">
                        v{dashboardData.summary.summary_version} • {dashboardData.summary.generated_by}
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Compact operational context synthesized from validated criteria & recent messages
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRefreshSummary}
                  disabled={summaryLoading || actionLoading}
                  className="text-xs bg-white/5 border-white/20 text-white hover:bg-white/10"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${summaryLoading ? "animate-spin" : ""}`} />
                  Refresh Summary
                </Button>
              </div>
            </div>

            {/* Summary Text Body */}
            <div className="py-3">
              <p className="text-sm leading-relaxed text-slate-200 font-sans">
                {dashboardData?.summary?.summary_text || (
                  <span className="text-slate-400 italic">
                    No summary generated yet. Click &ldquo;Refresh Summary&rdquo; to build one from validated requirements.
                  </span>
                )}
              </p>
            </div>

            {/* Structured Summary Metadata Chips */}
            {dashboardData?.summary?.structured_summary && (
              <div className="pt-3 border-t border-white/10 flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-400 text-[11px] uppercase font-semibold">Structured State:</span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-medium">
                  Status: {dashboardData.summary.structured_summary.qualification_status || "IN_PROGRESS"}
                </span>
                {dashboardData.summary.structured_summary.missing_fields && dashboardData.summary.structured_summary.missing_fields.length > 0 && (
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">
                    Missing: {dashboardData.summary.structured_summary.missing_fields.join(", ")}
                  </span>
                )}
                {dashboardData.summary.structured_summary.clarifications && dashboardData.summary.structured_summary.clarifications.length > 0 && (
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-medium">
                    Clarify: {dashboardData.summary.structured_summary.clarifications.join(", ")}
                  </span>
                )}
                {dashboardData.next_action?.label && (
                  <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-medium ml-auto">
                    Next: {dashboardData.next_action.label}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Operator Notes & Next Expected Action Bar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Next Expected Action Panel */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Next Expected Action</span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                    {dashboardData?.next_action?.action || "ASK_FIELD"}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-slate-900 mb-1">
                  {dashboardData?.next_action?.label || "Collect Requirements"}
                </h4>
                <p className="text-xs text-slate-600">
                  {dashboardData?.next_action?.description || "Awaiting tenant response or next missing criteria."}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>Completion:</span>
                <span className="font-semibold text-slate-800">{dashboardData?.completion_percentage || requirement?.completion_percentage || 0}%</span>
              </div>
            </div>

            {/* Operator Notes Panel (2 cols) */}
            <div className="md:col-span-2 bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" />
                  Internal Operator Notes ({dashboardData?.operator_notes?.length || 0})
                </span>
                <span className="text-[10px] text-slate-400">Kept internal; never sent to tenant</span>
              </div>

              {/* Notes list */}
              <div className="space-y-1.5 max-h-28 overflow-y-auto pr-1 my-1">
                {(!dashboardData?.operator_notes || dashboardData.operator_notes.length === 0) ? (
                  <p className="text-xs text-slate-400 italic py-1">No operator notes recorded yet.</p>
                ) : (
                  dashboardData.operator_notes.map((note) => (
                    <div key={note.id} className="text-xs bg-slate-50 p-2 rounded-lg border border-slate-100 flex items-start justify-between gap-2">
                      <span className="text-slate-800">{note.note}</span>
                      <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                        {note.author_id} • {formatDate(note.created_at)}
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* Add Note Input */}
              <form onSubmit={handleAddNote} className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-2">
                <Input
                  placeholder="Add internal operator note..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  className="text-xs h-8 flex-1"
                />
                <Button size="sm" type="submit" disabled={noteLoading || !newNote.trim()} className="text-xs">
                  <Send className="w-3 h-3 mr-1" />
                  Add
                </Button>
              </form>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Requirements Detail Card (2 cols) */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold flex items-center justify-between">
                  <span>Structured Requirements Profile</span>
                  {requirement && <StatusBadge status={requirement.qualification_status} />}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!requirement ? (
                  <div className="py-8 text-center text-slate-500">
                    <p className="text-sm">No tenant requirements recorded yet for this lead.</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Click &ldquo;Create Requirements&rdquo; to input budget, preferred locations, and rental criteria.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                    {/* Preferred Locations */}
                    <div className="sm:col-span-2 bg-slate-50 p-3 rounded-xl border border-slate-100">
                      <span className="text-xs text-slate-500 block mb-1.5 font-medium">Preferred Locations</span>
                      {requirement.preferred_locations && requirement.preferred_locations.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {requirement.preferred_locations.map((loc, i) => (
                            <span
                              key={i}
                              className="bg-white border border-slate-200 text-slate-800 text-xs px-2.5 py-0.5 rounded-md font-medium"
                            >
                              {loc}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Not specified</span>
                      )}
                    </div>

                    {/* Budget with Confidence Badge */}
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs text-slate-500">Monthly Budget</span>
                        {requirement.budget_max !== null ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                            Confidence: High
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            Missing
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-slate-900 font-mono">
                        {requirement.budget_min !== null || requirement.budget_max !== null ? (
                          <>
                            {requirement.currency}{" "}
                            {requirement.budget_min !== null ? requirement.budget_min : "Any"} -{" "}
                            {requirement.budget_max !== null ? requirement.budget_max : "Any"}
                          </>
                        ) : (
                          <span className="text-slate-400 font-sans italic">Not specified</span>
                        )}
                      </span>
                    </div>

                    {/* Property Type & Bedrooms */}
                    <div>
                      <span className="text-xs text-slate-500 block mb-0.5">Property Type / Bedrooms</span>
                      <span className="font-semibold text-slate-900">
                        {requirement.property_type || "Any type"}
                        {requirement.bedrooms !== null ? ` • ${requirement.bedrooms} Bed` : ""}
                      </span>
                    </div>

                    {/* Move-in Date with Confidence Badge */}
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs text-slate-500">Target Move-in Date</span>
                        {requirement.move_in_date ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                            Confidence: High
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
                            Needs confirmation
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-slate-900">
                        {requirement.move_in_date || <span className="text-slate-400 italic font-normal">Not specified</span>}
                      </span>
                    </div>

                    {/* Lease Duration with Confidence Badge */}
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs text-slate-500">Lease Duration</span>
                        {requirement.lease_duration_months ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                            Confidence: High
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            Missing
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-slate-900">
                        {requirement.lease_duration_months ? (
                          `${requirement.lease_duration_months} Months`
                        ) : (
                          <span className="text-slate-400 italic font-normal">Not specified</span>
                        )}
                      </span>
                    </div>

                    {/* Occupants with Confidence Badge */}
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs text-slate-500">Occupants</span>
                        {requirement.occupants ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                            Confidence: High
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            Missing
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-slate-900">
                        {requirement.occupants ? (
                          `${requirement.occupants} Person(s)`
                        ) : (
                          <span className="text-slate-400 italic font-normal">Not specified</span>
                        )}
                      </span>
                    </div>

                    {/* Furnishing */}
                    <div>
                      <span className="text-xs text-slate-500 block mb-0.5">Furnishing Preference</span>
                      <span className="font-semibold text-slate-900">
                        {requirement.furnishing ? (
                          requirement.furnishing.replace(/_/g, " ")
                        ) : (
                          <span className="text-slate-400 italic font-normal">Flexible</span>
                        )}
                      </span>
                    </div>

                    {/* Special Requirements */}
                    {requirement.special_requirements && (
                      <div className="sm:col-span-2 pt-2 border-t border-slate-100">
                        <span className="text-xs text-slate-500 block mb-1">Special Requirements</span>
                        <pre className="text-xs text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-mono overflow-x-auto">
                          {JSON.stringify(requirement.special_requirements, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Qualification Progress & Decision Cards (1 col) */}
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <ListChecks className="w-4 h-4 text-sky-600" />
                    Qualification Progress
                  </span>
                  <span className="text-sm font-bold text-sky-600">
                    {progress ? `${progress.completion_percentage}%` : "0%"}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Progress Bar */}
                <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-sky-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${progress ? progress.completion_percentage : 0}%` }}
                  />
                </div>

                {/* Progress Status Indicator */}
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Status:</span>
                  <span className="font-semibold text-slate-800">
                    {progress ? progress.qualification_status.replace(/_/g, " ") : "NOT STARTED"}
                  </span>
                </div>

                {/* Completed Fields */}
                <div>
                  <span className="text-2xs font-bold text-emerald-800 uppercase tracking-wider block mb-1.5">
                    Completed Fields
                  </span>
                  {progress && progress.completed_fields.length > 0 ? (
                    <div className="space-y-1">
                      {progress.completed_fields.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs text-emerald-700">
                          <Check className="w-3.5 h-3.5 shrink-0 text-emerald-600" />
                          <span>{f.replace(/_/g, " ")}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400 italic">None completed</span>
                  )}
                </div>

                {/* Missing Required Fields */}
                <div className="pt-2 border-t border-slate-100">
                  <span className="text-2xs font-bold text-amber-800 uppercase tracking-wider block mb-1.5">
                    Missing Required Fields
                  </span>
                  {progress && progress.missing_fields.length > 0 ? (
                    <div className="space-y-1">
                      {progress.missing_fields.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs text-amber-800">
                          <Clock className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                          <span>{f.replace(/_/g, " ")}</span>
                        </div>
                      ))}
                    </div>
                  ) : progress ? (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      All required fields completed!
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400 italic">No requirement profile</span>
                  )}
                </div>

                {/* Clarification Required Fields (Phase 4) */}
                {((qualificationPreview?.clarification_fields && qualificationPreview.clarification_fields.length > 0) ||
                  (nextQuestion?.clarification_fields && nextQuestion.clarification_fields.length > 0)) && (
                  <div className="pt-2 border-t border-rose-100 bg-rose-50/50 p-2.5 rounded-lg border">
                    <span className="text-2xs font-bold text-rose-800 uppercase tracking-wider block mb-1.5 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3 text-rose-600" />
                      Clarification Required
                    </span>
                    <div className="space-y-1">
                      {(nextQuestion?.clarification_fields || qualificationPreview?.clarification_fields || []).map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs text-rose-700 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                          <span>{f.replace(/_/g, " ")} (Ambiguous / Needs Confirmation)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Next Question Engine (Phase 4) */}
                <div className="pt-3 border-t border-slate-100 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-2xs font-bold text-sky-900 uppercase tracking-wider flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-sky-600" />
                      Next Question Target
                    </span>
                    {(nextQuestion?.action || qualificationPreview?.next_question?.action) && (
                      <span className={`text-2xs font-bold px-2 py-0.5 rounded-full ${
                        (nextQuestion?.action || qualificationPreview?.next_question?.action) === "NO_QUESTION"
                          ? "bg-emerald-100 text-emerald-800"
                          : (nextQuestion?.action || qualificationPreview?.next_question?.action) === "HUMAN_REVIEW"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-sky-100 text-sky-800"
                      }`}>
                        {(nextQuestion?.action || qualificationPreview?.next_question?.action || "").replace(/_/g, " ")}
                      </span>
                    )}
                  </div>

                  {/* Target Field Info */}
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Target Field:</span>
                      <span className="font-semibold text-slate-800">
                        {nextQuestion?.field
                          ? nextQuestion.field.replace(/_/g, " ")
                          : qualificationPreview?.next_question?.field
                          ? qualificationPreview.next_question.field.replace(/_/g, " ")
                          : (nextQuestion?.action || qualificationPreview?.next_question?.action) === "NO_QUESTION"
                          ? "None (All Complete)"
                          : "Pending Selection"}
                      </span>
                    </div>

                    {/* Preview Text */}
                    {(nextQuestion?.question_text || qualificationPreview?.next_question?.preview_text) && (
                      <div className="pt-1.5 border-t border-slate-200/60">
                        <span className="text-2xs text-slate-500 block mb-1">Generated Question Preview:</span>
                        <div className="p-2 bg-white rounded border border-sky-100 text-xs text-sky-900 italic font-sans relative">
                          &ldquo;{nextQuestion?.question_text || qualificationPreview?.next_question?.preview_text}&rdquo;
                        </div>
                        <div className="mt-1 flex items-center justify-between text-2xs text-slate-400">
                          <span>
                            {nextQuestion?.fallback_used
                              ? "Deterministic Fallback Template"
                              : nextQuestion
                              ? "AI Phrased via Orchestrator"
                              : "Heuristic Preview"}
                          </span>
                          {nextQuestion && (
                            <span className="text-sky-600 font-medium">Status: GENERATED</span>
                          )}
                        </div>
                      </div>
                    )}

                    {(nextQuestion?.action === "HUMAN_REVIEW" || qualificationPreview?.next_question?.action === "HUMAN_REVIEW") && (
                      <div className="pt-1.5 border-t border-slate-200/60 text-xs text-rose-700 font-medium">
                        Escalated to Human Operator review (reason: {nextQuestion?.reason || qualificationPreview?.next_question?.reason}).
                      </div>
                    )}
                  </div>

                  {/* Action Button: Generate Next Question (Admin trigger, NO send button) */}
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full text-xs gap-1.5 bg-sky-600 hover:bg-sky-700"
                    disabled={questionLoading || !requirement}
                    onClick={() => handleGenerateNextQuestion(false)}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    {questionLoading ? "Determining Next Question..." : "Generate Next Question"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Qualification Decision Card (Module 3 Phase 6) */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Scale className="w-4 h-4 text-purple-600" />
                    Qualification Decision
                  </span>
                  {latestDecision && (
                    <span
                      className={`text-2xs font-bold px-2 py-0.5 rounded-full ${
                        latestDecision.decision === "QUALIFIED"
                          ? "bg-emerald-100 text-emerald-800"
                          : latestDecision.decision === "NEEDS_HUMAN_REVIEW"
                          ? "bg-amber-100 text-amber-800"
                          : latestDecision.decision === "DISQUALIFIED"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      {latestDecision.decision.replace(/_/g, " ")}
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3.5">
                {latestDecision ? (
                  <div className="space-y-2.5 text-xs">
                    {/* Meta summary */}
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Rule Version:</span>
                        <span className="font-mono font-medium text-slate-800">{latestDecision.rule_version}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Evaluated By:</span>
                        <span className="font-semibold text-slate-700">
                          {latestDecision.evaluated_by} ({latestDecision.evaluation_source})
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Completion:</span>
                        <span className="font-bold text-slate-800">{latestDecision.completion_percentage}%</span>
                      </div>
                      {(latestDecision.evaluated_at || latestDecision.created_at) && (
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500">Last Evaluated:</span>
                          <span className="text-slate-600">{formatDate((latestDecision.evaluated_at || latestDecision.created_at)!)}</span>
                        </div>
                      )}
                    </div>

                    {/* Reason Codes */}
                    <div>
                      <span className="text-2xs font-bold text-slate-500 uppercase tracking-wider block mb-1">
                        Reason Codes
                      </span>
                      {latestDecision.reason_codes && latestDecision.reason_codes.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {latestDecision.reason_codes.map((rc, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-3xs border border-slate-200"
                            >
                              {rc}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">None</span>
                      )}
                    </div>

                    {/* Blocking Fields */}
                    {latestDecision.blocking_fields && latestDecision.blocking_fields.length > 0 && (
                      <div className="p-2 rounded-lg bg-rose-50 border border-rose-200">
                        <span className="text-2xs font-bold text-rose-800 uppercase tracking-wider block mb-1 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 text-rose-600" />
                          Blocking Fields
                        </span>
                        <div className="space-y-0.5">
                          {latestDecision.blocking_fields.map((f, i) => (
                            <div key={i} className="text-xs text-rose-700 font-medium">
                              • {f.replace(/_/g, " ")}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic py-1">
                    No qualification decision evaluated yet. Click below to evaluate deterministic rules.
                  </p>
                )}

                {/* Buttons: Evaluate Decision & Human Override */}
                <div className="space-y-2 pt-1 border-t border-slate-100">
                  <div className="flex gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      className="flex-1 text-xs gap-1.5 bg-purple-600 hover:bg-purple-700 text-white"
                      disabled={evalModalLoading || !requirement}
                      onClick={handlePreviewEvaluation}
                    >
                      <Scale className="w-3.5 h-3.5" />
                      {evalModalLoading ? "Evaluating..." : "Evaluate Decision"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs gap-1 border-amber-300 text-amber-800 hover:bg-amber-50"
                      onClick={() => setIsDecisionOverrideModalOpen(true)}
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      Override
                    </Button>
                  </div>

                  {decisionHistory.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full text-xs text-slate-500 hover:text-slate-700"
                      onClick={() => setIsDecisionHistoryModalOpen(true)}
                    >
                      <History className="w-3.5 h-3.5 mr-1" />
                      View Decision History ({decisionHistory.length})
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Module 3 Phase 7: Clarifications Card */}
      {clarifications.length > 0 && (
        <Card className="border border-amber-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                Active Clarifications & Field Confirmations ({clarifications.length})
              </span>
              <span className="text-xs text-slate-500 font-normal">Max 2 attempts per field</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {clarifications.map((c) => (
                <div
                  key={c.id}
                  className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-800 font-mono">{c.field_name}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                        c.status === "RESOLVED"
                          ? "bg-emerald-100 text-emerald-800"
                          : c.status === "WAITING_FOR_TENANT" || c.status === "OPEN"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-slate-100 text-slate-700"
                      }`}>
                        {c.status}
                      </span>
                      <span className="text-slate-500 font-mono">
                        Attempts: {c.attempt_count}/2
                      </span>
                    </div>
                    <p className="text-slate-600">
                      <span className="font-semibold text-slate-800">Proposed: </span>
                      {String(c.proposed_value ?? "None")} • <span className="font-semibold text-slate-800">Reason: </span>
                      {c.reason}
                    </p>
                  </div>

                  {(c.status === "OPEN" || c.status === "WAITING_FOR_TENANT") && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleResolveClarification(c.id, "CONFIRM")}
                        className="text-xs text-emerald-700 border-emerald-300 hover:bg-emerald-50 h-7 px-2"
                      >
                        Confirm Value
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleResolveClarification(c.id, "REJECT")}
                        className="text-xs text-rose-700 hover:bg-rose-50 h-7 px-2"
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Module 3 Phase 10: Conversation History & Message Thread Section */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2 text-slate-900">
            <MessageSquare className="w-5 h-5 text-sky-600" />
            Qualification Conversation Thread
            {dashboardData?.recent_messages && dashboardData.recent_messages.length > 0 && (
              <span className="text-xs font-normal text-slate-500">
                ({dashboardData.recent_messages.length} messages)
              </span>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setOperatorMsgContent("");
                setIsOperatorMsgModalOpen(true);
              }}
              className="text-xs border-sky-300 text-sky-700 hover:bg-sky-50"
            >
              <Send className="w-3.5 h-3.5 mr-1" />
              Send Operator Message
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {(!dashboardData?.recent_messages || dashboardData.recent_messages.length === 0) ? (
            <div className="py-8 text-center text-slate-500">
              <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-medium">No conversation messages recorded yet.</p>
              <p className="text-xs text-slate-400 mt-0.5">
                Inbound WhatsApp replies from the tenant or outgoing assistant inquiries will appear here chronologically.
              </p>
            </div>
          ) : (
            <div className="space-y-4 max-h-[500px] overflow-y-auto p-2 pr-3">
              {dashboardData.recent_messages.map((msg) => {
                const isTenant = msg.sender_type === "TENANT" || msg.direction === "INBOUND";
                const isHuman = msg.sender_type === "HUMAN OPERATOR";
                const isSystem = msg.sender_type === "SYSTEM EVENT";

                if (isSystem) {
                  return (
                    <div key={msg.id} className="flex justify-center my-2">
                      <span className="px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-mono border border-slate-200">
                        {msg.content} • {formatDate(msg.timestamp)}
                      </span>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isTenant ? "items-start" : "items-end"}`}
                  >
                    {/* Header badge */}
                    <div className="flex items-center gap-1.5 mb-1 px-1">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          isTenant
                            ? "bg-slate-200 text-slate-700"
                            : isHuman
                            ? "bg-purple-100 text-purple-800 border border-purple-200"
                            : "bg-sky-100 text-sky-800 border border-sky-200"
                        }`}
                      >
                        {msg.sender_type || (isTenant ? "TENANT" : "AI ASSISTANT")}
                      </span>
                      {msg.timestamp && (
                        <span className="text-[10px] text-slate-400">
                          {formatDate(msg.timestamp)}
                        </span>
                      )}
                      {msg.delivery_status && !isTenant && (
                        <span className="text-[10px] text-emerald-600 font-medium">
                          • {msg.delivery_status}
                        </span>
                      )}
                    </div>

                    {/* Bubble */}
                    <div
                      className={`max-w-lg rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-2xs ${
                        isTenant
                          ? "bg-slate-100 text-slate-900 rounded-tl-sm border border-slate-200"
                          : isHuman
                          ? "bg-purple-50 text-purple-950 rounded-tr-sm border border-purple-200"
                          : "bg-sky-50 text-sky-950 rounded-tr-sm border border-sky-200"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Module 4 Phase 3: Property Matching & Candidate Search */}
      <PropertyMatchingSection
        leadId={leadId}
        qualificationStatus={requirement?.qualification_status || lead.status}
        onRefreshLead={loadLeadData}
      />

      {/* Module 5 Phase 2: Tenant Property Presentation & Interest Capture */}
      <LeadPropertyPresentationSection
        leadId={leadId}
        isQualified={
          requirement?.qualification_status === "QUALIFIED" ||
          requirement?.qualification_status === "QUALIFICATION_COMPLETE"
        }
      />

      {/* Module 5 Phase 1: Viewing Coordination */}
      <LeadViewingsSection
        leadId={leadId}
        isQualified={
          requirement?.qualification_status === "QUALIFIED" ||
          requirement?.qualification_status === "QUALIFICATION_COMPLETE"
        }
      />

      {/* Activity / Audit History Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-500" />
            Lead Activity & Audit History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {auditLogs.length === 0 ? (
            <p className="text-sm text-slate-500 py-4 text-center">No audit records recorded yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {auditLogs.map((log) => (
                <div key={log.id} className="py-3 flex items-start justify-between text-sm">
                  <div>
                    <span className="font-semibold text-slate-800">{log.action.replace(/_/g, " ")}</span>
                    <span className="text-xs text-slate-500 ml-2">by {log.actor_id}</span>
                    {log.new_value && (
                      <pre className="text-xs text-slate-600 bg-slate-50 p-2 rounded-md mt-1 overflow-x-auto max-w-xl font-mono">
                        {JSON.stringify(log.new_value, null, 2)}
                      </pre>
                    )}
                  </div>
                  <span className="text-xs text-slate-400 shrink-0 ml-4">
                    {formatDate(log.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* MODAL: DUPLICATE OVERRIDE */}
      <Modal
        isOpen={isOverrideModalOpen}
        onClose={() => setIsOverrideModalOpen(false)}
        title="Override Duplicate Lead"
      >
        <form onSubmit={handleOverrideDuplicate} className="space-y-4">
          <p className="text-sm text-slate-600">
            Proceeding will mark this lead as an authorized separate record and restore its status to Validating.
            An audit log will be created.
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Required Reason for Override *
            </label>
            <textarea
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-sky-500 focus:outline-hidden"
              rows={3}
              placeholder="e.g. Customer confirmed separate inquiry for a 2-bedroom unit"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              required
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsOverrideModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={actionLoading}
            >
              Confirm Override
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: MARK OPT-OUT */}
      <Modal
        isOpen={isOptOutModalOpen}
        onClose={() => setIsOptOutModalOpen(false)}
        title="Mark Lead as Opted Out"
      >
        <form onSubmit={handleMarkOptOut} className="space-y-4">
          <p className="text-sm text-slate-600">
            This will immediately prevent any automated or manual WhatsApp outreach to this phone number.
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Opt-out Reason / Note (Optional)
            </label>
            <Input
              placeholder="e.g. Replied STOP on SMS"
              value={optOutReason}
              onChange={(e) => setOptOutReason(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsOptOutModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              size="sm"
              isLoading={actionLoading}
            >
              Confirm Opt-Out
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: RESTORE CONTACT */}
      <Modal
        isOpen={isRestoreModalOpen}
        onClose={() => setIsRestoreModalOpen(false)}
        title="Restore Contact Status"
      >
        <form onSubmit={handleRestoreContact} className="space-y-4">
          <p className="text-sm text-slate-600">
            Restoring an opted-out contact requires operator authorization and compliance verification.
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Authorized By (Compliance Officer / Admin) *
            </label>
            <Input
              placeholder="e.g. compliance_admin_1"
              value={restoreAuthorizedBy}
              onChange={(e) => setRestoreAuthorizedBy(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Re-opt-in Reason / Documentation *
            </label>
            <textarea
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-sky-500 focus:outline-hidden"
              rows={2}
              placeholder="e.g. Customer provided written re-consent via email ticket #1024"
              value={restoreReason}
              onChange={(e) => setRestoreReason(e.target.value)}
              required
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsRestoreModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              isLoading={actionLoading}
            >
              Authorize & Restore
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: EDIT / CREATE TENANT REQUIREMENTS (MODULE 3) */}
      <Modal
        isOpen={isEditReqModalOpen}
        onClose={() => setIsEditReqModalOpen(false)}
        title={requirement ? "Edit Tenant Requirements" : "Create Tenant Requirements"}
      >
        <form onSubmit={handleSaveRequirements} className="space-y-4 max-h-[75vh] overflow-y-auto px-1">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Preferred Locations (Comma separated)
            </label>
            <Input
              placeholder="e.g. Novena, Newton, Orchard"
              value={reqForm.preferred_locations}
              onChange={(e) => setReqForm({ ...reqForm, preferred_locations: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Budget Min</label>
              <Input
                type="number"
                placeholder="e.g. 3000"
                value={reqForm.budget_min}
                onChange={(e) => setReqForm({ ...reqForm, budget_min: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Budget Max</label>
              <Input
                type="number"
                placeholder="e.g. 3500"
                value={reqForm.budget_max}
                onChange={(e) => setReqForm({ ...reqForm, budget_max: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Property Type</label>
              <select
                className="w-full py-2 px-3 border border-slate-200 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-sky-500"
                value={reqForm.property_type}
                onChange={(e) => setReqForm({ ...reqForm, property_type: e.target.value })}
              >
                <option value="Condo">Condo</option>
                <option value="HDB">HDB</option>
                <option value="Landed">Landed</option>
                <option value="Apartment">Apartment</option>
                <option value="Studio">Studio</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Bedrooms</label>
              <Input
                type="number"
                placeholder="e.g. 2"
                value={reqForm.bedrooms}
                onChange={(e) => setReqForm({ ...reqForm, bedrooms: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Move-in Date</label>
              <Input
                type="date"
                value={reqForm.move_in_date}
                onChange={(e) => setReqForm({ ...reqForm, move_in_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Lease (Months)</label>
              <Input
                type="number"
                placeholder="12"
                value={reqForm.lease_duration_months}
                onChange={(e) => setReqForm({ ...reqForm, lease_duration_months: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Occupants</label>
              <Input
                type="number"
                placeholder="1"
                value={reqForm.occupants}
                onChange={(e) => setReqForm({ ...reqForm, occupants: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Furnishing</label>
              <select
                className="w-full py-2 px-3 border border-slate-200 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-sky-500"
                value={reqForm.furnishing}
                onChange={(e) => setReqForm({ ...reqForm, furnishing: e.target.value })}
              >
                <option value="FURNISHED">Furnished</option>
                <option value="PARTIALLY_FURNISHED">Partially Furnished</option>
                <option value="UNFURNISHED">Unfurnished</option>
                <option value="FLEXIBLE">Flexible</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Special Requirements (JSON or Notes)
            </label>
            <textarea
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-sky-500 focus:outline-hidden font-mono"
              rows={2}
              placeholder='e.g. {"pets": true, "near_mrt": true}'
              value={reqForm.special_requirements}
              onChange={(e) => setReqForm({ ...reqForm, special_requirements: e.target.value })}
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsEditReqModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={actionLoading}
            >
              Save Requirements
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: FIELD PROVENANCE & HISTORY (MODULE 3) */}
      <Modal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        title="Requirement Field History & Traceability"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto px-1">
          <p className="text-xs text-slate-500">
            Traceability log of all tenant requirements collected, showing historical supersessions and operator edits.
          </p>

          {requirementHistory.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">No field mutation history recorded yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {requirementHistory.map((item) => (
                <div key={item.id} className="py-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm text-slate-900">
                      {item.field_name.replace(/_/g, " ")}
                    </span>
                    <StatusBadge status={item.status} />
                  </div>
                  <div className="flex flex-wrap items-center justify-between text-xs text-slate-600 gap-2">
                    <div>
                      Value: <span className="font-semibold font-mono text-slate-800">{JSON.stringify(item.value)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {item.confidence !== null && item.confidence !== undefined && (
                        <span className="text-2xs font-semibold px-1.5 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-100 font-mono">
                          Confidence: {(Number(item.confidence) * 100).toFixed(0)}%
                        </span>
                      )}
                      <span className="text-2xs text-slate-400">
                        Source: {item.source_type.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>
                  {item.source_message_id && (
                    <div className="text-3xs text-slate-400 font-mono">
                      Message Ref: {item.source_message_id}
                    </div>
                  )}
                  <div className="text-3xs text-slate-400">
                    Updated: {formatDate(item.created_at)}
                  </div>

                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsHistoryModalOpen(false)}
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL: ANALYZE TENANT MESSAGE (MODULE 3 PHASE 3) */}
      <Modal
        isOpen={isAnalyzeModalOpen}
        onClose={() => setIsAnalyzeModalOpen(false)}
        title="Analyze Inbound Tenant Message (AI Understanding)"
      >
        <form onSubmit={handleAnalyzeMessage} className="space-y-4">
          <p className="text-xs text-slate-500 leading-relaxed">
            Module 3 Phase 3 AI extraction: evaluate intent, search criteria, confidence scores, and clarification triggers.
            Testing this will NOT send any WhatsApp response or mark the lead qualified.
          </p>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Sample Tenant Message / Reply Text *
            </label>
            <textarea
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-sky-500 focus:outline-hidden"
              rows={3}
              placeholder="e.g. I am looking for a furnished 2 bedroom condo near Novena. Budget around 3500 and I want to move next month."
              value={analyzeText}
              onChange={(e) => setAnalyzeText(e.target.value)}
              required
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsAnalyzeModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={analyzeLoading}
              className="gap-1.5 bg-sky-600 hover:bg-sky-700"
            >
              <Bot className="w-3.5 h-3.5" />
              Analyze Message
            </Button>
          </div>

          {analyzeResult && (
            <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 text-xs">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <span className="font-semibold text-slate-700">Intent Analysis</span>
                <span className="font-mono font-bold px-2 py-0.5 rounded bg-sky-100 text-sky-800">
                  {analyzeResult.intent} ({(analyzeResult.intent_confidence * 100).toFixed(0)}%)
                </span>
              </div>

              {analyzeResult.message_summary && (
                <div>
                  <span className="text-slate-400 font-medium block">Summary:</span>
                  <span className="text-slate-700">{analyzeResult.message_summary}</span>
                </div>
              )}

              <div className="grid grid-cols-3 gap-2">
                <div className="p-2 rounded bg-emerald-50 border border-emerald-100">
                  <span className="text-2xs font-semibold text-emerald-800 block">Accepted</span>
                  <span className="font-mono font-bold text-emerald-900">
                    {analyzeResult.accepted_fields?.length || 0} fields
                  </span>
                </div>
                <div className="p-2 rounded bg-amber-50 border border-amber-100">
                  <span className="text-2xs font-semibold text-amber-800 block">Proposed</span>
                  <span className="font-mono font-bold text-amber-900">
                    {analyzeResult.proposed_fields?.length || 0} fields
                  </span>
                </div>
                <div className="p-2 rounded bg-rose-50 border border-rose-100">
                  <span className="text-2xs font-semibold text-rose-800 block">Clarification</span>
                  <span className="font-mono font-bold text-rose-900">
                    {analyzeResult.clarification_fields?.length || 0} fields
                  </span>
                </div>
              </div>

              {analyzeResult.accepted_fields && analyzeResult.accepted_fields.length > 0 && (
                <div>
                  <span className="text-2xs font-bold text-emerald-700 block mb-1">Accepted Criteria:</span>
                  <div className="flex flex-wrap gap-1">
                    {analyzeResult.accepted_fields.map((f: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono text-3xs">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {analyzeResult.clarification_fields && analyzeResult.clarification_fields.length > 0 && (
                <div>
                  <span className="text-2xs font-bold text-amber-700 block mb-1">Needs Clarification:</span>
                  <div className="flex flex-wrap gap-1">
                    {analyzeResult.clarification_fields.map((f: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-mono text-3xs">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </form>
      </Modal>

      {/* MODAL: EVALUATE QUALIFICATION PREVIEW / APPLY (Phase 6) */}
      <Modal
        isOpen={isEvalModalOpen}
        onClose={() => setIsEvalModalOpen(false)}
        title="Evaluate Qualification Decision"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Deterministic evaluation executes all configured qualification rules, field validity checks, conflict checks, and contact eligibility.
          </p>

          {evalPreviewResult && (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3.5 text-xs">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
                <span className="font-semibold text-slate-700">Evaluated Decision:</span>
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                    evalPreviewResult.decision === "QUALIFIED"
                      ? "bg-emerald-100 text-emerald-800"
                      : evalPreviewResult.decision === "NEEDS_HUMAN_REVIEW"
                      ? "bg-amber-100 text-amber-800"
                      : evalPreviewResult.decision === "DISQUALIFIED"
                      ? "bg-rose-100 text-rose-800"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {evalPreviewResult.decision.replace(/_/g, " ")}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-slate-600">
                <div>
                  <span className="text-2xs text-slate-400 block">Rule Version</span>
                  <span className="font-mono font-medium text-slate-800">{evalPreviewResult.rule_version}</span>
                </div>
                <div>
                  <span className="text-2xs text-slate-400 block">Completion</span>
                  <span className="font-bold text-slate-800">{evalPreviewResult.completion_percentage}%</span>
                </div>
              </div>

              {/* Reason Codes */}
              <div>
                <span className="text-2xs font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Reason Codes
                </span>
                {evalPreviewResult.reason_codes && evalPreviewResult.reason_codes.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {evalPreviewResult.reason_codes.map((rc, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-white text-slate-700 font-mono text-3xs border border-slate-200"
                      >
                        {rc}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-slate-400 italic">None</span>
                )}
              </div>

              {/* Missing Fields */}
              {evalPreviewResult.missing_fields && evalPreviewResult.missing_fields.length > 0 && (
                <div className="p-2 rounded bg-amber-50 border border-amber-200">
                  <span className="text-2xs font-bold text-amber-800 uppercase tracking-wider block mb-1">
                    Missing Required Fields
                  </span>
                  <div className="space-y-0.5 text-amber-700">
                    {evalPreviewResult.missing_fields.map((f, i) => (
                      <div key={i}>• {f.replace(/_/g, " ")}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Blocking Fields */}
              {evalPreviewResult.blocking_fields && evalPreviewResult.blocking_fields.length > 0 && (
                <div className="p-2 rounded bg-rose-50 border border-rose-200">
                  <span className="text-2xs font-bold text-rose-800 uppercase tracking-wider block mb-1">
                    Blocking / Invalid Fields
                  </span>
                  <div className="space-y-0.5 text-rose-700">
                    {evalPreviewResult.blocking_fields.map((f, i) => (
                      <div key={i}>• {f.replace(/_/g, " ")}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsEvalModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              isLoading={actionLoading}
              onClick={handleApplyEvaluation}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              Apply Decision
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL: HUMAN DECISION OVERRIDE (Phase 6) */}
      <Modal
        isOpen={isDecisionOverrideModalOpen}
        onClose={() => setIsDecisionOverrideModalOpen(false)}
        title="Human Qualification Override"
      >
        <form onSubmit={handleApplyOverride} className="space-y-4">
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
            <div className="flex items-center gap-1.5 font-bold">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              Operator Authorization Notice
            </div>
            <p>
              Manual qualification override bypasses automated validation rules. All overrides require an explicit justification and are permanently recorded in the immutable audit log.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Target Qualification Status *
            </label>
            <select
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 bg-white focus:ring-2 focus:ring-purple-500 focus:outline-hidden"
              value={overrideTargetStatus}
              onChange={(e) => setOverrideTargetStatus(e.target.value)}
            >
              <option value="QUALIFIED">QUALIFIED</option>
              <option value="NEEDS_HUMAN_REVIEW">NEEDS HUMAN REVIEW</option>
              <option value="DISQUALIFIED">DISQUALIFIED</option>
              <option value="IN_PROGRESS">IN PROGRESS</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Authorized Actor Identifier *
            </label>
            <Input
              value={overrideEvaluatedBy}
              onChange={(e) => setOverrideEvaluatedBy(e.target.value)}
              placeholder="e.g. lead_operator, compliance_agent"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Business Justification / Reason *
            </label>
            <textarea
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-purple-500 focus:outline-hidden"
              rows={3}
              placeholder="e.g. Tenant verified identity and income manually via phone call. Verified lease duration exception."
              value={overrideJustification}
              onChange={(e) => setOverrideJustification(e.target.value)}
              required
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsDecisionOverrideModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={overrideLoading}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              Confirm Override
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: DECISION HISTORY (Phase 6) */}
      <Modal
        isOpen={isDecisionHistoryModalOpen}
        onClose={() => setIsDecisionHistoryModalOpen(false)}
        title="Qualification Decision History"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Audit history of all deterministic qualification evaluations and human overrides for this lead.
          </p>

          <div className="max-h-96 overflow-y-auto space-y-3 divide-y divide-slate-100">
            {decisionHistory.map((d) => (
              <div key={d.id} className="pt-3 first:pt-0 space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span
                    className={`font-bold px-2 py-0.5 rounded text-2xs ${
                      d.decision === "QUALIFIED"
                        ? "bg-emerald-100 text-emerald-800"
                        : d.decision === "NEEDS_HUMAN_REVIEW"
                        ? "bg-amber-100 text-amber-800"
                        : d.decision === "DISQUALIFIED"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {d.decision.replace(/_/g, " ")}
                  </span>
                  <span className="text-2xs text-slate-400">
                    {d.evaluated_at ? formatDate(d.evaluated_at) : formatDate(d.created_at)}
                  </span>
                </div>

                <div className="flex items-center justify-between text-slate-600 text-2xs">
                  <span>
                    Source: <strong className="font-semibold text-slate-800">{d.evaluation_source}</strong> by{" "}
                    <span className="text-slate-700">{d.evaluated_by}</span>
                  </span>
                  <span className="font-mono text-slate-500">v{d.rule_version} • {d.completion_percentage}%</span>
                </div>

                {d.reason_codes && d.reason_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    {d.reason_codes.map((rc, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-3xs border border-slate-200">
                        {rc}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsDecisionHistoryModalOpen(false)}
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL: SEND OPERATOR MESSAGE (Phase 7) */}
      <Modal
        isOpen={isOperatorMsgModalOpen}
        onClose={() => setIsOperatorMsgModalOpen(false)}
        title="Send Message (Human Operator)"
      >
        <form onSubmit={handleSendOperatorMessage} className="space-y-4">
          <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-xs text-purple-900">
            <strong>Human Operator Attribution: </strong>
            This message will be sent through the assigned WhatsApp profile and permanently tagged as sent by an authorized human operator. Automated AI replies will remain safely paused.
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 mb-1 block">
              Message Content *
            </label>
            <textarea
              rows={4}
              value={operatorMsgContent}
              onChange={(e) => setOperatorMsgContent(e.target.value)}
              placeholder="Type your message to the tenant..."
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-purple-500 focus:outline-hidden"
              required
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsOperatorMsgModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              isLoading={actionLoading}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              Send Message
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: MANUAL ESCALATION (Phase 7) */}
      <Modal
        isOpen={isEscalateModalOpen}
        onClose={() => setIsEscalateModalOpen(false)}
        title="Escalate Lead to Human Review"
      >
        <form onSubmit={handleManualEscalate} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-700 mb-1 block">
              Escalation Reason *
            </label>
            <select
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value)}
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5 bg-white"
            >
              <option value="OPERATOR_TAKEOVER">Operator Takeover</option>
              <option value="COMPLAINT_OR_DISPUTE">Complaint / Dispute</option>
              <option value="UNRESOLVED_CONFLICT">Unresolved Requirement Conflict</option>
              <option value="WORKFLOW_INCONSISTENCY">Workflow Inconsistency</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 mb-1 block">
              Description / Context (Optional)
            </label>
            <textarea
              rows={3}
              value={escalateDescription}
              onChange={(e) => setEscalateDescription(e.target.value)}
              placeholder="Provide reason for escalating..."
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsEscalateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              isLoading={actionLoading}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              Escalate Lead
            </Button>
          </div>
        </form>
      </Modal>

      {/* MODAL: RESOLVE ESCALATION & RETURN TO AI (Phase 7 & Phase 10) */}
      <Modal
        isOpen={isResolveEscalationModalOpen}
        onClose={() => setIsResolveEscalationModalOpen(false)}
        title="Return to AI Qualification"
      >
        <div className="space-y-4">
          <div className="bg-sky-50 border border-sky-200 rounded-xl p-3.5 text-xs text-sky-900 leading-relaxed">
            <p className="font-semibold text-sky-950 mb-1">
              Return this conversation to AI qualification?
            </p>
            <p>
              The system will recalculate qualification state and continue from the current requirements.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 mb-1 block">
              Resolution Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={escalationResolutionNotes}
              onChange={(e) => setEscalationResolutionNotes(e.target.value)}
              placeholder="e.g. Spoke with tenant on phone, confirmed 2 pax and SGD 3500 budget."
              className="w-full text-sm border border-slate-300 rounded-lg p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsResolveEscalationModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              isLoading={actionLoading}
              onClick={() => handleReturnToAI(escalationResolutionNotes)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Resolve & Resume AI
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );

}
