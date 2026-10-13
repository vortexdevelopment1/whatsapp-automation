"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  ArrowLeft,
  Check,
  AlertCircle,
  MapPin,
  Home,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { PropertyCreateInput, PropertyType, PropertyStatus } from "@/types";

export default function NewPropertyPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<PropertyCreateInput>({
    canonical_name: "",
    building_name: "",
    address_line_1: "",
    address_line_2: "",
    unit_number: "",
    postal_code: "",
    district: "",
    city: "Singapore",
    state_region: "",
    country: "Singapore",
    latitude: null,
    longitude: null,
    property_type: "CONDO",
    bedrooms: 2,
    bathrooms: 2,
    size_sqft: null,
    furnishing: "FURNISHED",
    status: "ACTIVE",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    if (type === "number") {
      setForm((prev) => ({
        ...prev,
        [name]: value === "" ? null : parseFloat(value),
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        [name]: value,
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      const res = await api.createProperty(form);
      router.push(`/properties/${res.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create property.");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">
        <PageHeader
          title="Add Canonical Property"
          description="Register a new physical real estate asset into canonical inventory"
          breadcrumbs={[
            { label: "Properties", href: "/properties" },
            { label: "New Property", href: "/properties/new" },
          ]}
        />

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2 shadow-2xs">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Section 1: Physical Identity & Address */}
          <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-2xs space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 border-b border-slate-100 pb-3">
              <MapPin className="w-4 h-4 text-sky-600" />
              <span>Address & Physical Location</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Canonical Display Name
                </label>
                <input
                  type="text"
                  name="canonical_name"
                  value={form.canonical_name || ""}
                  onChange={handleChange}
                  placeholder="e.g. Novena Regency #08-04"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
                <p className="text-2xs text-slate-400 mt-1">
                  If empty, will auto-construct from building name and unit number.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Building / Condo Name
                </label>
                <input
                  type="text"
                  name="building_name"
                  value={form.building_name || ""}
                  onChange={handleChange}
                  placeholder="e.g. Novena Regency"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Unit Number
                </label>
                <input
                  type="text"
                  name="unit_number"
                  value={form.unit_number || ""}
                  onChange={handleChange}
                  placeholder="e.g. #08-04"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Street Address (Line 1)
                </label>
                <input
                  type="text"
                  name="address_line_1"
                  value={form.address_line_1 || ""}
                  onChange={handleChange}
                  placeholder="e.g. 275 Thomson Road"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Postal Code
                </label>
                <input
                  type="text"
                  name="postal_code"
                  value={form.postal_code || ""}
                  onChange={handleChange}
                  placeholder="e.g. 307645"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  District / Zone
                </label>
                <input
                  type="text"
                  name="district"
                  value={form.district || ""}
                  onChange={handleChange}
                  placeholder="e.g. D11 - Novena / Newton"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  City
                </label>
                <input
                  type="text"
                  name="city"
                  value={form.city || ""}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Country <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="country"
                  required
                  value={form.country || "Singapore"}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Latitude
                </label>
                <input
                  type="number"
                  step="0.0000001"
                  name="latitude"
                  value={form.latitude ?? ""}
                  onChange={handleChange}
                  placeholder="e.g. 1.3175"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Longitude
                </label>
                <input
                  type="number"
                  step="0.0000001"
                  name="longitude"
                  value={form.longitude ?? ""}
                  onChange={handleChange}
                  placeholder="e.g. 103.8436"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Property Characteristics */}
          <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-2xs space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 border-b border-slate-100 pb-3">
              <Home className="w-4 h-4 text-sky-600" />
              <span>Property Characteristics</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Property Type <span className="text-rose-500">*</span>
                </label>
                <select
                  name="property_type"
                  value={form.property_type}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                >
                  <option value="CONDO">Condominium</option>
                  <option value="APARTMENT">Apartment</option>
                  <option value="HDB">HDB Flat</option>
                  <option value="LANDED">Landed House</option>
                  <option value="STUDIO">Studio</option>
                  <option value="ROOM">Room Rental</option>
                  <option value="COMMERCIAL">Commercial</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Bedrooms
                </label>
                <input
                  type="number"
                  min="0"
                  name="bedrooms"
                  value={form.bedrooms ?? ""}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Bathrooms
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  name="bathrooms"
                  value={form.bathrooms ?? ""}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Floor Size (sqft)
                </label>
                <input
                  type="number"
                  min="0"
                  name="size_sqft"
                  value={form.size_sqft ?? ""}
                  onChange={handleChange}
                  placeholder="e.g. 850"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Furnishing
                </label>
                <select
                  name="furnishing"
                  value={form.furnishing || "UNKNOWN"}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                >
                  <option value="FURNISHED">Fully Furnished</option>
                  <option value="PARTIALLY_FURNISHED">Partially Furnished</option>
                  <option value="UNFURNISHED">Unfurnished</option>
                  <option value="FLEXIBLE">Flexible</option>
                  <option value="UNKNOWN">Unknown</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Status
                </label>
                <select
                  name="status"
                  value={form.status}
                  onChange={handleChange}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-200 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                >
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                  <option value="NEEDS_REVIEW">Needs Review</option>
                </select>
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex items-center justify-end gap-3 pt-4">
            <Link
              href="/properties"
              className="px-4 py-2 text-sm font-semibold rounded-lg text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold rounded-lg text-white bg-sky-600 hover:bg-sky-700 shadow-xs transition-colors disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              {submitting ? "Saving Property..." : "Save Property"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
