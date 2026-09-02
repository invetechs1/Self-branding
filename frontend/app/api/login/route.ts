/**
 * Validates credentials against the backend (which checks the bcrypt hash in
 * Postgres) and, on success, mints this app's own signed session cookie.
 * The backend never issues a session itself — that's this layer's job.
 */
import { NextRequest, NextResponse } from "next/server";
import { createSessionToken, SESSION_COOKIE_NAME, SESSION_MAX_AGE } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || "";

export async function POST(req: NextRequest) {
  const { email, password } = await req.json().catch(() => ({}));
  if (!email || !password) {
    return NextResponse.json({ error: "email and password are required" }, { status: 400 });
  }

  const backendResp = await fetch(`${BACKEND_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": BACKEND_API_KEY },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  if (!backendResp.ok) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const { email: verifiedEmail } = await backendResp.json();
  const token = await createSessionToken(verifiedEmail);

  // Secure must match how THIS request actually arrived, not NODE_ENV — a
  // production build served over plain HTTP (true today on the target VPS,
  // which has no TLS yet) would otherwise get a cookie no browser ever sends
  // back, breaking login silently. Checks x-forwarded-proto too, for when a
  // reverse proxy terminates TLS in front of this app.
  const isHttps = req.nextUrl.protocol === "https:" || req.headers.get("x-forwarded-proto") === "https";

  const res = NextResponse.json({ email: verifiedEmail });
  res.cookies.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: isHttps,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}
