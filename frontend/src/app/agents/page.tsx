"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, Search, Filter, RefreshCw, UserCheck, PhoneCall, Building2 } from "lucide-react";
import { api } from "@/lib/api";
import { Agent, AgentStatus, AuthorizationStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/utils";

export default function AgentsListPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<AgentStatus | "">("");
  const [authFilter, setAuthFilter] = useState<AuthorizationStatus | "">("");

  const loadAgents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listAgents({
        search: search || undefined,
        status: statusFilter ? statusFilter : undefined,
        authorization_status: authFilter ? authFilter : undefined,
      });
      setAgents(data);
    } catch (err: any) {
      setError(err.message || "Failed to load agents list.");
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, authFilter]);

  useEffect(() => {
    const handler = setTimeout(() => {
      loadAgents();
    }, 200);
    return () => clearTimeout(handler);
  }, [loadAgents]);

  return (
    <div>
      <PageHeader
        title="Property Agents"
        description="Authorized estate agent directory, license verification statuses, and communication profiles."
        actions={
          <Link href="/agents/new">
            <Button icon={<Plus className="w-4 h-4" />}>
              Create Agent
            </Button>
          </Link>
        }
      />

      {/* Filter Toolbar */}
      <Card className="p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4 justify-between items-stretch md:items-center">
          <div className="w-full md:w-80">
            <Input
              type="text"
              placeholder="Search by name, CEA reg, email, phone..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              icon={<Search className="w-4 h-4" />}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="w-36">
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
              >
                <option value="">All Statuses</option>
                <option value="DRAFT">Draft</option>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
                <option value="ARCHIVED">Archived</option>
              </Select>
            </div>

            <div className="w-40">
              <Select
                value={authFilter}
                onChange={(e) => setAuthFilter(e.target.value as any)}
              >
                <option value="">All Authorizations</option>
                <option value="PENDING">Pending</option>
                <option value="VERIFIED">Verified</option>
                <option value="REJECTED">Rejected</option>
              </Select>
            </div>

            <Button
              variant="outline"
              size="md"
              onClick={() => loadAgents()}
              title="Refresh list"
              icon={<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />}
            >
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>
      </Card>

      {/* Error state */}
      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* Agents Table Card */}
      <Card>
        {loading && agents.length === 0 ? (
          <div className="p-6">
            <TableSkeleton rows={4} cols={7} />
          </div>
        ) : agents.length === 0 ? (
          <EmptyState
            icon={<UserCheck className="w-8 h-8 text-slate-400" />}
            title="No agents found"
            description={
              search || statusFilter || authFilter
                ? "No agent records match the current filter criteria."
                : "Get started by adding your first authorized estate agent profile."
            }
            action={
              <Link href="/agents/new">
                <Button icon={<Plus className="w-4 h-4" />}>Create Agent</Button>
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200/80 text-left text-sm">
              <thead className="bg-slate-50/70 text-slate-600 font-semibold text-xs uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">Agent Details</th>
                  <th scope="col" className="px-6 py-3.5">Agency</th>
                  <th scope="col" className="px-6 py-3.5">CEA Registration</th>
                  <th scope="col" className="px-6 py-3.5">Contact</th>
                  <th scope="col" className="px-6 py-3.5">Authorization</th>
                  <th scope="col" className="px-6 py-3.5">Status</th>
                  <th scope="col" className="px-6 py-3.5">Last Updated</th>
                  <th scope="col" className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {agents.map((agent) => (
                  <tr key={agent.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-sky-100 text-sky-800 font-bold flex items-center justify-center text-xs flex-shrink-0">
                          {agent.full_name[0]}
                        </div>
                        <div>
                          <Link
                            href={`/agents/${agent.id}`}
                            className="font-semibold text-slate-900 hover:text-sky-600 transition-colors"
                          >
                            {agent.full_name}
                          </Link>
                          {agent.display_name && (
                            <p className="text-xs text-slate-400">aka {agent.display_name}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-800">{agent.agency_name}</div>
                      {agent.designation && (
                        <p className="text-xs text-slate-400">{agent.designation}</p>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-mono text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {agent.registration_number || "PENDING"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs">
                      <div className="text-slate-800 font-mono">{agent.phone || "—"}</div>
                      <div className="text-slate-400">{agent.email || "—"}</div>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={agent.authorization_status} type="auth" />
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={agent.status} type="agent" />
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500 whitespace-nowrap">
                      {formatDate(agent.updated_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link href={`/agents/${agent.id}`}>
                        <Button variant="outline" size="sm">
                          View
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
