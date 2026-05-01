import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth";

const BACKEND_BASE_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

function buildTargetUrl(request: NextRequest, path: string[]): string {
  const joinedPath = path.join("/");
  const base = BACKEND_BASE_URL.endsWith("/")
    ? BACKEND_BASE_URL.slice(0, -1)
    : BACKEND_BASE_URL;
  const query = request.nextUrl.search;
  return `${base}/${joinedPath}${query}`;
}

async function proxy(request: NextRequest, path: string[]): Promise<Response> {
  const targetUrl = buildTargetUrl(request, path);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  if (!headers.has("authorization")) {
    const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
    if (token) {
      headers.set("authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    // @ts-expect-error Next.js requires duplex when forwarding streaming bodies.
    duplex: "half",
    cache: "no-store",
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export async function GET(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<Response> {
  return proxy(request, context.params.path);
}

export async function POST(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<Response> {
  return proxy(request, context.params.path);
}

export async function PUT(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<Response> {
  return proxy(request, context.params.path);
}

export async function PATCH(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<Response> {
  return proxy(request, context.params.path);
}

export async function DELETE(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<Response> {
  return proxy(request, context.params.path);
}
