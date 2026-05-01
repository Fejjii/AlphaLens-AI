"use client";

import { Bell, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const initials =
    user?.full_name
      .split(" ")
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 2) || "AL";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/70 bg-background/80 px-4 backdrop-blur sm:px-5 lg:px-8">
      <div className="relative hidden max-w-lg flex-1 lg:block">
        <Search className="pointer-events-none absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search portfolios, memos, tickers..."
          className="pl-10"
        />
      </div>
      <div className="flex items-center gap-3">
        <Badge variant="outline" className="hidden font-mono sm:inline-flex">
          demo mode
        </Badge>
        <Badge variant="muted" className="font-mono">
          deterministic fallback
        </Badge>
        {user && (
          <Badge variant="outline" className="hidden capitalize sm:inline-flex">
            {user.plan}
          </Badge>
        )}
        <Button variant="ghost" size="icon" aria-label="Notifications">
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
    </header>
  );
}
