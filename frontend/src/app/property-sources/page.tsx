"use client";

import React, { useEffect, useState } from "react";
import {
  Layers,
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  X,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { PropertySource, PropertySourceCreateInput, PropertySourceType } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";

export default function PropertySourcesPage() {
  const [sources, setSources] = useState<PropertySource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState<PropertySourceCreateInput>({
    name: "",
    source_type: "MANUAL",
    external_system_name: "",
    status: "ACTIVE",
    configuration_reference: "",
  });

  const fetchSources = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listPropertySources();
      setSources(data);
    } catch (err: any) {
      setError(err.message || "Failed to load property sources.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      await api.createPropertySource(form);
      setIsModalOpen(false);
      setForm({
        name: "",
        source_type: "MANUAL",
        external_system_name: "",
        status: "ACTIVE",
        configuration_reference: "",
      });
      fetchSources();
    } catch (err: any) {
      setError(err.message || "Failed to create source.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (source: PropertySource) => {
    try {
      if (source.status === "ACTIVE") {
        await api.deactivatePropertySource(source.id);
      } else {
        await api.activatePropertySource(source.id);
      }
      fetchSources();
    } catch (err: any) {
      setError(err.message || "Failed to update source status.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <PageHeader
            title="Property Sources"
            description="Manage inventory providers, CSV imports, and verified MLS API feeds"
            breadcrumbs={[
              { label: "Properties", href: "/properties" },
              { label: "Sources", href: "/property-sources" },
            ]}
          />
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg text-white bg-sky-600 hover:bg-sky-700 shadow-xs transition-colors self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            Add Property Source
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2 shadow-2xs">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-slate-500 space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-sky-600 mx-auto" />
              <p className="text-sm">Loading sources...</p>
            </div>
          ) : sources.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <Layers className="w-8 h-8 text-slate-300 mx-auto" />
              <div className="text-sm font-semibold text-slate-700">No sources registered yet</div>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Add your first listing source or load demo inventory from the Properties page.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th scope="col" className="px-6 py-3.5">
                      Source Name
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Ingestion Type
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      External System
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Created At
                    </th>
                    <th scope="col" className="px-6 py-3.5 text-right">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sources.map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{s.name}</div>
                        <div className="text-2xs font-mono text-slate-400">ID: {s.id}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {s.source_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs font-mono text-slate-600">
                        {s.external_system_name || "—"}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            s.status === "ACTIVE"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                          }`}
                        >
                          {s.status === "ACTIVE" ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <XCircle className="w-3 h-3 text-slate-400" />
                          )}
                          {s.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleToggleStatus(s)}
                          className={`text-xs font-semibold px-3 py-1 rounded-lg border transition-colors ${
                            s.status === "ACTIVE"
                              ? "border-rose-200 text-rose-700 hover:bg-rose-50"
                              : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                          }`}
                        >
                          {s.status === "ACTIVE" ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal: Add Property Source */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-slate-900">Add Property Source</h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreate} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Source Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g. Agency Internal Sheet"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Source Type <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={form.source_type}
                    onChange={(e) => setForm({ ...form, source_type: e.target.value as PropertySourceType })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  >
                    <option value="MANUAL">MANUAL (Direct Entry)</option>
                    <option value="CSV_IMPORT">CSV_IMPORT (Agency File)</option>
                    <option value="CLIENT_INVENTORY">CLIENT_INVENTORY (Private Landlord)</option>
                    <option value="APPROVED_API">APPROVED_API (Partner Portal Feed)</option>
                    <option value="DEMO">DEMO (Synthetic Demo)</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    External System Name
                  </label>
                  <input
                    type="text"
                    value={form.external_system_name || ""}
                    onChange={(e) => setForm({ ...form, external_system_name: e.target.value })}
                    placeholder="e.g. MLS_DirectFeed_SG"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Configuration Reference
                  </label>
                  <input
                    type="text"
                    value={form.configuration_reference || ""}
                    onChange={(e) => setForm({ ...form, configuration_reference: e.target.value })}
                    placeholder="e.g. feeds/partner_v2_spec"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                  <p className="text-2xs text-slate-400 mt-1">
                    Do not store passwords or API secrets directly in this field.
                  </p>
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 font-semibold text-slate-600 hover:bg-slate-50 rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg disabled:opacity-50"
                  >
                    {submitting ? "Saving..." : "Create Source"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
