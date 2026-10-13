"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, Palette, MessageSquare, FileCode, SendHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentSubNavProps {
  agentId: string;
  templateCount?: number;
  messageCount?: number;
}

export const AgentSubNav: React.FC<AgentSubNavProps> = ({
  agentId,
  templateCount,
  messageCount,
}) => {
  const pathname = usePathname();

  const tabs = [
    {
      name: "Overview & Profile",
      href: `/agents/${agentId}`,
      exact: true,
      icon: User,
    },
    {
      name: "Branding Profile",
      href: `/agents/${agentId}/branding`,
      exact: false,
      icon: Palette,
    },
    {
      name: "WhatsApp Configuration",
      href: `/agents/${agentId}/whatsapp`,
      exact: false,
      icon: MessageSquare,
    },
    {
      name: "Templates",
      href: `/agents/${agentId}/templates`,
      exact: false,
      icon: FileCode,
      count: templateCount,
    },
    {
      name: "Messages Console",
      href: `/agents/${agentId}/messages`,
      exact: false,
      icon: SendHorizontal,
      count: messageCount,
    },
  ];

  return (
    <div className="border-b border-slate-200 mb-6 overflow-x-auto scrollbar-none">
      <nav className="flex space-x-6 min-w-max" aria-label="Agent Sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = tab.exact
            ? pathname === tab.href
            : pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.name}
              href={tab.href}
              className={cn(
                "group inline-flex items-center py-3 px-1 border-b-2 font-medium text-sm transition-all whitespace-nowrap gap-2",
                isActive
                  ? "border-sky-600 text-sky-600 font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 transition-colors",
                  isActive ? "text-sky-600" : "text-slate-400 group-hover:text-slate-600"
                )}
              />
              <span>{tab.name}</span>
              {tab.count !== undefined && (
                <span
                  className={cn(
                    "ml-1 py-0.5 px-2 rounded-full text-xs font-semibold",
                    isActive
                      ? "bg-sky-100 text-sky-700"
                      : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                  )}
                >
                  {tab.count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
};
