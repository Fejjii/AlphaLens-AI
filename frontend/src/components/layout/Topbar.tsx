"use client";

import { Bell, Search } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { PlanUsage, RuntimeStatus, UsageEvent } from "@/types/api";

type Overlay = "demo" | "runtime" | "plan" | "notifications" | null;
type SearchGroup = "Portfolio" | "Knowledge Base" | "Reports" | "Approvals" | "Actions";

interface SearchResultItem {
  id: string;
  group: SearchGroup;
  label: string;
  hint: string;
  href: string;
}

const TICKERS = ["NVDA", "AAPL", "MSFT"] as const;

export function Topbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [activeTopbarPanel, setActiveTopbarPanel] = useState<Overlay>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [planUsage, setPlanUsage] = useState<PlanUsage | null>(null);
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const topbarRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    void Promise.all([
      api.runtimeStatus(),
      api.fetchMyPlanUsage(),
      api.fetchUsageEvents(),
      api.fetchApprovals(),
    ])
      .then(([runtimeStatus, usage, usageEvents, approvals]) => {
        setRuntime(runtimeStatus);
        setPlanUsage(usage);
        setEvents(usageEvents);
        setPendingApprovals(approvals.filter((item) => item.status === "pending").length);
      })
      .catch(() => undefined);
  }, []);

  const failedProviders = useMemo(
    () => events.filter((event) => event.event_type === "tool_error" || event.event_type === "llm_error"),
    [events],
  );
  const fallbackEvents = useMemo(
    () => events.filter((event) => event.event_type === "llm_fallback"),
    [events],
  );
  const persistenceProvider = useMemo(
    () => runtime?.providers.find((provider) => provider.name === "Persistence") ?? null,
    [runtime],
  );
  const searchResults = useMemo<SearchResultItem[]>(() => buildSearchResults(searchQuery), [searchQuery]);

  const initials =
    user?.full_name
      .split(" ")
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 2) || "AL";

  const togglePanel = (panel: Exclude<Overlay, null>) => {
    setActiveTopbarPanel((current) => (current === panel ? null : panel));
  };

  const navigateAndClosePanel = (href: string) => {
    setActiveTopbarPanel(null);
    setSearchOpen(false);
    router.push(href);
  };

  useEffect(() => {
    if (!activeTopbarPanel) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!topbarRef.current) {
        return;
      }
      const target = event.target as Node | null;
      if (target && topbarRef.current.contains(target)) {
        return;
      }
      setActiveTopbarPanel(null);
      setSearchOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActiveTopbarPanel(null);
        setSearchOpen(false);
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeTopbarPanel]);

  useEffect(() => {
    setActiveTopbarPanel(null);
    setSearchOpen(false);
  }, [pathname]);

  return (
    <header
      ref={topbarRef}
      className="relative sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/70 bg-background/80 px-4 backdrop-blur sm:px-5 lg:px-8"
    >
      <div className="relative hidden max-w-lg flex-1 lg:block">
        <Search className="pointer-events-none absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search portfolios, memos, tickers..."
          value={searchQuery}
          onChange={(event) => {
            setSearchQuery(event.target.value);
            setSearchOpen(true);
          }}
          onFocus={() => setSearchOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setSearchOpen(false);
              return;
            }
            if (event.key !== "Enter") {
              return;
            }
            event.preventDefault();
            const topResult = searchResults[0];
            if (topResult) {
              navigateAndClosePanel(topResult.href);
              return;
            }
            setSearchOpen(true);
          }}
          className="pl-10"
        />
        {searchOpen ? (
          <div className="absolute left-0 right-0 top-12 z-50 max-h-[24rem] overflow-auto rounded-[0.875rem] border border-border/70 bg-card p-2 shadow-xl">
            {searchResults.length > 0 ? (
              groupedSearchEntries(searchResults).map(([group, items]) => (
                <div key={group} className="mb-2 last:mb-0">
                  <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {group}
                  </div>
                  <div className="space-y-1">
                    {items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className="w-full rounded-[0.75rem] border border-transparent px-2 py-1.5 text-left text-sm hover:border-border hover:bg-background/60"
                        onClick={() => navigateAndClosePanel(item.href)}
                      >
                        <div className="font-medium">{item.label}</div>
                        <div className="text-xs text-muted-foreground">{item.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className="px-2 py-2 text-sm text-muted-foreground">No results found.</div>
            )}
          </div>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="hidden sm:inline-flex"
          onClick={() => togglePanel("demo")}
          aria-expanded={activeTopbarPanel === "demo"}
          aria-controls="topbar-panel-demo"
        >
          <Badge variant="outline" className="font-mono">demo mode</Badge>
        </button>
        <button
          type="button"
          className="inline-flex"
          onClick={() => togglePanel("runtime")}
          aria-expanded={activeTopbarPanel === "runtime"}
          aria-controls="topbar-panel-runtime"
        >
          <Badge variant="muted" className="font-mono">deterministic fallback</Badge>
        </button>
        {user && (
          <button
            type="button"
            className="hidden sm:inline-flex"
            onClick={() => togglePanel("plan")}
            aria-expanded={activeTopbarPanel === "plan"}
            aria-controls="topbar-panel-plan"
          >
            <Badge variant="outline" className="hidden capitalize sm:inline-flex">
              {user.plan}
            </Badge>
          </button>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          onClick={() => togglePanel("notifications")}
          aria-expanded={activeTopbarPanel === "notifications"}
          aria-controls="topbar-panel-notifications"
        >
          <Bell className="h-4 w-4" />
        </Button>
        {user && (
          <div className="hidden text-right text-xs sm:block">
            <div className="font-medium text-foreground">{user.full_name}</div>
            <div className="text-muted-foreground">{user.email}</div>
          </div>
        )}
        <Avatar className="border border-border/80 bg-card">
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            logout();
            router.replace("/login");
          }}
        >
          Logout
        </Button>
      </div>
      {activeTopbarPanel === "demo" && (
        <PopoverCard
          id="topbar-panel-demo"
          title="Demo mode workspace"
          onClose={() => setActiveTopbarPanel(null)}
          widthClassName="w-[min(520px,calc(100vw-2rem))]"
        >
          <p className="text-sm text-muted-foreground">
            This workspace uses synthetic demo portfolio data including holdings, transactions, watchlist, cash,
            internal policy docs, and deterministic external provider fallbacks. No real trading or broker execution exists.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              { label: "Dashboard", href: "/" },
              { label: "Portfolio", href: "/portfolio" },
              { label: "Knowledge Base", href: "/knowledge-base" },
              { label: "Settings", href: "/settings" },
            ].map((item) => (
              <Button
                key={item.href}
                size="sm"
                variant="outline"
                onClick={() => navigateAndClosePanel(item.href)}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </PopoverCard>
      )}
      {activeTopbarPanel === "runtime" && (
        <PopoverCard
          id="topbar-panel-runtime"
          title="Provider runtime status"
          onClose={() => setActiveTopbarPanel(null)}
          widthClassName="w-[min(560px,calc(100vw-2rem))]"
        >
          {persistenceProvider?.status === "memory_fallback" ? (
            <div className="mb-3 rounded-[0.875rem] border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
              Persistence is using memory fallback. Users, feedback, reports, and sessions may disappear after restart.
            </div>
          ) : (
            <div className="mb-3 rounded-[0.875rem] border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
              Postgres persistence connected. User accounts and app data survive normal restarts.
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Fallback mode means the app returns deterministic demo outputs when external API keys or services are unavailable.
          </p>
          <ProviderGroup title="External providers" providers={(runtime?.providers ?? []).filter((item) => ["OpenAI LLM", "Speech", "Market Data", "Web/News", "Macro", "SEC"].includes(item.name))} />
          <ProviderGroup
            title="Infrastructure"
            providers={(runtime?.providers ?? []).filter((item) =>
              ["Qdrant", "Redis", "Plan quotas"].includes(item.name),
            )}
          />
          <ProviderGroup title="Persistence" providers={(runtime?.providers ?? []).filter((item) => item.name === "Persistence")} />
        </PopoverCard>
      )}
      {activeTopbarPanel === "plan" && (
        <PopoverCard
          id="topbar-panel-plan"
          title="Plan and quota usage"
          onClose={() => setActiveTopbarPanel(null)}
          widthClassName="w-[min(460px,calc(100vw-2rem))]"
        >
          <div className="text-sm text-muted-foreground">
            Current plan: <span className="capitalize text-foreground">{planUsage?.plan ?? user?.plan ?? "free"}</span>
          </div>
          <div className="mt-3 space-y-2">
            {Object.entries(planUsage?.monthly_usage ?? {}).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between rounded-[0.875rem] border border-border/60 px-3 py-2 text-xs">
                <span className="capitalize">{key.replaceAll("_", " ")}</span>
                <span className="tabular">{String(value)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <Button size="sm" onClick={() => navigateAndClosePanel("/settings")}>Open Settings</Button>
          </div>
        </PopoverCard>
      )}
      {activeTopbarPanel === "notifications" && (
        <PopoverCard
          id="topbar-panel-notifications"
          title="Notifications"
          onClose={() => setActiveTopbarPanel(null)}
          widthClassName="w-[min(440px,calc(100vw-2rem))]"
        >
          <div className="space-y-2 text-sm">
            <div className="rounded-[0.875rem] border border-border/60 px-3 py-2">
              Pending approvals: <span className="font-medium">{pendingApprovals}</span>
            </div>
            <div className="rounded-[0.875rem] border border-border/60 px-3 py-2">
              High risk alerts: <span className="font-medium">0</span>
            </div>
            <div className="rounded-[0.875rem] border border-border/60 px-3 py-2">
              Failed provider calls: <span className="font-medium">{failedProviders.length}</span>
            </div>
            <div className="rounded-[0.875rem] border border-border/60 px-3 py-2">
              Fallback events: <span className="font-medium">{fallbackEvents.length}</span>
            </div>
            {pendingApprovals === 0 && failedProviders.length === 0 && fallbackEvents.length === 0 ? (
              <div className="text-xs text-muted-foreground">No active notifications.</div>
            ) : null}
          </div>
        </PopoverCard>
      )}
    </header>
  );
}

function PopoverCard({
  id,
  title,
  onClose,
  children,
  widthClassName = "w-[min(420px,calc(100vw-2rem))]",
}: {
  id: string;
  title: string;
  onClose: () => void;
  children: ReactNode;
  widthClassName?: string;
}) {
  return (
    <div
      id={id}
      className={`${widthClassName} absolute right-2 top-14 z-40 max-h-[70vh] overflow-auto rounded-[1rem] border border-border/70 bg-card p-4 shadow-xl`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold">{title}</div>
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>
      {children}
    </div>
  );
}

function runtimeImpactLabel(name: string, status: RuntimeStatus["providers"][number]["status"]): string | null {
  if (name === "Web/News" && status === "fallback") {
    return "live news unavailable";
  }
  if (name === "Macro" && status === "fallback") {
    return "live FRED macro unavailable";
  }
  if (name === "SEC" && status === "fallback") {
    return "live filing retrieval unavailable";
  }
  if (name === "Persistence" && status === "memory_fallback") {
    return "data not durable";
  }
  if (name === "Qdrant" && status === "connected") {
    return "RAG vector search available";
  }
  if (name === "Redis" && status === "connected") {
    return "cache and rate limiting available";
  }
  return null;
}

function ProviderGroup({
  title,
  providers,
}: {
  title: string;
  providers: RuntimeStatus["providers"];
}) {
  if (providers.length === 0) {
    return null;
  }
  return (
    <div className="mt-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{title}</div>
      <div className="space-y-2">
        {providers.map((provider) => (
          <div key={provider.name} className="rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{provider.name}</span>
              <Badge variant={provider.status === "real" || provider.status === "connected" ? "success" : "warning"}>
                {provider.status}
              </Badge>
            </div>
            {runtimeImpactLabel(provider.name, provider.status) ? (
              <div className="mt-1 text-xs text-foreground/80">{runtimeImpactLabel(provider.name, provider.status)}</div>
            ) : null}
            {provider.reason ? <div className="mt-1 text-xs text-muted-foreground">{provider.reason}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function buildSearchResults(query: string): SearchResultItem[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return [];
  }
  const results: SearchResultItem[] = [];

  for (const ticker of TICKERS) {
    if (ticker.toLowerCase().includes(normalized)) {
      results.push({
        id: `portfolio-${ticker}`,
        group: "Portfolio",
        label: ticker,
        hint: "Open portfolio and focus this holding",
        href: `/portfolio?symbol=${ticker}`,
      });
    }
  }
  if (normalized.includes("policy") || normalized.includes("knowledge") || normalized.includes("kb")) {
    results.push({
      id: "kb-policy",
      group: "Knowledge Base",
      label: "Knowledge Base policy search",
      hint: "Search internal policy and uploaded documents",
      href: `/knowledge-base?q=${encodeURIComponent(query.trim())}`,
    });
  }
  if (normalized.includes("report") || normalized.includes("memo")) {
    results.push({
      id: "reports",
      group: "Reports",
      label: "Reports workspace",
      hint: "Open generated memos and report history",
      href: "/reports",
    });
  }
  if (normalized.includes("approval") || normalized.includes("approve")) {
    results.push({
      id: "approvals",
      group: "Approvals",
      label: "Approval queue",
      hint: "Review pending investment approvals",
      href: "/approvals",
    });
  }
  if (normalized.includes("scenario")) {
    results.push({
      id: "scenarios",
      group: "Actions",
      label: "Scenario simulations",
      hint: "Run deterministic scenario analysis",
      href: "/scenarios",
    });
  }
  if (results.length === 0 && normalized.length >= 2) {
    results.push({
      id: "kb-fallback",
      group: "Actions",
      label: `Search knowledge base for "${query.trim()}"`,
      hint: "No direct route match. Open KB search.",
      href: `/knowledge-base?q=${encodeURIComponent(query.trim())}`,
    });
  }
  return results;
}

function groupedSearchEntries(results: SearchResultItem[]): Array<[SearchGroup, SearchResultItem[]]> {
  const grouped = new Map<SearchGroup, SearchResultItem[]>();
  for (const result of results) {
    const existing = grouped.get(result.group) ?? [];
    existing.push(result);
    grouped.set(result.group, existing);
  }
  return Array.from(grouped.entries());
}
