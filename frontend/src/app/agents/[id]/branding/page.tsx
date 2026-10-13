"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Save, Palette, Eye, AlertCircle, CheckCircle, ExternalLink, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Agent, AgentBranding, BrandingStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentSubNav } from "@/components/shared/AgentSubNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

export default function AgentBrandingPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [branding, setBranding] = useState<AgentBranding | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    business_description: "",
    office_address: "",
    website: "",
    profile_photo_url: "",
    digital_name_card_url: "",
    lanyard_artwork_url: "",
    branding_status: "NOT_STARTED" as BrandingStatus,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, brandingData] = await Promise.all([
        api.getAgent(agentId),
        api.getBranding(agentId),
      ]);
      setAgent(agentData);
      setBranding(brandingData);
      setFormData({
        business_description: brandingData.business_description || "",
        office_address: brandingData.office_address || "",
        website: brandingData.website || "",
        profile_photo_url: brandingData.profile_photo_url || agentData.profile_photo_url || "",
        digital_name_card_url: brandingData.digital_name_card_url || "",
        lanyard_artwork_url: brandingData.lanyard_artwork_url || "",
        branding_status: brandingData.branding_status || "NOT_STARTED",
      });
    } catch (err: any) {
      setError(err.message || "Failed to load branding data.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);
      const updated = await api.updateBranding(agentId, {
        business_description: formData.business_description.trim() || null,
        office_address: formData.office_address.trim() || null,
        website: formData.website.trim() || null,
        profile_photo_url: formData.profile_photo_url.trim() || null,
        digital_name_card_url: formData.digital_name_card_url.trim() || null,
        lanyard_artwork_url: formData.lanyard_artwork_url.trim() || null,
        branding_status: formData.branding_status,
      });
      setBranding(updated);
      setSuccess("Branding profile successfully saved.");
    } catch (err: any) {
      setError(err.message || "Failed to update branding profile.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        breadcrumbs={[
          { label: "Agents", href: "/agents" },
          { label: agent?.full_name || "Agent", href: `/agents/${agentId}` },
          { label: "Branding" },
        ]}
        title={agent?.full_name ? `${agent.full_name} — Branding Profile` : "Branding Configuration"}
        description="Configure approved agency branding assets and manage the digital business card layout."
        badges={
          agent && (
            <>
              <StatusBadge status={agent.status} type="agent" />
              <StatusBadge status={branding?.branding_status || "NOT_STARTED"} type="branding" />
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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Configuration (7 cols) */}
        <div className="lg:col-span-7">
          <Card>
            <CardHeader className="py-4 px-6">
              <CardTitle className="text-sm font-semibold">
                <Palette className="w-4 h-4 text-sky-600" />
                Branding Asset Configuration
              </CardTitle>
              <div className="flex items-center gap-2 w-36">
                <Select
                  name="branding_status"
                  value={formData.branding_status}
                  onChange={handleChange}
                >
                  <option value="NOT_STARTED">NOT_STARTED</option>
                  <option value="DRAFT">DRAFT</option>
                  <option value="READY">READY</option>
                  <option value="APPROVED">APPROVED</option>
                </Select>
              </div>
            </CardHeader>

            <form onSubmit={handleSubmit}>
              <CardContent className="p-6 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Business Description & Bio
                  </label>
                  <textarea
                    name="business_description"
                    rows={3}
                    value={formData.business_description}
                    onChange={handleChange}
                    placeholder="Prime residential rental specialist, tenant representation, relocation..."
                    className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Office / Agency Address
                  </label>
                  <Input
                    type="text"
                    name="office_address"
                    value={formData.office_address}
                    onChange={handleChange}
                    placeholder="480 Lorong 6 Toa Payoh, PropNex Building, Singapore"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Official Agency Website
                  </label>
                  <Input
                    type="url"
                    name="website"
                    value={formData.website}
                    onChange={handleChange}
                    placeholder="https://agent.propnex.com/profile"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Profile Photo Asset URL
                  </label>
                  <Input
                    type="url"
                    name="profile_photo_url"
                    value={formData.profile_photo_url}
                    onChange={handleChange}
                    placeholder="https://example.com/assets/agent-headshot.png"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                      Digital Name Card URL
                    </label>
                    <Input
                      type="url"
                      name="digital_name_card_url"
                      value={formData.digital_name_card_url}
                      onChange={handleChange}
                      placeholder="https://example.com/card.png"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                      Lanyard Artwork URL
                    </label>
                    <Input
                      type="url"
                      name="lanyard_artwork_url"
                      value={formData.lanyard_artwork_url}
                      onChange={handleChange}
                      placeholder="https://example.com/lanyard.png"
                    />
                  </div>
                </div>
              </CardContent>

              <CardFooter className="flex justify-end p-4 px-6">
                <Button
                  type="submit"
                  loading={submitting}
                  icon={<Save className="w-4 h-4" />}
                >
                  Save Branding
                </Button>
              </CardFooter>
            </form>
          </Card>
        </div>

        {/* Live Digital Name Card Preview (5 cols, sticky on desktop) */}
        <div className="lg:col-span-5 space-y-4 lg:sticky lg:top-24">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            <Eye className="w-4 h-4 text-sky-600" />
            <span>Digital Business Card Live Preview</span>
          </div>

          <div className="bg-gradient-to-br from-slate-900 via-slate-850 to-sky-950 text-white rounded-2xl p-6 shadow-xl border border-slate-700/80 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-36 h-36 bg-sky-500/10 rounded-full blur-2xl" />

            <div className="relative z-10 flex flex-col justify-between min-h-[300px]">
              <div>
                <div className="flex justify-between items-start mb-4">
                  <div className="w-14 h-14 rounded-full bg-slate-800 border-2 border-sky-400 overflow-hidden flex items-center justify-center font-bold text-sky-300 text-lg flex-shrink-0">
                    {formData.profile_photo_url ? (
                      <img
                        src={formData.profile_photo_url}
                        alt="Agent profile"
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as any).style.display = "none";
                        }}
                      />
                    ) : (
                      agent?.full_name ? agent.full_name[0] : "A"
                    )}
                  </div>
                  <span className="text-xs uppercase font-mono tracking-widest text-sky-300 bg-sky-950/70 border border-sky-600/40 px-2 py-0.5 rounded">
                    {agent?.registration_number || "REG: PENDING"}
                  </span>
                </div>

                <h3 className="text-xl font-bold text-white tracking-tight">
                  {agent?.full_name || "Agent Legal Name"}
                </h3>
                <p className="text-sm text-sky-300 font-medium">
                  {agent?.designation || "Licensed Real Estate Specialist"}
                </p>
                <p className="text-xs text-slate-300 mt-0.5">
                  {agent?.agency_name || "Authorized Agency"}
                </p>

                {formData.business_description && (
                  <p className="text-xs text-slate-300 mt-3 line-clamp-3 italic leading-relaxed">
                    "{formData.business_description}"
                  </p>
                )}
              </div>

              <div className="border-t border-slate-700/80 pt-3 mt-4 space-y-1 text-xs text-slate-300 font-mono">
                {agent?.phone && <div>Tel: {agent.phone}</div>}
                {agent?.email && <div>Email: {agent.email}</div>}
                {formData.website && (
                  <div className="text-sky-300 truncate">
                    Web: {formData.website}
                  </div>
                )}
                {formData.office_address && (
                  <div className="text-slate-400 text-[11px] truncate">
                    Addr: {formData.office_address}
                  </div>
                )}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-500 bg-slate-100 p-3 rounded-lg border border-slate-200 leading-relaxed">
            <strong>Compliance Notice:</strong> This preview uses only authorized agent and agency information. All displayed credentials correspond to verified public agency records.
          </p>
        </div>
      </div>
    </div>
  );
}
