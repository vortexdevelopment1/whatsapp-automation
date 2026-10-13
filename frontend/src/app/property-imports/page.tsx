"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  UploadCloud,
  Plus,
  RefreshCw,
  Sparkles,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  Database,
  Building,
} from "lucide-react";
import { api } from "@/lib/api";
import { PropertyImportBatch, PropertySource } from "@/types";

export default function PropertyImportsPage() {
  const [batches, setBatches] = useState<PropertyImportBatch[]>([]);
  const [sources, setSources] = useState<PropertySource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [seeding, setSeeding] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const [batchData, sourceData] = await Promise.all([
        api.listPropertyImportBatches(),
        api.listPropertySources(),
      ]);
      setBatches(batchData);
      setSources(sourceData);
    } catch (err: any) {
      setError(err?.message || "Failed to load property import batches.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const handleSeedDemo = async () => {
    if (seeding) return;
    setSeeding(true);
    try {
      await api.seedDemoPropertyImport(100);
      await fetchBatches();
    } catch (err: any) {
      alert(err?.message || "Failed to seed synthetic demo batch.");
    } finally {
      setSeeding(false);
    }
  };

  const getSourceMap = () => {
    const map = new Map<string, string>();
    sources.forEach((s) => map.set(s.id, s.name));
    return map;
  };
  const sourceMap = getSourceMap();

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" /> Completed
          </span>
        );
      case "COMPLETED_WITH_WARNINGS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5" /> Completed w/ Warnings
          </span>
        );
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-50 text-sky-700 border border-sky-200 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Processing
          </span>
        );
      case "VALIDATING":
      case "UPLOADED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3.5 h-3.5" /> Ready to Process
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  const totalImportedRows = batches.reduce((acc, b) => acc + b.total_rows, 0);
  const totalNewProperties = batches.reduce((acc, b) => acc + b.new_property_rows, 0);
  const totalMatchedExisting = batches.reduce((acc, b) => acc + b.matched_existing_property_rows, 0);
  const totalPendingReviews = batches.reduce((acc, b) => acc + b.manual_review_rows, 0);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <UploadCloud className="w-7 h-7 text-sky-600" />
            Property Inventory Imports
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Ingest property listings from CSV files and approved feeds with deterministic normalization & deduplication.
          </p>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={fetchBatches}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={handleSeedDemo}
            disabled={seeding}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-sky-700 bg-sky-50 border border-sky-200/90 rounded-lg hover:bg-sky-100 transition-colors shadow-2xs disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {seeding ? "Generating..." : "Seed 100 Demo Rows"}
          </button>
          <Link
            href="/property-imports/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors shadow-2xs"
          >
            <Plus className="w-4 h-4" />
            New CSV Import
          </Link>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium uppercase tracking-wider">Total Rows Imported</span>
            <Database className="w-4 h-4 text-sky-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900">{totalImportedRows.toLocaleString()}</p>
          <p className="text-xs text-slate-500 mt-1">Across {batches.length} import batches</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium uppercase tracking-wider">New Properties Created</span>
            <Building className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-emerald-700">{totalNewProperties.toLocaleString()}</p>
          <p className="text-xs text-slate-500 mt-1">Canonical catalog entries</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium uppercase tracking-wider">Multi-Source Attached</span>
            <CheckCircle2 className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-blue-700">{totalMatchedExisting.toLocaleString()}</p>
          <p className="text-xs text-slate-500 mt-1">Linked to existing properties</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium uppercase tracking-wider">Manual Review Flagged</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-amber-700">{totalPendingReviews.toLocaleString()}</p>
          <p className="text-xs text-slate-500 mt-1">Uncertain duplicates</p>
        </div>
      </div>

      {/* Batch List Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200/80 flex justify-between items-center bg-slate-50/50">
          <h2 className="text-sm font-semibold text-slate-800">Import Batches</h2>
          <span className="text-xs text-slate-500">{batches.length} total batches</span>
        </div>

        {error && (
          <div className="p-4 bg-rose-50 border-b border-rose-200 text-rose-700 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="p-12 text-center text-slate-500">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-sky-600" />
            Loading import batches...
          </div>
        ) : batches.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <FileText className="w-8 h-8 mx-auto mb-3 text-slate-300" />
            <p className="font-medium text-slate-700">No import batches found</p>
            <p className="text-xs text-slate-500 mt-1">
              Upload a CSV file or click "Seed 100 Demo Rows" to create your first ingestion batch.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3">Source & File</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Rows</th>
                  <th className="px-4 py-3 text-right">Valid</th>
                  <th className="px-4 py-3 text-right">Duplicates</th>
                  <th className="px-4 py-3 text-right">New Props</th>
                  <th className="px-4 py-3 text-right">Reviews</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {batches.map((batch) => {
                  const sourceName = sourceMap.get(batch.source_id) || "Source " + batch.source_id.slice(0, 8);
                  return (
                    <tr key={batch.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="font-medium text-slate-900">{sourceName}</div>
                        <div className="text-xs text-slate-500 truncate max-w-xs">{batch.file_name || "Direct Feed"}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-bold uppercase tracking-wider bg-slate-100 text-slate-700">
                          {batch.import_type}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">{getStatusBadge(batch.status)}</td>
                      <td className="px-4 py-3.5 text-right font-medium text-slate-900">{batch.total_rows}</td>
                      <td className="px-4 py-3.5 text-right text-emerald-600 font-medium">{batch.valid_rows}</td>
                      <td className="px-4 py-3.5 text-right text-blue-600 font-medium">{batch.duplicate_listing_rows}</td>
                      <td className="px-4 py-3.5 text-right text-purple-600 font-medium">{batch.new_property_rows}</td>
                      <td className="px-4 py-3.5 text-right">
                        {batch.manual_review_rows > 0 ? (
                          <span className="font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full text-xs">
                            {batch.manual_review_rows}
                          </span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-500 whitespace-nowrap">
                        {new Date(batch.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <Link
                          href={`/property-imports/${batch.id}`}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-800"
                        >
                          View Batch <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
