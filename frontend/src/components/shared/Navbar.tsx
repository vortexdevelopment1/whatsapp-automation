"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Users, FileText, Shield, LogOut, Menu, X, UserCheck, Settings, Building2, Layers, Briefcase, UploadCloud, GitCompare, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { name: "Agents", href: "/agents", icon: Users },
    { name: "Leads", href: "/leads", icon: UserCheck },
    { name: "Properties", href: "/properties", icon: Building2 },
    { name: "Viewings", href: "/viewings", icon: Calendar },
    { name: "Imports", href: "/property-imports", icon: UploadCloud },
    { name: "Reviews", href: "/property-duplicate-review", icon: GitCompare },
    { name: "Sources", href: "/property-sources", icon: Layers },
    { name: "Listing Agents", href: "/property-agents", icon: Briefcase },
    { name: "Audit Logs", href: "/audit-logs", icon: FileText },
    { name: "Settings", href: "/settings", icon: Settings },
  ];



  return (
    <header className="bg-white border-b border-slate-200/90 sticky top-0 z-40 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Left: Brand Logo & Desktop Nav */}
          <div className="flex items-center gap-8">
            <Link href="/agents" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-sky-600 flex items-center justify-center text-white font-bold text-sm shadow-xs group-hover:bg-sky-700 transition-colors">
                RO
              </div>
              <span className="text-base font-bold text-slate-900 tracking-tight">
                Rental Ops
              </span>
            </Link>

            <nav className="hidden md:flex space-x-1 items-center">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      "inline-flex items-center px-3.5 py-2 text-sm font-medium rounded-lg transition-colors gap-2",
                      isActive
                        ? "bg-slate-100 text-slate-900 font-semibold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    )}
                  >
                    <Icon className={cn("w-4 h-4", isActive ? "text-sky-600" : "text-slate-400")} />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right: Desktop Profile / Status & Mobile Menu Toggle */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg">
              <Shield className="w-3.5 h-3.5 text-emerald-600" />
              <span>Admin Console</span>
            </div>

            <Link
              href="/login"
              className="hidden sm:flex text-slate-500 hover:text-slate-800 text-sm items-center gap-1.5 p-2 rounded-lg hover:bg-slate-50 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </Link>

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-4 space-y-1 shadow-lg">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  "flex items-center px-3.5 py-2.5 text-sm font-medium rounded-lg gap-2.5 transition-colors",
                  isActive
                    ? "bg-sky-50 text-sky-800 font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-sky-600" : "text-slate-400")} />
                {item.name}
              </Link>
            );
          })}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 px-3">
            <span className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-emerald-600" />
              Admin Session Active
            </span>
            <Link
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="text-rose-600 font-medium flex items-center gap-1"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign Out
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};
