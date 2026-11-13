import { NextRequest, NextResponse } from "next/server";
import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { validateBffPath } from "@/lib/bff-path";
import { fetchBackendWithAuth } from "@/lib/server-api";

async function handleProxy(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const safePath = validateBffPath(path);
  if (!safePath) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Invalid proxy path",
        status: 400,
        code: "INVALID_PATH",
        detail: "Path must target /v1/*",
      },
      { status: 400 }
    );
  }

  const targetPathWithQuery = `${safePath}${req.nextUrl.search}`;
  const headers: Record<string, string> = {
    Accept: req.headers.get("accept") ?? "application/json",
  };
  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  let body: ArrayBuffer | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const buf = await req.arrayBuffer();
    if (buf.byteLength > 0) {
      body = buf;
    }
  }

  const outcome = await fetchBackendWithAuth(req, targetPathWithQuery, {
    method: req.method,
    headers,
    body,
  });

  const upstream = outcome.response;
  let res: NextResponse;

  if (upstream.status === 204 || upstream.status === 304) {
    res = new NextResponse(null, { status: upstream.status });
  } else {
    const respBytes = await upstream.arrayBuffer();
    const respHeaders = new Headers();
    const upstreamType = upstream.headers.get("content-type");
    if (upstreamType) {
      respHeaders.set("Content-Type", upstreamType);
    }
    res = new NextResponse(respBytes, {
      status: upstream.status,
      headers: respHeaders,
    });
  }

  if (outcome.shouldClearCookies) {
    clearAuthCookies(res);
  } else if (outcome.refreshedTokens) {
    setAuthCookies(res, outcome.refreshedTokens);
  }

  return res;
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, context);
}

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, context);
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, context);
}

export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, context);
}

export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, context);
}
