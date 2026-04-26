# Doormat Frontend

Next.js App Router frontend for the self-hosted Doormat rental finder. It reads the FastAPI backend, keeps listing filters in the URL, receives live listing updates over SSE, and lets the user manage natural-language search preferences.

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). By default the frontend calls `http://localhost:8000`; override with `NEXT_PUBLIC_API_BASE` when the backend runs elsewhere.

## Checks

```bash
npm run lint
npm run build
```

The generated OpenAPI client lives in `src/client/` and is intentionally ignored by ESLint. Regenerate it from the backend OpenAPI schema rather than hand-editing generated files.
