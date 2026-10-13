"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  MapPin,
  Home,
  Layers,
  Plus,
  RefreshCw,
  Archive,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ExternalLink,
  User,
  Calendar,
  DollarSign,
  FileText,
  X,
  History,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  PropertyDetail,
  PropertyListing,
  PropertySource,
  PropertyAgent,
  PropertyListingCreateInput,
  ListingAvailabilityStatus,
  AuditLog,
} from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<PropertyDetail | null>(null);
  const [sources, setSources] = useState<PropertySource[]>([]);
  const [agents, setAgents] = useState<PropertyAgent[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"listings" | "audit">("listings");

  // Add Listing Modal state
  const [isListingModalOpen, setIsListingModalOpen] = useState(false);
  const [submittingListing, setSubmittingListing] = useState(false);
  const [listingForm, setListingForm] = useState<PropertyListingCreateInput>({
    source_id: "",
    agent_id: null,
    source_listing_id: "",
    source_url: "",
    asking_price: 3500,
    currency: "SGD",
    availability_status: "UNKNOWN",
    available_from: "",
    lease_min_months: 12,
    lease_max_months: null,
    listing_status: "ACTIVE",
  });

  const fetchPropertyData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [propData, sourcesData, agentsData, logsData] = await Promise.all([
        api.getProperty(propertyId),
        api.listPropertySources({ status: "ACTIVE" }),
        api.listPropertyAgents({ status: "ACTIVE" }),
        api.listAuditLogs({ entity_id: propertyId }),
      ]);
      setProperty(propData);
      setSources(sourcesData);
      setAgents(agentsData);
      setAuditLogs(logsData);
      if (sourcesData.length > 0 && !listingForm.source_id) {
        setListingForm((prev) => ({ ...prev, source_id: sourcesData[0].id }));
      }
    } catch (err: any) {
      setError(err.message || "Failed to load property details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (propertyId) {
      fetchPropertyData();
    }
  }, [propertyId]);

  const handleCreateListing = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmittingListing(true);
      await api.createPropertyListing(propertyId, {
        ...listingForm,
        agent_id: listingForm.agent_id || null,
        source_listing_id: listingForm.source_listing_id || null,
        source_url: listingForm.source_url || null,
        available_from: listingForm.available_from || null,
      });
      setIsListingModalOpen(false);
      // Reset form
      setListingForm({
        source_id: sources[0]?.id || "",
        agent_id: null,
        source_listing_id: "",
        source_url: "",
        asking_price: 3500,
        currency: "SGD",
        availability_status: "UNKNOWN",
        available_from: "",
        lease_min_months: 12,
        lease_max_months: null,
        listing_status: "ACTIVE",
      });
      fetchPropertyData();
    } catch (err: any) {
      setError(err.message || "Failed to add listing.");
    } finally {
      setSubmittingListing(false);
    }
  };

  const handleArchiveProperty = async () => {
    if (!confirm("Are you sure you want to archive this property?")) return;
    try {
      await api.archiveProperty(propertyId);
      fetchPropertyData();
    } catch (err: any) {
      setError(err.message || "Failed to archive property.");
    }
  };

  const handleArchiveListing = async (listingId: string) => {
    if (!confirm("Are you sure you want to archive this listing?")) return;
    try {
      await api.archivePropertyListing(listingId);
      fetchPropertyData();
    } catch (err: any) {
      setError(err.message || "Failed to archive listing.");
    }
  };

  const getAvailabilityBadge = (status: ListingAvailabilityStatus) => {
    switch (status) {
      case "AVAILABLE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Available
          </span>
        );
      case "UNAVAILABLE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            <X className="w-3 h-3 text-rose-600" />
            Unavailable
          </span>
        );
      case "AWAITING_VERIFICATION":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            Awaiting Verification
          </span>
        );
      case "CONDITIONAL":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-200">
            Conditional
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {status}
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex items-center justify-center">
        <div className="text-center text-slate-500 space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-sky-600 mx-auto" />
          <p className="text-sm">Loading property details...</p>
        </div>
      </div>
    );
  }

  if (!property) {
    return (
      <div className="min-h-screen bg-slate-50/50 p-8 text-center text-rose-600">
        Property not found.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <PageHeader
            title={property.canonical_name || "Canonical Property Profile"}
            description={`${property.building_name || ""} • ${property.district || property.city || "Singapore"}`}
            breadcrumbs={[
              { label: "Properties", href: "/properties" },
              { label: property.canonical_name || "Detail", href: `/properties/${property.id}` },
            ]}
          />
          <div className="flex items-center gap-2.5">
            {property.status !== "ARCHIVED" && (
              <button
                onClick={handleArchiveProperty}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-colors"
              >
                <Archive className="w-3.5 h-3.5" />
                Archive Property
              </button>
            )}
            <button
              onClick={() => setIsListingModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg text-white bg-sky-600 hover:bg-sky-700 shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              Attach New Listing
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2 shadow-2xs">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Canonical Property Attributes Card */}
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-sky-50 border border-sky-100 flex items-center justify-center text-sky-600 font-bold">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  {property.canonical_name}
                </h2>
                <div className="text-xs text-slate-500">
                  Physical Property ID: <span className="font-mono text-2xs">{property.id}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded text-xs font-bold uppercase bg-slate-100 text-slate-800">
                {property.property_type}
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  property.status === "ACTIVE"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {property.status}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Address</div>
              <div className="font-medium text-slate-900 mt-1">
                {property.address_line_1 || "—"}
                {property.unit_number ? ` ${property.unit_number}` : ""}
              </div>
              <div className="text-xs text-slate-500">
                {property.city || "Singapore"} {property.postal_code ? `(${property.postal_code})` : ""}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">District / Zone</div>
              <div className="font-medium text-slate-900 mt-1">
                {property.district || "Unassigned"}
              </div>
              <div className="text-xs text-slate-500">{property.country}</div>
            </div>

            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Bedrooms & Bath</div>
              <div className="font-medium text-slate-900 mt-1">
                {property.bedrooms !== null ? `${property.bedrooms} Beds` : "Studio/Room"}
                {property.bathrooms !== null ? ` • ${property.bathrooms} Baths` : ""}
              </div>
              <div className="text-xs text-slate-500">
                {property.size_sqft ? `${property.size_sqft} sqft` : "Size unrecorded"}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Furnishing & Coords</div>
              <div className="font-medium text-slate-900 mt-1">
                {property.furnishing?.replace(/_/g, " ") || "UNKNOWN"}
              </div>
              <div className="text-xs text-slate-500 font-mono text-2xs">
                {property.latitude && property.longitude
                  ? `${property.latitude}, ${property.longitude}`
                  : "No GPS coordinates"}
              </div>
            </div>
          </div>
        </div>

        {/* Tabs: Listings vs Audit Logs */}
        <div className="flex border-b border-slate-200 gap-6 text-sm font-semibold">
          <button
            onClick={() => setActiveTab("listings")}
            className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "listings"
                ? "border-sky-600 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Layers className="w-4 h-4" />
            Attached Listings ({property.listings?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "audit"
                ? "border-sky-600 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <History className="w-4 h-4" />
            Audit Activity ({auditLogs.length})
          </button>
        </div>

        {/* Tab 1: Listings Section */}
        {activeTab === "listings" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Active Market Listings</h3>
                <p className="text-xs text-slate-500">
                  Multiple agents or portals advertising this canonical physical property.
                </p>
              </div>
            </div>

            {property.listings?.length === 0 ? (
              <div className="bg-white p-8 rounded-xl border border-slate-200 text-center space-y-3">
                <Layers className="w-8 h-8 text-slate-300 mx-auto" />
                <div className="text-sm font-semibold text-slate-700">No listings attached yet</div>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Attach an advertisement listing record from an agency portal, agent, or CSV feed to this property.
                </p>
                <button
                  onClick={() => setIsListingModalOpen(true)}
                  className="px-4 py-2 text-xs font-semibold text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors"
                >
                  Attach First Listing
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {property.listings?.map((listing) => (
                  <div
                    key={listing.id}
                    className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-5 space-y-4 hover:border-slate-300 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                            {listing.source_name || "Direct Source"}
                          </span>
                          {listing.source_listing_id && (
                            <span className="text-2xs font-mono text-slate-400">
                              Ref: {listing.source_listing_id}
                            </span>
                          )}
                        </div>
                        <div className="text-lg font-bold text-slate-900 mt-2 flex items-baseline gap-1">
                          <span>{listing.currency}</span>
                          <span>{listing.asking_price ? Number(listing.asking_price).toLocaleString() : "TBD"}</span>
                          <span className="text-xs font-normal text-slate-500">/ month</span>
                        </div>
                      </div>
                      <div>{getAvailabilityBadge(listing.availability_status)}</div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs border-t border-b border-slate-100 py-3">
                      <div>
                        <span className="text-slate-400 block font-medium">Listing Agent</span>
                        <span className="font-semibold text-slate-800">
                          {listing.agent_name || "No agent linked"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-medium">Available From</span>
                        <span className="font-semibold text-slate-800">
                          {listing.available_from || "Immediate / TBD"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-medium">Lease Term</span>
                        <span className="font-semibold text-slate-800">
                          Min {listing.lease_min_months || 12} mos
                          {listing.lease_max_months ? ` (Max ${listing.lease_max_months} mos)` : ""}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-medium">Status</span>
                        <span className="font-semibold text-slate-800">{listing.listing_status}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs pt-1">
                      {listing.source_url ? (
                        <a
                          href={listing.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-sky-600 hover:text-sky-800 font-medium"
                        >
                          Source URL <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-slate-400">No portal URL</span>
                      )}

                      {listing.listing_status !== "ARCHIVED" && (
                        <button
                          onClick={() => handleArchiveListing(listing.id)}
                          className="text-rose-600 hover:text-rose-800 font-medium text-2xs"
                        >
                          Archive Listing
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Audit Logs Section */}
        {activeTab === "audit" && (
          <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
            {auditLogs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No audit activity recorded for this property yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {auditLogs.map((log) => (
                  <div key={log.id} className="p-4 flex items-start justify-between text-xs hover:bg-slate-50/50">
                    <div>
                      <div className="font-bold text-slate-900">{log.action}</div>
                      <div className="text-slate-500 mt-0.5">
                        Actor: <span className="font-mono text-slate-700">{log.actor_id}</span>
                      </div>
                      {log.new_value && (
                        <div className="mt-1 font-mono text-2xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100">
                          {JSON.stringify(log.new_value)}
                        </div>
                      )}
                    </div>
                    <div className="text-slate-400 whitespace-nowrap ml-4">
                      {new Date(log.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal: Attach New Listing */}
        {isListingModalOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-slate-900">
                  Attach Listing to Property
                </h3>
                <button
                  onClick={() => setIsListingModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateListing} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Property Source <span className="text-rose-500">*</span>
                  </label>
                  <select
                    required
                    value={listingForm.source_id}
                    onChange={(e) => setListingForm({ ...listingForm, source_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  >
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.source_type})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Listing Agent (Optional)
                  </label>
                  <select
                    value={listingForm.agent_id || ""}
                    onChange={(e) => setListingForm({ ...listingForm, agent_id: e.target.value || null })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  >
                    <option value="">No external agent assigned</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.full_name} ({a.agency_name || "Independent"})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Asking Price <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="number"
                      required
                      min="0"
                      value={listingForm.asking_price ?? ""}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          asking_price: e.target.value === "" ? null : parseFloat(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Currency</label>
                    <input
                      type="text"
                      value={listingForm.currency}
                      onChange={(e) => setListingForm({ ...listingForm, currency: e.target.value.toUpperCase() })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Availability Status</label>
                    <select
                      value={listingForm.availability_status}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          availability_status: e.target.value as ListingAvailabilityStatus,
                        })
                      }
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    >
                      <option value="UNKNOWN">UNKNOWN</option>
                      <option value="NOT_CHECKED">NOT_CHECKED</option>
                      <option value="AWAITING_VERIFICATION">AWAITING_VERIFICATION</option>
                      <option value="AVAILABLE">AVAILABLE</option>
                      <option value="UNAVAILABLE">UNAVAILABLE</option>
                      <option value="CONDITIONAL">CONDITIONAL</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Available From</label>
                    <input
                      type="date"
                      value={listingForm.available_from || ""}
                      onChange={(e) => setListingForm({ ...listingForm, available_from: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Source Listing ID</label>
                    <input
                      type="text"
                      value={listingForm.source_listing_id || ""}
                      onChange={(e) => setListingForm({ ...listingForm, source_listing_id: e.target.value })}
                      placeholder="e.g. PORTAL-889"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Min Lease (Months)</label>
                    <input
                      type="number"
                      min="1"
                      value={listingForm.lease_min_months ?? ""}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          lease_min_months: e.target.value === "" ? null : parseInt(e.target.value, 10),
                        })
                      }
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Source URL</label>
                  <input
                    type="url"
                    value={listingForm.source_url || ""}
                    onChange={(e) => setListingForm({ ...listingForm, source_url: e.target.value })}
                    placeholder="https://..."
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setIsListingModalOpen(false)}
                    className="px-4 py-2 font-semibold text-slate-600 hover:bg-slate-50 rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingListing}
                    className="px-4 py-2 font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg disabled:opacity-50"
                  >
                    {submittingListing ? "Attaching..." : "Save Listing"}
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
