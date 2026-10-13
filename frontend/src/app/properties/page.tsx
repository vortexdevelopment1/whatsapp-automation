"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Plus,
  Search,
  Filter,
  RefreshCw,
  Home,
  Tag,
  Bed,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Archive,
  ChevronRight,
  Database,
} from "lucide-react";
import { api } from "@/lib/api";
import { Property, PropertyType, PropertyStatus } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";

export default function PropertiesPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [selectedBedrooms, setSelectedBedrooms] = useState<string>("");
  const [seeding, setSeeding] = useState(false);
  const [seedSuccess, setSeedSuccess] = useState<string | null>(null);

  const fetchProperties = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listProperties({
        search: search || undefined,
        property_type: selectedType || undefined,
        status: selectedStatus || undefined,
        bedrooms: selectedBedrooms ? parseInt(selectedBedrooms, 10) : undefined,
      });
      setProperties(data);
    } catch (err: any) {
      setError(err.message || "Failed to load properties.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, [selectedType, selectedStatus, selectedBedrooms]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProperties();
  };

  const handleSeedDemoData = async () => {
    try {
      setSeeding(true);
      setSeedSuccess(null);
      const res = await api.seedDemoInventory();
      setSeedSuccess(
        `Demo data loaded: ${res.seeded.properties_count} properties, ${res.seeded.listings_count} listings across ${res.seeded.sources_count} sources.`
      );
      fetchProperties();
    } catch (err: any) {
      setError(err.message || "Failed to seed demo data.");
    } finally {
      setSeeding(false);
    }
  };

  const getStatusBadge = (status: PropertyStatus) => {
    switch (status) {
      case "ACTIVE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Active
          </span>
        );
      case "INACTIVE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <Clock className="w-3 h-3 text-slate-500" />
            Inactive
          </span>
        );
      case "ARCHIVED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <Archive className="w-3 h-3 text-rose-500" />
            Archived
          </span>
        );
      case "NEEDS_REVIEW":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-500" />
            Needs Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  const getTypeBadge = (type: PropertyType) => {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-100">
        {type}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <PageHeader
            title="Property Inventory"
            description="Manage canonical physical properties and review attached multi-source listings"
            breadcrumbs={[{ label: "Properties", href: "/properties" }]}
          />
          <div className="flex items-center gap-2.5 self-start sm:self-auto">
            <button
              onClick={handleSeedDemoData}
              disabled={seeding}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 shadow-2xs transition-colors disabled:opacity-50"
              title="Seed synthetic Singapore demo properties and listings"
            >
              <Database className="w-4 h-4 text-sky-600" />
              {seeding ? "Seeding..." : "Load Demo Inventory"}
            </button>
            <Link
              href="/properties/new"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg text-white bg-sky-600 hover:bg-sky-700 shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Property
            </Link>
          </div>
        </div>

        {/* Notifications */}
        {seedSuccess && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between shadow-2xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <span>{seedSuccess}</span>
            </div>
            <button
              onClick={() => setSeedSuccess(null)}
              className="text-emerald-700 hover:text-emerald-900 text-xs font-semibold ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2 shadow-2xs">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Search & Filters */}
        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
          <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by canonical name, building, address, district, or postal code..."
                className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
            >
              Search
            </button>
          </form>

          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100 text-xs text-slate-600">
            <div className="flex items-center gap-1.5 font-medium text-slate-700">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              Filters:
            </div>

            {/* Property Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-1 focus:ring-sky-500"
            >
              <option value="">All Types</option>
              <option value="CONDO">Condo</option>
              <option value="APARTMENT">Apartment</option>
              <option value="HDB">HDB</option>
              <option value="LANDED">Landed</option>
              <option value="STUDIO">Studio</option>
              <option value="COMMERCIAL">Commercial</option>
            </select>

            {/* Bedrooms Filter */}
            <select
              value={selectedBedrooms}
              onChange={(e) => setSelectedBedrooms(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-1 focus:ring-sky-500"
            >
              <option value="">Any Bedrooms</option>
              <option value="0">Studio / 0 Bed</option>
              <option value="1">1 Bedroom</option>
              <option value="2">2 Bedrooms</option>
              <option value="3">3 Bedrooms</option>
              <option value="4">4+ Bedrooms</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-1 focus:ring-sky-500"
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="ARCHIVED">Archived</option>
            </select>

            {(search || selectedType || selectedStatus || selectedBedrooms) && (
              <button
                onClick={() => {
                  setSearch("");
                  setSelectedType("");
                  setSelectedStatus("");
                  setSelectedBedrooms("");
                }}
                className="text-sky-600 hover:text-sky-800 font-medium ml-auto"
              >
                Clear all filters
              </button>
            )}
          </div>
        </div>

        {/* Properties List / Table */}
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-slate-500 space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-sky-600 mx-auto" />
              <p className="text-sm">Loading properties inventory...</p>
            </div>
          ) : properties.length === 0 ? (
            <div className="p-12 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                <Building2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900">No properties found</h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Try adjusting your search filters, create a new property manually, or click "Load Demo Inventory".
                </p>
              </div>
              <div className="flex justify-center gap-3 pt-2">
                <button
                  onClick={handleSeedDemoData}
                  className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                >
                  Load Demo Data
                </button>
                <Link
                  href="/properties/new"
                  className="px-3 py-1.5 text-xs font-semibold text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors"
                >
                  Add Property
                </Link>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th scope="col" className="px-6 py-3.5">
                      Property
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Type & Layout
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      District / Area
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Furnishing
                    </th>
                    <th scope="col" className="px-6 py-3.5 text-center">
                      Listings
                    </th>
                    <th scope="col" className="px-6 py-3.5">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3.5 text-right">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {properties.map((prop) => (
                    <tr
                      key={prop.id}
                      className="hover:bg-slate-50/80 transition-colors group cursor-pointer"
                      onClick={() => (window.location.href = `/properties/${prop.id}`)}
                    >
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 group-hover:text-sky-600 transition-colors">
                          {prop.canonical_name || "Unnamed Unit"}
                        </div>
                        <div className="text-xs text-slate-500 truncate max-w-xs">
                          {prop.building_name ? `${prop.building_name} • ` : ""}
                          {prop.address_line_1 || "Address pending"}
                          {prop.unit_number ? ` ${prop.unit_number}` : ""}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {getTypeBadge(prop.property_type)}
                          <span className="text-xs text-slate-600">
                            {prop.bedrooms !== null ? `${prop.bedrooms} Bed` : "—"}
                            {prop.bathrooms !== null ? ` • ${prop.bathrooms} Bath` : ""}
                          </span>
                        </div>
                        {prop.size_sqft && (
                          <div className="text-xs text-slate-400 mt-0.5">{prop.size_sqft} sqft</div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-xs text-slate-800 font-medium">
                          {prop.district || prop.city || "Singapore"}
                        </div>
                        {prop.postal_code && (
                          <div className="text-xs text-slate-400">Postal {prop.postal_code}</div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600">
                        {prop.furnishing?.replace(/_/g, " ") || "UNKNOWN"}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span
                          className={`inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                            prop.listings_count > 0
                              ? "bg-sky-100 text-sky-800 border border-sky-200"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          {prop.listings_count} {prop.listings_count === 1 ? "listing" : "listings"}
                        </span>
                      </td>
                      <td className="px-6 py-4">{getStatusBadge(prop.status)}</td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/properties/${prop.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-800"
                        >
                          View Details
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
