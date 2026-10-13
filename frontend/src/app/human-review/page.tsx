"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  UserCheck,
  RotateCw,
  ArrowRight,
  MessageSquare,
  Clock,
  ShieldAlert,
  Play,
  CheckCircle,
  Eye,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { HumanReviewQueueItem } from "@/types";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";

export default function HumanReviewQueuePage() {
  const [queue, setQueue] = useState<HumanReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<HumanReviewQueueItem | null>(null);
  const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const items = await api.getHumanReviewQueue();
      setQueue(items);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load Human Review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleTakeover = async (leadId: string) => {
    try {
      setActionLoading(true);
      await api.takeoverConversation(leadId);
      setSuccessMsg("Successfully took over conversation. AI is paused.");
      loadQueue();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to take over conversation");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReturnToAI = async (leadId: string) => {
    try {
      setActionLoading(true);
      await api.returnToAI(leadId);
      setSuccessMsg("Returned to AI. Qualification state recalculated.");
      loadQueue();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to return conversation to AI");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem) return;
    try {
      setActionLoading(true);
      await api.returnToAI(selectedItem.lead_id, resolutionNotes);
      setSuccessMsg("Escalation resolved and conversation returned to AI.");
      setIsResolveModalOpen(false);
      loadQueue();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to resolve escalation");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-amber-500" />
            Human Review Queue
          </h1>
          <p className="text-sm text-muted-foreground">
            Monitor and resolve escalations, ambiguous tenant criteria, and manual takeover requests.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadQueue}
            className="flex items-center gap-1.5"
          >
            <RotateCw className="w-4 h-4" />
            Refresh Queue
          </Button>
          <Link href="/faqs">
            <Button variant="outline" size="sm">
              Manage FAQs
            </Button>
          </Link>
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

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 bg-card/60 animate-pulse rounded-xl border border-border" />
          ))}
        </div>
      ) : queue.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3 opacity-60" />
            <p className="text-base font-semibold text-foreground">Human Review Queue is Clear</p>
            <p className="text-sm text-muted-foreground mt-1">
              There are no pending escalations, disputes, or clarification limit timeouts at this time.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {queue.map((item) => (
            <Card
              key={item.lead_id}
              className="border border-border/80 hover:border-amber-500/40 transition-colors"
            >
              <CardContent className="p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-base text-foreground">
                      {item.lead_name}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">
                      {item.phone}
                    </span>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20 uppercase">
                      {item.reason_code}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground border border-border">
                      {item.qualification_status}
                    </span>
                    {item.ai_paused && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-500 border border-rose-500/20">
                        AI PAUSED
                      </span>
                    )}
                  </div>

                  {item.description && (
                    <p className="text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">Reason Detail: </span>
                      {item.description}
                    </p>
                  )}

                  {item.last_message && (
                    <div className="text-xs bg-muted/50 p-2.5 rounded-lg border border-border/50 max-w-2xl">
                      <span className="font-semibold text-muted-foreground block mb-0.5">Last Message:</span>
                      <p className="text-foreground italic">"{item.last_message}"</p>
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> Waiting: {item.time_waiting_minutes} mins
                    </span>
                    {item.assigned_to && (
                      <span className="flex items-center gap-1 font-medium text-foreground">
                        <UserCheck className="w-3.5 h-3.5 text-primary" /> Assigned: {item.assigned_to}
                      </span>
                    )}
                    {item.missing_fields && item.missing_fields.length > 0 && (
                      <span className="text-xs text-amber-600 dark:text-amber-400">
                        Missing: {item.missing_fields.join(", ")}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 lg:flex-col lg:items-end justify-end">
                  <Link href={`/leads/${item.lead_id}`}>
                    <Button size="sm" variant="outline" className="flex items-center gap-1 text-xs">
                      <Eye className="w-3.5 h-3.5" />
                      Open Lead
                    </Button>
                  </Link>

                  <Button
                    size="sm"
                    variant="outline"
                    className="flex items-center gap-1 text-xs border-amber-500/40 text-amber-600 dark:text-amber-400 hover:bg-amber-500/10"
                    onClick={() => handleTakeover(item.lead_id)}
                    disabled={actionLoading}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    Take Over
                  </Button>

                  <Button
                    size="sm"
                    className="flex items-center gap-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={() => {
                      setSelectedItem(item);
                      setResolutionNotes("");
                      setIsResolveModalOpen(true);
                    }}
                    disabled={actionLoading}
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Resolve & Return
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Resolve Escalation & Return to AI */}
      <Modal
        isOpen={isResolveModalOpen}
        onClose={() => setIsResolveModalOpen(false)}
        title="Resolve Escalation & Return to AI"
      >
        <form onSubmit={handleResolve} className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Resolving this review item will unpause AI qualification, recalculate tenant requirement completeness, and resume conversation from the current state without restarting.
          </p>

          <div>
            <label className="text-xs font-semibold text-foreground mb-1 block">
              Resolution Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={resolutionNotes}
              onChange={(e) => setResolutionNotes(e.target.value)}
              placeholder="e.g. Tenant confirmed budget verbally, criteria updated."
              className="w-full bg-background border border-border rounded-lg p-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsResolveModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={actionLoading}>
              {actionLoading ? "Processing..." : "Resolve & Resume AI"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
