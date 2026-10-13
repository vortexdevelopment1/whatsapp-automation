"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  CheckCircle,
  Power,
  Archive,
  Palette,
  MessageSquare,
  FileCode,
  AlertTriangle,
  RefreshCw,
  Edit2,
  Clock,
  ShieldCheck,
  Building2,
  Mail,
  Phone,
  FileBadge,
  SendHorizontal,
} from "lucide-react";
import { api } from "@/lib/api";
import { Agent, AgentBranding, WhatsAppProfile, MessageTemplate, AuditLog } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentSubNav } from "@/components/shared/AgentSubNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [branding, setBranding] = useState<AgentBranding | null>(null);
  const [whatsapp, setWhatsapp] = useState<WhatsAppProfile | null>(null);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    full_name: "",
    display_name: "",
    agency_name: "",
    designation: "",
    registration_number: "",
    phone: "",
    email: "",
    notes: "",
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, brandingData, whatsappData, templatesData, msgsData, logsData] =
        await Promise.all([
          api.getAgent(agentId),
          api.getBranding(agentId),
          api.getWhatsAppConfig(agentId),
          api.listTemplates(agentId),
          api.listMessages(agentId),
          api.listAuditLogs({ entity_id: agentId, limit: 10 }),
        ]);
      setAgent(agentData);
      setBranding(brandingData);
      setWhatsapp(whatsappData);
      setTemplates(templatesData);
      setMessages(msgsData || []);
      setAuditLogs(logsData);

      setEditForm({
        full_name: agentData.full_name,
        display_name: agentData.display_name || "",
        agency_name: agentData.agency_name,
        designation: agentData.designation || "",
        registration_number: agentData.registration_number || "",
        phone: agentData.phone || "",
        email: agentData.email || "",
        notes: agentData.notes || "",
      });
    } catch (err: any) {
      setError(err.message || "Failed to load agent profile data.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Status Action Handlers
  const handleVerify = async (newStatus: "VERIFIED" | "REJECTED") => {
    if (!agent) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await api.updateAgent(agent.id, { authorization_status: newStatus });
      setAgent(updated);
      setSuccessMsg(`Authorization status updated to ${newStatus}.`);
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivate = async () => {
    if (!agent) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await api.activateAgent(agent.id);
      setAgent(updated);
      setSuccessMsg("Agent activated successfully.");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!agent) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await api.deactivateAgent(agent.id);
      setAgent(updated);
      setSuccessMsg("Agent deactivated.");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!agent) return;
    if (!confirm("Are you sure you want to archive this agent record?")) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await api.archiveAgent(agent.id);
      setAgent(updated);
      setSuccessMsg("Agent archived.");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agent) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await api.updateAgent(agent.id, {
        full_name: editForm.full_name.trim(),
        display_name: editForm.display_name.trim() || null,
        agency_name: editForm.agency_name.trim(),
        designation: editForm.designation.trim() || null,
        registration_number: editForm.registration_number.trim() || null,
        phone: editForm.phone.trim() || null,
        email: editForm.email.trim() || null,
        notes: editForm.notes.trim() || null,
      });
      setAgent(updated);
      setIsEditModalOpen(false);
      setSuccessMsg("Agent profile updated successfully.");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !agent) {
    return (
      <div className="py-24 text-center text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-sky-600" />
        <p className="text-sm">Loading agent profile...</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="py-16 text-center text-slate-700">
        <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
        <h2 className="text-lg font-bold">Agent Not Found</h2>
        <p className="text-sm text-slate-500 mt-1">This agent profile may have been removed or does not exist.</p>
        <Link href="/agents" className="inline-block mt-4">
          <Button variant="outline">Back to Agents</Button>
        </Link>
      </div>
    );
  }

  const isVerified = agent.authorization_status === "VERIFIED";

  return (
    <div>
      <PageHeader
        breadcrumbs={[
          { label: "Agents", href: "/agents" },
          { label: agent.full_name },
        ]}
        title={agent.full_name}
        description={`${agent.agency_name} ${agent.designation ? `• ${agent.designation}` : ""}`}
        badges={
          <>
            <StatusBadge status={agent.status} type="agent" />
            <StatusBadge status={agent.authorization_status} type="auth" />
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditModalOpen(true)}
              icon={<Edit2 className="w-3.5 h-3.5" />}
            >
              Edit Profile
            </Button>

            {agent.authorization_status !== "VERIFIED" && (
              <Button
                variant="primary"
                size="sm"
                loading={actionLoading}
                onClick={() => handleVerify("VERIFIED")}
                icon={<CheckCircle className="w-3.5 h-3.5" />}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                Verify Authorization
              </Button>
            )}

            {agent.authorization_status === "VERIFIED" && agent.status !== "ACTIVE" && (
              <Button
                variant="primary"
                size="sm"
                loading={actionLoading}
                onClick={handleActivate}
                icon={<Power className="w-3.5 h-3.5" />}
              >
                Activate Agent
              </Button>
            )}

            {agent.authorization_status !== "VERIFIED" && agent.status !== "ACTIVE" && (
              <div className="relative group">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled
                  icon={<Power className="w-3.5 h-3.5" />}
                >
                  Activate (Unverified)
                </Button>
                <div className="absolute right-0 bottom-full mb-1.5 hidden group-hover:block w-64 p-2.5 bg-slate-800 text-white text-xs rounded-lg shadow-xl z-30 leading-snug">
                  Strict Rule: Agent can only be activated after authorization is VERIFIED.
                </div>
              </div>
            )}

            {agent.status === "ACTIVE" && (
              <Button
                variant="outline"
                size="sm"
                loading={actionLoading}
                onClick={handleDeactivate}
                icon={<Power className="w-3.5 h-3.5" />}
              >
                Deactivate
              </Button>
            )}

            {agent.status !== "ARCHIVED" && (
              <Button
                variant="outline"
                size="sm"
                loading={actionLoading}
                onClick={handleArchive}
                icon={<Archive className="w-3.5 h-3.5" />}
              >
                Archive
              </Button>
            )}
          </div>
        }
      />

      {/* Sub-Navigation Tabs */}
      <AgentSubNav
        agentId={agentId}
        templateCount={templates.length}
        messageCount={messages.length}
      />

      {/* Notifications */}
      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      {successMsg && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-700 font-bold ml-4">×</button>
        </div>
      )}

      {/* Content Layout: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Details & Audit Trail (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          <Card>
            <CardHeader className="py-4 px-6">
              <CardTitle className="text-sm font-semibold">
                <FileBadge className="w-4 h-4 text-sky-600" />
                Profile Information
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditModalOpen(true)}
                icon={<Edit2 className="w-3.5 h-3.5" />}
              >
                Edit
              </Button>
            </CardHeader>
            <CardContent className="p-6">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5 text-sm">
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Legal Full Name</dt>
                  <dd className="mt-1 font-semibold text-slate-900 text-base">{agent.full_name}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Display Name</dt>
                  <dd className="mt-1 text-slate-800">{agent.display_name || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Agency Name</dt>
                  <dd className="mt-1 text-slate-800 flex items-center gap-1.5 font-medium">
                    <Building2 className="w-4 h-4 text-slate-400" />
                    {agent.agency_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Designation</dt>
                  <dd className="mt-1 text-slate-800">{agent.designation || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">CEA Registration No.</dt>
                  <dd className="mt-1 font-mono text-sm font-semibold text-slate-800 bg-slate-100/80 px-2 py-0.5 rounded border border-slate-200 inline-block">
                    {agent.registration_number || "PENDING"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Contact Phone</dt>
                  <dd className="mt-1 text-slate-800 font-mono flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    {agent.phone || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Official Email</dt>
                  <dd className="mt-1 text-slate-800 flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-slate-400" />
                    {agent.email || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Registered Since</dt>
                  <dd className="mt-1 text-slate-600 text-xs font-mono">{formatDate(agent.created_at)}</dd>
                </div>
                <div className="sm:col-span-2 pt-2 border-t border-slate-100">
                  <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Internal Notes</dt>
                  <dd className="mt-1 text-slate-600 text-xs italic bg-slate-50 p-3 rounded-lg border border-slate-200/60 leading-relaxed">
                    {agent.notes || "No internal operator notes added."}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Audit Activity */}
          <Card>
            <CardHeader className="py-4 px-6">
              <CardTitle className="text-sm font-semibold">
                <Clock className="w-4 h-4 text-slate-500" />
                Recent Audit Trail ({auditLogs.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {auditLogs.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-400">
                  No audit log entries recorded yet.
                </div>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {auditLogs.map((log) => (
                    <li key={log.id} className="p-4 px-6 flex items-center justify-between hover:bg-slate-50/60 transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                          {log.action}
                        </span>
                        <span className="text-xs text-slate-500">by {log.actor_id}</span>
                      </div>
                      <span className="text-xs text-slate-400 font-mono">{formatDate(log.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Integration Quick Statuses (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Authorization Compliance Card */}
          <Card>
            <CardHeader className="py-4 px-5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                Authorization Status
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-3">
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-600">Verification</span>
                  <StatusBadge status={agent.authorization_status} type="auth" />
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-600">Lifecycle</span>
                  <StatusBadge status={agent.status} type="agent" />
                </div>
              </div>

              {!isVerified ? (
                <p className="text-xs text-amber-800 bg-amber-50/80 p-3 rounded-lg border border-amber-200 leading-relaxed">
                  Notice: Agent profile must be verified before account activation is permitted.
                </p>
              ) : (
                <p className="text-xs text-emerald-800 bg-emerald-50/80 p-3 rounded-lg border border-emerald-200 leading-relaxed">
                  Verified: Real estate license and agent authorization confirmed.
                </p>
              )}
            </CardContent>
          </Card>

          {/* WhatsApp Integration Card */}
          <Card>
            <CardHeader className="py-4 px-5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-600" />
                WhatsApp Cloud Profile
              </CardTitle>
              <Link href={`/agents/${agent.id}/whatsapp`}>
                <Button variant="ghost" size="sm">Configure</Button>
              </Link>
            </CardHeader>
            <CardContent className="p-5 space-y-2.5 text-xs text-slate-600">
              <div className="flex justify-between items-center">
                <span>Status:</span>
                <StatusBadge status={whatsapp?.connection_status || "NOT_CONFIGURED"} type="whatsapp" />
              </div>
              <div className="flex justify-between items-center">
                <span>Webhook:</span>
                <span className={whatsapp?.webhook_verified ? "text-emerald-600 font-semibold" : "text-slate-400"}>
                  {whatsapp?.webhook_verified ? "Verified" : "Unverified"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>Phone ID:</span>
                <span className="font-mono text-slate-800 font-medium">
                  {whatsapp?.phone_number_id || "Not configured"}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Branding Summary Card */}
          <Card>
            <CardHeader className="py-4 px-5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Palette className="w-4 h-4 text-sky-600" />
                Branding Profile
              </CardTitle>
              <Link href={`/agents/${agent.id}/branding`}>
                <Button variant="ghost" size="sm">Manage</Button>
              </Link>
            </CardHeader>
            <CardContent className="p-5 space-y-2.5 text-xs text-slate-600">
              <div className="flex justify-between items-center">
                <span>Status:</span>
                <StatusBadge status={branding?.branding_status || "NOT_STARTED"} type="branding" />
              </div>
              <div className="flex justify-between items-center">
                <span>Website:</span>
                <span className="text-slate-800 truncate max-w-[150px]">
                  {branding?.website || "—"}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Edit Profile Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="Edit Agent Profile"
        description="Update profile details and internal operator notes."
        maxWidth="lg"
      >
        <form onSubmit={handleSaveEdit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Full Legal Name</label>
              <Input
                type="text"
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Display Name</label>
              <Input
                type="text"
                value={editForm.display_name}
                onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Agency Name</label>
              <Input
                type="text"
                value={editForm.agency_name}
                onChange={(e) => setEditForm({ ...editForm, agency_name: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Designation</label>
              <Input
                type="text"
                value={editForm.designation}
                onChange={(e) => setEditForm({ ...editForm, designation: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">CEA Registration</label>
              <Input
                type="text"
                value={editForm.registration_number}
                onChange={(e) => setEditForm({ ...editForm, registration_number: e.target.value })}
                className="font-mono uppercase"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Phone Number</label>
              <Input
                type="text"
                value={editForm.phone}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                className="font-mono"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Email Address</label>
              <Input
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1.5">Internal Notes</label>
              <textarea
                rows={3}
                value={editForm.notes}
                onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button variant="outline" type="button" onClick={() => setIsEditModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={actionLoading}>
              Save Changes
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
