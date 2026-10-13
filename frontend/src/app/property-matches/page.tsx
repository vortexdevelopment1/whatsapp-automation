"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Building2,
  Users,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  ChevronRight,
  ExternalLink,
  Award,
  Send,
  RotateCcw,
} from "lucide-react";
import { api } from "@/lib/api";
import { Lead } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { formatDate } from "@/lib/utils";

export default function PropertyMatchesHubPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const loadLeads = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listLeads({ limit: 50 });
      setLeads(data);
    } catch (err: any) {
      console.error("Failed to load leads for matching overview:", err);
      setError(err.message || "Failed to load matching candidates hub.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeads();
  }, []);

  const filteredLeads = leads.filter((l) => {
    const matchesSearch =
      !search ||
      (l.full_name && l.full_name.toLowerCase().includes(search.toLowerCase())) ||
      (l.phone && l.phone.includes(search));

    const matchesStatus =
      statusFilter === "ALL" ||
      statusFilter === (l.status as string);

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <PageHeader
        title="Property Matching & Shortlist Hub"
        description="Operator hub for lead-to-property matching runs, agent verifications, shortlists, and Module 5 handoffs."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={loadLeads}
            disabled={loading}
            className="text-xs gap-1.5"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {/* KPI Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Active Leads
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{leads.length}</div>
          <p className="text-[11px] text-slate-400 mt-1">Under tenant pipeline</p>
        </div>

        <div className="p-4 bg-emerald-50/70 rounded-xl border border-emerald-200/80 shadow-xs">
          <div className="text-xs font-semibold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
            <Award className="w-4 h-4 text-emerald-600" />
            Qualified for Matching
          </div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">
            {leads.filter((l) => (l.status as string) === "QUALIFIED" || (l.status as string) === "REPLIED").length}
          </div>
          <p className="text-[11px] text-emerald-600 mt-1">Eligible for property search & outreach</p>
        </div>

        <div className="p-4 bg-indigo-50/70 rounded-xl border border-indigo-200/80 shadow-xs">
          <div className="text-xs font-semibold text-indigo-800 uppercase tracking-wider flex items-center gap-1.5">
            <Send className="w-4 h-4 text-indigo-600" />
            In Qualification Loop
          </div>
          <div className="text-2xl font-bold text-indigo-700 mt-1">
            {leads.filter((l) => (l.status as string) === "QUALIFYING" || l.status === "NEW" || (l.status as string) === "CONTACTED").length}
          </div>
          <p className="text-[11px] text-indigo-600 mt-1">Awaiting requirements completion</p>
        </div>

        <div className="p-4 bg-purple-50/70 rounded-xl border border-purple-200/80 shadow-xs">
          <div className="text-xs font-semibold text-purple-800 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-purple-600" />
            Ready for Module 5
          </div>
          <div className="text-2xl font-bold text-purple-700 mt-1">
            {leads.filter((l) => (l.status as string) === "QUALIFIED").length}
          </div>
          <p className="text-[11px] text-purple-600 mt-1">Viewing coordination gating</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="border-slate-200 shadow-xs">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search tenant name or phone..."
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Filter className="w-4 h-4 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter leads by status"
                className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Qualification Statuses</option>
                <option value="QUALIFIED">Qualified (Matching Ready)</option>
                <option value="QUALIFYING">In Progress (Qualifying)</option>
                <option value="DISQUALIFIED">Disqualified</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Leads Table */}
      <Card className="border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50/80 text-slate-600 border-b border-slate-200 uppercase tracking-wider text-[11px] font-semibold">
              <tr>
                <th className="py-3 px-4">Lead / Tenant</th>
                <th className="py-3 px-4">Phone</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Module 4 Matching Pipeline</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredLeads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No leads found matching current criteria.
                  </td>
                </tr>
              ) : (
                filteredLeads.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">
                        {l.full_name || "Tenant"}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">{l.id.substring(0, 8)}...</div>
                    </td>
                    <td className="py-3 px-4 font-mono">{l.phone || "—"}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={l.status} />
                    </td>
                    <td className="py-3 px-4">
                      {(l.status as string) === "QUALIFIED" ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Ready for Shortlist Matching
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          Requires Lead Qualification
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{formatDate(l.created_at)}</td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <Link
                        href={`/leads/${l.id}/property-matching`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 shadow-2xs transition-colors"
                      >
                        <Building2 className="w-3.5 h-3.5" />
                        Open Matching Dashboard
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
