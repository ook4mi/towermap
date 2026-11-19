# TowerMap

A lightweight, **read-only** self-hosted dashboard that maps every Docker Compose stack, published host port, `gluetun` VPN dependency, and `*.ook4mi.ovh` domain route on `tower` (`192.168.68.62`).

## Features

- **Stacks & Containers**: Containers grouped by Compose project with instant search, status/health badges, and `via gluetun` indicators.
- **Port Registry & Free-Port Checker**: Sortable table of every bound TCP/UDP host port (including indirect `gluetun` ports) plus an interactive **"Is Port X Free?"** checker and next-available port suggester (`4010–4099`).
- **Gluetun Topology & Blast-Radius Warnings**: Live VPN status, public exit IP/country, attached containers list, and warnings for stale container IDs or containers started prior to `gluetun`'s last restart.
- **Domain Route Correlation (`*.ook4mi.ovh`)**: Correlates Technitium DNS → Nginx Proxy Manager → Docker containers to flag `OK`, `Target Down`, `Orphan Proxy`, `DNS Only`, and `External` routes.
- **Offline Mock Mode**: Runs cleanly on macOS with `MOCK_MODE=true` and realistic `tower` snapshot data.
- **Graceful Degradation**: Optional integrations (Gluetun, NPM, Technitium DNS) fail safely without breaking Docker or Port views.

---

## Local Development (macOS / Offline Mock Mode)

Copy the environment template first:

```bash
cp .env.example .env
```

### 1. Backend (FastAPI on `:8000`)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

Run backend lint and tests:

```bash
cd backend
ruff check .
pytest -v
```

### 2. Frontend (Vite + React + TypeScript on `:5173`)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — Vite automatically proxies `/api/*` requests to `http://localhost:8000`.

Run frontend checks:

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## Docker Build & Run (Single Production Container)

The multi-stage `Dockerfile` builds the React SPA with `node:22-alpine` and bundles it into a `python:3.12-slim` image where FastAPI serves both `/api/*` and the static UI on port `8000`.

Build and run locally in mock mode:

```bash
docker build -t towermap:local .
docker run --rm -p 4010:8000 -e MOCK_MODE=true towermap:local
```

Then open `http://localhost:4010`.

---

## Deployment on `tower`

See [`compose.yaml`](./compose.yaml) for the production stack targeting `/home/ook4mi/docker/towermap/compose.yaml`.
Create `/home/ook4mi/appdata/towermap/.env` with your optional credentials (`GLUETUN_API_KEY`, `NPM_IDENTITY`, `NPM_SECRET`, `TECHNITIUM_API_TOKEN`) and deploy:

```bash
docker compose pull
docker compose up -d
```

See [`SPEC.md`](./SPEC.md) for full architecture and API specifications.
