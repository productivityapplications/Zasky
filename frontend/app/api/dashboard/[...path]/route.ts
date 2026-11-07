import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_BASE = (
  process.env.ZASKY_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8100"
).replace(/\/+$/, "");
const DASHBOARD_TOKEN = process.env.ZASKY_DASHBOARD_TOKEN ?? "";

const ALLOWED_ROOTS = new Set(["today", "tasks", "reconciliations"]);
const SAFE_SEGMENT = /^[A-Za-z0-9-]+$/;

function jsonError(detail: string, status: number): NextResponse {
  return NextResponse.json({ detail }, { status });
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await context.params;
  if (
    !path.length ||
    !ALLOWED_ROOTS.has(path[0]) ||
    path.some((segment) => !SAFE_SEGMENT.test(segment))
  ) {
    return jsonError("Unknown dashboard endpoint.", 404);
  }
  if (!DASHBOARD_TOKEN) {
    return jsonError("ZASKY_DASHBOARD_TOKEN is not configured on the server.", 503);
  }
  if (!/^https?:\/\//.test(API_BASE)) {
    return jsonError("The dashboard API URL must use http:// or https://.", 503);
  }

  const target = `${API_BASE}/api/dashboard/${path
    .map(encodeURIComponent)
    .join("/")}${request.nextUrl.search}`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${DASHBOARD_TOKEN}`,
        Accept: "application/json",
        ...(request.method === "POST"
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
    });
  } catch (error) {
    const message =
      error instanceof Error && error.name === "TimeoutError"
        ? "The dashboard backend timed out."
        : "Could not reach the dashboard backend.";
    return jsonError(message, 504);
  }

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return forward(request, context);
}
