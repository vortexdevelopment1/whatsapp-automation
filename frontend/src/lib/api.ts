import {
  Agent,
  AgentCreateInput,
  AgentUpdateInput,
  AgentBranding,
  BrandingUpdateInput,
  WhatsAppProfile,
  WhatsAppProfileUpdateInput,
  MessageTemplate,
  TemplateCreateInput,
  TemplateUpdateInput,
  AuditLog,
  AgentStatus,
  AuthorizationStatus,
  Lead,
  LeadDuplicateCheckResponse,
  LeadEligibilityCheckResponse,
  TenantRequirement,
  TenantRequirementHistory,
  QualificationProgress,
  NextQuestionResponse,
  QualificationPreviewResponse,
  QualificationLiveStatus,
  QualificationDecisionResponse,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const role = typeof window !== "undefined" ? localStorage.getItem("user_role") || "operator" : "operator";
  const adminId = typeof window !== "undefined" ? localStorage.getItem("admin_id") || "operator" : "operator";
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Role": role,
      "X-Admin-Id": adminId,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = `Error ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        if (typeof errorJson.detail === "string") {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join(", ");
        }
      }
    } catch {
      // Keep default error text
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  // Agents
  async listAgents(params?: {
    search?: string;
    status?: AgentStatus;
    authorization_status?: AuthorizationStatus;
    skip?: number;
    limit?: number;
  }): Promise<Agent[]> {
    const query = new URLSearchParams();
    if (params?.search) query.append("search", params.search);
    if (params?.status) query.append("status", params.status);
    if (params?.authorization_status) query.append("authorization_status", params.authorization_status);
    if (params?.skip !== undefined) query.append("skip", params.skip.toString());
    if (params?.limit !== undefined) query.append("limit", params.limit.toString());

    const qs = query.toString() ? `?${query.toString()}` : "";
    return fetchJson<Agent[]>(`/api/agents${qs}`);
  },

  async getAgent(id: string): Promise<Agent> {
    return fetchJson<Agent>(`/api/agents/${id}`);
  },

  async createAgent(data: AgentCreateInput): Promise<Agent> {
    return fetchJson<Agent>("/api/agents", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateAgent(id: string, data: AgentUpdateInput): Promise<Agent> {
    return fetchJson<Agent>(`/api/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async activateAgent(id: string): Promise<Agent> {
    return fetchJson<Agent>(`/api/agents/${id}/activate`, {
      method: "POST",
    });
  },

  async deactivateAgent(id: string): Promise<Agent> {
    return fetchJson<Agent>(`/api/agents/${id}/deactivate`, {
      method: "POST",
    });
  },

  async archiveAgent(id: string): Promise<Agent> {
    return fetchJson<Agent>(`/api/agents/${id}/archive`, {
      method: "POST",
    });
  },

  // Branding
  async getBranding(agentId: string): Promise<AgentBranding> {
    return fetchJson<AgentBranding>(`/api/agents/${agentId}/branding`);
  },

  async updateBranding(agentId: string, data: BrandingUpdateInput): Promise<AgentBranding> {
    return fetchJson<AgentBranding>(`/api/agents/${agentId}/branding`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  // WhatsApp
  async getWhatsAppConfig(agentId: string): Promise<WhatsAppProfile> {
    return fetchJson<WhatsAppProfile>(`/api/agents/${agentId}/whatsapp`);
  },

  async updateWhatsAppConfig(agentId: string, data: WhatsAppProfileUpdateInput): Promise<WhatsAppProfile> {
    return fetchJson<WhatsAppProfile>(`/api/agents/${agentId}/whatsapp`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  // Templates
  async listTemplates(agentId: string): Promise<MessageTemplate[]> {
    return fetchJson<MessageTemplate[]>(`/api/agents/${agentId}/templates`);
  },

  async createTemplate(agentId: string, data: TemplateCreateInput): Promise<MessageTemplate> {
    return fetchJson<MessageTemplate>(`/api/agents/${agentId}/templates`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateTemplate(templateId: string, data: TemplateUpdateInput): Promise<MessageTemplate> {
    return fetchJson<MessageTemplate>(`/api/templates/${templateId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  // Audit Logs
  async listAuditLogs(params?: {
    entity_type?: string;
    entity_id?: string;
    skip?: number;
    limit?: number;
  }): Promise<AuditLog[]> {
    const query = new URLSearchParams();
    if (params?.entity_type) query.append("entity_type", params.entity_type);
    if (params?.entity_id) query.append("entity_id", params.entity_id);
    if (params?.skip !== undefined) query.append("skip", params.skip.toString());
    if (params?.limit !== undefined) query.append("limit", params.limit.toString());

    const qs = query.toString() ? `?${query.toString()}` : "";
    return fetchJson<AuditLog[]>(`/api/audit-logs${qs}`);
  },

  // Messages
  async listMessages(agentId: string, skip: number = 0, limit: number = 50) {
    return fetchJson<any[]>(`/api/agents/${agentId}/messages?skip=${skip}&limit=${limit}`);
  },

  async sendTestMessage(agentId: string, data: { recipient: string; content: string; message_type?: string }) {
    return fetchJson<any>(`/api/agents/${agentId}/messages/test`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Leads
  async listLeads(params?: {
    search?: string;
    status?: string;
    source_id?: string;
    consent_status?: string;
    opt_out_status?: string;
    contact_eligibility?: string;
    skip?: number;
    limit?: number;
  }): Promise<Lead[]> {
    const query = new URLSearchParams();
    if (params?.search) query.append("search", params.search);
    if (params?.status) query.append("status", params.status);
    if (params?.source_id) query.append("source_id", params.source_id);
    if (params?.consent_status) query.append("consent_status", params.consent_status);
    if (params?.opt_out_status) query.append("opt_out_status", params.opt_out_status);
    if (params?.contact_eligibility) query.append("contact_eligibility", params.contact_eligibility);
    if (params?.skip !== undefined) query.append("skip", params.skip.toString());
    if (params?.limit !== undefined) query.append("limit", params.limit.toString());

    const qs = query.toString() ? `?${query.toString()}` : "";
    return fetchJson<Lead[]>(`/api/leads${qs}`);
  },

  async getLead(id: string): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads/${id}`);
  },

  async createLead(data: any): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateLead(id: string, data: any): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async validateLead(id: string): Promise<any> {
    return fetchJson<any>(`/api/leads/${id}/validate`, {
      method: "POST",
    });
  },

  async checkLeadDuplicate(id: string): Promise<LeadDuplicateCheckResponse> {
    return fetchJson<LeadDuplicateCheckResponse>(`/api/leads/${id}/check-duplicate`, {
      method: "POST",
    });
  },

  async overrideLeadDuplicate(id: string, reason: string): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads/${id}/duplicate-override`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  async checkContactEligibility(id: string): Promise<LeadEligibilityCheckResponse> {
    return fetchJson<LeadEligibilityCheckResponse>(`/api/leads/${id}/check-contact-eligibility`, {
      method: "POST",
    });
  },

  async markLeadOptOut(id: string, reason?: string): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads/${id}/mark-opt-out`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  async restoreLeadContact(id: string, data: { reason?: string; authorized_by?: string }): Promise<Lead> {
    return fetchJson<Lead>(`/api/leads/${id}/restore-contact`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Tenant Requirements (Module 3)
  async getTenantRequirements(leadId: string): Promise<TenantRequirement> {
    return fetchJson<TenantRequirement>(`/api/leads/${leadId}/requirements`);
  },

  async createTenantRequirements(leadId: string, data: any): Promise<TenantRequirement> {
    return fetchJson<TenantRequirement>(`/api/leads/${leadId}/requirements`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateTenantRequirements(leadId: string, data: any): Promise<TenantRequirement> {
    return fetchJson<TenantRequirement>(`/api/leads/${leadId}/requirements`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async getRequirementHistory(leadId: string): Promise<TenantRequirementHistory[]> {
    return fetchJson<TenantRequirementHistory[]>(`/api/leads/${leadId}/requirements/history`);
  },

  async getMissingRequirements(leadId: string): Promise<string[]> {
    return fetchJson<string[]>(`/api/leads/${leadId}/requirements/missing`);
  },

  async getQualificationProgress(leadId: string): Promise<QualificationProgress> {
    return fetchJson<QualificationProgress>(`/api/leads/${leadId}/qualification-progress`);
  },

  // System & AI Diagnostics (Module 3 Phase 2)
  async getAIHealth(): Promise<{
    configured: boolean;
    provider: string;
    model: string;
    status: string;
    timeout_seconds: number;
    max_retries: number;
    last_success_at: string | null;
    last_failure_at: string | null;
    last_failure_error: string | null;
  }> {
    return fetchJson(`/api/system/ai/health`);
  },

  // Module 3 Phase 3: Tenant Message Understanding
  async analyzeTenantMessage(leadId: string, messageId: string): Promise<any> {
    return fetchJson(`/api/leads/${leadId}/messages/${messageId}/analyze`, {
      method: "POST",
    });
  },

  async devExtractRequirements(text: string): Promise<any> {
    return fetchJson(`/api/dev/module3/extract`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },

  // Module 3 Phase 4: Missing Field Detection & Next Question Engine
  async generateNextQuestion(leadId: string, collectOptional: boolean = false): Promise<NextQuestionResponse> {
    return fetchJson<NextQuestionResponse>(`/api/leads/${leadId}/qualification/next-question?collect_optional=${collectOptional}`, {
      method: "POST",
    });
  },

  async previewQualification(leadId: string): Promise<QualificationPreviewResponse> {
    return fetchJson<QualificationPreviewResponse>(`/api/leads/${leadId}/qualification/preview`);
  },

  // Module 3 Phase 5: Live Qualification Loop Controls & Status
  async getQualificationLiveStatus(leadId: string): Promise<QualificationLiveStatus> {
    return fetchJson<QualificationLiveStatus>(`/api/leads/${leadId}/qualification/status`);
  },

  async pauseAIQualification(leadId: string): Promise<TenantRequirement> {
    return fetchJson<TenantRequirement>(`/api/leads/${leadId}/qualification/pause`, {
      method: "POST",
    });
  },

  async resumeAIQualification(leadId: string): Promise<TenantRequirement> {
    return fetchJson<TenantRequirement>(`/api/leads/${leadId}/qualification/resume`, {
      method: "POST",
    });
  },

  async retryQualificationMessage(leadId: string, messageId: string): Promise<any> {
    return fetchJson<any>(`/api/leads/${leadId}/qualification/retry/${messageId}`, {
      method: "POST",
    });
  },

  async processQualificationMessage(leadId: string, messageId: string): Promise<any> {
    return fetchJson<any>(`/api/leads/${leadId}/qualification/process-message/${messageId}`, {
      method: "POST",
    });
  },

  // Module 3 Phase 6: Qualification Decision Engine
  async evaluateQualification(
    leadId: string,
    data?: {
      apply?: boolean;
      human_override_status?: string;
      override_reason?: string;
      evaluated_by?: string;
    }
  ): Promise<QualificationDecisionResponse> {
    return fetchJson<QualificationDecisionResponse>(`/api/leads/${leadId}/qualification/evaluate`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  },

  async getQualificationDecisionHistory(leadId: string): Promise<QualificationDecisionResponse[]> {
    return fetchJson<QualificationDecisionResponse[]>(`/api/leads/${leadId}/qualification/decision-history`);
  },

  // Module 3 Phase 7: Confidence Hardening, Clarification, FAQ & Human Escalation
  async getHumanReviewQueue(): Promise<import("../types").HumanReviewQueueItem[]> {
    return fetchJson<import("../types").HumanReviewQueueItem[]>("/api/leads/human-review-queue");
  },

  async getLeadEscalations(leadId: string): Promise<import("../types").ConversationEscalation[]> {
    return fetchJson<import("../types").ConversationEscalation[]>(`/api/leads/${leadId}/escalations`);
  },

  async createLeadEscalation(leadId: string, data?: { reason_code?: string; description?: string }): Promise<import("../types").ConversationEscalation> {
    return fetchJson<import("../types").ConversationEscalation>(`/api/leads/${leadId}/escalations`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  },

  async takeoverConversation(leadId: string): Promise<import("../types").ConversationEscalation> {
    return fetchJson<import("../types").ConversationEscalation>(`/api/leads/${leadId}/takeover`, {
      method: "POST",
    });
  },

  async sendOperatorMessage(leadId: string, content: string): Promise<any> {
    return fetchJson<any>(`/api/leads/${leadId}/operator-message`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  },

  async returnToAI(leadId: string, resolutionNotes?: string): Promise<any> {
    return fetchJson<any>(`/api/leads/${leadId}/return-to-ai`, {
      method: "POST",
      body: JSON.stringify({ resolution_notes: resolutionNotes }),
    });
  },

  async getLeadClarifications(leadId: string): Promise<import("../types").QualificationClarification[]> {
    return fetchJson<import("../types").QualificationClarification[]>(`/api/leads/${leadId}/clarifications`);
  },

  async resolveClarification(leadId: string, clarificationId: string, data?: { action?: string; resolved_value?: any }): Promise<import("../types").QualificationClarification> {
    return fetchJson<import("../types").QualificationClarification>(`/api/leads/${leadId}/clarifications/${clarificationId}/resolve`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  },

  async listFAQs(category?: string, status?: string): Promise<import("../types").FAQEntry[]> {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return fetchJson<import("../types").FAQEntry[]>(`/api/faqs${qs}`);
  },

  async getFAQ(faqId: string): Promise<import("../types").FAQEntry> {
    return fetchJson<import("../types").FAQEntry>(`/api/faqs/${faqId}`);
  },

  async createFAQ(data: import("../types").FAQCreateInput): Promise<import("../types").FAQEntry> {
    return fetchJson<import("../types").FAQEntry>("/api/faqs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateFAQ(faqId: string, data: import("../types").FAQUpdateInput): Promise<import("../types").FAQEntry> {
    return fetchJson<import("../types").FAQEntry>(`/api/faqs/${faqId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async setFAQStatus(faqId: string, newStatus: string): Promise<import("../types").FAQEntry> {
    return fetchJson<import("../types").FAQEntry>(`/api/faqs/${faqId}/status?new_status=${newStatus}`, {
      method: "PATCH",
    });
  },

  async matchFAQ(query: string, category?: string): Promise<any> {
    return fetchJson<any>("/api/faqs/match", {
      method: "POST",
      body: JSON.stringify({ query, category }),
    });
  },

  // Module 3 Phase 8: Memory, Summary & Dashboard
  async getQualificationDashboard(leadId: string): Promise<import("../types").QualificationDashboardData> {
    return fetchJson<import("../types").QualificationDashboardData>(`/api/leads/${leadId}/qualification/dashboard`);
  },

  async getQualificationSummary(leadId: string): Promise<import("../types").ConversationSummary> {
    return fetchJson<import("../types").ConversationSummary>(`/api/leads/${leadId}/qualification/summary`);
  },

  async refreshQualificationSummary(leadId: string): Promise<{ success: boolean; summary: import("../types").ConversationSummary; refreshed_reason: string }> {
    return fetchJson<{ success: boolean; summary: import("../types").ConversationSummary; refreshed_reason: string }>(`/api/leads/${leadId}/qualification/summary/refresh`, {
      method: "POST",
    });
  },

  async listLeadNotes(leadId: string): Promise<import("../types").ConversationNote[]> {
    return fetchJson<import("../types").ConversationNote[]>(`/api/leads/${leadId}/notes`);
  },

  async createLeadNote(leadId: string, note: string): Promise<import("../types").ConversationNote> {
    return fetchJson<import("../types").ConversationNote>(`/api/leads/${leadId}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
  },

  // Module 4 Phase 1: Property Inventory API
  async listProperties(params?: {
    search?: string;
    property_type?: string;
    country?: string;
    city?: string;
    bedrooms?: number;
    status?: string;
    skip?: number;
    limit?: number;
  }): Promise<import("../types").Property[]> {
    const qs = new URLSearchParams();
    if (params?.search) qs.append("search", params.search);
    if (params?.property_type) qs.append("property_type", params.property_type);
    if (params?.country) qs.append("country", params.country);
    if (params?.city) qs.append("city", params.city);
    if (params?.bedrooms !== undefined) qs.append("bedrooms", params.bedrooms.toString());
    if (params?.status) qs.append("status", params.status);
    if (params?.skip !== undefined) qs.append("skip", params.skip.toString());
    if (params?.limit !== undefined) qs.append("limit", params.limit.toString());
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").Property[]>(`/api/properties${query}`);
  },

  async getProperty(id: string): Promise<import("../types").PropertyDetail> {
    return fetchJson<import("../types").PropertyDetail>(`/api/properties/${id}`);
  },

  async createProperty(data: import("../types").PropertyCreateInput): Promise<import("../types").Property> {
    return fetchJson<import("../types").Property>("/api/properties", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateProperty(id: string, data: import("../types").PropertyUpdateInput): Promise<import("../types").Property> {
    return fetchJson<import("../types").Property>(`/api/properties/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async archiveProperty(id: string): Promise<import("../types").Property> {
    return fetchJson<import("../types").Property>(`/api/properties/${id}/archive`, {
      method: "POST",
    });
  },

  async createPropertyListing(
    propertyId: string,
    data: import("../types").PropertyListingCreateInput
  ): Promise<import("../types").PropertyListing> {
    return fetchJson<import("../types").PropertyListing>(`/api/properties/${propertyId}/listings`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async listPropertyListingsForProperty(propertyId: string): Promise<import("../types").PropertyListing[]> {
    return fetchJson<import("../types").PropertyListing[]>(`/api/properties/${propertyId}/listings`);
  },

  async getPropertyListing(listingId: string): Promise<import("../types").PropertyListing> {
    return fetchJson<import("../types").PropertyListing>(`/api/property-listings/${listingId}`);
  },

  async updatePropertyListing(
    listingId: string,
    data: import("../types").PropertyListingUpdateInput
  ): Promise<import("../types").PropertyListing> {
    return fetchJson<import("../types").PropertyListing>(`/api/property-listings/${listingId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async archivePropertyListing(listingId: string): Promise<import("../types").PropertyListing> {
    return fetchJson<import("../types").PropertyListing>(`/api/property-listings/${listingId}/archive`, {
      method: "POST",
    });
  },

  async updateListingAvailability(
    listingId: string,
    data: { availability_status: string; available_from?: string | null; last_verified_at?: string | null }
  ): Promise<import("../types").PropertyListing> {
    return fetchJson<import("../types").PropertyListing>(`/api/property-listings/${listingId}/availability`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  // Property Sources
  async listPropertySources(params?: { source_type?: string; status?: string }): Promise<import("../types").PropertySource[]> {
    const qs = new URLSearchParams();
    if (params?.source_type) qs.append("source_type", params.source_type);
    if (params?.status) qs.append("status", params.status);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").PropertySource[]>(`/api/property-sources${query}`);
  },

  async createPropertySource(data: import("../types").PropertySourceCreateInput): Promise<import("../types").PropertySource> {
    return fetchJson<import("../types").PropertySource>("/api/property-sources", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async getPropertySource(id: string): Promise<import("../types").PropertySource> {
    return fetchJson<import("../types").PropertySource>(`/api/property-sources/${id}`);
  },


  async updatePropertySource(

    id: string,
    data: import("../types").PropertySourceUpdateInput
  ): Promise<import("../types").PropertySource> {
    return fetchJson<import("../types").PropertySource>(`/api/property-sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async activatePropertySource(id: string): Promise<import("../types").PropertySource> {
    return fetchJson<import("../types").PropertySource>(`/api/property-sources/${id}/activate`, {
      method: "POST",
    });
  },

  async deactivatePropertySource(id: string): Promise<import("../types").PropertySource> {
    return fetchJson<import("../types").PropertySource>(`/api/property-sources/${id}/deactivate`, {
      method: "POST",
    });
  },

  // Property Agents
  async listPropertyAgents(params?: {
    search?: string;
    agency_name?: string;
    status?: string;
  }): Promise<import("../types").PropertyAgent[]> {
    const qs = new URLSearchParams();
    if (params?.search) qs.append("search", params.search);
    if (params?.agency_name) qs.append("agency_name", params.agency_name);
    if (params?.status) qs.append("status", params.status);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").PropertyAgent[]>(`/api/property-agents${query}`);
  },

  async getPropertyAgent(id: string): Promise<import("../types").PropertyAgent> {
    return fetchJson<import("../types").PropertyAgent>(`/api/property-agents/${id}`);
  },

  async createPropertyAgent(data: import("../types").PropertyAgentCreateInput): Promise<import("../types").PropertyAgent> {
    return fetchJson<import("../types").PropertyAgent>("/api/property-agents", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updatePropertyAgent(
    id: string,
    data: import("../types").PropertyAgentUpdateInput
  ): Promise<import("../types").PropertyAgent> {
    return fetchJson<import("../types").PropertyAgent>(`/api/property-agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async archivePropertyAgent(id: string): Promise<import("../types").PropertyAgent> {
    return fetchJson<import("../types").PropertyAgent>(`/api/property-agents/${id}/archive`, {
      method: "POST",
    });
  },

  async seedDemoInventory(): Promise<{ status: string; seeded: any }> {
    return fetchJson<{ status: string; seeded: any }>("/api/dev/module4/seed-inventory", {
      method: "POST",
    });
  },

  // ---------------------------------------------------------
  // MODULE 4 — PHASE 2: IMPORT, NORMALIZATION & DEDUPLICATION
  // ---------------------------------------------------------

  async uploadPropertyImportCSV(sourceId: string, file: File): Promise<import("../types").PropertyImportBatch> {
    const formData = new FormData();
    formData.append("source_id", sourceId);
    formData.append("file", file);

    const res = await fetch(`${API_BASE_URL}/api/property-imports/upload`, {
      method: "POST",
      headers: {
        "X-Admin-Id": "operator-ui",
      },
      body: formData,
    });

    if (!res.ok) {
      let errDetail = "Failed to upload CSV file.";
      try {
        const body = await res.json();
        errDetail = body.detail || errDetail;
      } catch {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  async seedDemoPropertyImport(rowCount: number = 100): Promise<import("../types").PropertyImportBatch> {
    return fetchJson<import("../types").PropertyImportBatch>(`/api/property-imports/demo-seed?row_count=${rowCount}`, {
      method: "POST",
    });
  },

  async listPropertyImportBatches(status?: string, sourceId?: string): Promise<import("../types").PropertyImportBatch[]> {
    const qs = new URLSearchParams();
    if (status) qs.append("status", status);
    if (sourceId) qs.append("source_id", sourceId);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").PropertyImportBatch[]>(`/api/property-imports${query}`);
  },

  async getPropertyImportBatch(id: string): Promise<import("../types").PropertyImportBatch> {
    return fetchJson<import("../types").PropertyImportBatch>(`/api/property-imports/${id}`);
  },

  async previewPropertyImportBatch(id: string): Promise<import("../types").PropertyImportPreviewResponse> {
    return fetchJson<import("../types").PropertyImportPreviewResponse>(`/api/property-imports/${id}/preview`, {
      method: "POST",
    });
  },

  async commitPropertyImportBatch(id: string): Promise<import("../types").PropertyImportBatch> {
    return fetchJson<import("../types").PropertyImportBatch>(`/api/property-imports/${id}/commit`, {
      method: "POST",
    });
  },

  async retryPropertyImportBatch(id: string): Promise<import("../types").PropertyImportBatch> {
    return fetchJson<import("../types").PropertyImportBatch>(`/api/property-imports/${id}/retry`, {
      method: "POST",
    });
  },

  async getPropertyImportBatchRows(id: string, skip: number = 0, limit: number = 100): Promise<import("../types").PropertyImportRow[]> {
    return fetchJson<import("../types").PropertyImportRow[]>(`/api/property-imports/${id}/rows?skip=${skip}&limit=${limit}`);
  },

  async listPropertyDuplicateReviews(status?: string): Promise<import("../types").PropertyDuplicateReview[]> {
    const qs = new URLSearchParams();
    if (status) qs.append("status", status);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").PropertyDuplicateReview[]>(`/api/property-duplicate-reviews${query}`);
  },

  async getPropertyDuplicateReview(id: string): Promise<import("../types").PropertyDuplicateReview> {
    return fetchJson<import("../types").PropertyDuplicateReview>(`/api/property-duplicate-reviews/${id}`);
  },

  async attachDuplicateReviewToExisting(
    id: string,
    targetPropertyId?: string,
    reason?: string
  ): Promise<import("../types").PropertyDuplicateReview> {
    return fetchJson<import("../types").PropertyDuplicateReview>(`/api/property-duplicate-reviews/${id}/attach-existing`, {
      method: "POST",
      body: JSON.stringify({ target_property_id: targetPropertyId, reason }),
    });
  },

  async createNewPropertyFromDuplicateReview(
    id: string,
    reason?: string
  ): Promise<import("../types").PropertyDuplicateReview> {
    return fetchJson<import("../types").PropertyDuplicateReview>(`/api/property-duplicate-reviews/${id}/create-new`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  async ignoreDuplicateReview(
    id: string,
    reason?: string
  ): Promise<import("../types").PropertyDuplicateReview> {
    return fetchJson<import("../types").PropertyDuplicateReview>(`/api/property-duplicate-reviews/${id}/ignore`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  // Module 4 — Phase 3: Property Matching & Candidate Search
  async runPropertyMatching(
    leadId: string,
    config?: Record<string, any>
  ): Promise<import("../types").RunMatchingResponse> {
    return fetchJson<import("../types").RunMatchingResponse>(`/api/leads/${leadId}/property-matching/run`, {
      method: "POST",
      body: JSON.stringify({ config }),
    });
  },

  async listPropertyMatchingRuns(leadId: string): Promise<import("../types").PropertyMatchingRun[]> {
    return fetchJson<import("../types").PropertyMatchingRun[]>(`/api/leads/${leadId}/property-matching/runs`);
  },

  async listPropertyMatches(
    leadId: string,
    params?: { status?: string; run_id?: string; skip?: number; limit?: number }
  ): Promise<import("../types").PropertyMatch[]> {
    const qs = new URLSearchParams();
    if (params?.status) qs.append("status", params.status);
    if (params?.run_id) qs.append("run_id", params.run_id);
    if (params?.skip !== undefined) qs.append("skip", String(params.skip));
    if (params?.limit !== undefined) qs.append("limit", String(params.limit));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").PropertyMatch[]>(`/api/leads/${leadId}/property-matches${query}`);
  },

  async getPropertyMatch(matchId: string): Promise<import("../types").PropertyMatch> {
    return fetchJson<import("../types").PropertyMatch>(`/api/property-matches/${matchId}`);
  },

  async overridePropertyMatch(
    matchId: string,
    data: { target_status: string; reason: string }
  ): Promise<import("../types").PropertyMatch> {
    return fetchJson<import("../types").PropertyMatch>(`/api/property-matches/${matchId}/override`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Module 4 — Phase 4: Property Scoring & Ranking
  async scorePropertyMatches(
    leadId: string,
    config?: Record<string, any>
  ): Promise<import("../types").ScoreMatchesResponse> {
    return fetchJson<import("../types").ScoreMatchesResponse>(`/api/leads/${leadId}/property-matching/score`, {
      method: "POST",
      body: JSON.stringify({ config }),
    });
  },

  async getScoringConfiguration(): Promise<import("../types").PropertyScoringConfig> {
    return fetchJson<import("../types").PropertyScoringConfig>("/api/property-matching/scoring-config");
  },

  async updateScoringConfiguration(
    config: import("../types").PropertyScoringConfig
  ): Promise<import("../types").PropertyScoringConfig> {
    return fetchJson<import("../types").PropertyScoringConfig>("/api/property-matching/scoring-config", {
      method: "PATCH",
      body: JSON.stringify(config),
    });
  },

  async markPropertyMatchStale(
    matchId: string,
    reason: string
  ): Promise<import("../types").PropertyMatch> {
    return fetchJson<import("../types").PropertyMatch>(`/api/property-matches/${matchId}/mark-stale`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  // Module 4 — Phase 5: Property-Agent Mapping + WhatsApp Outreach
  async previewAgentOutreach(
    matchId: string,
    templateId?: string
  ): Promise<import("../types").OutreachMessagePreview> {
    const qs = templateId ? `?template_id=${templateId}` : "";
    return fetchJson<import("../types").OutreachMessagePreview>(
      `/api/property-matches/${matchId}/agent-outreach/preview${qs}`,
      { method: "POST" }
    );
  },

  async sendAgentOutreach(
    matchId: string,
    data?: { template_id?: string; outreach_type?: string; manual_reason?: string }
  ): Promise<import("../types").PropertyAgentOutreach> {
    return fetchJson<import("../types").PropertyAgentOutreach>(
      `/api/property-matches/${matchId}/agent-outreach`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    );
  },

  async runBulkAgentOutreach(
    leadId: string,
    data?: { max_candidates?: number; template_id?: string }
  ): Promise<import("../types").BulkAgentOutreachRunResponse> {
    return fetchJson<import("../types").BulkAgentOutreachRunResponse>(
      `/api/leads/${leadId}/property-agent-outreach/run`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    );
  },

  async getMatchOutreachHistory(
    matchId: string
  ): Promise<import("../types").PropertyAgentOutreach[]> {
    return fetchJson<import("../types").PropertyAgentOutreach[]>(
      `/api/property-matches/${matchId}/agent-outreach`
    );
  },

  async getPropertyAgentConversation(
    conversationId: string
  ): Promise<import("../types").PropertyAgentConversationDetail> {
    return fetchJson<import("../types").PropertyAgentConversationDetail>(
      `/api/property-agent-conversations/${conversationId}`
    );
  },

  // Module 4 Phase 6: Availability Verification
  async getPropertyMatchAvailability(
    matchId: string
  ): Promise<any> {
    return fetchJson<any>(`/api/property-matches/${matchId}/availability`);
  },

  async getPropertyMatchVerificationHistory(
    matchId: string
  ): Promise<import("../types").PropertyAvailabilityVerification[]> {
    return fetchJson<import("../types").PropertyAvailabilityVerification[]>(
      `/api/property-matches/${matchId}/verification-history`
    );
  },

  async overridePropertyMatchAvailability(
    matchId: string,
    data: import("../types").ManualVerificationOverridePayload
  ): Promise<import("../types").PropertyAvailabilityVerification> {
    return fetchJson<import("../types").PropertyAvailabilityVerification>(
      `/api/property-matches/${matchId}/availability-override`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  },

  async analyzePropertyAgentMessage(
    messageId: string
  ): Promise<any> {
    return fetchJson<any>(`/api/property-agent-messages/${messageId}/analyze`, {
      method: "POST",
    });
  },

  async resolveAmbiguousAgentMessage(
    messageId: string,
    propertyMatchId: string,
    reason: string
  ): Promise<any> {
    return fetchJson<any>(`/api/property-agent-messages/${messageId}/resolve-match`, {
      method: "POST",
      body: JSON.stringify({ property_match_id: propertyMatchId, reason }),
    });
  },

  // Module 4 Phase 7: Follow-up & Fallback
  async listPropertyAgentFollowUps(
    params?: { lead_id?: string; match_id?: string; outreach_id?: string; status?: string }
  ): Promise<import("../types").PropertyAgentFollowUp[]> {
    const q = new URLSearchParams();
    if (params?.lead_id) q.set("lead_id", params.lead_id);
    if (params?.match_id) q.set("match_id", params.match_id);
    if (params?.outreach_id) q.set("outreach_id", params.outreach_id);
    if (params?.status) q.set("status", params.status);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return fetchJson<import("../types").PropertyAgentFollowUp[]>(`/api/property-agent-followups${qs}`);
  },

  async getPropertyMatchFollowUps(
    matchId: string
  ): Promise<import("../types").PropertyAgentFollowUp[]> {
    return fetchJson<import("../types").PropertyAgentFollowUp[]>(
      `/api/property-matches/${matchId}/followups`
    );
  },

  async sendManualPropertyAgentFollowUp(
    outreachId: string,
    reason?: string
  ): Promise<import("../types").PropertyAgentFollowUp> {
    return fetchJson<import("../types").PropertyAgentFollowUp>(
      `/api/property-agent-outreach/${outreachId}/follow-up`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  },

  async cancelPropertyAgentFollowUp(
    followupId: string,
    reason?: string
  ): Promise<import("../types").PropertyAgentFollowUp> {
    return fetchJson<import("../types").PropertyAgentFollowUp>(
      `/api/property-agent-followups/${followupId}/cancel`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  },

  async getFallbackPreview(
    matchId: string
  ): Promise<import("../types").FallbackPreviewResponse> {
    return fetchJson<import("../types").FallbackPreviewResponse>(
      `/api/property-matches/${matchId}/fallback-preview`
    );
  },

  async executeFallback(
    matchId: string,
    reason?: string
  ): Promise<import("../types").ExecuteFallbackResponse> {
    return fetchJson<import("../types").ExecuteFallbackResponse>(
      `/api/property-matches/${matchId}/execute-fallback`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  },

  // Module 4 Phase 8/10: Verified Shortlist & Lead Matching Dashboard
  async getPropertyMatchingDashboard(
    leadId: string
  ): Promise<import("../types").PropertyMatchingDashboardResponse> {
    return fetchJson<import("../types").PropertyMatchingDashboardResponse>(
      `/api/leads/${leadId}/property-matching/dashboard`
    );
  },

  async buildPropertyShortlist(
    leadId: string
  ): Promise<import("../types").PropertyShortlist> {
    return fetchJson<import("../types").PropertyShortlist>(
      `/api/leads/${leadId}/property-shortlist/build`,
      {
        method: "POST",
      }
    );
  },

  async getPropertyShortlist(
    leadId: string
  ): Promise<import("../types").PropertyShortlist | null> {
    return fetchJson<import("../types").PropertyShortlist | null>(
      `/api/leads/${leadId}/property-shortlist`
    );
  },

  async refreshPropertyShortlist(
    leadId: string
  ): Promise<import("../types").PropertyShortlist> {
    return fetchJson<import("../types").PropertyShortlist>(
      `/api/leads/${leadId}/property-shortlist/refresh`,
      {
        method: "POST",
      }
    );
  },

  async addShortlistItem(
    shortlistId: string,
    matchId: string,
    data?: { manual_override_reason?: string; force_override?: boolean }
  ): Promise<import("../types").PropertyShortlistItem> {
    return fetchJson<import("../types").PropertyShortlistItem>(
      `/api/property-shortlists/${shortlistId}/items/${matchId}`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    );
  },

  async removeShortlistItem(
    shortlistId: string,
    matchId: string
  ): Promise<import("../types").PropertyShortlist> {
    return fetchJson<import("../types").PropertyShortlist>(
      `/api/property-shortlists/${shortlistId}/items/${matchId}`,
      {
        method: "DELETE",
      }
    );
  },

  async reorderShortlist(
    shortlistId: string,
    items: { property_match_id: string; position: number }[]
  ): Promise<import("../types").PropertyShortlist> {
    return fetchJson<import("../types").PropertyShortlist>(
      `/api/property-shortlists/${shortlistId}/reorder`,
      {
        method: "PATCH",
        body: JSON.stringify({ items }),
      }
    );
  },

  async getModule5Handoff(
    leadId: string
  ): Promise<import("../types").Module5HandoffPayload> {
    return fetchJson<import("../types").Module5HandoffPayload>(
      `/api/leads/${leadId}/property-shortlist/module5-handoff`
    );
  },

  // Module 5 Phase 1: Viewings API
  async createViewingFromMatch(
    matchId: string,
    payload?: import("../types").ViewingCreatePayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/property-matches/${matchId}/viewings`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  async listLeadViewings(
    leadId: string,
    statusFilter?: string
  ): Promise<import("../types").ViewingListResponse> {
    const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
    return fetchJson<import("../types").ViewingListResponse>(`/api/leads/${leadId}/viewings${qs}`);
  },

  async listViewings(params?: {
    status?: string;
    lead_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<import("../types").ViewingListResponse> {
    const qs = new URLSearchParams();
    if (params?.status) qs.append("status", params.status);
    if (params?.lead_id) qs.append("lead_id", params.lead_id);
    if (params?.limit) qs.append("limit", params.limit.toString());
    if (params?.offset) qs.append("offset", params.offset.toString());
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson<import("../types").ViewingListResponse>(`/api/viewings${query}`);
  },

  async getViewingDetail(viewingId: string): Promise<import("../types").ViewingDetail> {
    return fetchJson<import("../types").ViewingDetail>(`/api/viewings/${viewingId}`);
  },

  async updateViewingMetadata(
    viewingId: string,
    payload: import("../types").ViewingUpdatePayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async addViewingSlot(
    viewingId: string,
    payload: import("../types").ViewingSlotCreatePayload
  ): Promise<import("../types").ViewingSlot> {
    return fetchJson<import("../types").ViewingSlot>(`/api/viewings/${viewingId}/slots`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async selectViewingSlot(
    viewingId: string,
    slotId: string
  ): Promise<import("../types").ViewingSlot> {
    return fetchJson<import("../types").ViewingSlot>(`/api/viewings/${viewingId}/slots/${slotId}/select`, {
      method: "POST",
    });
  },

  async transitionViewing(
    viewingId: string,
    payload: import("../types").ViewingTransitionPayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}/transition`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async cancelViewing(
    viewingId: string,
    payload: import("../types").ViewingCancelPayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}/cancel`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async completeViewing(
    viewingId: string,
    payload?: import("../types").ViewingCompletePayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}/complete`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  async recordViewingNoShow(
    viewingId: string,
    payload?: import("../types").ViewingNoShowPayload
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}/no-show`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  // Module 5 Phase 2: Property Presentation & Tenant Interest APIs
  async presentPropertyMatchToTenant(
    matchId: string
  ): Promise<import("../types").PropertyInterest> {
    return fetchJson<import("../types").PropertyInterest>(
      `/api/property-matches/${matchId}/present-to-tenant`,
      { method: "POST" }
    );
  },

  async startPropertyPresentation(
    leadId: string
  ): Promise<import("../types").PropertyPresentationResult> {
    return fetchJson<import("../types").PropertyPresentationResult>(
      `/api/leads/${leadId}/property-presentation/start`,
      { method: "POST" }
    );
  },

  async listLeadPropertyInterests(
    leadId: string
  ): Promise<import("../types").PropertyInterestListResponse> {
    return fetchJson<import("../types").PropertyInterestListResponse>(
      `/api/leads/${leadId}/property-interests`
    );
  },

  async getPropertyInterestDetail(
    interestId: string
  ): Promise<import("../types").PropertyInterest> {
    return fetchJson<import("../types").PropertyInterest>(
      `/api/property-interests/${interestId}`
    );
  },

  async updatePropertyInterestManual(
    interestId: string,
    payload: { status: import("../types").PropertyInterestStatus; tenant_notes?: string; actor_id?: string }
  ): Promise<import("../types").PropertyInterest> {
    return fetchJson<import("../types").PropertyInterest>(
      `/api/property-interests/${interestId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      }
    );
  },

  async processTenantInterestMessage(
    leadId: string,
    payload: { message_content: string; interactive_payload?: string; inbound_message_id?: string }
  ): Promise<import("../types").TenantInterestProcessResult> {
    return fetchJson<import("../types").TenantInterestProcessResult>(
      `/api/leads/${leadId}/tenant-message/process-interest`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  // Module 5 Phase 3: Viewing Agent Availability Collection
  async requestAgentAvailability(
    viewingId: string,
    payload: { actor_id?: string; custom_message?: string; tenant_broad_availability?: string } = {}
  ): Promise<import("../types").ViewingAvailabilityRequest> {
    return fetchJson<import("../types").ViewingAvailabilityRequest>(
      `/api/viewings/${viewingId}/agent-availability/request`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async getViewingAvailabilityStatus(
    viewingId: string
  ): Promise<import("../types").ViewingAgentAvailabilityStatus> {
    return fetchJson<import("../types").ViewingAgentAvailabilityStatus>(
      `/api/viewings/${viewingId}/agent-availability`
    );
  },

  async analyzeViewingAgentMessage(
    messageId: string,
    payload: { actor_id?: string; override_viewing_id?: string } = {}
  ): Promise<any> {
    return fetchJson<any>(
      `/api/viewing-agent-messages/${messageId}/analyze`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async manuallyCorrelateAgentMessage(
    messageId: string,
    payload: { viewing_id: string; reason: string; actor_id?: string }
  ): Promise<any> {
    return fetchJson<any>(
      `/api/viewing-agent-messages/${messageId}/resolve-viewing`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  // Module 5 Phase 4: Tenant Availability & Slot Matching
  async requestTenantAvailability(
    viewingId: string,
    payload: { strategy?: string; custom_message?: string; actor_id?: string } = {}
  ): Promise<import("../types").TenantViewingAvailabilityRequestResult> {
    return fetchJson<import("../types").TenantViewingAvailabilityRequestResult>(
      `/api/viewings/${viewingId}/tenant-availability/request`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async getViewingTenantAvailabilityStatus(
    viewingId: string
  ): Promise<import("../types").ViewingTenantAvailabilityStatus> {
    return fetchJson<import("../types").ViewingTenantAvailabilityStatus>(
      `/api/viewings/${viewingId}/tenant-availability`
    );
  },

  async matchViewingSlots(
    viewingId: string,
    payload: { duration_minutes?: number; interval_minutes?: number } = {}
  ): Promise<import("../types").ViewingSlotMatchingResult> {
    return fetchJson<import("../types").ViewingSlotMatchingResult>(
      `/api/viewings/${viewingId}/match-slots`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async proposeCandidateSlot(
    viewingId: string,
    slotId: string,
    payload: { reason?: string; actor_id?: string } = {}
  ): Promise<import("../types").ViewingSlot> {
    return fetchJson<import("../types").ViewingSlot>(
      `/api/viewings/${viewingId}/slots/${slotId}/propose`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async recordManualTenantAvailability(
    viewingId: string,
    payload: { windows: import("../types").TenantAvailabilityWindowItem[]; notes?: string; actor_id?: string }
  ): Promise<any> {
    return fetchJson<any>(
      `/api/viewings/${viewingId}/tenant-availability/manual`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  // Module 5 Phase 5: Viewing Confirmation & Final Booking
  async requestTenantConfirmation(
    viewingId: string,
    payload: { custom_message?: string; actor_id?: string } = {}
  ): Promise<import("../types").ViewingConfirmationRequestResult> {
    return fetchJson<import("../types").ViewingConfirmationRequestResult>(
      `/api/viewings/${viewingId}/confirmation/tenant/request`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async requestAgentConfirmation(
    viewingId: string,
    payload: { custom_message?: string; actor_id?: string } = {}
  ): Promise<import("../types").ViewingConfirmationRequestResult> {
    return fetchJson<import("../types").ViewingConfirmationRequestResult>(
      `/api/viewings/${viewingId}/confirmation/agent/request`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async confirmTenant(
    viewingId: string,
    payload: { reason: string; notes?: string; actor_id?: string }
  ): Promise<import("../types").ViewingConfirmationStatusOverview> {
    return fetchJson<import("../types").ViewingConfirmationStatusOverview>(
      `/api/viewings/${viewingId}/confirmation/tenant/confirm`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async confirmAgent(
    viewingId: string,
    payload: { reason: string; notes?: string; actor_id?: string }
  ): Promise<import("../types").ViewingConfirmationStatusOverview> {
    return fetchJson<import("../types").ViewingConfirmationStatusOverview>(
      `/api/viewings/${viewingId}/confirmation/agent/confirm`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async declineTenant(
    viewingId: string,
    payload: { reason: string; actor_id?: string }
  ): Promise<import("../types").ViewingConfirmationStatusOverview> {
    return fetchJson<import("../types").ViewingConfirmationStatusOverview>(
      `/api/viewings/${viewingId}/confirmation/tenant/decline`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async declineAgent(
    viewingId: string,
    payload: { reason: string; actor_id?: string }
  ): Promise<import("../types").ViewingConfirmationStatusOverview> {
    return fetchJson<import("../types").ViewingConfirmationStatusOverview>(
      `/api/viewings/${viewingId}/confirmation/agent/decline`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async finalizeViewingBooking(
    viewingId: string,
    payload: { reason?: string; actor_id?: string } = {}
  ): Promise<import("../types").ViewingFinalizeBookingResult> {
    return fetchJson<import("../types").ViewingFinalizeBookingResult>(
      `/api/viewings/${viewingId}/finalize-booking`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },

  async getViewingConfirmationStatus(
    viewingId: string
  ): Promise<import("../types").ViewingConfirmationStatusOverview> {
    return fetchJson<import("../types").ViewingConfirmationStatusOverview>(
      `/api/viewings/${viewingId}/confirmation-status`
    );
  },

  // Module 5 Phase 6: Reminders, Reschedule & Cancellation
  async listViewingReminders(viewingId: string): Promise<import("../types").ViewingReminder[]> {
    return fetchJson<import("../types").ViewingReminder[]>(`/api/viewings/${viewingId}/reminders`);
  },

  async rebuildViewingReminders(viewingId: string): Promise<import("../types").ViewingReminder[]> {
    return fetchJson<import("../types").ViewingReminder[]>(
      `/api/viewings/${viewingId}/reminders/rebuild`,
      { method: "POST" }
    );
  },

  async rescheduleViewing(
    viewingId: string,
    payload: { requested_by: string; reason?: string }
  ): Promise<import("../types").Viewing> {
    return fetchJson<import("../types").Viewing>(`/api/viewings/${viewingId}/reschedule`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },


  async getViewingScheduleHistory(
    viewingId: string
  ): Promise<import("../types").ViewingScheduleHistory[]> {
    return fetchJson<import("../types").ViewingScheduleHistory[]>(
      `/api/viewings/${viewingId}/schedule-history`
    );
  },
};










