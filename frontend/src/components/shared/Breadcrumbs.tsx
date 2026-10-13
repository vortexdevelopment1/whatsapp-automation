import React from "react";
import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export const Breadcrumbs: React.FC<{ items: BreadcrumbItem[] }> = ({ items }) => {
  return (
    <nav className="flex items-center space-x-1.5 text-xs text-slate-500 font-medium mb-3">
      <Link
        href="/agents"
        className="hover:text-slate-800 transition-colors flex items-center gap-1"
      >
        <Home className="w-3.5 h-3.5 text-slate-400" />
        <span>Dashboard</span>
      </Link>
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <React.Fragment key={index}>
            <ChevronRight className="w-3.5 h-3.5 text-slate-300 flex-shrink-0" />
            {item.href && !isLast ? (
              <Link href={item.href} className="hover:text-slate-800 transition-colors">
                {item.label}
              </Link>
            ) : (
              <span className="text-slate-800 truncate font-semibold">{item.label}</span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};
