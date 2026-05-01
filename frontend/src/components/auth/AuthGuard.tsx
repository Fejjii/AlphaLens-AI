"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { AUTH_ROUTES, isProtectedPath } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) {
      return;
    }
    if (!isAuthenticated && isProtectedPath(pathname)) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (isAuthenticated && AUTH_ROUTES.has(pathname)) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Loading AlphaLens AI...
      </div>
    );
  }

  if (!isAuthenticated && isProtectedPath(pathname)) {
    return null;
  }

  if (isAuthenticated && AUTH_ROUTES.has(pathname)) {
    return null;
  }

  return <>{children}</>;
}
