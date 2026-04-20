# Umuve Commercial Portal

Multi-tenant B2B portal at **portal.goumuve.com** (Spec 04). Separate Next.js app
so it deploys on its own cadence from `/platform/`.

## 72h MVP scope (shipped)

- Next.js 14 App Router + Tailwind + Zustand auth store
- Pages: `/login`, `/invite`, `/` (dashboard), `/properties`, `/jobs`,
  `/invoices`, `/team`, `/settings`
- Portal JWT in localStorage, attached to every `portalFetch()`
- Brand red `#DC2626`

## Running

```bash
cd portal
cp .env.example .env.local
# Point at your backend:
# NEXT_PUBLIC_API_URL=http://localhost:5001
npm install
npm run dev   # http://localhost:3002
```

## Flow

1. Sales team runs `flask portal orgs-create --name "Acme GC" --billing-email
   ops@acme.example --owner-email ops@acme.example --tier pro` on the backend.
2. CLI prints an invite URL. Customer clicks → `/invite?token=...`.
3. `/orgs/invite/accept` returns a portal JWT; auth store persists it.
4. Dashboard loads `/portal/v1/dashboard/summary`.

## Deploying (Vercel)

- Separate Vercel project pointed at this folder.
- Set `NEXT_PUBLIC_API_URL=https://junkos-backend.onrender.com`.
- Custom domain: `portal.goumuve.com`.
