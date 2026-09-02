# Dashboard — Yahya AI Content Intelligence Platform

Next.js (App Router) dashboard, built to match the client-approved "Yahya Intelligence" design —
same design tokens, component classes, and layout, wired to live data instead of the prototype's demo
data. See [`docs/architecture-assessment.md`](../docs/architecture-assessment.md) § F for the UX plan
and journeys this implements.

## Setup

```bash
npm install
cp .env.local.example .env.local   # BACKEND_URL + BACKEND_API_KEY must match the backend's .env
npm run dev
```

The backend must be running first (see `../backend/README.md`), including having created at least one
login account with `python scripts/create_user.py`.

## How auth works

Two separate layers:

1. **Backend service auth** — the dashboard never talks to the backend directly from the browser. Every
   request goes to this app's own `/api/proxy/*` route (`app/api/proxy/[...path]/route.ts`), which runs
   server-side, attaches the `X-API-Key` header from `BACKEND_API_KEY`, and forwards to `BACKEND_URL`.
   The backend API key is never sent to, or visible in, the browser.
2. **Human login** — `/login` posts to `/api/login`, which checks the email/password against the
   bcrypt hash stored in Postgres (via the backend's `/auth/login`) and, on success, sets this app's own
   signed session cookie (`SESSION_SECRET`, see `lib/session.ts`). `proxy.ts` (Next.js's route-protection
   file convention) redirects any request without a valid session to `/login`. Sign out clears the
   cookie via `/api/logout`.

## Screens implemented

| Route | Screen | Status |
|---|---|---|
| `/today` | Today's Intelligence | Live — reads `/clusters` |
| `/opportunities` | Content Opportunities | Live — reads `/opportunities`, can trigger draft generation |
| `/drafts` | Drafts & Approval | Live — full review flow: approve/edit/reject/regenerate, `A`/`E`/`R`/`N` keyboard shortcuts, red-level sign-off gate |
| Performance & Learning | Not yet built | Needs the learning-engine port (architecture-assessment.md Phase 5) before there's real data to show |
| Settings | Not yet built | Needs `knowledge_items`/`interests`/`system_config` write endpoints first |

## Build

```bash
npm run build
npm start
```
