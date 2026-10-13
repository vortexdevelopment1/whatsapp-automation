export type AgentStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
export type AuthorizationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED';
export type BrandingStatus = 'NOT_STARTED' | 'DRAFT' | 'READY' | 'APPROVED';
export type WhatsAppConnectionStatus = 'NOT_CONFIGURED' | 'CONFIGURED' | 'CONNECTED' | 'ERROR' | 'DISABLED';
export type TemplateStatus = 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'DISABLED';

export interface Agent {
  id: string;
  full_name: string;
  display_name: string | null;
  agency_name: string;
  designation: string | null;
  registration_number: string | null;
  phone: string | null;
  email: string | null;
  profile_photo_url: string | null;
  status: AgentStatus;
  authorization_status: AuthorizationStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateInput {
  full_name: string;
  display_name?: string | null;
  agency_name: string;
  designation?: string | null;
  registration_number?: string | null;
  phone?: string | null;
  email?: string | null;
  profile_photo_url?: string | null;
  notes?: string | null;
}

export interface AgentUpdateInput {
  full_name?: string;
  display_name?: string | null;
  agency_name?: string;
  designation?: string | null;
  registration_number?: string | null;
  phone?: string | null;
  email?: string | null;
  profile_photo_url?: string | null;
  notes?: string | null;
  authorization_status?: AuthorizationStatus;
}

export interface AgentBranding {
  id: string;
  agent_id: string;
  business_description: string | null;
  office_address: string | null;
  website: string | null;
  profile_photo_url: string | null;
  digital_name_card_url: string | null;
  lanyard_artwork_url: string | null;
  branding_status: BrandingStatus;
  created_at: string;
  updated_at: string;
}

export interface BrandingUpdateInput {
  business_description?: string | null;
  office_address?: string | null;
  website?: string | null;
  profile_photo_url?: string | null;
  digital_name_card_url?: string | null;
  lanyard_artwork_url?: string | null;
  branding_status?: BrandingStatus;
}

export interface WhatsAppProfile {
  id: string;
  agent_id: string;
  meta_business_account_id: string | null;
  phone_number_id: string | null;
  display_phone_number: string | null;
  business_display_name: string | null;
  connection_status: WhatsAppConnectionStatus;
  webhook_verified: boolean;
  last_webhook_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WhatsAppProfileUpdateInput {
  meta_business_account_id?: string | null;
  phone_number_id?: string | null;
  display_phone_number?: string | null;
  business_display_name?: string | null;
  connection_status?: WhatsAppConnectionStatus;
}

export interface MessageTemplate {
  id: string;
  agent_id: string | null;
  template_name: string;
  meta_template_name: string | null;
  language: string;
  category: string | null;
  body: string;
  status: TemplateStatus;
  created_at: string;
  updated_at: string;
}

export interface TemplateCreateInput {
  template_name: string;
  meta_template_name?: string | null;
  language: string;
  category?: string | null;
  body: string;
  status?: TemplateStatus;
}

export interface TemplateUpdateInput {
  template_name?: string;
  meta_template_name?: string | null;
  language?: string;
  category?: string | null;
  body?: string;
  status?: TemplateStatus;
}

export interface AuditLog {
  id: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  old_value: any;
  new_value: any;
  created_at: string;
}

export type MessageDirection = 'INBOUND' | 'OUTBOUND';
export type MessageType = 'TEXT' | 'TEMPLATE' | 'IMAGE' | 'DOCUMENT' | 'STATUS' | 'UNKNOWN';

export interface WhatsAppMessage {
  id: string;
  whatsapp_profile_id: string;
  provider_message_id: string | null;
  direction: MessageDirection;
  message_type: MessageType;
  sender: string | null;
  recipient: string | null;
  content: string | null;
  provider_status: string | null;
  raw_payload: any;
  created_at: string;
}

export type LeadStatus =
  | 'NEW'
  | 'VALIDATING'
  | 'DUPLICATE'
  | 'INELIGIBLE'
  | 'READY_FOR_OUTREACH'
  | 'OUTREACH_QUEUED'
  | 'CONTACTED'
  | 'DELIVERED'
  | 'READ'
  | 'REPLIED'
  | 'OPTED_OUT'
  | 'FAILED'
  | 'ARCHIVED';

export type ConsentStatus = 'UNKNOWN' | 'CONSENTED' | 'NOT_CONSENTED';
export type OptOutStatus = 'ACTIVE' | 'OPTED_OUT';
export type ContactEligibility = 'UNKNOWN' | 'ELIGIBLE' | 'INELIGIBLE';

export interface Lead {
  id: string;
  full_name: string | null;
  phone: string;
  phone_normalized: string;
  email: string | null;
  source_id: string | null;
  status: LeadStatus;
  consent_status: ConsentStatus;
  opt_out_status: OptOutStatus;
  contact_eligibility: ContactEligibility;
  assigned_agent_id: string | null;
  assigned_whatsapp_profile_id: string | null;
  duplicate_override: boolean;
  duplicate_override_reason: string | null;
  duplicate_of_id: string | null;
  created_at: string;
  updated_at: string;
  source?: {
    id: string;
    name: string;
    source_type: string;
  } | null;
}

export interface LeadDuplicateSummary {
  id: string;
  full_name: string | null;
  phone: string;
  phone_normalized: string;
  status: LeadStatus;
}

export interface LeadDuplicateCheckResponse {
  duplicate: boolean;
  existing_lead_id: string | null;
  match_reasons: string[];
  existing_lead: LeadDuplicateSummary | null;
}

export interface LeadEligibilityCheckResponse {
  lead_id: string;
  eligibility: ContactEligibility;
  reasons: string[];
}

export type QualificationStatus =
  | 'NOT_STARTED'
  | 'IN_PROGRESS'
  | 'QUALIFYING'
  | 'WAITING_FOR_TENANT'
  | 'QUALIFIED'
  | 'QUALIFICATION_COMPLETE'
  | 'NEEDS_HUMAN_REVIEW'
  | 'DISQUALIFIED';

export type QualificationMode = 'AI_ACTIVE' | 'HUMAN_REVIEW' | 'PAUSED';

export type RequirementFieldStatus = 'PROPOSED' | 'CONFIRMED' | 'REJECTED' | 'SUPERSEDED';
export type RequirementSourceType = 'TENANT_MESSAGE' | 'HUMAN_OPERATOR' | 'SYSTEM';

export interface TenantRequirement {
  id: string;
  lead_id: string;
  preferred_locations: string[] | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string;
  property_type: string | null;
  bedrooms: number | null;
  move_in_date: string | null;
  lease_duration_months: number | null;
  occupants: number | null;
  furnishing: string | null;
  special_requirements: Record<string, any> | null;
  qualification_status: QualificationStatus;
  completion_percentage: number;
  ai_paused: boolean;
  created_at: string;
  updated_at: string;
}

export interface QualificationLiveStatus {
  lead_id: string;
  qualification_mode: QualificationMode;
  qualification_status: QualificationStatus;
  ai_paused: boolean;
  completion_percentage: number;
  completed_fields: string[];
  missing_fields: string[];
  clarification_fields: string[];
  last_tenant_message: {
    id: string;
    content: string;
    created_at: string;
  } | null;
  last_ai_processing: {
    id: string;
    status: string;
    intent: string | null;
    created_at: string;
    completed_at: string | null;
    error_code?: string | null;
  } | null;
  last_outbound_question: {
    id: string;
    content: string;
    created_at: string;
  } | null;
  latest_decision?: {
    id: string;
    decision: QualificationStatus;
    reason_codes: string[];
    blocking_fields: string[];
    rule_version: string;
    evaluation_source: string;
    evaluated_by: string;
    override_reason?: string | null;
    created_at?: string | null;
  } | null;
}

export interface QualificationDecisionResponse {
  id?: string;
  lead_id: string;
  tenant_requirement_id?: string | null;
  decision: QualificationStatus;
  reason_codes: string[];
  missing_fields: string[];
  blocking_fields: string[];
  completion_percentage: number;
  rule_version: string;
  applied: boolean;
  evaluated_by: string;
  evaluation_source: string;
  override_reason?: string | null;
  created_at?: string | null;
  evaluated_at?: string | null;
}

export interface TenantRequirementHistory {
  id: string;
  tenant_requirement_id: string;
  field_name: string;
  value: any;
  confidence: number | null;
  source_message_id: string | null;
  status: RequirementFieldStatus;
  source_type: RequirementSourceType;
  created_at: string;
  updated_at: string;
}

export interface QualificationProgress {
  lead_id: string;
  qualification_status: QualificationStatus;
  completion_percentage: number;
  ready: boolean;
  missing_fields: string[];
  completed_fields: string[];
  required_fields: string[];
  optional_fields: string[];
}

export type QuestionAction = 'ASK_FIELD' | 'ASK_CLARIFICATION' | 'NO_QUESTION' | 'HUMAN_REVIEW';
export type QuestionType = 'MISSING_FIELD' | 'CLARIFICATION' | 'CONFIRMATION' | 'CONFLICT_RESOLUTION';

export interface NextQuestionResponse {
  lead_id: string;
  action: QuestionAction;
  field: string | null;
  question_type: QuestionType | null;
  question_text: string | null;
  fallback_used: boolean;
  reason: string;
  completion_percentage: number;
  completed_fields: string[];
  missing_fields: string[];
  clarification_fields: string[];
}

export interface QualificationPreviewResponse {
  lead_id: string;
  completion_percentage: number;
  completed_fields: string[];
  missing_fields: string[];
  clarification_fields: string[];
  next_question: {
    action: QuestionAction;
    field?: string;
    question_type?: QuestionType;
    reason?: string;
    preview_text?: string;
  } | null;
}

// Module 3 Phase 7 Types
export type FAQStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE';

export interface FAQEntry {
  id: string;
  question: string;
  answer: string;
  category: string;
  keywords: string[];
  language: string;
  status: FAQStatus;
  version: string;
  created_at: string;
  updated_at: string;
}

export interface FAQCreateInput {
  question: string;
  answer: string;
  category?: string;
  keywords?: string[];
  language?: string;
  status?: FAQStatus;
  version?: string;
}

export interface FAQUpdateInput {
  question?: string;
  answer?: string;
  category?: string;
  keywords?: string[];
  language?: string;
  status?: FAQStatus;
  version?: string;
}

export type EscalationStatus = 'OPEN' | 'ASSIGNED' | 'RESOLVED' | 'CANCELLED';
export type EscalationReason =
  | 'TENANT_REQUESTED_HUMAN'
  | 'CLARIFICATION_LIMIT_EXCEEDED'
  | 'UNRESOLVED_CONFLICT'
  | 'REPEATED_AI_FAILURE'
  | 'UNSUPPORTED_BUSINESS_QUESTION'
  | 'COMPLAINT_OR_DISPUTE'
  | 'WORKFLOW_INCONSISTENCY'
  | 'OPERATOR_TAKEOVER'
  | 'DECISION_RULE_FAILED';

export interface ConversationEscalation {
  id: string;
  lead_id: string;
  reason_code: EscalationReason | string;
  description: string | null;
  status: EscalationStatus;
  assigned_to: string | null;
  created_by: string;
  resolution_notes: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HumanReviewQueueItem {
  lead_id: string;
  lead_name: string;
  phone: string;
  escalation_id: string | null;
  reason_code: string;
  description: string | null;
  qualification_status: string;
  missing_fields: string[];
  last_message: string | null;
  last_message_at: string | null;
  time_waiting_minutes: number;
  assigned_to: string | null;
  escalation_status: string;
  ai_paused: boolean;
}

export type ClarificationStatus = 'OPEN' | 'WAITING_FOR_TENANT' | 'RESOLVED' | 'ESCALATED' | 'CANCELLED';

export interface QualificationClarification {
  id: string;
  lead_id: string;
  field_name: string;
  reason: string;
  proposed_value: any;
  status: ClarificationStatus;
  attempt_count: number;
  last_question_id: string | null;
  resolved_value: any;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface ConversationSummary {
  id: string;
  lead_id: string;
  conversation_id: string | null;
  summary_text: string;
  structured_summary: {
    qualification_status?: string;
    completion_percentage?: number;
    confirmed_requirements?: Record<string, any>;
    missing_fields?: string[];
    clarifications?: string[];
    conflicts?: any[];
    human_review?: boolean;
    ai_mode?: string;
  } | null;
  summary_version: number;
  last_message_id: string | null;
  generated_by: 'AI' | 'SYSTEM' | 'HUMAN';
  prompt_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationNote {
  id: string;
  lead_id: string;
  conversation_id: string | null;
  author_id: string;
  note: string;
  created_at: string;
}

export interface DashboardRequirementField {
  field_name: string;
  label: string;
  value: any;
  status: 'CONFIRMED' | 'PROPOSED' | 'NEEDS_CLARIFICATION' | 'MISSING' | 'CONFLICT';
  confidence_level?: string | null;
  reason?: string | null;
}

export interface QualificationDashboardData {
  lead_id: string;
  lead_name: string | null;
  lead_phone: string;
  qualification_status: QualificationStatus;
  completion_percentage: number;
  ai_mode: QualificationMode;
  ai_paused: boolean;
  is_human_review: boolean;
  requirements: Record<string, any>;
  field_details: DashboardRequirementField[];
  missing_fields: string[];
  clarification_fields: string[];
  clarifications: any[];
  conflicts: any[];
  active_escalation: {
    id: string;
    reason_code: string;
    description: string | null;
    status: string;
    assigned_to: string | null;
    created_at: string;
  } | null;
  summary: ConversationSummary | null;
  next_action: {
    action: string;
    label: string;
    description: string;
  };
  recent_messages: Array<{
    id: string;
    direction: string;
    sender_type: string;
    content: string;
    timestamp: string | null;
    delivery_status?: string | null;
  }>;
  operator_notes: ConversationNote[];
  last_ai_activity: {
    intent: string;
    intent_confidence: number | null;
    status: string;
    processed_at: string | null;
    model: string;
  } | null;
}

// ==========================================
// Module 4 Phase 1: Property Inventory Types
// ==========================================

export type PropertyType =
  | 'CONDO'
  | 'APARTMENT'
  | 'HDB'
  | 'LANDED'
  | 'STUDIO'
  | 'ROOM'
  | 'COMMERCIAL'
  | 'OTHER'
  | 'UNKNOWN';

export type PropertyStatus = 'ACTIVE' | 'INACTIVE' | 'ARCHIVED' | 'NEEDS_REVIEW';

export type PropertySourceType =
  | 'MANUAL'
  | 'CSV_IMPORT'
  | 'CLIENT_INVENTORY'
  | 'APPROVED_API'
  | 'DEMO'
  | 'OTHER';

export type PropertySourceStatus = 'ACTIVE' | 'INACTIVE';

export type PropertyListingStatus =
  | 'ACTIVE'
  | 'INACTIVE'
  | 'EXPIRED'
  | 'REMOVED'
  | 'ARCHIVED'
  | 'NEEDS_REVIEW';

export type ListingAvailabilityStatus =
  | 'UNKNOWN'
  | 'NOT_CHECKED'
  | 'AWAITING_VERIFICATION'
  | 'AVAILABLE'
  | 'UNAVAILABLE'
  | 'CONDITIONAL';

export type PropertyAgentStatus = 'ACTIVE' | 'INACTIVE' | 'ARCHIVED' | 'UNVERIFIED';

export interface Property {
  id: string;
  canonical_name: string | null;
  building_name: string | null;
  address_line_1: string | null;
  address_line_2: string | null;
  unit_number: string | null;
  postal_code: string | null;
  city: string | null;
  state_region: string | null;
  district: string | null;
  country: string;
  latitude: number | null;
  longitude: number | null;
  property_type: PropertyType;
  bedrooms: number | null;
  bathrooms: number | null;
  size_sqft: number | null;
  furnishing: string | null;
  status: PropertyStatus;
  listings_count: number;
  created_at: string;
  updated_at: string;
}

export interface PropertyCreateInput {
  canonical_name?: string | null;
  building_name?: string | null;
  address_line_1?: string | null;
  address_line_2?: string | null;
  unit_number?: string | null;
  postal_code?: string | null;
  city?: string | null;
  state_region?: string | null;
  district?: string | null;
  country?: string;
  latitude?: number | null;
  longitude?: number | null;
  property_type?: PropertyType;
  bedrooms?: number | null;
  bathrooms?: number | null;
  size_sqft?: number | null;
  furnishing?: string | null;
  status?: PropertyStatus;
}

export interface PropertyUpdateInput {
  canonical_name?: string | null;
  building_name?: string | null;
  address_line_1?: string | null;
  address_line_2?: string | null;
  unit_number?: string | null;
  postal_code?: string | null;
  city?: string | null;
  state_region?: string | null;
  district?: string | null;
  country?: string;
  latitude?: number | null;
  longitude?: number | null;
  property_type?: PropertyType;
  bedrooms?: number | null;
  bathrooms?: number | null;
  size_sqft?: number | null;
  furnishing?: string | null;
  status?: PropertyStatus;
}

export interface PropertySource {
  id: string;
  name: string;
  source_type: PropertySourceType;
  external_system_name: string | null;
  status: PropertySourceStatus;
  configuration_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface PropertySourceCreateInput {
  name: string;
  source_type?: PropertySourceType;
  external_system_name?: string | null;
  status?: PropertySourceStatus;
  configuration_reference?: string | null;
}

export interface PropertySourceUpdateInput {
  name?: string;
  source_type?: PropertySourceType;
  external_system_name?: string | null;
  status?: PropertySourceStatus;
  configuration_reference?: string | null;
}

export interface PropertyAgent {
  id: string;
  full_name: string | null;
  agency_name: string | null;
  registration_number: string | null;
  phone: string | null;
  phone_normalized: string | null;
  email: string | null;
  status: PropertyAgentStatus;
  source_id: string | null;
  external_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface PropertyAgentCreateInput {
  full_name?: string | null;
  agency_name?: string | null;
  registration_number?: string | null;
  phone?: string | null;
  email?: string | null;
  status?: PropertyAgentStatus;
  source_id?: string | null;
  external_reference?: string | null;
}

export interface PropertyAgentUpdateInput {
  full_name?: string | null;
  agency_name?: string | null;
  registration_number?: string | null;
  phone?: string | null;
  email?: string | null;
  status?: PropertyAgentStatus;
  source_id?: string | null;
  external_reference?: string | null;
}

export interface PropertyListing {
  id: string;
  property_id: string;
  source_id: string;
  source_listing_id: string | null;
  source_url: string | null;
  listing_reference: string | null;
  agent_id: string | null;
  asking_price: number | null;
  currency: string;
  availability_status: ListingAvailabilityStatus;
  available_from: string | null;
  lease_min_months: number | null;
  lease_max_months: number | null;
  listing_status: PropertyListingStatus;
  source_last_updated_at: string | null;
  last_verified_at: string | null;
  metadata?: Record<string, any> | null;
  source_name?: string | null;
  agent_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PropertyListingCreateInput {
  source_id: string;
  source_listing_id?: string | null;
  source_url?: string | null;
  listing_reference?: string | null;
  agent_id?: string | null;
  asking_price?: number | null;
  currency?: string;
  availability_status?: ListingAvailabilityStatus;
  available_from?: string | null;
  lease_min_months?: number | null;
  lease_max_months?: number | null;
  listing_status?: PropertyListingStatus;
  metadata?: Record<string, any> | null;
}

export interface PropertyListingUpdateInput {
  source_id?: string;
  source_listing_id?: string | null;
  source_url?: string | null;
  listing_reference?: string | null;
  agent_id?: string | null;
  asking_price?: number | null;
  currency?: string;
  availability_status?: ListingAvailabilityStatus;
  available_from?: string | null;
  lease_min_months?: number | null;
  lease_max_months?: number | null;
  listing_status?: PropertyListingStatus;
  metadata?: Record<string, any> | null;
}

export interface PropertyDetail extends Property {
  listings: PropertyListing[];
}

// ---------------------------------------------------------
// MODULE 4 — PHASE 2: IMPORT, NORMALIZATION & DEDUPLICATION
// ---------------------------------------------------------

export type PropertyImportType = 'CSV' | 'DEMO' | 'API' | 'MANUAL';
export type PropertyImportBatchStatus =
  | 'UPLOADED'
  | 'VALIDATING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_WARNINGS'
  | 'FAILED';

export type PropertyImportRowStatus =
  | 'PENDING'
  | 'VALID'
  | 'INVALID'
  | 'DUPLICATE_LISTING'
  | 'MATCHED_EXISTING_PROPERTY'
  | 'NEW_PROPERTY_CREATED'
  | 'NEEDS_REVIEW'
  | 'FAILED';

export type DuplicateReviewStatus = 'OPEN' | 'ATTACHED_EXISTING' | 'CREATED_NEW' | 'IGNORED';
export type DuplicateConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface PropertyImportBatch {
  id: string;
  source_id: string;
  file_name: string | null;
  import_type: PropertyImportType;
  status: PropertyImportBatchStatus;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_listing_rows: number;
  matched_existing_property_rows: number;
  new_property_rows: number;
  manual_review_rows: number;
  created_by: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_summary: Record<string, any> | null;
}

export interface PropertyImportRow {
  id: string;
  batch_id: string;
  row_number: number;
  raw_payload: Record<string, any>;
  normalized_payload: Record<string, any> | null;
  status: PropertyImportRowStatus;
  property_id: string | null;
  listing_id: string | null;
  error_codes: any[] | null;
  created_at: string;
  processed_at: string | null;
}

export interface PreviewRowItem {
  row_number: number;
  raw_payload: Record<string, any>;
  normalized_payload: Record<string, any> | null;
  status: PropertyImportRowStatus;
  dedup_verdict: string | null;
  dedup_confidence: string | null;
  dedup_reasons: string[] | null;
  target_property_id: string | null;
  target_listing_id: string | null;
  errors: any[] | null;
}

export interface PropertyImportPreviewResponse {
  batch_id: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_listing_rows: number;
  matched_existing_property_rows: number;
  new_property_rows: number;
  manual_review_rows: number;
  sample_rows: PreviewRowItem[];
}

export interface CandidatePropertySummary {
  id: string;
  canonical_name: string;
  building_name: string | null;
  address_line_1: string | null;
  address_line_2: string | null;
  unit_number: string | null;
  postal_code: string | null;
  property_type: PropertyType;
  bedrooms: number | null;
  bathrooms: number | null;
  size_sqft: number | null;
}

export interface PropertyDuplicateReview {
  id: string;
  import_row_id: string | null;
  candidate_property_id: string | null;
  incoming_normalized_data: Record<string, any>;
  match_reasons: string[];
  confidence_level: DuplicateConfidenceLevel;
  status: DuplicateReviewStatus;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_reason: string | null;
  created_at: string;
  updated_at: string;
  candidate_property: CandidatePropertySummary | null;
}

// =============================================================================
// Module 4 — Phase 3: Candidate Property Search + Hard Filters
// =============================================================================

export type PropertyMatchStatus =
  | 'CANDIDATE'
  | 'ELIGIBLE_FOR_SCORING'
  | 'FILTERED_OUT'
  | 'NEEDS_REVIEW'
  | 'SCORED'
  | 'BELOW_OUTREACH_THRESHOLD'
  | 'READY_FOR_AGENT_VERIFICATION'
  | 'AWAITING_AGENT'
  | 'AVAILABLE'
  | 'UNAVAILABLE'
  | 'CONDITIONAL'
  | 'VERIFIED_CANDIDATE'
  | 'AGENT_UNRESPONSIVE';


export type MatchingRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED';

export interface HardFilterRuleResult {
  rule: string;
  passed: boolean;
  reason: string;
  code?: string;
  tenant_value?: any;
  property_value?: any;
  tolerance_cutoff?: any;
}

export interface HardFilterResult {
  passed: boolean;
  needs_review: boolean;
  rules: HardFilterRuleResult[];
  failed_rules: string[];
  reason_codes: string[];
}

export interface PropertyMatch {
  id: string;
  lead_id: string;
  property_id: string;
  listing_id: string | null;
  matching_run_id: string | null;
  match_status: PropertyMatchStatus;
  hard_filter_passed: boolean | null;
  hard_filter_result: HardFilterResult | null;
  filter_rule_version: string | null;
  matching_config_version: string | null;
  match_score: number | null;
  rank: number | null;
  score_breakdown: Record<string, any> | null;
  scoring_config_version: string | null;
  scoring_explanation: string | null;
  is_stale: boolean;
  stale_reason: string | null;
  availability_status: string | null;
  agent_verification_status?: string | null;
  manual_override: boolean;
  manual_override_by: string | null;
  manual_override_at: string | null;
  manual_override_reason: string | null;
  created_at: string;
  updated_at: string;
  property_data?: {
    id: string;
    canonical_name: string;
    building_name: string | null;
    address_line_1: string | null;
    address_line_2: string | null;
    unit_number: string | null;
    postal_code: string | null;
    city: string | null;
    district: string | null;
    property_type: string;
    bedrooms: number | null;
    bathrooms: number | null;
    size_sqft: number | null;
    furnishing: string | null;
  } | null;
  listing_data?: {
    id: string;
    asking_price: number | null;
    currency: string;
    availability_status: string;
    available_from: string | null;
    lease_min_months: number | null;
    lease_max_months: number | null;
    listing_status: string;
  } | null;
}

export interface PropertyMatchingRun {
  id: string;
  lead_id: string;
  qualification_decision_id: string | null;
  config_version: string;
  status: MatchingRunStatus;
  total_inventory_considered: number;
  eligible_candidates: number;
  filtered_candidates: number;
  needs_review_candidates: number;
  scored_candidates: number;
  ready_for_verification_candidates: number;
  below_threshold_candidates: number;
  scoring_config_version: string | null;
  top_score: number | null;
  requirement_snapshot: Record<string, any> | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RunMatchingResponse {
  run_id: string;
  status: MatchingRunStatus;
  total_inventory_considered: number;
  eligible_candidates: number;
  filtered_candidates: number;
  needs_review_candidates: number;
  config_version: string;
}

export interface PropertyMatchOverrideRequest {
  target_status: PropertyMatchStatus;
  reason: string;
}

export interface PropertyScoringConfig {
  scoring_config_version: string;
  active: boolean;
  location_weight: number;
  budget_weight: number;
  property_type_weight: number;
  bedrooms_weight: number;
  move_in_weight: number;
  lease_weight: number;
  furnishing_weight: number;
  availability_weight: number;
  minimum_score_for_outreach: number;
  maximum_candidates_for_agent_verification: number;
  missing_data_policy: string;
  extra_bedroom_policy: string;
}

export interface ScoreMatchesResponse {
  lead_id: string;
  scored: number;
  ready_for_agent_verification: number;
  below_threshold: number;
  top_score: number | null;
  scoring_config_version: string;
}

export type PropertyAgentOutreachStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'SENT'
  | 'DELIVERED'
  | 'READ'
  | 'FAILED'
  | 'CANCELLED'
  | 'REPLIED';

export type PropertyAgentOutreachType =
  | 'INITIAL_AVAILABILITY_CHECK'
  | 'MANUAL'
  | 'MANUAL_RETRY'
  | 'MANUAL_FOLLOW_UP';

export interface PropertyAgentOutreach {
  id: string;
  lead_id: string;
  property_id: string;
  listing_id?: string | null;
  property_match_id: string;
  property_agent_id: string;
  conversation_id?: string | null;
  whatsapp_message_id?: string | null;
  template_id?: string | null;
  outreach_type: PropertyAgentOutreachType;
  status: PropertyAgentOutreachStatus;
  provider_message_id?: string | null;
  idempotency_key: string;
  reference_code?: string | null;
  recipient_phone?: string | null;
  message_content?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  replied_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  agent_name?: string | null;
  agency_name?: string | null;
  property_title?: string | null;
}

export interface OutreachMessagePreview {
  match_id: string;
  listing_id?: string | null;
  property_agent_id?: string | null;
  recipient_phone?: string | null;
  reference_code: string;
  template_id?: string | null;
  message_content: string;
  context_variables: Record<string, any>;
}

export interface BulkAgentOutreachRunResponse {
  lead_id: string;
  selected: number;
  queued: number;
  sent: number;
  failed: number;
  already_contacted: number;
  outreach_records: PropertyAgentOutreach[];
}

export interface PropertyAgentConversationMessageItem {
  id: string;
  direction: string;
  content: string | null;
  provider_status: string | null;
  created_at: string;
}

export interface PropertyAgentConversationDetail {
  id: string;
  property_agent_id: string;
  lead_id: string;
  property_id: string;
  listing_id?: string | null;
  property_match_id: string;
  conversation_type: string;
  status: string;
  reference_code?: string | null;
  last_message_at?: string | null;
  created_at: string;
  agent_name?: string | null;
  agency_name?: string | null;
  agent_phone?: string | null;
  property_title?: string | null;
  messages: PropertyAgentConversationMessageItem[];
}

export interface PropertyAvailabilityVerification {
  id: string;
  property_match_id?: string | null;
  listing_id?: string | null;
  property_agent_id?: string | null;
  outreach_id?: string | null;
  source_message_id?: string | null;
  intent?: string | null;
  availability_status: string;
  asking_price?: number | null;
  currency?: string | null;
  available_from?: string | null;
  minimum_lease_months?: number | null;
  maximum_lease_months?: number | null;
  furnishing?: string | null;
  viewing_possible?: boolean | null;
  viewing_notes?: string | null;
  conditions?: Record<string, any> | null;
  special_restrictions?: Record<string, any> | null;
  verification_status: string;
  verification_source: string;
  overall_confidence?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManualVerificationOverridePayload {
  availability_status: string;
  asking_price?: number | null;
  currency?: string;
  available_from?: string | null;
  minimum_lease_months?: number | null;
  maximum_lease_months?: number | null;
  furnishing?: string | null;
  viewing_possible?: boolean | null;
  viewing_notes?: string | null;
  conditions?: Record<string, any> | null;
  special_restrictions?: Record<string, any> | null;
  reason: string;
}

// Module 4 — Phase 7: Follow-up & Fallback Interfaces
export interface PropertyAgentFollowUp {
  id: string;
  lead_id: string;
  property_match_id: string;
  listing_id?: string | null;
  property_agent_id: string;
  outreach_id: string;
  conversation_id?: string | null;
  followup_type: string;
  attempt_number: number;
  status: string;
  due_at: string;
  sent_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  idempotency_key: string;
  message_content?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FallbackPreviewResponse {
  match_id: string;
  current_match_status: string;
  current_outreach_status?: string | null;
  recommended_action: string;
  reason?: string | null;
  alternate_listing?: {
    id: string;
    property_id: string;
    property_agent_id: string;
    agent_name?: string;
    agent_phone?: string;
    asking_price?: number;
    source_reference?: string;
  } | null;
  next_property_match?: {
    id: string;
    property_id: string;
    listing_id?: string | null;
    rank?: number | null;
    match_score?: number | null;
  } | null;
  total_agent_contacts: number;
  max_total_agent_contacts: number;
}

export interface ExecuteFallbackResponse {
  status: string;
  action: string;
  match_id: string;
  new_outreach_id?: string | null;
  new_match_id?: string | null;
  details?: Record<string, any> | null;
}

// ==========================================
// Module 4 — Phase 8/10: Verified Shortlist & Dashboard
// ==========================================

export interface CandidateComparisonItem {
  field_name: string;
  tenant_requirement: string;
  property_value: string;
  status: "MATCH" | "WARNING" | "MISMATCH" | "UNKNOWN" | string;
}

export interface CandidateDetailItem {
  property_match_id: string;
  property_id: string;
  listing_id?: string | null;
  property_agent_id?: string | null;
  system_rank?: number | null;
  match_score?: number | null;
  is_stale: boolean;
  stale_reason?: string | null;
  property_name: string;
  building_name?: string | null;
  address: string;
  district?: string | null;
  property_type: string;
  bedrooms?: number | null;
  bathrooms?: number | null;
  size_sqft?: number | null;
  furnishing?: string | null;
  asking_price?: number | null;
  currency: string;
  available_from?: string | null;
  lease_min_months?: number | null;
  availability_status?: string | null;
  agent_verification_status?: string | null;
  agent_name?: string | null;
  agent_agency?: string | null;
  followup_status?: string | null;
  shortlist_status: string;
  in_shortlist: boolean;
  shortlist_position?: number | null;
  explanation?: string | null;
  reasons: string[];
  warnings: string[];
  comparison: CandidateComparisonItem[];
  verified_at?: string | null;
}

export interface PropertyShortlistItem {
  id: string;
  shortlist_id: string;
  property_match_id: string;
  position: number;
  shortlist_status: string;
  score_at_selection?: number | null;
  verification_id?: string | null;
  reason_codes?: string[];
  warnings?: string[];
  explanation?: string | null;
  manual_override: boolean;
  manual_override_reason?: string | null;
  created_at: string;
  updated_at?: string | null;
  property_id?: string | null;
  listing_id?: string | null;
  property_agent_id?: string | null;
  property_name?: string | null;
  property_address?: string | null;
  building_name?: string | null;
  district?: string | null;
  property_type?: string | null;
  bedrooms?: number | null;
  bathrooms?: number | null;
  size_sqft?: number | null;
  furnishing?: string | null;
  asking_price?: number | null;
  currency?: string | null;
  available_from?: string | null;
  lease_min_months?: number | null;
  availability_status?: string | null;
  agent_name?: string | null;
  agent_agency?: string | null;
  verified_at?: string | null;
}

export interface PropertyShortlist {
  id: string;
  lead_id: string;
  matching_run_id?: string | null;
  version: number;
  status: string;
  config_version: string;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  items: PropertyShortlistItem[];
}

export interface DashboardSummaryCards {
  total_candidates: number;
  eligible: number;
  awaiting_agents: number;
  verified_available: number;
  conditional: number;
  unavailable: number;
  needs_review: number;
  shortlisted: number;
}

export interface DashboardFunnelStep {
  step_name: string;
  count: number;
}

export interface PropertyMatchingDashboardResponse {
  lead_id: string;
  tenant_name?: string | null;
  qualification_status: string;
  matching_status: string;
  last_matching_run_at?: string | null;
  current_shortlist_status?: string | null;
  current_shortlist_version?: number | null;
  current_shortlist_id?: string | null;
  module5_ready: boolean;
  summary: DashboardSummaryCards;
  funnel: DashboardFunnelStep[];
  shortlist?: PropertyShortlist | null;
  candidates: CandidateDetailItem[];
}

export interface Module5PropertyItem {
  property_match_id: string;
  property_id: string;
  listing_id?: string | null;
  property_agent_id?: string | null;
  shortlist_position: number;
  match_score?: number | null;
  availability: string;
  asking_price?: number | null;
  currency: string;
  available_from?: string | null;
  minimum_lease_months?: number | null;
  verification_id?: string | null;
  verified_at?: string | null;
}

export interface Module5HandoffPayload {
  lead_id: string;
  shortlist_id: string;
  shortlist_version: number;
  qualification_status: string;
  shortlist_status: string;
  handoff_status: string;
  generated_at: string;
  tenant_requirements: Record<string, any>;
  properties: Module5PropertyItem[];
}

// Module 5 Phase 1: Viewing Coordination Types
export type ViewingStatus =
  | 'DRAFT'
  | 'AWAITING_AGENT_AVAILABILITY'
  | 'AWAITING_TENANT_AVAILABILITY'
  | 'SLOTS_AVAILABLE'
  | 'SLOT_PROPOSED'
  | 'AWAITING_TENANT_CONFIRMATION'
  | 'AWAITING_AGENT_CONFIRMATION'
  | 'CONFIRMED'
  | 'RESCHEDULE_REQUESTED'
  | 'CANCELLED'
  | 'COMPLETED'
  | 'NO_SHOW'
  | 'REJECTED'
  | 'NEEDS_HUMAN_REVIEW';

export type ViewingConfirmationStatus = 'NOT_REQUIRED' | 'PENDING' | 'CONFIRMED' | 'DECLINED';
export type ViewingLocationType = 'IN_PERSON' | 'VIRTUAL' | 'OTHER';
export type ViewingSlotSource = 'PROPERTY_AGENT' | 'TENANT' | 'SYSTEM' | 'HUMAN_OPERATOR';
export type ViewingSlotStatus = 'PROPOSED' | 'AVAILABLE' | 'SELECTED' | 'REJECTED' | 'EXPIRED' | 'BOOKED' | 'CANCELLED';
export type ViewingEventType =
  | 'VIEWING_CREATED'
  | 'STATUS_CHANGED'
  | 'SLOT_CREATED'
  | 'SLOT_SELECTED'
  | 'SLOT_UPDATED'
  | 'TENANT_CONFIRMED'
  | 'TENANT_DECLINED'
  | 'AGENT_CONFIRMED'
  | 'AGENT_DECLINED'
  | 'RESCHEDULE_REQUESTED'
  | 'VIEWING_CANCELLED'
  | 'VIEWING_COMPLETED'
  | 'NO_SHOW_RECORDED'
  | 'HUMAN_REVIEW_REQUIRED'
  | 'METADATA_UPDATED';

export type ViewingActorType = 'SYSTEM' | 'AI' | 'OPERATOR' | 'TENANT' | 'PROPERTY_AGENT';

export interface ViewingSlot {
  id: string;
  viewing_id: string;
  source: ViewingSlotSource;
  start_at: string;
  end_at?: string | null;
  timezone: string;
  status: ViewingSlotStatus;
  source_message_id?: string | null;
  is_mutual_match?: boolean;
  created_at: string;
  updated_at: string;
}

export interface ViewingEvent {
  id: string;
  viewing_id: string;
  event_type: ViewingEventType;
  old_status?: string | null;
  new_status?: string | null;
  actor_type: ViewingActorType;
  actor_id?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

export interface ViewingPropertySummary {
  property_id: string;
  canonical_name?: string | null;
  building_name?: string | null;
  address?: string | null;
  district?: string | null;
  property_type?: string | null;
  bedrooms?: number | null;
}

export interface ViewingListingSummary {
  listing_id: string;
  asking_price?: number | null;
  currency: string;
  available_from?: string | null;
  lease_min_months?: number | null;
}

export interface ViewingAgentSummary {
  agent_id: string;
  full_name?: string | null;
  agency_name?: string | null;
  phone?: string | null;
}

export interface Viewing {
  id: string;
  lead_id: string;
  shortlist_id?: string | null;
  shortlist_item_id?: string | null;
  property_match_id: string;
  property_id: string;
  listing_id: string;
  property_agent_id: string;
  status: ViewingStatus;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  timezone: string;
  duration_minutes: number;
  location_type: ViewingLocationType;
  location_text?: string | null;
  meeting_url?: string | null;
  tenant_confirmation_status: ViewingConfirmationStatus;
  agent_confirmation_status: ViewingConfirmationStatus;
  schedule_version?: number;
  reschedule_count: number;
  previous_scheduled_start_at?: string | null;
  previous_scheduled_end_at?: string | null;
  reschedule_reason?: string | null;
  cancellation_reason?: string | null;
  cancelled_by?: string | null;
  cancelled_at?: string | null;
  completed_at?: string | null;
  outcome?: string | null;
  outcome_notes?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  property_summary?: ViewingPropertySummary | null;
  listing_summary?: ViewingListingSummary | null;
  agent_summary?: ViewingAgentSummary | null;
  lead_name?: string | null;
}

export interface ViewingDetail extends Viewing {
  slots: ViewingSlot[];
  events: ViewingEvent[];
}

export interface ViewingListResponse {
  total: number;
  items: Viewing[];
}

export interface ViewingCreatePayload {
  property_match_id?: string;
  duration_minutes?: number;
  timezone?: string;
  location_type?: ViewingLocationType;
  location_text?: string;
  meeting_url?: string;
  created_by?: string;
}

export interface ViewingUpdatePayload {
  duration_minutes?: number;
  timezone?: string;
  location_type?: ViewingLocationType;
  location_text?: string;
  meeting_url?: string;
  outcome_notes?: string;
}

export interface ViewingTransitionPayload {
  target_status: ViewingStatus;
  reason?: string;
  actor_type?: ViewingActorType;
  actor_id?: string;
}

export interface ViewingCancelPayload {
  reason?: string;
  reason_code?: string;
  cancelled_by?: string;
}

export interface ViewingCompletePayload {
  notes?: string;
}

export interface ViewingNoShowPayload {
  actor?: 'TENANT' | 'PROPERTY_AGENT';
  notes?: string;
}

export interface ViewingSlotCreatePayload {
  source?: ViewingSlotSource;
  start_at: string;
  end_at?: string;
  timezone?: string;
}

// Module 5 Phase 2: Property Presentation & Tenant Interest Types
export type PropertyInterestStatus =
  | 'NOT_PRESENTED'
  | 'PRESENTED'
  | 'INTERESTED'
  | 'NOT_INTERESTED'
  | 'WANTS_MORE_DETAILS'
  | 'VIEWING_REQUESTED'
  | 'OTHER_OPTIONS_REQUESTED'
  | 'UNSURE'
  | 'NEEDS_CLARIFICATION';

export type TenantInterestIntent =
  | 'INTERESTED'
  | 'NOT_INTERESTED'
  | 'REQUEST_VIEWING'
  | 'REQUEST_MORE_DETAILS'
  | 'REQUEST_NEXT_OPTION'
  | 'REQUEST_OTHER_OPTIONS'
  | 'COMPARE_PROPERTIES'
  | 'ASK_PROPERTY_QUESTION'
  | 'UNCLEAR'
  | 'UNRELATED';

export interface TenantSafePropertySummary {
  property_match_id: string;
  property_id: string;
  listing_id: string;
  name: string;
  building_name?: string | null;
  address?: string | null;
  district?: string | null;
  property_type: string;
  bedrooms?: number | null;
  furnishing?: string | null;
  asking_price?: number | null;
  currency: string;
  available_from?: string | null;
  lease_min_months?: number | null;
  source_url?: string | null;
  summary_text: string;
}

export interface PropertyInterest {
  id: string;
  lead_id: string;
  property_match_id: string;
  shortlist_id?: string | null;
  shortlist_item_id?: string | null;
  viewing_id?: string | null;
  status: PropertyInterestStatus;
  source_message_id?: string | null;
  presented_at?: string | null;
  responded_at?: string | null;
  presented_price?: number | null;
  presented_currency: string;
  presented_availability?: string | null;
  presentation_notes?: string | null;
  last_intent?: TenantInterestIntent | null;
  tenant_notes?: string | null;
  created_at: string;
  updated_at: string;
  property_summary?: TenantSafePropertySummary | null;
}

export interface PropertyInterestListResponse {
  total: number;
  items: PropertyInterest[];
}

export interface PropertyPresentationResult {
  success: boolean;
  lead_id: string;
  presented_count: number;
  items: PropertyInterest[];
  message_sent: boolean;
  message_id?: string | null;
  note?: string | null;
}

export interface TenantInterestProcessResult {
  intent: TenantInterestIntent;
  correlated_property_match_id?: string | null;
  confidence: number;
  needs_clarification: boolean;
  clarification_question?: string | null;
  viewing_created: boolean;
  viewing_id?: string | null;
  response_text?: string | null;
  property_interest?: PropertyInterest | null;
}

// Module 5 Phase 3: Agent Availability Collection Types
export type ViewingAvailabilityRequestStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'SENT'
  | 'DELIVERED'
  | 'READ'
  | 'REPLIED'
  | 'FAILED'
  | 'CANCELLED';

export type AgentAvailabilityResponseIntent =
  | 'PROVIDE_VIEWING_SLOTS'
  | 'PROVIDE_SINGLE_SLOT'
  | 'NO_VIEWING_AVAILABILITY'
  | 'REQUEST_TENANT_AVAILABILITY'
  | 'PROPOSE_ALTERNATIVE_DATE'
  | 'PROPERTY_NO_LONGER_AVAILABLE'
  | 'ASK_FOR_CONTEXT'
  | 'UNRELATED'
  | 'UNCLEAR';

export type ViewingCorrelationStatus =
  | 'RESOLVED'
  | 'AMBIGUOUS'
  | 'UNMATCHED'
  | 'MANUALLY_ASSIGNED';

export interface ViewingAvailabilityRequest {
  id: string;
  viewing_id: string;
  lead_id: string;
  property_match_id: string;
  listing_id: string;
  property_agent_id: string;
  conversation_id?: string | null;
  status: ViewingAvailabilityRequestStatus;
  provider_message_id?: string | null;
  idempotency_key: string;
  outbound_message_text?: string | null;
  raw_response_text?: string | null;
  response_intent?: AgentAvailabilityResponseIntent | null;
  correlation_status: ViewingCorrelationStatus;
  agent_notes?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  replied_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ViewingAgentAvailabilityStatus {
  viewing_id: string;
  viewing_status: string;
  latest_request?: ViewingAvailabilityRequest | null;
  property_agent: {
    id: string;
    full_name: string;
    agency_name?: string | null;
    phone?: string | null;
  };
  current_slots: ViewingSlot[];
  agent_notes?: string | null;
  correlation_status?: string | null;
  needs_human_review: boolean;
}

// Module 5 Phase 4: Tenant Availability & Slot Matching Types
export type TenantAvailabilityResponseIntent =
  | 'SELECT_SLOT'
  | 'PROVIDE_AVAILABILITY'
  | 'REQUEST_OTHER_SLOT'
  | 'NONE_OF_THESE_WORK'
  | 'ASK_VIEWING_QUESTION'
  | 'CANCEL_VIEWING_REQUEST'
  | 'UNCLEAR'
  | 'UNRELATED';

export type SlotMatchType =
  | 'EXACT'
  | 'OVERLAP'
  | 'TENANT_SELECTED'
  | 'MANUAL_OPERATOR';

export interface TenantAvailabilityWindowItem {
  start_at: string;
  end_at: string;
  timezone: string;
  confidence?: number;
}

export interface MutualSlotMatchItem {
  start_at: string;
  end_at: string;
  timezone: string;
  match_type: SlotMatchType;
  agent_slot_id?: string | null;
  tenant_slot_id?: string | null;
  reason: string;
  is_proposed: boolean;
}

export interface ViewingSlotMatchingResult {
  viewing_id: string;
  total_mutual_slots: number;
  mutual_slots: MutualSlotMatchItem[];
  agent_slots_count: number;
  tenant_windows_count: number;
  status: string;
  recommended_slot?: MutualSlotMatchItem | null;
}

export interface ViewingTenantAvailabilityStatus {
  viewing_id: string;
  viewing_status: string;
  agent_slots: ViewingSlot[];
  tenant_slots: ViewingSlot[];
  mutual_slots: MutualSlotMatchItem[];
  current_proposed_slot?: ViewingSlot | null;
  needs_human_review: boolean;
}

export interface TenantViewingAvailabilityRequestResult {
  viewing_id: string;
  lead_id: string;
  strategy: string;
  message_sent: boolean;
  provider_message_id?: string | null;
  offered_slots: ViewingSlot[];
  sent_at?: string | null;
}

// Module 5 Phase 5: Viewing Confirmation & Booking Types
export type TenantConfirmationIntent =
  | 'CONFIRM_VIEWING'
  | 'DECLINE_VIEWING'
  | 'REQUEST_DIFFERENT_TIME'
  | 'CANCEL_VIEWING'
  | 'ASK_VIEWING_QUESTION'
  | 'UNCLEAR'
  | 'UNRELATED';

export type AgentConfirmationIntent =
  | 'CONFIRM_VIEWING'
  | 'DECLINE_VIEWING'
  | 'SLOT_NO_LONGER_AVAILABLE'
  | 'REQUEST_DIFFERENT_TIME'
  | 'PROPERTY_NO_LONGER_AVAILABLE'
  | 'UNCLEAR'
  | 'UNRELATED';

export type ConfirmationParty = 'TENANT' | 'PROPERTY_AGENT';

export interface ViewingConfirmationRequestResult {
  viewing_id: string;
  party: ConfirmationParty;
  status: ViewingConfirmationStatus;
  message_sent: boolean;
  provider_message_id?: string | null;
  sent_at?: string | null;
  proposed_start_at?: string | null;
  proposed_end_at?: string | null;
}

export interface ViewingConfirmationStatusOverview {
  viewing_id: string;
  booking_reference: string;
  viewing_status: string;
  tenant_confirmation_status: ViewingConfirmationStatus;
  agent_confirmation_status: ViewingConfirmationStatus;
  proposed_slot?: ViewingSlot | null;
  booked_slot?: ViewingSlot | null;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  timezone: string;
  location_type: string;
  location_text?: string | null;
  meeting_url?: string | null;
  policy_summary: Record<string, any>;
  can_finalize: boolean;
  is_confirmed: boolean;
}

export interface ViewingFinalizeBookingResult {
  viewing_id: string;
  booking_reference: string;
  status: string;
  booked_slot_id: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  timezone: string;
  location_text?: string | null;
  meeting_url?: string | null;
  tenant_notified: boolean;
  agent_notified: boolean;
  confirmed_at: string;
}

// ==========================================
// Module 5 — Phase 6: Viewing Reminders & Reschedule & Cancellation
// ==========================================

export type ViewingReminderParty = 'TENANT' | 'PROPERTY_AGENT' | 'OPERATOR';
export type ViewingReminderType = 'UPCOMING_VIEWING' | 'FINAL_REMINDER' | 'CUSTOM';
export type ViewingReminderStatus = 'PENDING' | 'QUEUED' | 'SENT' | 'FAILED' | 'CANCELLED' | 'SKIPPED';

export interface ViewingReminder {
  id: string;
  viewing_id: string;
  party: ViewingReminderParty;
  reminder_type: ViewingReminderType;
  offset_minutes?: number | null;
  booking_version: number;
  scheduled_for: string;
  timezone: string;
  status: ViewingReminderStatus;
  message_id?: string | null;
  provider_message_id?: string | null;
  attempt_count: number;
  max_attempts: number;
  idempotency_key: string;
  sent_at?: string | null;
  cancelled_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ViewingScheduleHistory {
  id: string;
  viewing_id: string;
  version: number;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  slot_id?: string | null;
  changed_by: string;
  reason?: string | null;
  created_at: string;
}
















