"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/shared/Navbar";
import { PageHeader } from "@/components/shared/PageHeader";
import { api } from "@/lib/api";
import { Bot, CheckCircle2, AlertTriangle, ShieldCheck, Cpu, RefreshCw } from "lucide-react";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAIHealth();
      setHealth(data);
    } catch (err: any) {
      setError(err.message || "Failed to load AI health status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="System & AI Diagnostics"
          description="Operational telemetry and integration status for AI services (Module 3 Phase 2)."
          breadcrumbs={[
            { label: "Dashboard", href: "/agents" },
            { label: "Settings & AI Status" },
          ]}
          actions={

            <button
              onClick={fetchStatus}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition shadow-2xs"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh Status
            </button>
          }
        />

        {error && (
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-sm flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* AI Orchestrator Diagnostic Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center font-bold">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  AI Orchestrator Engine
                </h3>
                <p className="text-xs text-slate-500">
                  Central abstraction layer for controlled LLM execution and telemetry
                </p>
              </div>
            </div>

            {health && (
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                  health.status === "READY"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                {health.status === "READY" ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                )}
                {health.status}
              </span>
            )}
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium text-slate-400 block mb-1">
                AI Provider
              </span>
              <span className="text-base font-semibold text-slate-800 capitalize">
                {health?.provider || "Loading..."}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium text-slate-400 block mb-1">
                Active Model
              </span>
              <span className="text-base font-semibold text-slate-800 font-mono text-sm">
                {health?.model || "Loading..."}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium text-slate-400 block mb-1">
                Timeout & Retries
              </span>
              <span className="text-sm font-semibold text-slate-800">
                {health ? `${health.timeout_seconds}s / ${health.max_retries} retries` : "..."}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium text-slate-400 block mb-1">
                Config Status
              </span>
              <span className="text-sm font-semibold text-slate-800">
                {health?.configured ? "Configured" : "Unconfigured"}
              </span>
            </div>
          </div>

          {/* Telemetry Timestamps */}
          <div className="px-6 py-4 bg-slate-50/70 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-slate-400 font-medium">Last Successful Call: </span>
              <span className="text-slate-700 font-semibold">
                {health?.last_success_at
                  ? new Date(health.last_success_at).toLocaleString()
                  : "No successful calls recorded yet"}
              </span>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Last Failed Call: </span>
              <span className="text-slate-700 font-semibold">
                {health?.last_failure_at
                  ? new Date(health.last_failure_at).toLocaleString()
                  : "None"}
              </span>
              {health?.last_failure_error && (
                <div className="mt-1 text-rose-600 font-mono text-[11px] truncate">
                  {health.last_failure_error}
                </div>
              )}
            </div>
          </div>

          {/* Security Notice */}
          <div className="px-6 py-3 bg-white border-t border-slate-100 flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              Security notice: API keys are strictly maintained server-side and are never transmitted to or accessible by client browsers.
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
