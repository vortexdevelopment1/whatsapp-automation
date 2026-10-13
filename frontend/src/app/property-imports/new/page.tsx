"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  UploadCloud,
  ArrowLeft,
  FileText,
  AlertCircle,
  CheckCircle2,
  Download,
  Info,
  Layers,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { PropertySource } from "@/types";

export default function NewPropertyImportPage() {
  const router = useRouter();
  const [sources, setSources] = useState<PropertySource[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSources() {
      try {
        const data = await api.listPropertySources();
        setSources(data);
        if (data.length > 0) {
          const activeSource = data.find((s) => s.status === "ACTIVE") || data[0];
          setSelectedSourceId(activeSource.id);
        }
      } catch (err: any) {
        setError(err?.message || "Failed to load sources.");
      }
    }
    loadSources();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.endsWith(".csv")) {
        setError("Only CSV files are allowed.");
        setFile(null);
        return;
      }
      if (selected.size > 10 * 1024 * 1024) {
        setError("File size exceeds 10MB limit.");
        setFile(null);
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSourceId) {
      setError("Please select an approved property source.");
      return;
    }
    if (!file) {
      setError("Please select a valid CSV file to upload.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const batch = await api.uploadPropertyImportCSV(selectedSourceId, file);
      router.push(`/property-imports/${batch.id}`);
    } catch (err: any) {
      setError(err?.message || "Upload failed. Please check file format.");
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadSample = () => {
    const headers = [
      "source_listing_id",
      "source_url",
      "property_name",
      "building_name",
      "address_line_1",
      "address_line_2",
      "postal_code",
      "city",
      "state_region",
      "country",
      "property_type",
      "bedrooms",
      "bathrooms",
      "size_sqft",
      "furnishing",
      "asking_price",
      "currency",
      "available_from",
      "lease_min_months",
      "lease_max_months",
      "availability_status",
      "listing_status",
      "agent_name",
      "agent_agency",
      "agent_registration_number",
      "agent_phone",
      "agent_email",
      "source_last_updated_at",
    ];

    const sampleRow = [
      "EXT-001",
      "https://example.com/listings/001",
      "Marina Bay Suites 2BR",
      "Marina Bay Suites",
      "3 Central Boulevard",
      "#15-02",
      "018965",
      "Singapore",
      "Singapore",
      "Singapore",
      "Condominium",
      "2",
      "2",
      "1050",
      "Fully Furnished",
      "6500",
      "SGD",
      "2026-11-01",
      "12",
      "24",
      "available",
      "ACTIVE",
      "Alice Tan",
      "PropNex Realty",
      "R012345A",
      "+65 9123 4567",
      "alice.tan@propnex.com.sg",
      "2026-10-01T08:00:00Z",
    ];

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), sampleRow.join(",")].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "property_import_sample_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back button */}
      <div>
        <Link
          href="/property-imports"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Import Batches
        </Link>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200/80 bg-slate-50/50 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <UploadCloud className="w-5 h-5 text-sky-600" />
              Upload Property CSV
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Ingest batch listings. Original source data will be preserved and normalized.
            </p>
          </div>
          <button
            type="button"
            onClick={handleDownloadSample}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <Download className="w-3.5 h-3.5" />
            Template CSV
          </button>
        </div>

        {error && (
          <div className="p-4 bg-rose-50 border-b border-rose-200 text-rose-700 text-sm flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600" />
            <div>
              <p className="font-semibold text-xs uppercase tracking-wide">Import Error</p>
              <p className="text-xs mt-0.5">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Source Selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Approved Property Source <span className="text-rose-500">*</span>
            </label>
            <select
              value={selectedSourceId}
              onChange={(e) => setSelectedSourceId(e.target.value)}
              className="w-full text-sm rounded-lg border-slate-300 shadow-2xs focus:border-sky-500 focus:ring-sky-500"
              required
            >
              <option value="" disabled>
                Select an approved source...
              </option>
              {sources.map((src) => (
                <option key={src.id} value={src.id}>
                  {src.name} ({src.source_type} — {src.status})
                </option>
              ))}
            </select>
            <p className="text-2xs text-slate-500 mt-1.5 flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              All rows imported will preserve provenance linking back to this approved source.
            </p>
          </div>

          {/* File Upload Box */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              CSV File <span className="text-rose-500">*</span>
            </label>
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-sky-400 transition-colors bg-slate-50/50">
              <FileText className="w-10 h-10 mx-auto mb-3 text-slate-400" />
              {file ? (
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-slate-900 flex items-center justify-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    {file.name}
                  </p>
                  <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-xs text-rose-600 hover:underline pt-2 block mx-auto"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <>
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <span className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-sky-700 bg-sky-50 border border-sky-200 rounded-lg hover:bg-sky-100 transition-colors">
                      Choose CSV File
                    </span>
                    <input
                      id="file-upload"
                      name="file-upload"
                      type="file"
                      accept=".csv"
                      className="sr-only"
                      onChange={handleFileChange}
                    />
                  </label>
                  <p className="text-2xs text-slate-500 mt-2">UTF-8 or Latin-1 encoded CSV files up to 10MB.</p>
                </>
              )}
            </div>
          </div>

          {/* Guidelines Banner */}
          <div className="bg-sky-50/70 border border-sky-200/80 rounded-lg p-4 text-xs text-sky-900 space-y-2">
            <div className="font-semibold flex items-center gap-1.5 text-sky-950">
              <Info className="w-4 h-4 text-sky-700 shrink-0" />
              Ingestion & Normalization Rules:
            </div>
            <ul className="list-disc list-inside space-y-1 text-sky-800">
              <li><strong>Source Uniqueness:</strong> Existing listings with the same <code>source_listing_id</code> will be updated safely.</li>
              <li><strong>Physical Deduplication:</strong> Identical unit numbers in the same postal code/building will attach to existing canonical properties.</li>
              <li><strong>Safe Review Queue:</strong> Ambiguous listings missing unit numbers will be held for manual review. No destructive merges.</li>
            </ul>
          </div>

          {/* Form Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Link
              href="/property-imports"
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={uploading || !file || !selectedSourceId}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors shadow-2xs disabled:opacity-50"
            >
              <UploadCloud className="w-4 h-4" />
              {uploading ? "Uploading & Validating..." : "Upload & Validate CSV"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
