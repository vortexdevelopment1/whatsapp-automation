"use client";

import React, { useState, useEffect, useCallback } from "react";
import { FileText, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { AuditLog } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/utils";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [entityFilter, setEntityFilter] = useState("");
  const [search, setSearch] = useState("");

  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listAuditLogs({
        entity_type: entityFilter || undefined,
        limit: 100,
      });
      setLogs(data);
    } catch (err: any) {
      setError(err.message || "Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }, [entityFilter]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const filteredLogs = logs.filter((log) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      log.action.toLowerCase().includes(s) ||
      log.actor_id.toLowerCase().includes(s) ||
      log.entity_id.toLowerCase().includes(s)
    );
  });

  return (
    <div>
      <PageHeader
        title="System Audit Trail"
        description="Immutable audit trail of administrator agent verifications, activations, configuration updates, and test events."
        actions={
          <Button
            variant="outline"
            size="md"
            onClick={() => loadLogs()}
            icon={<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />}
          >
            Refresh
          </Button>
        }
      />

      {/* Filter toolbar */}
      <Card className="p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch sm:items-center">
          <div className="w-full sm:w-80">
            <Input
              type="text"
              placeholder="Search by action, actor, or entity..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              icon={<Search className="w-4 h-4" />}
            />
          </div>

          <div className="w-full sm:w-60">
            <Select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
            >
              <option value="">All Entity Types</option>
              <option value="Agent">Agent</option>
              <option value="AgentBrandingProfile">AgentBrandingProfile</option>
              <option value="WhatsAppProfile">WhatsAppProfile</option>
              <option value="MessageTemplate">MessageTemplate</option>
              <option value="WhatsAppMessage">WhatsAppMessage</option>
            </Select>
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* Table */}
      <Card>
        {loading && logs.length === 0 ? (
          <div className="p-6">
            <TableSkeleton rows={6} cols={6} />
          </div>
        ) : filteredLogs.length === 0 ? (
          <EmptyState
            icon={<FileText className="w-8 h-8 text-slate-400" />}
            title="No audit events found"
            description="No audit trail events match your current filter selection."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200/80 text-left text-sm">
              <thead className="bg-slate-50/70 text-slate-600 font-semibold text-xs uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">Timestamp</th>
                  <th scope="col" className="px-6 py-3.5">Action Event</th>
                  <th scope="col" className="px-6 py-3.5">Entity Type</th>
                  <th scope="col" className="px-6 py-3.5">Entity ID</th>
                  <th scope="col" className="px-6 py-3.5">Actor</th>
                  <th scope="col" className="px-6 py-3.5">Changes Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4 text-xs font-mono text-slate-500 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-600 font-medium">
                      {log.entity_type}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-500 truncate max-w-[120px]">
                      {log.entity_id}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-700 font-semibold">
                      {log.actor_id}
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-slate-500 truncate max-w-[260px]">
                      {log.new_value ? JSON.stringify(log.new_value) : "—"}
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
