"use client";

import { Bell, Search } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Topbar() {
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
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="h-4 w-4" />
        </Button>
        <Avatar className="border border-border/80 bg-card">
          <AvatarFallback>AL</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
