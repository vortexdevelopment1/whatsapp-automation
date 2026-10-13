"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  HelpCircle,
  Plus,
  Search,
  CheckCircle2,
  XCircle,
  Edit2,
  Power,
  RotateCw,
  Sparkles,
  ArrowLeft,
  Tag,
  Globe,
  BookOpen,
} from "lucide-react";
import { api } from "@/lib/api";
import { FAQEntry, FAQCreateInput, FAQUpdateInput } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";

export default function FAQManagementPage() {
  const [faqs, setFaqs] = useState<FAQEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCategory, setFilterCategory] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [searchKeyword, setSearchKeyword] = useState<string>("");

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [selectedFaq, setSelectedFaq] = useState<FAQEntry | null>(null);

  // Form states
  const [formQuestion, setFormQuestion] = useState("");
  const [formAnswer, setFormAnswer] = useState("");
  const [formCategory, setFormCategory] = useState("GENERAL");
  const [formKeywords, setFormKeywords] = useState("");
  const [formLanguage, setFormLanguage] = useState("en");
  const [formVersion, setFormVersion] = useState("v1");
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Test match state
  const [testQuery, setTestQuery] = useState("");
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const loadFaqs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.listFAQs(
        filterCategory || undefined,
        filterStatus || undefined
      );
      setFaqs(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load FAQs");
    } finally {
      setLoading(false);
    }
  }, [filterCategory, filterStatus]);

  useEffect(() => {
    loadFaqs();
  }, [loadFaqs]);

  const handleOpenCreate = () => {
    setFormQuestion("");
    setFormAnswer("");
    setFormCategory("GENERAL");
    setFormKeywords("");
    setFormLanguage("en");
    setFormVersion("v1");
    setErrorMsg(null);
    setIsCreateModalOpen(true);
  };

  const handleOpenEdit = (faq: FAQEntry) => {
    setSelectedFaq(faq);
    setFormQuestion(faq.question);
    setFormAnswer(faq.answer);
    setFormCategory(faq.category);
    setFormKeywords((faq.keywords || []).join(", "));
    setFormLanguage(faq.language);
    setFormVersion(faq.version);
    setErrorMsg(null);
    setIsEditModalOpen(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formQuestion.trim() || !formAnswer.trim()) {
      setErrorMsg("Question and answer are required.");
      return;
    }
    try {
      setSaving(true);
      setErrorMsg(null);
      const keywordsList = formKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      const payload: FAQCreateInput = {
        question: formQuestion.trim(),
        answer: formAnswer.trim(),
        category: formCategory.trim() || "GENERAL",
        keywords: keywordsList,
        language: formLanguage.trim() || "en",
        version: formVersion.trim() || "v1",
      };
      await api.createFAQ(payload);
      setSuccessMsg("FAQ entry created successfully.");
      setIsCreateModalOpen(false);
      loadFaqs();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create FAQ");
    } finally {
      setSaving(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFaq) return;
    try {
      setSaving(true);
      setErrorMsg(null);
      const keywordsList = formKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      const payload: FAQUpdateInput = {
        question: formQuestion.trim(),
        answer: formAnswer.trim(),
        category: formCategory.trim(),
        keywords: keywordsList,
        language: formLanguage.trim(),
        version: formVersion.trim(),
      };
      await api.updateFAQ(selectedFaq.id, payload);
      setSuccessMsg("FAQ entry updated successfully.");
      setIsEditModalOpen(false);
      loadFaqs();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update FAQ");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (faq: FAQEntry) => {
    try {
      const nextStatus = faq.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
      await api.setFAQStatus(faq.id, nextStatus);
      setSuccessMsg(`FAQ status changed to ${nextStatus}.`);
      loadFaqs();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to change FAQ status");
    }
  };

  const handleTestMatch = async () => {
    if (!testQuery.trim()) return;
    try {
      setTesting(true);
      const res = await api.matchFAQ(testQuery.trim());
      setTestResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || "Match test failed");
    } finally {
      setTesting(false);
    }
  };

  const filteredFaqs = faqs.filter((faq) => {
    if (!searchKeyword.trim()) return true;
    const term = searchKeyword.toLowerCase();
    return (
      faq.question.toLowerCase().includes(term) ||
      faq.answer.toLowerCase().includes(term) ||
      (faq.keywords || []).some((k) => k.toLowerCase().includes(term))
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href="/leads"
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            >
              <ArrowLeft className="w-3 h-3" /> Back to Leads
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-primary" />
            Approved FAQ Knowledge Base
          </h1>
          <p className="text-sm text-muted-foreground">
            Authoritative source of business truth. AI answers tenant questions strictly from approved content.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setTestQuery("");
              setTestResult(null);
              setIsTestModalOpen(true);
            }}
            className="flex items-center gap-1.5"
          >
            <Sparkles className="w-4 h-4 text-amber-500" />
            Test Matcher
          </Button>
          <Button
            size="sm"
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" />
            Add FAQ
          </Button>
        </div>
      </div>

      {successMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 rounded-lg text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-xs underline ml-2">Dismiss</button>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 rounded-lg text-sm flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-xs underline ml-2">Dismiss</button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center bg-card p-4 rounded-xl border border-border">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            placeholder="Search questions, answers, or keywords..."
            className="pl-9 text-sm"
          />
        </div>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="bg-background border border-border text-sm rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All Categories</option>
          <option value="GENERAL">GENERAL</option>
          <option value="DOCUMENTS">DOCUMENTS</option>
          <option value="FEES">FEES</option>
          <option value="VIEWING">VIEWING</option>
          <option value="POLICY">POLICY</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-background border border-border text-sm rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All Statuses</option>
          <option value="ACTIVE">ACTIVE</option>
          <option value="INACTIVE">INACTIVE</option>
          <option value="DRAFT">DRAFT</option>
        </select>
        <Button variant="ghost" size="sm" onClick={loadFaqs} className="flex items-center gap-1">
          <RotateCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
      </div>

      {/* FAQ Cards List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 bg-card/60 animate-pulse rounded-xl border border-border" />
          ))}
        </div>
      ) : filteredFaqs.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <HelpCircle className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-40" />
            <p className="text-base font-semibold text-foreground">No approved FAQs found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Add your first FAQ entry to let the AI safely answer tenant business questions.
            </p>
            <Button size="sm" onClick={handleOpenCreate} className="mt-4">
              Add FAQ
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredFaqs.map((faq) => (
            <Card key={faq.id} className="border border-border/80 hover:border-primary/40 transition-colors flex flex-col justify-between">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                    {faq.category}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                        faq.status === "ACTIVE"
                          ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                          : faq.status === "DRAFT"
                          ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                          : "bg-muted text-muted-foreground border border-border"
                      }`}
                    >
                      {faq.status}
                    </span>
                    <span className="text-[10px] text-muted-foreground">v{faq.version}</span>
                  </div>
                </div>
                <CardTitle className="text-base font-semibold mt-2 text-foreground leading-snug">
                  {faq.question}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {faq.answer}
                </p>

                {faq.keywords && faq.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1 items-center pt-2 border-t border-border/60">
                    <Tag className="w-3 h-3 text-muted-foreground mr-1" />
                    {faq.keywords.map((kw, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between pt-2 border-t border-border/60 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Globe className="w-3 h-3" /> {faq.language.toUpperCase()}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleStatus(faq)}
                      title={faq.status === "ACTIVE" ? "Deactivate" : "Activate"}
                      className="p-1 hover:text-foreground transition-colors"
                    >
                      <Power className={`w-3.5 h-3.5 ${faq.status === "ACTIVE" ? "text-emerald-500" : "text-muted-foreground"}`} />
                    </button>
                    <button
                      onClick={() => handleOpenEdit(faq)}
                      title="Edit FAQ"
                      className="p-1 hover:text-foreground transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-blue-500" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Create FAQ */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Add Approved FAQ Entry"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Tenant Question Pattern *
            </label>
            <Input
              value={formQuestion}
              onChange={(e) => setFormQuestion(e.target.value)}
              placeholder="e.g. What documents do I need to prepare?"
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Approved Official Answer *
            </label>
            <textarea
              rows={4}
              value={formAnswer}
              onChange={(e) => setFormAnswer(e.target.value)}
              placeholder="Enter approved answer text without speculation..."
              className="w-full bg-background border border-border rounded-lg p-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Category</label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                className="w-full bg-background border border-border rounded-lg p-2 text-sm text-foreground"
              >
                <option value="GENERAL">GENERAL</option>
                <option value="DOCUMENTS">DOCUMENTS</option>
                <option value="FEES">FEES</option>
                <option value="VIEWING">VIEWING</option>
                <option value="POLICY">POLICY</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Version</label>
              <Input
                value={formVersion}
                onChange={(e) => setFormVersion(e.target.value)}
                placeholder="v1"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Keywords (comma-separated)
            </label>
            <Input
              value={formKeywords}
              onChange={(e) => setFormKeywords(e.target.value)}
              placeholder="e.g. documents, pass, ic, payslip, requirements"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? "Saving..." : "Create Entry"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Edit FAQ */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="Edit Approved FAQ Entry"
      >
        <form onSubmit={handleEditSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Tenant Question Pattern *
            </label>
            <Input
              value={formQuestion}
              onChange={(e) => setFormQuestion(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Approved Official Answer *
            </label>
            <textarea
              rows={4}
              value={formAnswer}
              onChange={(e) => setFormAnswer(e.target.value)}
              className="w-full bg-background border border-border rounded-lg p-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Category</label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                className="w-full bg-background border border-border rounded-lg p-2 text-sm text-foreground"
              >
                <option value="GENERAL">GENERAL</option>
                <option value="DOCUMENTS">DOCUMENTS</option>
                <option value="FEES">FEES</option>
                <option value="VIEWING">VIEWING</option>
                <option value="POLICY">POLICY</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Version</label>
              <Input
                value={formVersion}
                onChange={(e) => setFormVersion(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Keywords (comma-separated)
            </label>
            <Input
              value={formKeywords}
              onChange={(e) => setFormKeywords(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsEditModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? "Updating..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Test FAQ Matcher */}
      <Modal
        isOpen={isTestModalOpen}
        onClose={() => setIsTestModalOpen(false)}
        title="Test FAQ Intent Matcher"
      >
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Test how arbitrary tenant queries match against current active approved FAQs without sending WhatsApp messages.
          </p>

          <div className="flex gap-2">
            <Input
              value={testQuery}
              onChange={(e) => setTestQuery(e.target.value)}
              placeholder="e.g. what papers do i need?"
              className="text-sm"
              onKeyDown={(e) => e.key === "Enter" && handleTestMatch()}
            />
            <Button size="sm" onClick={handleTestMatch} disabled={testing}>
              {testing ? "Testing..." : "Test"}
            </Button>
          </div>

          {testResult && (
            <div className={`p-4 rounded-xl border ${testResult.matched ? "bg-emerald-500/10 border-emerald-500/30" : "bg-rose-500/10 border-rose-500/30"}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">
                  {testResult.matched ? "Match Found" : "No Match (Fallback Triggered)"}
                </span>
                {testResult.confidence > 0 && (
                  <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    Confidence: {(testResult.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              {testResult.matched && testResult.faq ? (
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="font-semibold text-muted-foreground">Matched Question:</span>
                    <p className="font-medium text-foreground">{testResult.faq.question}</p>
                  </div>
                  <div>
                    <span className="font-semibold text-muted-foreground">Approved Answer:</span>
                    <p className="text-foreground whitespace-pre-wrap">{testResult.faq.answer}</p>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-rose-600 dark:text-rose-400">
                  <span className="font-semibold block mb-1">Safe Fallback Response:</span>
                  <p className="italic">{testResult.fallback_message}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
