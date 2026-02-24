# life-event

Monorepo skeleton for the Life Event workflow platform.

## Milestone 0 quickstart

### Infrastructure
```bash
cd infra
docker compose up -d
```

### Backend
```bash
cd backend
pip install -e .[dev]
uvicorn app.main:app --reload
pytest
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run build
```
