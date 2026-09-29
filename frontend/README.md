# Frontend

FinkiBOT's web app: chat, search, quiz maker, subscriptions, an Insights dashboard,
and an MCP tools playground. React 19 + TypeScript, built on TanStack Start (router +
SSR shell) with Tailwind CSS and shadcn/ui components.

Talks to the FastAPI backend over plain REST calls - see `src/lib/api.ts` for the full
typed client. No backend logic lives here.

## Development

Normally started as part of the everyday setup in the project root
[README](../README.md) - this section is for running the frontend on its own.

```sh
npm install
npm run dev
```

Requires `VITE_API_BASE_URL` (see `.env.example`) pointing at a running backend -
defaults to `http://localhost:8000`.

## Layout

| Path | Purpose |
|---|---|
| `src/routes/` | One file per page (TanStack Router file-based routing) |
| `src/components/ui/` | shadcn/ui primitives (only the ones the app uses) |
| `src/components/Sidebar.tsx` | Nav, theme toggle, language toggle |
| `src/lib/api.ts` | Typed API client + response types for every backend endpoint |
| `src/lib/theme.tsx`, `src/lib/i18n.tsx` | Dark mode and МК/EN language providers |
