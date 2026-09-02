/**
 * Server-side proxy to the FastAPI backend. The backend API key never reaches
 * the browser — only this route (running on the server) knows it. The
 * frontend calls same-origin `/api/proxy/*`, which forwards to BACKEND_URL
 * with the X-API-Key header attached here.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || "";

async function forward(req: NextRequest, path: string[]) {
  const url = `${BACKEND_URL}/${path.join("/")}${req.nextUrl.search}`;
  const init: RequestInit = {
    method: req.method,
    headers: { "X-API-Key": BACKEND_API_KEY, "Content-Type": "application/json" },
    cache: "no-store",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const resp = await fetch(url, init);
  const text = await resp.text();
  return new NextResponse(text, {
    status: resp.status,
    headers: { "Content-Type": resp.headers.get("Content-Type") || "application/json" },
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, { params }: RouteContext) {
  return forward(req, (await params).path);
}
export async function POST(req: NextRequest, { params }: RouteContext) {
  return forward(req, (await params).path);
}
export async function PATCH(req: NextRequest, { params }: RouteContext) {
  return forward(req, (await params).path);
}
