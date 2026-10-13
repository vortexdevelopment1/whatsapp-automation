"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  RefreshCw,
  Play,
  Eye,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  ShieldAlert,
  GitCompare,
  Building,
  Home,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  PropertyImportBatch,
  PropertyImportRow,
  PropertyImportPreviewResponse,
  PropertySource,
} from "@/types";

export default function PropertyImportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const batchId = params.id as string;

  const [batch, setBatch] = useState<PropertyImportBatch | null>(null);
  const [source, setSource] = useState<PropertySource | null>(null);
  const [rows, setRows] = useState<PropertyImportRow[]>([]);
  const [preview, setPreview] = useState<PropertyImportPreviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"rows" | "preview">("rows");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const b = await api.getPropertyImportBatch(batchId);
      setBatch(b);

      const [r, s] = await Promise.all([
        api.getPropertyImportBatchRows(batchId, 0, 150),
        api.getPropertySource(b.source_id),
      ]);
      setRows(r);
      setSource(s);
    } catch (err: any) {
      setError(err?.message || "Failed to load batch data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (batchId) {
      loadData();
    }
  }, [batchId]);

  const handlePreview = async () => {
    setActionLoading("preview");
    setError(null);
    try {
      const prev = await api.previewPropertyImportBatch(batchId);
      setPreview(prev);
      setActiveTab("preview");
    } catch (err: any) {
      setError(err?.message || "Failed to generate preview.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCommit = async () => {
    if (!confirm("Are you sure you want to commit this import batch? Valid records will create and update catalog inventory.")) {
      return;
    }
    setActionLoading("commit");
    setError(null);
    try {
      await api.commitPropertyImportBatch(batchId);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to commit batch.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async () => {
    setActionLoading("retry");
    setError(null);
    try {
      await api.retryPropertyImportBatch(batchId);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to retry batch.");
    } finally {
      setActionLoading(null);
    }
  };

  const getRowBadge = (status: string) => {
    switch (status) {
      case "NEW_PROPERTY_CREATED":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            New Property
          </span>
        );
      case "MATCHED_EXISTING_PROPERTY":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            Attached Property
          </span>
        );
      case "DUPLICATE_LISTING":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            Updated Listing
          </span>
        );
      case "NEEDS_REVIEW":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            Needs Review
          </span>
        );
      case "VALID":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Valid
          </span>
        );
      case "INVALID":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            Invalid
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  if (loading && !batch) {
    return (
      <div className="p-16 text-center text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-sky-600" />
        Loading batch details...
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="p-16 text-center text-slate-600">
        <p className="font-semibold text-lg text-rose-600">Batch not found</p>
        <Link href="/property-imports" className="text-sm text-sky-600 underline mt-2 block">
          Return to Imports
        </Link>
      </div>
    );
  }

  const isCommitted =
    batch.status === "COMPLETED" || batch.status === "COMPLETED_WITH_WARNINGS";

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div>
        <Link
          href="/property-imports"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Import Batches
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-100 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-900">
                {batch.file_name || "Direct API Feed"}
              </h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-slate-100 text-slate-800">
                {batch.import_type}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Source: <span className="font-medium text-slate-700">{source?.name || batch.source_id}</span> • Uploaded on{" "}
              {new Date(batch.created_at).toLocaleString()}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {!isCommitted && (
              <>
                <button
                  onClick={handlePreview}
                  disabled={actionLoading !== null}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
                >
                  <Eye className="w-4 h-4 text-slate-500" />
                  {actionLoading === "preview" ? "Analyzing..." : "Dry-Run Preview"}
                </button>
                <button
                  onClick={handleCommit}
                  disabled={actionLoading !== null}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors shadow-2xs disabled:opacity-50"
                >
                  <Play className="w-4 h-4" />
                  {actionLoading === "commit" ? "Processing..." : "Commit Batch"}
                </button>
              </>
            )}

            {isCommitted && (
              <button
                onClick={handleRetry}
                disabled={actionLoading !== null}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                {actionLoading === "retry" ? "Retrying..." : "Safe Retry"}
              </button>
            )}

            {batch.manual_review_rows > 0 && (
              <Link
                href="/property-duplicate-review"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors shadow-2xs"
              >
                <GitCompare className="w-4 h-4 text-amber-700" />
                Review Duplicates ({batch.manual_review_rows})
              </Link>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
            {error}
          </div>
        )}

        {/* Counters summary */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-5">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-slate-500 uppercase tracking-wider block">Total Rows</span>
            <span className="text-lg font-bold text-slate-900">{batch.total_rows}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-emerald-600 uppercase tracking-wider block">Valid Rows</span>
            <span className="text-lg font-bold text-emerald-700">{batch.valid_rows}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-rose-600 uppercase tracking-wider block">Invalid Rows</span>
            <span className="text-lg font-bold text-rose-700">{batch.invalid_rows}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-sky-600 uppercase tracking-wider block">Duplicate Listings</span>
            <span className="text-lg font-bold text-sky-700">{batch.duplicate_listing_rows}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-purple-600 uppercase tracking-wider block">New Properties</span>
            <span className="text-lg font-bold text-purple-700">{batch.new_property_rows}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/70">
            <span className="text-2xs font-bold text-amber-600 uppercase tracking-wider block">Needs Review</span>
            <span className="text-lg font-bold text-amber-700">{batch.manual_review_rows}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab("rows")}
          className={`py-2.5 px-4 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "rows"
              ? "border-sky-600 text-sky-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          Import Rows ({rows.length})
        </button>
        {preview && (
          <button
            onClick={() => setActiveTab("preview")}
            className={`py-2.5 px-4 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "preview"
                ? "border-sky-600 text-sky-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Dry-Run Analysis Preview ({preview.sample_rows.length})
          </button>
        )}
      </div>

      {/* Content for Tabs */}
      {activeTab === "rows" ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-center w-12">#</th>
                  <th className="px-4 py-3">Property Name / Building</th>
                  <th className="px-4 py-3">Address & Unit</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Beds / Type</th>
                  <th className="px-4 py-3">Agent</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Details / Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => {
                  const norm = row.normalized_payload || {};
                  const raw = row.raw_payload || {};
                  return (
                    <tr key={row.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-center text-xs font-mono text-slate-400">
                        {row.row_number}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900 text-xs">
                          {norm.property_name || raw.property_name || "—"}
                        </div>
                        <div className="text-2xs text-slate-500">
                          {norm.building_name || raw.building_name || "—"}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div>{norm.address_line_1 || raw.address_line_1 || "—"}</div>
                        <div className="text-2xs font-mono text-slate-500">
                          Unit: {norm.unit_number || raw.address_line_2 || "None"} • Postal: {norm.postal_code || "—"}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                        {norm.currency || "SGD"} {norm.asking_price ? norm.asking_price.toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div>{norm.bedrooms !== null ? `${norm.bedrooms} BR` : "—"}</div>
                        <div className="text-2xs uppercase text-slate-500 font-semibold">{norm.property_type || "—"}</div>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div>{norm.agent?.full_name || raw.agent_name || "—"}</div>
                        <div className="text-2xs text-slate-500">{norm.agent?.phone_normalized || raw.agent_phone || "—"}</div>
                      </td>
                      <td className="px-4 py-3">{getRowBadge(row.status)}</td>
                      <td className="px-4 py-3 text-xs">
                        {row.error_codes && row.error_codes.length > 0 ? (
                          <div className="text-rose-600 text-2xs space-y-0.5">
                            {row.error_codes.map((err, i) => (
                              <div key={i}>• {typeof err === "string" ? err : JSON.stringify(err)}</div>
                            ))}
                          </div>
                        ) : row.property_id ? (
                          <Link
                            href={`/properties/${row.property_id}`}
                            className="inline-flex items-center gap-1 text-2xs font-semibold text-sky-600 hover:text-sky-800"
                          >
                            <Home className="w-3 h-3" /> View Property
                          </Link>
                        ) : (
                          <span className="text-slate-400 text-2xs">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Preview Tab */
        preview && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Dry-Run Deduplication Analysis</h3>
                <p className="text-2xs text-slate-500 mt-0.5">
                  Calculated without mutating existing database inventory.
                </p>
              </div>
              <span className="text-xs font-semibold text-sky-700 bg-sky-50 px-2.5 py-1 rounded-full border border-sky-200">
                Ready for Commit
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-center w-12">#</th>
                    <th className="px-4 py-3">Property</th>
                    <th className="px-4 py-3">Address</th>
                    <th className="px-4 py-3">Price</th>
                    <th className="px-4 py-3">Analysis Result</th>
                    <th className="px-4 py-3">Confidence & Signals</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.sample_rows.map((r) => {
                    const norm = r.normalized_payload || {};
                    return (
                      <tr key={r.row_number} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-4 py-3 text-center text-xs font-mono text-slate-400">
                          {r.row_number}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-semibold text-slate-900 text-xs">
                            {norm.property_name || "—"}
                          </div>
                          <div className="text-2xs text-slate-500">{norm.building_name || "—"}</div>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <div>{norm.address_line_1 || "—"}</div>
                          <div className="text-2xs font-mono text-slate-500">
                            Unit: {norm.unit_number || "None"} • Postal: {norm.postal_code || "—"}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                          {norm.currency} {norm.asking_price ? norm.asking_price.toLocaleString() : "—"}
                        </td>
                        <td className="px-4 py-3">
                          {getRowBadge(r.status)}
                          <div className="text-2xs text-slate-500 mt-0.5">{r.dedup_verdict || "—"}</div>
                        </td>
                        <td className="px-4 py-3 text-2xs">
                          {r.dedup_confidence && (
                            <span className="font-bold uppercase text-slate-700 block mb-0.5">
                              Confidence: {r.dedup_confidence}
                            </span>
                          )}
                          {r.dedup_reasons && r.dedup_reasons.length > 0 ? (
                            <div className="text-slate-500 space-y-0.5">
                              {r.dedup_reasons.map((reason, idx) => (
                                <span
                                  key={idx}
                                  className="inline-block bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-2xs mr-1"
                                >
                                  {reason}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}
    </div>
  );
}
