# GeoVaris Data Dictionary Platform — Build 0.2

**Clean data. Confident results.**

Build 0.2 adds the first branded Next.js user interface to the working FastAPI/PostgreSQL foundation.

## Included
- GeoVaris-branded dashboard using the supplied logo and Data Dictionary icon
- Clients screen and create-client form
- Projects screen and create-project form
- Local API connectivity
- CORS configuration
- Docker Compose services for PostgreSQL, FastAPI, and Next.js

## Run
Keep your existing `.env` and add these two lines if they are not already present:

```text
FRONTEND_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then run:

```bash
docker compose up --build
```

Open:
- UI: http://localhost:3000
- API: http://localhost:8000/docs
