"use client";

import { usePathname } from "next/navigation";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { AUTH_ROUTES } from "@/lib/auth";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (AUTH_ROUTES.has(pathname)) {
    return <main className="min-h-screen px-4 py-6 sm:px-5 lg:px-8">{children}</main>;
  }

  return (
    <div className="flex min-h-screen bg-transparent">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-5 sm:px-5 lg:px-8 lg:py-6">{children}</main>
      </div>
    </div>
  );
}
