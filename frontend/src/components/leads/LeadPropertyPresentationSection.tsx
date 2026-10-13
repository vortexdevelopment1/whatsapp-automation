"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Share2,
  Send,
  Eye,
  Calendar,
  Clock,
  Building2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  MapPin,
  ExternalLink,
  MessageSquare,
  Sparkles,
  Edit3,
  Check,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  PropertyInterest,
  PropertyInterestStatus,
  PropertyShortlist,
  PropertyShortlistItem,
} from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { formatDate } from "@/lib/utils";

interface LeadPropertyPresentationSectionProps {
  leadId: string;
  isQualified?: boolean;
}

export function LeadPropertyPresentationSection({
  leadId,
  isQualified = true,
}: LeadPropertyPresentationSectionProps) {
  const [interests, setInterests] = useState<PropertyInterest[]>([]);
  const [shortlist, setShortlist] = useState<PropertyShortlist | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Manual interest modal
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [selectedInterest, setSelectedInterest] = useState<PropertyInterest | null>(null);
  const [manualStatus, setManualStatus] = useState<PropertyInterestStatus>("INTERESTED");
  const [manualNotes, setManualNotes] = useState("");

  // Simulate reply modal
  const [simulateModalOpen, setSimulateModalOpen] = useState(false);
  const [simulateMessage, setSimulateMessage] = useState("");
  const [simulateResult, setSimulateResult] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [interestsRes, shortlistRes] = await Promise.all([
        api.listLeadPropertyInterests(leadId),
        api.getPropertyShortlist(leadId).catch(() => null),
      ]);
      setInterests(interestsRes.items || []);
      setShortlist(shortlistRes);
    } catch (err: any) {
      setError(err.message || "Failed to load property presentations");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Present Single
  const handlePresentSingle = async (matchId: string) => {
    try {
      setActionLoading(true);
      await api.presentPropertyMatchToTenant(matchId);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to present property to tenant");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Start Presentation
  const handleStartPresentation = async () => {
    try {
      setActionLoading(true);
      await api.startPropertyPresentation(leadId);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to start property presentation");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Manual Status Update
  const handleUpdateManual = async () => {
    if (!selectedInterest) return;
    try {
      setActionLoading(true);
      await api.updatePropertyInterestManual(selectedInterest.id, {
        status: manualStatus,
        tenant_notes: manualNotes || undefined,
      });
      setManualModalOpen(false);
      setSelectedInterest(null);
      setManualNotes("");
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to update interest status");
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Simulate Inbound Message
  const handleSimulateMessage = async () => {
    if (!simulateMessage.trim()) return;
    try {
      setActionLoading(true);
      setSimulateResult(null);
      const res = await api.processTenantInterestMessage(leadId, {
        message_content: simulateMessage,
      });
      setSimulateResult(
        `Intent: ${res.intent} · Viewing Created: ${res.viewing_created ? "YES" : "NO"}\nResponse: ${res.response_text}`
      );
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to process message");
    } finally {
      setActionLoading(false);
    }
  };

  const interestByMatchId = new Map(interests.map((i) => [i.property_match_id, i]));
  const items = shortlist?.items || [];

  return (
    <Card className="border-slate-200 shadow-2xs">
      <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-semibold flex items-center gap-2 text-slate-800">
          <Share2 className="w-4 h-4 text-sky-600" />
          Tenant Property Presentation & Interest Capture
        </CardTitle>
        <div className="flex items-center gap-2">
          {shortlist && shortlist.status === "READY" && (
            <Button
              size="sm"
              onClick={handleStartPresentation}
              disabled={actionLoading || !isQualified}
              className="bg-sky-600 hover:bg-sky-700 text-white text-xs h-8 gap-1"
            >
              <Send className="w-3.5 h-3.5" />
              Present Next Property
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSimulateModalOpen(true)}
            className="text-xs h-8 gap-1 border-slate-300"
          >
            <MessageSquare className="w-3.5 h-3.5 text-slate-500" />
            Simulate Tenant Reply
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={loading}
            className="text-xs h-8 gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-600" : ""}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-5">
        {loading ? (
          <div className="p-8 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin text-sky-600" />
            <p className="text-xs">Loading presentation status...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-rose-50 rounded-lg text-rose-700 text-xs">{error}</div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <Share2 className="w-8 h-8 mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-medium text-slate-600">No shortlist items to present</p>
            <p className="text-xs text-slate-400 mt-1">
              Curate and finalize a READY shortlist in Module 4 to begin presenting properties to the tenant.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item: PropertyShortlistItem) => {
              const interest = interestByMatchId.get(item.property_match_id);
              const summary = interest?.property_summary;

              const name =
                summary?.name ||
                item.property_name ||
                item.building_name ||
                "Shortlisted Property";
              const price = summary?.asking_price
                ? `$${summary.asking_price.toLocaleString()}/mo`
                : item.asking_price
                ? `$${item.asking_price.toLocaleString()}/mo`
                : "Price upon inquiry";
              const beds = summary?.bedrooms
                ? `${summary.bedrooms} Beds`
                : item.bedrooms
                ? `${item.bedrooms} Beds`
                : "—";
              const isPresented = interest && interest.status !== "NOT_PRESENTED";

              return (
                <div
                  key={item.id}
                  className={`p-4 rounded-xl border transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                    interest?.status === "VIEWING_REQUESTED"
                      ? "bg-emerald-50/30 border-emerald-300"
                      : isPresented
                      ? "bg-sky-50/20 border-sky-200"
                      : "bg-white border-slate-200"
                  }`}
                >
                  <div className="space-y-1.5 max-w-xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-900 text-sm">
                        #{item.position} · {name}
                      </span>
                      <StatusBadge status={interest?.status || "NOT_PRESENTED"} />
                      {interest?.viewing_id && (
                        <Link
                          href={`/viewings/${interest.viewing_id}`}
                          className="text-xs font-semibold text-emerald-700 bg-emerald-100 hover:bg-emerald-200 px-2 py-0.5 rounded-full flex items-center gap-1 transition-colors"
                        >
                          Viewing Created <ExternalLink className="w-3 h-3" />
                        </Link>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="font-semibold text-slate-800">{price}</span>
                      <span>{beds} · {summary?.property_type || item.property_type || "Condo"}</span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        {summary?.district || summary?.address || item.district || item.property_address || "Singapore"}
                      </span>
                      {interest?.presented_at && (
                        <span>
                          Presented: <strong>{formatDate(interest.presented_at)}</strong>
                        </span>
                      )}
                    </div>

                    {interest?.tenant_notes && (
                      <p className="text-xs text-slate-600 bg-slate-100/80 p-2 rounded-lg italic">
                        "{interest.tenant_notes}"
                      </p>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant={isPresented ? "outline" : "primary"}
                      onClick={() => handlePresentSingle(item.property_match_id)}
                      disabled={actionLoading || !isQualified}
                      className={`text-xs gap-1 ${
                        !isPresented
                          ? "bg-sky-600 hover:bg-sky-700 text-white"
                          : "border-sky-300 text-sky-700 hover:bg-sky-50"
                      }`}
                    >
                      <Send className="w-3.5 h-3.5" />
                      {isPresented ? "Present Again" : "Present to Tenant"}
                    </Button>

                    {interest && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedInterest(interest);
                          setManualStatus(interest.status);
                          setManualNotes(interest.tenant_notes || "");
                          setManualModalOpen(true);
                        }}
                        className="text-xs gap-1 border-slate-300 text-slate-700 hover:bg-slate-50"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                        Record Interest
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* MODAL 1: Manual Interest Update */}
      <Modal
        isOpen={manualModalOpen}
        onClose={() => setManualModalOpen(false)}
        title="Record Tenant Interest"
        description="Manually record or update tenant feedback for this property."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Interest Status
            </label>
            <select
              value={manualStatus}
              onChange={(e) => setManualStatus(e.target.value as PropertyInterestStatus)}
              className="w-full text-xs rounded-lg border border-slate-300 p-2"
            >
              <option value="INTERESTED">INTERESTED</option>
              <option value="VIEWING_REQUESTED">VIEWING_REQUESTED</option>
              <option value="NOT_INTERESTED">NOT_INTERESTED</option>
              <option value="WANTS_MORE_DETAILS">WANTS_MORE_DETAILS</option>
              <option value="OTHER_OPTIONS_REQUESTED">OTHER_OPTIONS_REQUESTED</option>
              <option value="UNSURE">UNSURE</option>
              <option value="NEEDS_CLARIFICATION">NEEDS_CLARIFICATION</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Tenant Notes / Details
            </label>
            <textarea
              rows={3}
              value={manualNotes}
              onChange={(e) => setManualNotes(e.target.value)}
              placeholder="e.g. Tenant phoned operator saying they loved the unit and want to see it"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setManualModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={actionLoading}
              onClick={handleUpdateManual}
              className="bg-sky-600 hover:bg-sky-700 text-white"
            >
              Save Interest
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 2: Simulate Tenant Reply */}
      <Modal
        isOpen={simulateModalOpen}
        onClose={() => {
          setSimulateModalOpen(false);
          setSimulateResult(null);
        }}
        title="Simulate Tenant WhatsApp Response"
        description="Test how the system understands tenant replies, correlates properties, and triggers viewing workflows."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Tenant Message Content
            </label>
            <textarea
              rows={3}
              value={simulateMessage}
              onChange={(e) => setSimulateMessage(e.target.value)}
              placeholder="e.g. I'd love to schedule a viewing for Novena Residence"
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5"
            />
          </div>

          {simulateResult && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono whitespace-pre-wrap text-slate-800">
              {simulateResult}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSimulateModalOpen(false);
                setSimulateResult(null);
              }}
            >
              Close
            </Button>
            <Button
              size="sm"
              disabled={actionLoading || !simulateMessage.trim()}
              onClick={handleSimulateMessage}
              className="bg-sky-600 hover:bg-sky-700 text-white"
            >
              Process Response
            </Button>
          </div>
        </div>
      </Modal>
    </Card>
  );
}
