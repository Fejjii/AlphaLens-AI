import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type {
  Approval,
  ApprovalStatus,
  Investigation,
  PortfolioSummary,
  UsageSummary,
} from "@/types/api";
import { AUTH_COOKIE_NAME } from "@/lib/auth";
import { mockPortfolio, mockUsageSummary } from "@/lib/mock";

function normalizeBaseUrl(raw: string): string {
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

const API_URL = normalizeBaseUrl(
  process.env.BACKEND_INTERNAL_URL ?? process.env.API_URL ?? "http://localhost:8000",
);

async function serverRequest<T>(path: string): Promise<T> {
  const token = (await cookies()).get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    redirect("/login");
  }
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403) {
    redirect("/login");
  }
  if (!response.ok) {
    throw new Error(`Server request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function withServerFallback<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch (error) {
    if (error instanceof Error && error.message.includes("401")) {
      throw error;
    }
    return fallback;
  }
}

export const serverApi = {
  portfolioSummary: () =>
    withServerFallback(serverRequest<PortfolioSummary>("/portfolio/summary"), mockPortfolio),
  approvals: (status?: ApprovalStatus) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return serverRequest<Approval[]>(`/approvals${query}`);
  },
  investigations: () => serverRequest<Investigation[]>("/investigations"),
  fetchUsageSummary: () =>
    withServerFallback(serverRequest<UsageSummary>("/usage/summary"), mockUsageSummary),
};
