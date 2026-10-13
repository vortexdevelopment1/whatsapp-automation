"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GitCompare,
  CheckCircle2,
  AlertTriangle,
  Building,
  Home,
  PlusCircle,
  XCircle,
  ExternalLink,
  RefreshCw,
  ArrowRight,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { PropertyDuplicateReview } from "@/types";

export default function PropertyDuplicateReviewPage() {
  const [reviews, setReviews] = useState<PropertyDuplicateReview[]>([]);
  const [selectedReview, setSelectedReview] = useState<PropertyDuplicateReview | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("OPEN");
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReviews = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPropertyDuplicateReviews(statusFilter || undefined);
      setReviews(data);
      if (data.length > 0) {
        setSelectedReview(data[0]);
      } else {
        setSelectedReview(null);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load duplicate review items.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [statusFilter]);

  const handleAttach = async () => {
    if (!selectedReview) return;
    const confirmMsg = `Attach this incoming listing to existing property "${
      selectedReview.candidate_property?.canonical_name || "Existing Property"
    }"?`;
    if (!confirm(confirmMsg)) return;

    setActionLoading(true);
    try {
      await api.attachDuplicateReviewToExisting(
        selectedReview.id,
        selectedReview.candidate_property_id || undefined,
        "Operator confirmed match and attached listing"
      );
      await fetchReviews();
    } catch (err: any) {
      alert(err?.message || "Failed to attach to existing property.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateNew = async () => {
    if (!selectedReview) return;
    if (
      !confirm(
        "Confirm that this is a separate physical property? A new canonical property will be created."
      )
    )
      return;

    setActionLoading(true);
    try {
      await api.createNewPropertyFromDuplicateReview(
        selectedReview.id,
        "Operator confirmed distinct physical property"
      );
      await fetchReviews();
    } catch (err: any) {
      alert(err?.message || "Failed to create new property.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleIgnore = async () => {
    if (!selectedReview) return;
    const reason = prompt("Enter a reason for ignoring this duplicate review:", "Dismissed by operator");
    if (reason === null) return;

    setActionLoading(true);
    try {
      await api.ignoreDuplicateReview(selectedReview.id, reason);
      await fetchReviews();
    } catch (err: any) {
      alert(err?.message || "Failed to ignore review item.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <GitCompare className="w-7 h-7 text-amber-600" />
            Duplicate Property Reviews
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Resolve ambiguous listings where the canonical property match is uncertain (e.g. missing unit numbers).
          </p>
        </div>

        {/* Filter Pills & Refresh */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-100 p-1 rounded-lg flex items-center gap-1 text-xs">
            <button
              onClick={() => setStatusFilter("OPEN")}
              className={`px-3 py-1 rounded-md font-medium transition-colors ${
                statusFilter === "OPEN" ? "bg-white text-slate-900 shadow-2xs font-semibold" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Pending ({reviews.filter((r) => r.status === "OPEN").length || 0})
            </button>
            <button
              onClick={() => setStatusFilter("")}
              className={`px-3 py-1 rounded-md font-medium transition-colors ${
                statusFilter === "" ? "bg-white text-slate-900 shadow-2xs font-semibold" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              All History
            </button>
          </div>

          <button
            onClick={fetchReviews}
            className="p-2 text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-slate-500">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-sky-600" />
          Loading duplicate review queue...
        </div>
      ) : reviews.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-16 text-center shadow-2xs">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-900">Review Queue Empty</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            There are no uncertain property candidates requiring operator review at this time.
          </p>
          <Link
            href="/property-imports"
            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:underline mt-4"
          >
            Check Import Batches <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Review Items List */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden h-[calc(100vh-280px)] flex flex-col">
            <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Uncertain Candidates ({reviews.length})
              </span>
            </div>
            <div className="overflow-y-auto divide-y divide-slate-100 flex-1">
              {reviews.map((rev) => {
                const norm = rev.incoming_normalized_data || {};
                const isSelected = selectedReview?.id === rev.id;
                return (
                  <button
                    key={rev.id}
                    onClick={() => setSelectedReview(rev)}
                    className={`w-full text-left p-4 transition-colors block ${
                      isSelected ? "bg-amber-50/70 border-l-4 border-l-amber-600" : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex justify-between items-start gap-2 mb-1">
                      <span className="text-xs font-bold text-slate-900 truncate">
                        {norm.property_name || norm.building_name || "Incoming Listing"}
                      </span>
                      <span
                        className={`text-2xs font-semibold px-2 py-0.5 rounded uppercase tracking-wider ${
                          rev.confidence_level === "HIGH"
                            ? "bg-emerald-100 text-emerald-800"
                            : rev.confidence_level === "MEDIUM"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {rev.confidence_level}
                      </span>
                    </div>
                    <p className="text-2xs text-slate-500 truncate">
                      {norm.address_line_1 || "No address"} • Unit: {norm.unit_number || "Missing"}
                    </p>
                    <div className="flex items-center gap-1.5 mt-2 text-2xs text-slate-600">
                      <span className="font-semibold text-slate-900">
                        {norm.currency || "SGD"} {norm.asking_price ? norm.asking_price.toLocaleString() : "—"}
                      </span>
                      <span>•</span>
                      <span>{norm.bedrooms !== null ? `${norm.bedrooms} BR` : ""}</span>
                      <span>•</span>
                      <span className="capitalize">{norm.property_type}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Side-by-Side Comparison & Resolution */}
          {selectedReview && (
            <div className="lg:col-span-2 space-y-4">
              <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
                {/* Review Header Banner */}
                <div className="p-5 border-b border-slate-200/80 bg-slate-50/50 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-amber-800 bg-amber-100 px-2 py-0.5 rounded">
                        Review Status: {selectedReview.status}
                      </span>
                      <span className="text-xs text-slate-500 font-mono">ID: {selectedReview.id.slice(0, 8)}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {selectedReview.match_reasons.map((r, i) => (
                        <span
                          key={i}
                          className="bg-slate-100 text-slate-700 text-2xs font-medium px-2 py-0.5 rounded"
                        >
                          Signal: {r.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Actions (if status is OPEN) */}
                  {selectedReview.status === "OPEN" && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={handleAttach}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors shadow-2xs disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Attach to Existing
                      </button>
                      <button
                        onClick={handleCreateNew}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors shadow-2xs disabled:opacity-50"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        Create New Property
                      </button>
                      <button
                        onClick={handleIgnore}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5 text-slate-400" />
                        Ignore
                      </button>
                    </div>
                  )}
                </div>

                {/* Side-by-Side Comparison Grid */}
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left: Incoming Listing */}
                  <div className="border border-amber-200 rounded-xl p-5 bg-amber-50/20 space-y-4">
                    <div className="flex items-center justify-between border-b border-amber-200/80 pb-2.5">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                        <Home className="w-4 h-4 text-amber-700" />
                        Incoming Listing
                      </h3>
                      <span className="text-2xs font-semibold text-amber-800 bg-amber-100 px-2 py-0.5 rounded">
                        From Ingestion Feed
                      </span>
                    </div>

                    <div className="space-y-3 text-xs">
                      <div>
                        <span className="text-slate-500 block text-2xs">Property / Building Name</span>
                        <span className="font-semibold text-slate-900">
                          {selectedReview.incoming_normalized_data?.property_name ||
                            selectedReview.incoming_normalized_data?.building_name ||
                            "—"}
                        </span>
                      </div>

                      <div>
                        <span className="text-slate-500 block text-2xs">Normalized Address</span>
                        <span className="font-medium text-slate-800">
                          {selectedReview.incoming_normalized_data?.address_normalized ||
                            selectedReview.incoming_normalized_data?.address_line_1 ||
                            "—"}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="text-slate-500 block text-2xs">Unit Number</span>
                          <span className={`font-mono font-bold ${selectedReview.incoming_normalized_data?.unit_number ? "text-slate-900" : "text-amber-700 italic"}`}>
                            {selectedReview.incoming_normalized_data?.unit_number || "Missing from source"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 block text-2xs">Postal Code</span>
                          <span className="font-mono text-slate-800">
                            {selectedReview.incoming_normalized_data?.postal_code || "—"}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="text-slate-500 block text-2xs">Property Type</span>
                          <span className="font-medium text-slate-800">
                            {selectedReview.incoming_normalized_data?.property_type || "—"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 block text-2xs">Bedrooms</span>
                          <span className="font-medium text-slate-800">
                            {selectedReview.incoming_normalized_data?.bedrooms !== null
                              ? `${selectedReview.incoming_normalized_data.bedrooms} BR`
                              : "—"}
                          </span>
                        </div>
                      </div>

                      <div>
                        <span className="text-slate-500 block text-2xs">Asking Price</span>
                        <span className="font-bold text-slate-900 text-sm">
                          {selectedReview.incoming_normalized_data?.currency || "SGD"}{" "}
                          {selectedReview.incoming_normalized_data?.asking_price
                            ? selectedReview.incoming_normalized_data.asking_price.toLocaleString()
                            : "—"}
                        </span>
                      </div>

                      {selectedReview.incoming_normalized_data?.agent && (
                        <div className="pt-2 border-t border-amber-200/60">
                          <span className="text-slate-500 block text-2xs">Listing Agent</span>
                          <span className="font-medium text-slate-800">
                            {selectedReview.incoming_normalized_data.agent.full_name || "—"} (
                            {selectedReview.incoming_normalized_data.agent.agency_name || "Agency"})
                          </span>
                          <span className="block text-2xs text-slate-500">
                            {selectedReview.incoming_normalized_data.agent.phone_normalized || "—"}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Candidate Existing Property */}
                  <div className="border border-blue-200 rounded-xl p-5 bg-blue-50/20 space-y-4">
                    <div className="flex items-center justify-between border-b border-blue-200/80 pb-2.5">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-blue-900 flex items-center gap-1.5">
                        <Building className="w-4 h-4 text-blue-700" />
                        Candidate Property
                      </h3>
                      <span className="text-2xs font-semibold text-blue-800 bg-blue-100 px-2 py-0.5 rounded">
                        Catalog Inventory
                      </span>
                    </div>

                    {selectedReview.candidate_property ? (
                      <div className="space-y-3 text-xs">
                        <div>
                          <span className="text-slate-500 block text-2xs">Canonical Property Name</span>
                          <Link
                            href={`/properties/${selectedReview.candidate_property.id}`}
                            className="font-semibold text-blue-700 hover:underline flex items-center gap-1"
                          >
                            {selectedReview.candidate_property.canonical_name}
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        </div>

                        <div>
                          <span className="text-slate-500 block text-2xs">Address</span>
                          <span className="font-medium text-slate-800">
                            {selectedReview.candidate_property.address_line_1 || "—"}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-slate-500 block text-2xs">Unit Number</span>
                            <span className="font-mono font-bold text-slate-900">
                              {selectedReview.candidate_property.unit_number || "No unit on record"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-2xs">Postal Code</span>
                            <span className="font-mono text-slate-800">
                              {selectedReview.candidate_property.postal_code || "—"}
                            </span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-slate-500 block text-2xs">Property Type</span>
                            <span className="font-medium text-slate-800">
                              {selectedReview.candidate_property.property_type}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-2xs">Bedrooms</span>
                            <span className="font-medium text-slate-800">
                              {selectedReview.candidate_property.bedrooms !== null
                                ? `${selectedReview.candidate_property.bedrooms} BR`
                                : "—"}
                            </span>
                          </div>
                        </div>

                        <div>
                          <span className="text-slate-500 block text-2xs">Building Name</span>
                          <span className="font-medium text-slate-800">
                            {selectedReview.candidate_property.building_name || "—"}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="p-8 text-center text-slate-400 text-xs">
                        No specific candidate property linked.
                      </div>
                    )}
                  </div>
                </div>

                {/* Resolution History Banner if Resolved */}
                {selectedReview.status !== "OPEN" && (
                  <div className="bg-slate-50 p-4 border-t border-slate-200 text-xs text-slate-600">
                    <p className="font-bold text-slate-800">Resolution Details:</p>
                    <p className="mt-0.5">
                      Resolved by: <strong>{selectedReview.resolved_by || "system"}</strong> on{" "}
                      {selectedReview.resolved_at
                        ? new Date(selectedReview.resolved_at).toLocaleString()
                        : "—"}
                    </p>
                    {selectedReview.resolution_reason && (
                      <p className="text-slate-500 mt-0.5 italic">"{selectedReview.resolution_reason}"</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
