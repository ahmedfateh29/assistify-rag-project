"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  Clipboard,
  LayoutDashboard,
  Lock,
  Menu,
  MessageSquare,
  Settings,
  Shield,
  Ticket,
  Users,
  X,
} from "lucide-react";
import { LogoutLink } from "@/src/components/ui/LogoutLink";
import { useProfile } from "@/src/hooks/useProfile";
import { useRoleNav } from "@/src/hooks/useRoleNav";
import { appPath } from "@/src/lib/routes";

const ICON_BY_LABEL: Record<string, React.ComponentType<{ className?: string }>> = {
  Dashboard: LayoutDashboard,
  Overview: LayoutDashboard,
  Superadmin: Shield,
  Users: Users,
  Analytics: BarChart3,
  "Audit Logs": Clipboard,
  "Access Requests": Lock,
  Knowledge: BookOpen,
  "Knowledge Base": BookOpen,
  Tickets: Ticket,
  "Support Tickets": Ticket,
  Notifications: Bell,
  Profile: Settings,
  "Manage Admins": Shield,
  Customers: Users,
  Chat: MessageSquare,
  "My Tickets": Ticket,
  Businesses: Building2,
};

function navIcon(label: string) {
  const Icon = ICON_BY_LABEL[label] ?? LayoutDashboard;
  return <Icon className="h-5 w-5" />;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { profile } = useProfile();
  const { sideLinks, homeHref } = useRoleNav();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const showSide = sideLinks.length > 0;

  const isActive = (href: string) => {
    if (href === "/logout") return false;
    const path = href.replace(/\/$/, "");
    const current = (pathname ?? "").replace(/\/$/, "");
    return current === path || current.startsWith(`${path}/`);
  };

  const displayName = profile?.full_name || profile?.username || "User";
  const roleLabel = profile?.role?.replace(/_/g, " ") ?? "";
  const businessLabel = profile?.tenant_name || (profile?.tenant_id ? `Business #${profile.tenant_id}` : "");

  return (
    <div className="flex h-screen bg-[#232323] text-[#fafaff]">
      {showSide && (
        <div
          className={`${
            sidebarOpen ? "w-64" : "w-0"
          } flex flex-col overflow-hidden border-r border-[#333333] bg-[#171717] transition-all duration-300`}
        >
          <div className="border-b border-[#333333] p-6">
            <Link href={homeHref} className="flex items-center gap-2">
              <MessageSquare className="h-6 w-6 text-[#10a37f]" />
              <span className="text-xl font-bold text-[#10a37f]">Assistify</span>
            </Link>
          </div>

          <nav className="flex-1 space-y-2 overflow-y-auto p-4">
            {sideLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-colors ${
                  isActive(link.href)
                    ? "bg-[#10a37f] text-white"
                    : "text-[#9ca3af] hover:bg-[#2b2b2b] hover:text-[#fafaff]"
                }`}
              >
                {navIcon(link.label)}
                <span>{link.label}</span>
              </Link>
            ))}
          </nav>

          <div className="border-t border-[#333333] p-4">
            <LogoutLink />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#333333] bg-[#2b2b2b] px-6 py-4">
          {showSide && (
            <button
              type="button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="rounded-lg p-2 text-[#9ca3af] transition-colors hover:bg-[#444444]"
              aria-label="Toggle sidebar"
            >
              {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          )}

          <div className="ml-auto flex items-center gap-4">
            <Link
              href={appPath("/")}
              className="rounded-lg bg-[#10a37f] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0d8a6b]"
            >
              Open Chat
            </Link>
            <div className="text-right">
              <p className="text-sm font-medium text-[#fafaff]">{displayName}</p>
              <p className="text-xs capitalize text-[#9ca3af]">{roleLabel}</p>
              {businessLabel ? (
                <p className="text-xs text-[#10a37f]">{businessLabel}</p>
              ) : null}
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-[#10a37f] to-[#2563eb] text-sm font-bold text-white">
              {displayName.charAt(0).toUpperCase()}
            </div>
          </div>
        </div>

        <main className="flex-1 overflow-y-auto bg-[#232323] p-8">{children}</main>
      </div>
    </div>
  );
}
