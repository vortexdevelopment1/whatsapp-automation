"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Save,
  MessageSquare,
  CheckCircle,
  AlertCircle,
  Send,
  Zap,
  ShieldCheck,
  Clock,
  Radio,
  Lock,
} from "lucide-react";
import { api } from "@/lib/api";
import { Agent, WhatsAppProfile, WhatsAppConnectionStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentSubNav } from "@/components/shared/AgentSubNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { formatDate } from "@/lib/utils";

export default function AgentWhatsAppConfigPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [profile, setProfile] = useState<WhatsAppProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    meta_business_account_id: "",
    phone_number_id: "",
    display_phone_number: "",
    business_display_name: "",
    connection_status: "NOT_CONFIGURED" as WhatsAppConnectionStatus,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, whatsappData] = await Promise.all([
        api.getAgent(agentId),
        api.getWhatsAppConfig(agentId),
      ]);
      setAgent(agentData);
      setProfile(whatsappData);
      setFormData({
        meta_business_account_id: whatsappData.meta_business_account_id || "",
        phone_number_id: whatsappData.phone_number_id || "",
        display_phone_number: whatsappData.display_phone_number || "",
        business_display_name: whatsappData.business_display_name || "",
        connection_status: whatsappData.connection_status || "NOT_CONFIGURED",
      });
    } catch (err: any) {
      setError(err.message || "Failed to load WhatsApp configuration.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);
      const updated = await api.updateWhatsAppConfig(agentId, {
        meta_business_account_id: formData.meta_business_account_id.trim() || null,
        phone_number_id: formData.phone_number_id.trim() || null,
        display_phone_number: formData.display_phone_number.trim() || null,
        business_display_name: formData.business_display_name.trim() || null,
        connection_status: formData.connection_status,
      });
      setProfile(updated);
      setSuccess("WhatsApp configuration saved successfully.");
    } catch (err: any) {
      setError(err.message || "Failed to update configuration.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyConnection = async () => {
    try {
      setActionLoading(true);
      setError(null);
      setSuccess(null);
      if (!formData.phone_number_id) {
        throw new Error("Cannot verify: Phone Number ID is required.");
      }
      const updated = await api.updateWhatsAppConfig(agentId, {
        connection_status: "CONFIGURED",
      });
      setProfile(updated);
      setFormData((prev) => ({ ...prev, connection_status: "CONFIGURED" }));
      setSuccess("Configuration verified and connection status updated to CONFIGURED.");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        breadcrumbs={[
          { label: "Agents", href: "/agents" },
          { label: agent?.full_name || "Agent", href: `/agents/${agentId}` },
          { label: "WhatsApp Setup" },
        ]}
        title={agent?.full_name ? `${agent.full_name} — WhatsApp Configuration` : "WhatsApp Configuration"}
        description="Connect and manage Meta WhatsApp Cloud API credentials and webhook integration status."
        badges={
          agent && (
            <>
              <StatusBadge status={agent.status} type="agent" />
              <StatusBadge status={profile?.connection_status || "NOT_CONFIGURED"} type="whatsapp" />
            </>
          )
        }
      />

      <AgentSubNav agentId={agentId} />

      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess(null)} className="text-emerald-700 font-bold ml-4">×</button>
        </div>
      )}

      {/* Diagnostics / Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card className="p-4 sm:p-5 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Connection Status
            </div>
            <div className="mt-1.5">
              <StatusBadge status={profile?.connection_status || "NOT_CONFIGURED"} type="whatsapp" />
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center">
            <Radio className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 sm:p-5 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Webhook Verification
            </div>
            <div className="mt-1.5 font-semibold text-sm">
              {profile?.webhook_verified ? (
                <span className="text-emerald-600 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4" /> Verified Active
                </span>
              ) : (
                <span className="text-slate-400">Unverified</span>
              )}
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 sm:p-5 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Last Webhook Inbound
            </div>
            <div className="mt-1.5 text-xs text-slate-700 font-mono">
              {formatDate(profile?.last_webhook_at)}
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Configuration Form Card */}
      <Card>
        <CardHeader className="py-4 px-6">
          <CardTitle className="text-sm font-semibold">
            <MessageSquare className="w-4 h-4 text-emerald-600" />
            Meta WhatsApp Profile Attributes
          </CardTitle>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium bg-slate-100 px-2.5 py-1 rounded-md">
            <Lock className="w-3.5 h-3.5 text-slate-400" />
            Tokens stored securely in backend env
          </div>
        </CardHeader>

        <form onSubmit={handleSave}>
          <CardContent className="p-6 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Meta Business Account ID (WABA ID)
                </label>
                <Input
                  type="text"
                  name="meta_business_account_id"
                  value={formData.meta_business_account_id}
                  onChange={handleChange}
                  placeholder="e.g. 102938475610293"
                  className="font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Phone Number ID
                </label>
                <Input
                  type="text"
                  name="phone_number_id"
                  value={formData.phone_number_id}
                  onChange={handleChange}
                  placeholder="e.g. 109283746519283"
                  className="font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Display Phone Number
                </label>
                <Input
                  type="text"
                  name="display_phone_number"
                  value={formData.display_phone_number}
                  onChange={handleChange}
                  placeholder="e.g. +65 9123 4567"
                  className="font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Business Display Name
                </label>
                <Input
                  type="text"
                  name="business_display_name"
                  value={formData.business_display_name}
                  onChange={handleChange}
                  placeholder="e.g. Sarah Tan — PropNex Realty"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Connection Status Override
                </label>
                <Select
                  name="connection_status"
                  value={formData.connection_status}
                  onChange={handleChange}
                >
                  <option value="NOT_CONFIGURED">NOT_CONFIGURED</option>
                  <option value="CONFIGURED">CONFIGURED</option>
                  <option value="CONNECTED">CONNECTED</option>
                  <option value="ERROR">ERROR</option>
                  <option value="DISABLED">DISABLED</option>
                </Select>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex flex-wrap justify-between items-center gap-3 p-4 px-6">
            <Button
              type="button"
              variant="outline"
              size="sm"
              loading={actionLoading}
              onClick={handleVerifyConnection}
              icon={<Zap className="w-3.5 h-3.5 text-amber-500" />}
            >
              Verify Connection
            </Button>

            <Button
              type="submit"
              loading={submitting}
              icon={<Save className="w-4 h-4" />}
            >
              Save Configuration
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
