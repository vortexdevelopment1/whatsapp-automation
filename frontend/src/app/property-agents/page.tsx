"use client";

import React, { useEffect, useState } from "react";
import {
  Briefcase,
  Plus,
  RefreshCw,
  Search,
  Phone,
  Mail,
  Archive,
  CheckCircle2,
  AlertTriangle,
  X,
  Edit2,
  Building,
} from "lucide-react";
import { api } from "@/lib/api";
import { PropertyAgent, PropertyAgentCreateInput, PropertyAgentStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";

export default function PropertyAgentsPage() {
  const [agents, setAgents] = useState<PropertyAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editingAgent, setEditingAgent] = useState<PropertyAgent | null>(null);

  const [form, setForm] = useState<PropertyAgentCreateInput>({
    full_name: "",
    agency_name: "",
    registration_number: "",
    phone: "",
    email: "",
    status: "ACTIVE",
  });

  const fetchAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listPropertyAgents({ search: search || undefined });
      setAgents(data);
    } catch (err: any) {
      setError(err.message || "Failed to load listing agents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAgents();
  };

  const openCreateModal = () => {
    setEditingAgent(null);
    setForm({
      full_name: "",
      agency_name: "",
      registration_number: "",
      phone: "",
      email: "",
      status: "ACTIVE",
    });
    setIsModalOpen(true);
  };

  const openEditModal = (agent: PropertyAgent) => {
    setEditingAgent(agent);
    setForm({
      full_name: agent.full_name || "",
      agency_name: agent.agency_name || "",
      registration_number: agent.registration_number || "",
      phone: agent.phone || "",
      email: agent.email || "",
      status: agent.status,
    });
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      if (editingAgent) {
        await api.updatePropertyAgent(editingAgent.id, form);
      } else {
        await api.createPropertyAgent(form);
      }
      setIsModalOpen(false);
      fetchAgents();
    } catch (err: any) {
      setError(err.message || "Failed to save agent.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleArchive = async (agentId: string) => {
    if (!confirm("Are you sure you want to archive this property agent?")) return;
    try {
      await api.archivePropertyAgent(agentId);
      fetchAgents();
    } catch (err: any) {
      setError(err.message || "Failed to archive agent.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <PageHeader
            title="External Property Agents"
            description="Counterparty landlord and listing agents for open-market property listings"
            breadcrumbs={[
              { label: "Properties", href: "/properties" },
              { label: "Listing Agents", href: "/property-agents" },
            ]}
          />
          <button
            onClick={openCreateModal}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg text-white bg-sky-600 hover:bg-sky-700 shadow-xs transition-colors self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            Add Property Agent
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2 shadow-2xs">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Search */}
        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <form onSubmit={handleSearchSubmit} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by agent name, agency, registration number, or phone..."
                className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
            >
              Search
            </button>
          </form>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-slate-500 space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-sky-600 mx-auto" />
              <p className="text-sm">Loading agents...</p>
            </div>
          ) : agents.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <Briefcase className="w-8 h-8 text-slate-300 mx-auto" />
              <div className="text-sm font-semibold text-slate-700">No property agents found</div>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Add an external agent record or seed demo inventory from the Properties page.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th scope="col" className="px-6 py-3.5">
                      Agent Name
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Agency / CEA Reg
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Contact
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3.5 text-right">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {agents.map((a) => (
                    <tr key={a.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{a.full_name || "Unnamed Agent"}</div>
                        <div className="text-2xs font-mono text-slate-400">ID: {a.id}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-slate-800 font-medium">{a.agency_name || "Independent"}</div>
                        {a.registration_number && (
                          <div className="text-xs font-mono text-slate-400">CEA: {a.registration_number}</div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs space-y-0.5">
                        {a.phone && (
                          <div className="flex items-center gap-1.5 text-slate-700">
                            <Phone className="w-3 h-3 text-slate-400" />
                            <span>{a.phone}</span>
                            {a.phone_normalized && a.phone_normalized !== a.phone && (
                              <span className="text-2xs text-slate-400 font-mono">({a.phone_normalized})</span>
                            )}
                          </div>
                        )}
                        {a.email && (
                          <div className="flex items-center gap-1.5 text-slate-500">
                            <Mail className="w-3 h-3 text-slate-400" />
                            <span>{a.email}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            a.status === "ACTIVE"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : a.status === "ARCHIVED"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                          }`}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => openEditModal(a)}
                            className="p-1.5 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
                            title="Edit Agent"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          {a.status !== "ARCHIVED" && (
                            <button
                              onClick={() => handleArchive(a.id)}
                              className="p-1.5 text-rose-500 hover:text-rose-700 rounded-lg hover:bg-rose-50 transition-colors"
                              title="Archive Agent"
                            >
                              <Archive className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal: Add/Edit Property Agent */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-slate-900">
                  {editingAgent ? "Edit Property Agent" : "Add Property Agent"}
                </h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleSave} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Full Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={form.full_name || ""}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    placeholder="e.g. John Tan"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Agency Name
                  </label>
                  <input
                    type="text"
                    value={form.agency_name || ""}
                    onChange={(e) => setForm({ ...form, agency_name: e.target.value })}
                    placeholder="e.g. PropNex Realty"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Registration Number (CEA)
                  </label>
                  <input
                    type="text"
                    value={form.registration_number || ""}
                    onChange={(e) => setForm({ ...form, registration_number: e.target.value })}
                    placeholder="e.g. R012345A"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    value={form.phone || ""}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="e.g. +65 9123 4567"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                  <p className="text-2xs text-slate-400 mt-1">
                    Will be normalized automatically (e.g. +6591234567).
                  </p>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={form.email || ""}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="e.g. agent@propnex.sg"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Status</label>
                  <select
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value as PropertyAgentStatus })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="UNVERIFIED">UNVERIFIED</option>
                    <option value="ARCHIVED">ARCHIVED</option>
                  </select>
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
                    {submitting ? "Saving..." : "Save Agent"}
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
