"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Calendar,
  Clock,
  Building2,
  Phone,
  RefreshCw,
  Plus,
  CheckCircle2,
  ChevronRight,
  MapPin,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";

import { api } from "@/lib/api";
import { Viewing, PropertyMatch } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils";

interface LeadViewingsSectionProps {
  leadId: string;
  isQualified?: boolean;
}

export function LeadViewingsSection({ leadId, isQualified = true }: LeadViewingsSectionProps) {
  const router = useRouter();
  const [viewings, setViewings] = useState<Viewing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadViewings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.listLeadViewings(leadId);
      setViewings(res.items || []);
    } catch (err: any) {
      setError(err.message || "Failed to load lead viewings");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadViewings();
  }, [loadViewings]);

  return (
    <Card className="border-slate-200 shadow-2xs">
      <CardHeader className="border-b border-slate-100 bg-slate-50/50 py-3.5 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-semibold flex items-center gap-2 text-slate-800">
          <Calendar className="w-4 h-4 text-sky-600" />
          Viewings & Coordination ({viewings.length})
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadViewings}
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
            <p className="text-xs">Loading viewings...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-rose-50 rounded-lg text-rose-700 text-xs">
            {error}
          </div>
        ) : viewings.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <Calendar className="w-8 h-8 mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-medium text-slate-600">No viewings scheduled for this lead</p>
            <p className="text-xs text-slate-400 mt-1">
              Viewings can be scheduled once property matches are shortlisted and verified.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {viewings.map((v) => (
              <div
                key={v.id}
                className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 text-sm">
                      {v.property_summary?.canonical_name ||
                        v.property_summary?.building_name ||
                        "Property"}
                    </span>
                    <StatusBadge status={v.status} />
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      {v.property_summary?.address || v.property_summary?.district || "—"}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      {v.scheduled_start_at ? (
                        <span className="font-medium text-slate-700">
                          {formatDate(v.scheduled_start_at)} ({v.timezone})
                        </span>
                      ) : (
                        <span className="italic text-slate-400">Time unconfirmed</span>
                      )}
                    </span>
                    <span>
                      Agent: <strong>{v.agent_summary?.full_name || "—"}</strong> ({v.agent_summary?.agency_name || "Independent"})
                    </span>
                  </div>

                  <div className="flex items-center gap-3 pt-1 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400">Tenant:</span>
                      <StatusBadge status={v.tenant_confirmation_status} />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400">Agent:</span>
                      <StatusBadge status={v.agent_confirmation_status} />
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Link href={`/viewings/${v.id}`}>
                    <Button variant="outline" size="sm" className="text-xs gap-1">
                      View Coordination
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
