"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Save, AlertCircle, User, ShieldCheck, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function CreateAgentPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Field errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Form State
  const [formData, setFormData] = useState({
    full_name: "",
    display_name: "",
    agency_name: "",
    designation: "",
    registration_number: "",
    phone: "",
    email: "",
    profile_photo_url: "",
    notes: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const errors: Record<string, string> = {};

    if (!formData.full_name.trim()) {
      errors.full_name = "Legal full name is required.";
    }
    if (!formData.agency_name.trim()) {
      errors.agency_name = "Agency name is required.";
    }
    if (formData.email && !formData.email.includes("@")) {
      errors.email = "Please provide a valid email format.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setError("Please fix the validation errors below.");
      return;
    }

    try {
      setSubmitting(true);
      const created = await api.createAgent({
        full_name: formData.full_name.trim(),
        display_name: formData.display_name.trim() || null,
        agency_name: formData.agency_name.trim(),
        designation: formData.designation.trim() || null,
        registration_number: formData.registration_number.trim() || null,
        phone: formData.phone.trim() || null,
        email: formData.email.trim() || null,
        profile_photo_url: formData.profile_photo_url.trim() || null,
        notes: formData.notes.trim() || null,
      });

      router.push(`/agents/${created.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create agent profile.");
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <PageHeader
        breadcrumbs={[
          { label: "Agents", href: "/agents" },
          { label: "Create Agent" },
        ]}
        title="Create Authorized Agent"
        description="Register a licensed real estate agent profile into the operations database."
      />

      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* SECTION 1: Basic Information */}
        <Card>
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-semibold">
              <User className="w-4 h-4 text-sky-600" />
              Basic Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Full Legal Name <span className="text-rose-500">*</span>
                </label>
                <Input
                  type="text"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  required
                  placeholder="e.g. Sarah Tan Mei Ling"
                  error={fieldErrors.full_name}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Display / Preferred Name
                </label>
                <Input
                  type="text"
                  name="display_name"
                  value={formData.display_name}
                  onChange={handleChange}
                  placeholder="e.g. Sarah Tan"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Agency Name <span className="text-rose-500">*</span>
                </label>
                <Input
                  type="text"
                  name="agency_name"
                  value={formData.agency_name}
                  onChange={handleChange}
                  required
                  placeholder="e.g. PropNex Realty Pte Ltd"
                  error={fieldErrors.agency_name}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Designation / Title
                </label>
                <Input
                  type="text"
                  name="designation"
                  value={formData.designation}
                  onChange={handleChange}
                  placeholder="e.g. Associate Senior District Director"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* SECTION 2: Professional Information */}
        <Card>
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Professional & Contact Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  CEA Registration No.
                </label>
                <Input
                  type="text"
                  name="registration_number"
                  value={formData.registration_number}
                  onChange={handleChange}
                  placeholder="e.g. R012345A"
                  className="font-mono uppercase"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Phone Number
                </label>
                <Input
                  type="text"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="+65 9123 4567"
                  className="font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Official Email
                </label>
                <Input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="sarah.tan@example.com"
                  error={fieldErrors.email}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* SECTION 3: Media & Notes */}
        <Card>
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-semibold">
              <FileText className="w-4 h-4 text-slate-600" />
              Media Assets & Notes
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Profile Photo URL
              </label>
              <Input
                type="url"
                name="profile_photo_url"
                value={formData.profile_photo_url}
                onChange={handleChange}
                placeholder="https://example.com/photos/agent.jpg"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Internal Operator Notes
              </label>
              <textarea
                name="notes"
                rows={3}
                value={formData.notes}
                onChange={handleChange}
                placeholder="License check notes, verified team affiliation, regional focus..."
                className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-3">
            <Link href="/agents">
              <Button variant="outline" type="button">
                Cancel
              </Button>
            </Link>
            <Button
              type="submit"
              loading={submitting}
              icon={<Save className="w-4 h-4" />}
            >
              Save Agent Profile
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}
