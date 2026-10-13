import React from "react";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  type?: "agent" | "auth" | "whatsapp" | "branding" | "template";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type = "agent" }) => {
  let colorClasses = "bg-slate-100 text-slate-700 border-slate-300";

  switch (status) {
    case "ACTIVE":
    case "VERIFIED":
    case "CONNECTED":
    case "APPROVED":
    case "ELIGIBLE":
    case "CONSENTED":
    case "READ":
    case "REPLIED":
    case "QUALIFIED":
    case "QUALIFICATION_COMPLETE":
    case "CONFIRMED":
    case "COMPLETED":
    case "AVAILABLE":
    case "VERIFIED_CANDIDATE":
    case "SHORTLISTED":
    case "BOOKED":
    case "SELECTED":
    case "INTERESTED":
    case "VIEWING_REQUESTED":
      colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-300";
      break;
    case "PENDING":
    case "PENDING_APPROVAL":
    case "CONFIGURED":
    case "READY":
    case "VALIDATING":
    case "UNKNOWN":
    case "WAITING_FOR_TENANT":
    case "NEEDS_HUMAN_REVIEW":
    case "NEEDS_REVIEW":
    case "HUMAN_REVIEW":
    case "CONDITIONAL":
    case "CONDITIONAL_CANDIDATE":
    case "AWAITING_AGENT":
    case "AWAITING_AGENT_AVAILABILITY":
    case "AWAITING_TENANT_AVAILABILITY":
    case "AWAITING_TENANT_CONFIRMATION":
    case "AWAITING_AGENT_CONFIRMATION":
    case "RESCHEDULE_REQUESTED":
    case "READY_FOR_AGENT_VERIFICATION":
    case "SCORED":
    case "WANTS_MORE_DETAILS":
    case "OTHER_OPTIONS_REQUESTED":
    case "NEEDS_CLARIFICATION":
      colorClasses = "bg-amber-50 text-amber-700 border-amber-300";
      break;
    case "NEW":
    case "READY_FOR_OUTREACH":
    case "OUTREACH_QUEUED":
    case "CONTACTED":
    case "DELIVERED":
    case "IN_PROGRESS":
    case "QUALIFYING":
    case "AI_ACTIVE":
    case "PROPOSED":
    case "SLOTS_AVAILABLE":
    case "SLOT_PROPOSED":
    case "PRESENTED":
      colorClasses = "bg-sky-50 text-sky-700 border-sky-300";
      break;
    case "DRAFT":
    case "NOT_CONFIGURED":
    case "NOT_STARTED":
    case "NOT_REQUIRED":
    case "NOT_PRESENTED":
    case "SUPERSEDED":
    case "PAUSED":
      colorClasses = "bg-slate-50 text-slate-600 border-slate-300";
      break;
    case "REJECTED":
    case "ERROR":
    case "FAILED":
    case "DISQUALIFIED":
    case "INELIGIBLE":
    case "NOT_CONSENTED":
    case "OPTED_OUT":
    case "UNAVAILABLE":
    case "NOT_SHORTLIST_ELIGIBLE":
    case "STALE":
    case "AGENT_UNRESPONSIVE":
    case "CANCELLED":
    case "DECLINED":
    case "NO_SHOW":
    case "NOT_INTERESTED":
      colorClasses = "bg-rose-50 text-rose-700 border-rose-300";
      break;
    case "DUPLICATE":
      colorClasses = "bg-amber-100 text-amber-800 border-amber-400 font-semibold";
      break;
    case "INACTIVE":
    case "DISABLED":
    case "ARCHIVED":
    case "EXPIRED":
      colorClasses = "bg-zinc-100 text-zinc-500 border-zinc-300";
      break;
    default:
      colorClasses = "bg-slate-100 text-slate-700 border-slate-200";
  }


  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        colorClasses
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
};
