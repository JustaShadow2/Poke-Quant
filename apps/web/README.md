# PokéQuant Web

Next.js 15 (App Router) + TypeScript + Tailwind client — a **financial terminal**
for alternative assets. Phase 1 ships two surfaces:

- **Catalog** (`/`) — every tracked instrument.
- **Product** (`/instruments/[id]`) — price history + a baseline forecast with an
  uncertainty band and horizon toggles.

## Develop

```bash
npm install
cp .env.example .env.local   # point API_BASE_URL at the running API
npm run dev                  # http://localhost:3000
```

The backend must be running (`pokequant serve`, default `http://localhost:8000`).
Seed + generate data first so pages have content:

```bash
pokequant seed && pokequant synth && pokequant ingest snapshot
pokequant features build && pokequant train && pokequant forecast run
```

## Scripts

- `npm run dev` — dev server on :3000
- `npm run build` / `npm run start` — production build / serve
- `npm run typecheck` — `tsc --noEmit`

## Data flow

All data is fetched **server-side** (`lib/api.ts`) and passed to a client chart
component, so the browser never needs cross-origin access to the API. `API_BASE_URL`
is used server-to-server (e.g. `http://api:8000` in Docker); `NEXT_PUBLIC_API_BASE_URL`
is the browser fallback.
