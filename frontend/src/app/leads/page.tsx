"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  UserCheck,
  Search,
  Filter,
  Plus,
  RefreshCw,
  Phone,
  Mail,
  ArrowRight,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { Lead } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";

export default function LeadsListPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Create Lead Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm, setCreateForm] = useState({
    full_name: "",
    phone: "",
    email: "",
    consent_status: "UNKNOWN",
  });

  const loadLeads = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listLeads({
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      });
      setLeads(data);
    } catch (err: any) {
      setError(err.message || "Failed to load leads");
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreateLoading(true);
      setError(null);
      await api.createLead({
        full_name: createForm.full_name.trim() || undefined,
        phone: createForm.phone.trim(),
        email: createForm.email.trim() || undefined,
        consent_status: createForm.consent_status,
      });
      setIsCreateModalOpen(false);
      setCreateForm({ full_name: "", phone: "", email: "", consent_status: "UNKNOWN" });
      await loadLeads();
    } catch (err: any) {
      setError(err.message || "Failed to create lead");
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <UserCheck className="w-6 h-6 text-sky-600" />
            Lead Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Capture, normalize, deduplicate, and qualify inbound rental leads.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsCreateModalOpen(true)}
            className="gap-1.5"
          >
            <Plus className="w-4 h-4" />
            Create Lead
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Filter / Search Bar */}
      <Card>
        <CardContent className="p-4 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search leads by name, phone, or email..."
              className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-sky-500"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="sm:w-48">
            <select
              className="w-full py-2 px-3 border border-slate-200 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-sky-500 text-slate-700"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="NEW">NEW</option>
              <option value="VALIDATING">VALIDATING</option>
              <option value="DUPLICATE">DUPLICATE</option>
              <option value="READY_FOR_OUTREACH">READY FOR OUTREACH</option>
              <option value="INELIGIBLE">INELIGIBLE</option>
              <option value="OPTED_OUT">OPTED OUT</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>
          <Button variant="outline" size="sm" onClick={loadLeads} className="gap-1">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </CardContent>
      </Card>

      {/* Leads Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-12 text-center text-slate-500 flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            Loading leads...
          </div>
        ) : leads.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            No leads found matching your criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-xs font-semibold text-slate-500 tracking-wider">
                  <th className="py-3.5 px-4">Lead Name</th>
                  <th className="py-3.5 px-4">Phone (Normalized)</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Eligibility</th>
                  <th className="py-3.5 px-4">Consent</th>
                  <th className="py-3.5 px-4">Created</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {leads.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      <Link href={`/leads/${l.id}`} className="hover:text-sky-600 transition-colors">
                        {l.full_name || "Unnamed Lead"}
                      </Link>
                      {l.duplicate_override && (
                        <span className="ml-2 inline-block bg-purple-50 text-purple-700 border border-purple-200 text-3xs px-1.5 py-0.2 rounded-full font-bold">
                          OVERRIDDEN
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700">
                      {l.phone_normalized}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={l.status} />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={l.contact_eligibility} />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={l.consent_status} />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {formatDate(l.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/leads/${l.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-800"
                      >
                        View Details
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE LEAD MODAL */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Lead"
      >
        <form onSubmit={handleCreateLead} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
            <Input
              placeholder="e.g. Rachel Lim"
              value={createForm.full_name}
              onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Phone Number (Singapore or International) *
            </label>
            <Input
              placeholder="e.g. +65 9123 4567 or 91234567"
              value={createForm.phone}
              onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
              required
            />
            <p className="text-3xs text-slate-400 mt-1">
              Numbers will be automatically normalized into canonical E.164 format.
            </p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Email</label>
            <Input
              type="email"
              placeholder="rachel.lim@example.com"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Consent Status</label>
            <select
              className="w-full py-2 px-3 border border-slate-200 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-sky-500"
              value={createForm.consent_status}
              onChange={(e) => setCreateForm({ ...createForm, consent_status: e.target.value })}
            >
              <option value="UNKNOWN">UNKNOWN</option>
              <option value="CONSENTED">CONSENTED</option>
              <option value="NOT_CONSENTED">NOT CONSENTED</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={createLoading}
            >
              Create Lead
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
