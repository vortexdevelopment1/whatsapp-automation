"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  Send,
  Award,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";
import { Lead, TenantRequirement } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { PropertyMatchingSection } from "@/components/leads/PropertyMatchingSection";

export default function LeadPropertyMatchingDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const [lead, setLead] = useState<Lead | null>(null);
  const [requirement, setRequirement] = useState<TenantRequirement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLeadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [leadData, reqData] = await Promise.all([
        api.getLead(leadId),
        api.getTenantRequirements(leadId).catch(() => null),
      ]);
      setLead(leadData);
      setRequirement(reqData);
    } catch (err: any) {
      console.error("Failed to load lead details:", err);
      setError(err.message || "Failed to load lead property-matching dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeadData();
  }, [leadId]);

  const isQualified = requirement?.qualification_status === "QUALIFIED";

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center space-x-2 text-xs text-slate-500">
        <Link href="/leads" className="hover:text-indigo-600 transition-colors">
          Leads
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        <Link href={`/leads/${leadId}`} className="hover:text-indigo-600 transition-colors">
          {lead ? `${lead.full_name || lead.phone || leadId.substring(0, 8)}` : "Lead"}
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        <span className="font-semibold text-slate-800">Property Matching & Shortlist</span>
      </nav>

      {/* Main Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <Link
                href={`/leads/${leadId}`}
                className="inline-flex items-center text-xs text-slate-500 hover:text-slate-800 p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
                title="Back to Lead Overview"
              >
                <ArrowLeft className="w-4 h-4" />
              </Link>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <Building2 className="w-6 h-6 text-indigo-600" />
                Property Matching Dashboard
              </h1>
              {requirement?.qualification_status && (
                <StatusBadge status={requirement.qualification_status} />
              )}
            </div>
            <p className="text-xs text-slate-500">
              Deterministic property search, ranking, multi-agent WhatsApp verification, shortlist generation, and Module 5 handoff readiness.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadLeadData}
              disabled={loading}
              className="text-xs gap-1.5 border-slate-300"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh Lead
            </Button>
            <Link
              href={`/leads/${leadId}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View Lead CRM
            </Link>
          </div>
        </div>

        {/* Tenant Requirements Quick Bar */}
        {requirement && (
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs">
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Location</span>
              <span className="font-semibold text-slate-800">
                {requirement.preferred_locations && requirement.preferred_locations.length > 0
                  ? requirement.preferred_locations.join(", ")
                  : "Any"}
              </span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Max Budget</span>
              <span className="font-semibold text-slate-800">
                {requirement.budget_max ? `SGD ${Number(requirement.budget_max).toLocaleString()}` : "N/A"}
              </span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Property Type</span>
              <span className="font-semibold text-slate-800">{requirement.property_type || "Any"}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Bedrooms</span>
              <span className="font-semibold text-slate-800">{requirement.bedrooms ?? "Any"} BR</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Move-in Date</span>
              <span className="font-semibold text-slate-800">{requirement.move_in_date || "Flexible"}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Min Lease</span>
              <span className="font-semibold text-slate-800">{requirement.lease_duration_months || 12} mo</span>
            </div>
          </div>
        )}
      </div>

      {/* Main Matching & Shortlist Dashboard Section */}
      <PropertyMatchingSection
        leadId={leadId}
        qualificationStatus={requirement?.qualification_status}
        onRefreshLead={loadLeadData}
      />
    </div>
  );
}
