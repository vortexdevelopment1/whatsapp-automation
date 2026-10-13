"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Send,
  ArrowDownLeft,
  ArrowUpRight,
  MessageSquare,
  Clock,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Info,
} from "lucide-react";
import { api } from "@/lib/api";
import { Agent, WhatsAppProfile, WhatsAppMessage } from "@/types";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentSubNav } from "@/components/shared/AgentSubNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/utils";

export default function AgentMessagesPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [profile, setProfile] = useState<WhatsAppProfile | null>(null);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Send form
  const [recipient, setRecipient] = useState("+65 9123 4567");
  const [content, setContent] = useState("Hello, this is a verified test message from our rental operations console.");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, waData, msgs] = await Promise.all([
        api.getAgent(agentId),
        api.getWhatsAppConfig(agentId),
        api.listMessages(agentId),
      ]);
      setAgent(agentData);
      setProfile(waData);
      setMessages(msgs || []);
    } catch (err: any) {
      setError(err.message || "Failed to load messages.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipient.trim() || !content.trim()) return;

    try {
      setSending(true);
      setError(null);
      setSuccess(null);
      await api.sendTestMessage(agentId, {
        recipient: recipient.trim(),
        content: content.trim(),
        message_type: "TEXT",
      });
      setSuccess("Test message sent successfully.");
      setContent("");
      loadData();
    } catch (err: any) {
      setError(err.message || "Failed to send message.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <PageHeader
        breadcrumbs={[
          { label: "Agents", href: "/agents" },
          { label: agent?.full_name || "Agent", href: `/agents/${agentId}` },
          { label: "Messages" },
        ]}
        title={agent?.full_name ? `${agent.full_name} — Message Console` : "WhatsApp Message Console"}
        description="Internal test console to inspect inbound/outbound WhatsApp traffic, delivery receipts, and send test messages."
        badges={
          agent && (
            <>
              <StatusBadge status={agent.status} type="agent" />
              <StatusBadge status={profile?.connection_status || "NOT_CONFIGURED"} type="whatsapp" />
            </>
          )
        }
      />

      <AgentSubNav agentId={agentId} messageCount={messages.length} />

      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center justify-between">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="text-emerald-700 font-bold ml-4">×</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Messages Timeline (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          <Card>
            <CardHeader className="py-3 px-5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-sky-600" />
                Message Activity Stream ({messages.length})
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => loadData()}
                icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
              >
                Refresh
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {loading && messages.length === 0 ? (
                <div className="p-8 space-y-4">
                  <Skeleton className="h-16 w-3/4" />
                  <Skeleton className="h-16 w-3/4 ml-auto" />
                  <Skeleton className="h-16 w-2/3" />
                </div>
              ) : messages.length === 0 ? (
                <EmptyState
                  icon={<MessageSquare className="w-6 h-6 text-slate-400" />}
                  title="No messages recorded"
                  description="No inbound or outbound WhatsApp messages exist for this agent profile yet."
                />
              ) : (
                <div className="divide-y divide-slate-100 max-h-[560px] overflow-y-auto p-4 space-y-3">
                  {messages.map((msg) => {
                    const isOutbound = msg.direction === "OUTBOUND";
                    return (
                      <div
                        key={msg.id}
                        className={`flex flex-col ${
                          isOutbound ? "items-end" : "items-start"
                        } pt-2`}
                      >
                        <div
                          className={`max-w-[85%] rounded-2xl p-4 border shadow-2xs ${
                            isOutbound
                              ? "bg-sky-50/80 border-sky-200/80 text-slate-900 rounded-tr-xs"
                              : "bg-white border-slate-200 text-slate-900 rounded-tl-xs"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3 text-xs mb-1.5 border-b border-slate-200/40 pb-1">
                            <span className="font-semibold flex items-center gap-1">
                              {isOutbound ? (
                                <>
                                  <ArrowUpRight className="w-3.5 h-3.5 text-sky-600" />
                                  <span className="text-sky-800 font-mono text-[11px]">OUTBOUND</span>
                                </>
                              ) : (
                                <>
                                  <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-600" />
                                  <span className="text-emerald-800 font-mono text-[11px]">INBOUND</span>
                                </>
                              )}
                            </span>
                            <span className="text-[11px] font-mono text-slate-400">
                              {formatDate(msg.created_at)}
                            </span>
                          </div>

                          <p className="text-sm leading-relaxed whitespace-pre-wrap">
                            {msg.content}
                          </p>

                          <div className="mt-2.5 pt-2 border-t border-slate-200/40 flex items-center justify-between text-[11px] text-slate-500 font-mono">
                            <span>
                              {isOutbound ? `To: ${msg.recipient || "—"}` : `From: ${msg.sender || "—"}`}
                            </span>
                            {msg.provider_status && (
                              <span className="uppercase text-[10px] font-bold bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                                {msg.provider_status}
                              </span>
                            )}
                          </div>
                        </div>

                        {msg.provider_message_id && (
                          <span className="text-[10px] font-mono text-slate-400 mt-0.5 px-1">
                            ID: {msg.provider_message_id}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Test Dispatch Console (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <Card>
            <CardHeader className="py-4 px-5">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Send className="w-4 h-4 text-sky-600" />
                Send Test Message
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              <form onSubmit={handleSend} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Test Recipient Number
                  </label>
                  <Input
                    type="text"
                    value={recipient}
                    onChange={(e) => setRecipient(e.target.value)}
                    required
                    placeholder="+65 9123 4567"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Use E.164 international format (e.g. +65...).
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Message Text
                  </label>
                  <textarea
                    rows={4}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    required
                    placeholder="Enter test message content..."
                    className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 font-sans"
                  />
                </div>

                <Button
                  type="submit"
                  loading={sending}
                  className="w-full"
                  icon={<Send className="w-4 h-4" />}
                >
                  Send Outbound Test
                </Button>
              </form>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-1.5">
                <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-sky-600" />
                  Console Guidelines
                </div>
                <p className="text-[11px] leading-relaxed">
                  Test messages sent from this console are recorded in the audit trail and tracked by their provider message ID.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
