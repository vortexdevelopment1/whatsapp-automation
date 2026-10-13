"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Calendar,
  Clock,
  UserCheck,
  Building2,
  Phone,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  MapPin,
  CalendarDays,
  ShieldAlert,
  ArrowUpRight,
} from "lucide-react";

import { api } from "@/lib/api";
import { Viewing, ViewingStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { formatDate } from "@/lib/utils";

export default function ViewingsListPage() {
  const [viewings, setViewings] = useState<Viewing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedTab, setSelectedTab] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const loadViewings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.listViewings({ limit: 100 });
      setViewings(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load viewings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadViewings();
  }, [loadViewings]);

  // Derived filter list
  const filteredViewings = viewings.filter((v) => {
    // Tab filter
    if (selectedTab === "CONFIRMED" && v.status !== "CONFIRMED") return false;
    if (selectedTab === "RESCHEDULE_REQUESTED" && v.status !== "RESCHEDULE_REQUESTED") return false;
    if (selectedTab === "PENDING_CONFIRMATION") {
      if (
        v.status !== "AWAITING_TENANT_CONFIRMATION" &&
        v.status !== "AWAITING_AGENT_CONFIRMATION"
      ) {
        return false;
      }
    }
    if (selectedTab === "SLOTS_AVAILABLE") {
      if (v.status !== "SLOTS_AVAILABLE" && v.status !== "SLOT_PROPOSED") return false;
    }
    if (selectedTab === "NEEDS_REVIEW" && v.status !== "NEEDS_HUMAN_REVIEW") return false;
    if (selectedTab === "COMPLETED" && v.status !== "COMPLETED") return false;
    if (selectedTab === "CANCELLED" && v.status !== "CANCELLED" && v.status !== "REJECTED") return false;

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const tenantMatch = v.lead_name?.toLowerCase().includes(q);
      const propMatch = v.property_summary?.canonical_name?.toLowerCase().includes(q) ||
        v.property_summary?.building_name?.toLowerCase().includes(q) ||
        v.property_summary?.address?.toLowerCase().includes(q);
      const agentMatch = v.agent_summary?.full_name?.toLowerCase().includes(q) ||
        v.agent_summary?.agency_name?.toLowerCase().includes(q);
      if (!tenantMatch && !propMatch && !agentMatch) return false;
    }

    return true;
  });

  // KPI calculations
  const confirmedCount = viewings.filter((v) => v.status === "CONFIRMED").length;
  const pendingCount = viewings.filter(
    (v) =>
      v.status === "AWAITING_TENANT_CONFIRMATION" ||
      v.status === "AWAITING_AGENT_CONFIRMATION" ||
      v.status === "SLOT_PROPOSED"
  ).length;
  const slotsAvailableCount = viewings.filter(
    (v) => v.status === "SLOTS_AVAILABLE" || v.status === "AWAITING_AGENT_AVAILABILITY"
  ).length;
  const needsReviewCount = viewings.filter((v) => v.status === "NEEDS_HUMAN_REVIEW").length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <PageHeader
        title="Viewing Coordination"
        description="Track and coordinate tenant property viewings, agent confirmation, and schedule status"
        badges={
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            Module 5 Phase 1
          </span>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={loadViewings}
            disabled={loading}
            className="flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-sky-600" : ""}`} />
            Refresh
          </Button>
        }
      />

      {/* KPI Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="border-slate-200 shadow-2xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Viewings</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{total}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600">
              <Calendar className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-emerald-200 bg-emerald-50/20 shadow-2xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-emerald-800 uppercase tracking-wider">Confirmed</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{confirmedCount}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-700">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-amber-200 bg-amber-50/20 shadow-2xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-amber-800 uppercase tracking-wider">Pending Confirmation</p>
              <p className="text-2xl font-bold text-amber-700 mt-1">{pendingCount}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-amber-700">
              <Clock className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-sky-200 bg-sky-50/20 shadow-2xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-sky-800 uppercase tracking-wider">Slots Available</p>
              <p className="text-2xl font-bold text-sky-700 mt-1">{slotsAvailableCount}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-sky-100 flex items-center justify-center text-sky-700">
              <CalendarDays className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-rose-200 bg-rose-50/20 shadow-2xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-rose-800 uppercase tracking-wider">Needs Review</p>
              <p className="text-2xl font-bold text-rose-700 mt-1">{needsReviewCount}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center text-rose-700">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
        {/* Tab Filters */}
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: "ALL", label: "All" },
            { id: "CONFIRMED", label: "Confirmed" },
            { id: "RESCHEDULE_REQUESTED", label: "Reschedule Requested" },
            { id: "PENDING_CONFIRMATION", label: "Pending Confirmation" },
            { id: "SLOTS_AVAILABLE", label: "Slots Available" },
            { id: "NEEDS_REVIEW", label: "Needs Review" },
            { id: "COMPLETED", label: "Completed" },
            { id: "CANCELLED", label: "Cancelled" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedTab(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                selectedTab === tab.id
                  ? "bg-slate-900 text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tenant, property, agent..."
            className="pl-9 h-9 text-xs"
          />
        </div>
      </div>

      {/* Main Content / Viewings Table */}
      <Card className="border-slate-200 shadow-2xs overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-sky-600" />
            <p className="text-sm">Loading viewing coordination list...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-600">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-rose-500" />
            <p className="text-sm font-semibold">{error}</p>
            <Button size="sm" variant="outline" onClick={loadViewings} className="mt-3">
              Try Again
            </Button>
          </div>
        ) : filteredViewings.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Calendar className="w-10 h-10 mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-medium text-slate-700">No viewings found</p>
            <p className="text-xs text-slate-400 mt-1">
              {searchQuery || selectedTab !== "ALL"
                ? "Try adjusting your search or active filter tabs."
                : "Create viewings for qualified leads from the Lead Detail page."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3">Tenant / Lead</th>
                  <th className="px-5 py-3">Property</th>
                  <th className="px-5 py-3">Listing Agent</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Scheduled Time</th>
                  <th className="px-5 py-3 text-center">Confirmations</th>
                  <th className="px-5 py-3">Last Updated</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredViewings.map((v) => {
                  return (
                    <tr key={v.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Tenant */}
                      <td className="px-5 py-4">
                        <Link
                          href={`/leads/${v.lead_id}`}
                          className="font-semibold text-slate-900 hover:text-sky-600 flex items-center gap-1 group"
                        >
                          <span>{v.lead_name || "Lead Details"}</span>
                          <ArrowUpRight className="w-3 h-3 text-slate-400 group-hover:text-sky-600 transition-colors" />
                        </Link>
                        <p className="text-xs text-slate-400 font-mono mt-0.5">
                          ID: {v.lead_id.slice(0, 8)}...
                        </p>
                      </td>

                      {/* Property */}
                      <td className="px-5 py-4">
                        <div className="font-medium text-slate-900">
                          {v.property_summary?.canonical_name ||
                            v.property_summary?.building_name ||
                            "Property"}
                        </div>
                        <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                          <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate max-w-[200px]">
                            {v.property_summary?.address || v.property_summary?.district || "—"}
                          </span>
                        </div>
                        {v.listing_summary?.asking_price && (
                          <div className="text-xs font-mono text-slate-600 mt-0.5">
                            ${v.listing_summary.asking_price.toLocaleString()}/mo
                          </div>
                        )}
                      </td>

                      {/* Agent */}
                      <td className="px-5 py-4">
                        <div className="font-medium text-slate-800">
                          {v.agent_summary?.full_name || "Agent"}
                        </div>
                        <div className="text-xs text-slate-500">
                          {v.agent_summary?.agency_name || "Independent"}
                        </div>
                        {v.agent_summary?.phone && (
                          <div className="text-xs text-slate-400 font-mono mt-0.5 flex items-center gap-1">
                            <Phone className="w-3 h-3" />
                            {v.agent_summary.phone}
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-5 py-4">
                        <StatusBadge status={v.status} />
                      </td>

                      {/* Scheduled Time */}
                      <td className="px-5 py-4">
                        {v.scheduled_start_at ? (
                          <div>
                            <div className="font-medium text-slate-900 flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-sky-600" />
                              {formatDate(v.scheduled_start_at)}
                            </div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5 flex flex-wrap items-center gap-1.5">
                              <span>{v.timezone} ({v.duration_minutes}m)</span>
                              <span className="font-semibold px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 text-2xs">
                                v{v.schedule_version || 1}
                              </span>
                              {v.reschedule_count > 0 && (
                                <span className="font-semibold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 text-2xs">
                                  Rescheduled
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Not scheduled yet</span>
                        )}
                      </td>

                      {/* Confirmation States (Separated) */}
                      <td className="px-5 py-4 text-center">
                        <div className="flex flex-col gap-1 items-center justify-center">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="text-slate-500 font-medium w-14 text-right">Tenant:</span>
                            <StatusBadge status={v.tenant_confirmation_status} />
                          </div>
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="text-slate-500 font-medium w-14 text-right">Agent:</span>
                            <StatusBadge status={v.agent_confirmation_status} />
                          </div>
                        </div>
                      </td>

                      {/* Last Updated */}
                      <td className="px-5 py-4 text-xs text-slate-500">
                        {formatDate(v.updated_at || v.created_at)}
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right">
                        <Link href={`/viewings/${v.id}`}>
                          <Button variant="outline" size="sm" className="gap-1 text-xs">
                            Details
                            <ChevronRight className="w-3 h-3 text-slate-400" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
