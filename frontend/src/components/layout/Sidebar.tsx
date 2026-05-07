"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bot,
  ClipboardCheck,
  DollarSign,
  FileText,
  LayoutDashboard,
  Library,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/agent", label: "Agent Chat", icon: Bot },
  { href: "/portfolio", label: "Portfolio", icon: BarChart3 },
  { href: "/investigations", label: "Investigations", icon: Search },
  { href: "/approvals", label: "Approvals", icon: ClipboardCheck },
  { href: "/usage", label: "Usage", icon: DollarSign },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/scenarios", label: "Scenarios", icon: ShieldAlert },
  { href: "/knowledge-base", label: "Knowledge Base", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
];

const SIDEBAR_WIDTH_KEY = "alphalens.sidebar.width";
const DEFAULT_WIDTH = 280;
const MIN_WIDTH = 220;
const MAX_WIDTH = 380;

interface SidebarProps {
  width?: number;
  onWidthChange?: (width: number) => void;
}

export function Sidebar({ width, onWidthChange }: SidebarProps) {
  const pathname = usePathname();
  const [internalWidth, setInternalWidth] = useState(DEFAULT_WIDTH);
  const resizingRef = useRef(false);
  const widthValue = useMemo(() => width ?? internalWidth, [internalWidth, width]);

  useEffect(() => {
    if (typeof window === "undefined" || width != null) return;
    const saved = window.localStorage.getItem(SIDEBAR_WIDTH_KEY);
    if (!saved) return;
    const parsed = Number(saved);
    if (!Number.isFinite(parsed)) return;
    const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, parsed));
    setInternalWidth(clamped);
    onWidthChange?.(clamped);
  }, [onWidthChange, width]);

  useEffect(() => {
    if (width == null || typeof window === "undefined") return;
    window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(width));
  }, [width]);

  const setWidth = (next: number) => {
    const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next));
    if (width == null) {
      setInternalWidth(clamped);
    }
    onWidthChange?.(clamped);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(clamped));
    }
  };

  const startResize = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    resizingRef.current = true;
    const originX = event.clientX;
    const startWidth = widthValue;

    const onMove = (moveEvent: MouseEvent) => {
      if (!resizingRef.current) return;
      const delta = moveEvent.clientX - originX;
      setWidth(startWidth + delta);
    };
    const onUp = () => {
      resizingRef.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <aside
      className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border/70 bg-card/75 backdrop-blur xl:flex"
      style={{ width: `${widthValue}px` }}
    >
      <div className="border-b border-border/70 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-2 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <span className="text-sm font-semibold tracking-tight">AlphaLens AI</span>
            <div className="text-xs text-muted-foreground">Agentic investment intelligence</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-[0.875rem] px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-foreground shadow-[inset_0_0_0_1px_rgba(96,165,250,0.12)]"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              <Icon className={cn("h-4 w-4", active && "text-primary")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border/70 p-4 text-xs text-muted-foreground">
        <div className="rounded-[0.875rem] border border-border/70 bg-background/40 px-3 py-3">
          <div className="font-medium text-foreground">v0.1.0</div>
          <div className="mt-1">Demo workspace with deterministic fallback data enabled.</div>
        </div>
      </div>
      <button
        type="button"
        className="absolute inset-y-0 -right-1.5 w-3 cursor-col-resize rounded-full bg-transparent transition-colors hover:bg-primary/20"
        aria-label="Resize sidebar"
        onMouseDown={startResize}
      >
        <span className="mx-auto block h-12 w-[2px] rounded-full bg-border/80" />
      </button>
    </aside>
  );
}
