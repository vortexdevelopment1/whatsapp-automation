"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Plus,
  Edit2,
  FileCode,
  Save,
  CheckCircle,
  AlertCircle,
  Clock,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { Agent, MessageTemplate, TemplateStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentSubNav } from "@/components/shared/AgentSubNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/utils";

export default function AgentTemplatesPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    template_name: "",
    meta_template_name: "",
    language: "en_US",
    category: "UTILITY",
    body: "",
    status: "DRAFT" as TemplateStatus,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, templatesData] = await Promise.all([
        api.getAgent(agentId),
        api.listTemplates(agentId),
      ]);
      setAgent(agentData);
      setTemplates(templatesData);
    } catch (err: any) {
      setError(err.message || "Failed to load templates.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openCreateModal = () => {
    setEditingTemplateId(null);
    setFormData({
      template_name: "",
      meta_template_name: "",
      language: "en_US",
      category: "UTILITY",
      body: "Hi {{1}}, thank you for inquiring about the property at {{2}}. I am {{3}} from {{4}}.",
      status: "DRAFT",
    });
    setIsModalOpen(true);
  };

  const openEditModal = (tpl: MessageTemplate) => {
    setEditingTemplateId(tpl.id);
    setFormData({
      template_name: tpl.template_name,
      meta_template_name: tpl.meta_template_name || "",
      language: tpl.language,
      category: tpl.category || "UTILITY",
      body: tpl.body,
      status: tpl.status,
    });
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.template_name.trim() || !formData.body.trim()) {
      setError("Template name and body content are required.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      if (editingTemplateId) {
        await api.updateTemplate(editingTemplateId, {
          template_name: formData.template_name.trim(),
          meta_template_name: formData.meta_template_name.trim() || null,
          language: formData.language.trim(),
          category: formData.category.trim() || null,
          body: formData.body.trim(),
          status: formData.status,
        });
        setSuccess("Template updated successfully.");
      } else {
        await api.createTemplate(agentId, {
          template_name: formData.template_name.trim(),
          meta_template_name: formData.meta_template_name.trim() || null,
          language: formData.language.trim(),
          category: formData.category.trim() || null,
          body: formData.body.trim(),
          status: formData.status,
        });
        setSuccess("New template created successfully.");
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      setError(err.message || "Failed to save template.");
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
          { label: "Templates" },
        ]}
        title={agent?.full_name ? `${agent.full_name} — WhatsApp Templates` : "WhatsApp Message Templates"}
        description="Assign and configure pre-approved WhatsApp message templates for automated and manual agent responses."
        badges={
          agent && <StatusBadge status={agent.status} type="agent" />
        }
        actions={
          <Button
            onClick={openCreateModal}
            icon={<Plus className="w-4 h-4" />}
          >
            Create Template
          </Button>
        }
      />

      <AgentSubNav agentId={agentId} templateCount={templates.length} />

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

      {/* Templates List */}
      <Card>
        {loading && templates.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading templates...</div>
        ) : templates.length === 0 ? (
          <EmptyState
            icon={<FileCode className="w-8 h-8 text-slate-400" />}
            title="No templates configured"
            description="Add WhatsApp message templates to streamline outbound agent communication."
            action={
              <Button onClick={openCreateModal} icon={<Plus className="w-4 h-4" />}>
                Create Template
              </Button>
            }
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {templates.map((tpl) => (
              <div key={tpl.id} className="p-5 sm:p-6 hover:bg-slate-50/60 transition-colors">
                <div className="flex flex-col sm:flex-row justify-between sm:items-start gap-4 mb-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h4 className="text-base font-bold text-slate-900 font-mono tracking-tight">
                        {tpl.template_name}
                      </h4>
                      <StatusBadge status={tpl.status} type="template" />
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 mt-1.5">
                      <span>Language: <strong className="text-slate-700">{tpl.language}</strong></span>
                      {tpl.category && <span>Category: <strong className="text-slate-700">{tpl.category}</strong></span>}
                      {tpl.meta_template_name && (
                        <span>Meta Slug: <strong className="text-slate-700 font-mono">{tpl.meta_template_name}</strong></span>
                      )}
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditModal(tpl)}
                    icon={<Edit2 className="w-3.5 h-3.5" />}
                  >
                    Edit
                  </Button>
                </div>

                <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 text-xs font-mono text-slate-800 whitespace-pre-wrap leading-relaxed">
                  {tpl.body}
                </div>

                <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                  <span className="flex items-center gap-1 font-sans">
                    <Sparkles className="w-3.5 h-3.5 text-sky-500" />
                    Variable placeholders supported: {"{{1}}, {{2}}"}
                  </span>
                  <span className="font-mono text-[11px]">Updated {formatDate(tpl.updated_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Modal Dialog */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingTemplateId ? "Edit Message Template" : "Create New Message Template"}
        description="Configure template parameters and body text for WhatsApp Cloud API."
        maxWidth="lg"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Template Identifier Name <span className="text-rose-500">*</span>
            </label>
            <Input
              type="text"
              value={formData.template_name}
              onChange={(e) => setFormData({ ...formData, template_name: e.target.value })}
              required
              placeholder="e.g. rental_inquiry_ack"
              className="font-mono"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Language Code
              </label>
              <Input
                type="text"
                value={formData.language}
                onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                required
                placeholder="en_US"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Category
              </label>
              <Select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              >
                <option value="MARKETING">MARKETING</option>
                <option value="UTILITY">UTILITY</option>
                <option value="AUTHENTICATION">AUTHENTICATION</option>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Meta Template Slug
              </label>
              <Input
                type="text"
                value={formData.meta_template_name}
                onChange={(e) => setFormData({ ...formData, meta_template_name: e.target.value })}
                placeholder="meta_template_v1"
                className="font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Status
              </label>
              <Select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
              >
                <option value="DRAFT">DRAFT</option>
                <option value="PENDING_APPROVAL">PENDING_APPROVAL</option>
                <option value="APPROVED">APPROVED</option>
                <option value="REJECTED">REJECTED</option>
                <option value="DISABLED">DISABLED</option>
              </Select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Template Body <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={4}
              value={formData.body}
              onChange={(e) => setFormData({ ...formData, body: e.target.value })}
              required
              placeholder="Hi {{1}}, thank you for reaching out regarding..."
              className="w-full px-3 py-2 text-sm font-mono bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={submitting}>
              Save Template
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
